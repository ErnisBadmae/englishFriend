"""Абстракция LLM провайдеров для голосового ментора.

Поддерживаемые провайдеры:
- vLLM (по умолчанию): Свой сервер, OpenAI-совместимый API
- Groq: Бесплатно 30 req/min, очень быстро (~200ms)
- OpenAI: Премиум качество

Все провайдеры используют OpenAI-совместимый API формат.

Улучшения:
- Конфигурируемые модели, temperature, timeout
- Retry с exponential backoff (tenacity)
- Защита от prompt injection
- Langfuse tracing for observability
"""

from __future__ import annotations

import re
import logging
import time
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

import httpx
from openai import AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.core.config import settings
from app.core.observability import get_langfuse, get_request_id, get_user_id

logger = logging.getLogger(__name__)


# ============== Prompt Injection Protection ==============

# Паттерны для детекции prompt injection
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?)",
    r"disregard\s+(all\s+)?(previous|above|prior)",
    r"forget\s+(everything|all|your)\s+(you|instructions?)",
    r"you\s+are\s+now\s+(a|an|DAN|evil)",
    r"pretend\s+(you're|you\s+are)\s+(not|a)",
    r"act\s+as\s+(if|though)\s+you",
    r"system\s*:\s*",  # Попытка вставить system prompt
    r"<\|?system\|?>",  # Маркеры system
]

_injection_regex = re.compile(
    "|".join(INJECTION_PATTERNS), re.IGNORECASE
)


def sanitize_user_input(text: str) -> str:
    """Базовая санитизация пользовательского ввода.

    Удаляет потенциально опасные паттерны prompt injection.
    Не изменяет легитимный текст.

    Args:
        text: Сырой текст от пользователя

    Returns:
        Очищенный текст
    """
    if not text:
        return text

    # Проверяем на injection patterns
    if _injection_regex.search(text):
        logger.warning(f"Potential prompt injection detected: {text[:100]}...")
        # Заменяем опасные паттерны на безобидный текст
        text = _injection_regex.sub("[filtered]", text)

    # Удаляем попытки вставить разделители ролей
    text = re.sub(r"(assistant|system|user)\s*:", "", text, flags=re.IGNORECASE)

    return text.strip()


# ============== Retry Configuration ==============

# Ретраим только на сетевых ошибках и rate limits
RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.ReadTimeout,
)


def create_retry_decorator(max_retries: int = None):
    """Создать декоратор retry с настройками из конфига."""
    retries = max_retries or settings.llm_max_retries
    return retry(
        stop=stop_after_attempt(retries),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        before_sleep=lambda retry_state: logger.warning(
            f"LLM request failed, retrying ({retry_state.attempt_number}/{retries}): "
            f"{retry_state.outcome.exception()}"
        ),
    )


# ============== Langfuse Tracing ==============


def trace_llm_generation(
    model: str,
    messages: list[dict],
    output: str,
    latency_ms: float,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    trace_name: str = "llm_generate",
):
    """Log LLM generation to Langfuse.

    Args:
        model: Model name (e.g., "groq/llama-3.3-70b")
        messages: Input messages
        output: LLM output text
        latency_ms: Latency in milliseconds
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        trace_name: Name for the trace
    """
    langfuse = get_langfuse()
    if langfuse is None:
        return

    request_id = get_request_id()
    user_id = get_user_id()

    try:
        # Create trace for this generation
        trace = langfuse.trace(
            name=trace_name,
            id=f"{request_id}-llm" if request_id else None,
            user_id=str(user_id) if user_id else None,
            metadata={"request_id": request_id},
        )

        # Log the generation
        usage = {}
        if input_tokens is not None:
            usage["input"] = input_tokens
        if output_tokens is not None:
            usage["output"] = output_tokens

        trace.generation(
            name="completion",
            model=model,
            input=messages,
            output=output,
            usage=usage if usage else None,
            metadata={"latency_ms": round(latency_ms, 2)},
        )

        logger.debug(
            f"Langfuse trace: model={model} latency={latency_ms:.0f}ms "
            f"tokens={input_tokens}/{output_tokens}"
        )
    except Exception as e:
        logger.warning(f"Failed to log to Langfuse: {e}")


# ============== Base Provider ==============

class LLMProvider(ABC):
    """Абстрактный LLM провайдер."""

    @abstractmethod
    async def generate(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> str:
        """Сгенерировать ответ."""
        pass

    @abstractmethod
    async def generate_stream(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> AsyncIterator[str]:
        """Потоковая генерация ответа."""
        pass

    def _build_messages(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
    ) -> list[dict]:
        """Собрать список сообщений для API."""
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)

        # Санитизируем пользовательский ввод
        clean_message = sanitize_user_input(user_message)
        messages.append({"role": "user", "content": clean_message})

        return messages


# ============== vLLM Provider ==============

class VLLMProvider(LLMProvider):
    """vLLM провайдер - свой сервер с OpenAI-совместимым API."""

    def __init__(self):
        # Создаём httpx клиент с отключённым прокси для локальной сети
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.vllm_timeout, connect=10.0),
            trust_env=False,  # Отключаем корпоративный прокси для локальной сети
        )
        self._client = AsyncOpenAI(
            api_key="EMPTY",  # vLLM не требует ключ
            base_url=settings.vllm_base_url,
            http_client=http_client,
        )
        self._retry = create_retry_decorator(settings.vllm_max_retries)

    async def generate(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> str:
        messages = self._build_messages(user_message, system_prompt, conversation_history)
        start_time = time.time()

        @self._retry
        async def _call():
            response = await self._client.chat.completions.create(
                model=settings.vllm_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=settings.llm_temperature,
            )
            return response

        response = await _call()
        output = response.choices[0].message.content or ""
        latency_ms = (time.time() - start_time) * 1000

        # Log to Langfuse
        usage = response.usage
        trace_llm_generation(
            model=f"vllm/{settings.vllm_model}",
            messages=messages,
            output=output,
            latency_ms=latency_ms,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
        )

        return output

    async def generate_stream(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> AsyncIterator[str]:
        messages = self._build_messages(user_message, system_prompt, conversation_history)

        stream = await self._client.chat.completions.create(
            model=settings.vllm_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=settings.llm_temperature,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# ============== PersonaPlex Provider ==============

class PersonaPlexProvider(LLMProvider):
    """PersonaPlex провайдер - vLLM-совместимый API в облаке (Colab/Runpod/etc)."""

    def __init__(self):
        if not settings.personaplex_base_url:
            raise ValueError(
                "PERSONAPLEX_BASE_URL is not set. "
                "Set it to your Colab/cloud endpoint URL (e.g. https://xxx.ngrok-free.app/v1)"
            )
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.personaplex_timeout, connect=15.0),
        )
        self._client = AsyncOpenAI(
            api_key=settings.personaplex_api_key or "EMPTY",
            base_url=settings.personaplex_base_url,
            http_client=http_client,
        )
        self._retry = create_retry_decorator()

    async def generate(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> str:
        messages = self._build_messages(user_message, system_prompt, conversation_history)
        start_time = time.time()

        @self._retry
        async def _call():
            response = await self._client.chat.completions.create(
                model=settings.personaplex_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=settings.llm_temperature,
            )
            return response

        response = await _call()
        output = response.choices[0].message.content or ""
        latency_ms = (time.time() - start_time) * 1000

        usage = response.usage
        trace_llm_generation(
            model=f"personaplex/{settings.personaplex_model}",
            messages=messages,
            output=output,
            latency_ms=latency_ms,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
        )

        return output

    async def generate_stream(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> AsyncIterator[str]:
        messages = self._build_messages(user_message, system_prompt, conversation_history)

        stream = await self._client.chat.completions.create(
            model=settings.personaplex_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=settings.llm_temperature,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# ============== Groq Provider ==============

class GroqProvider(LLMProvider):
    """Groq провайдер - бесплатно, очень быстро (~200ms)."""

    def __init__(self):
        from groq import AsyncGroq
        self._client = AsyncGroq(
            api_key=settings.groq_api_key,
            timeout=settings.groq_timeout,
        )
        self._retry = create_retry_decorator()

    async def generate(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> str:
        messages = self._build_messages(user_message, system_prompt, conversation_history)
        start_time = time.time()

        @self._retry
        async def _call():
            response = await self._client.chat.completions.create(
                model=settings.groq_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=settings.llm_temperature,
            )
            return response

        response = await _call()
        output = response.choices[0].message.content or ""
        latency_ms = (time.time() - start_time) * 1000

        # Log to Langfuse
        usage = response.usage
        trace_llm_generation(
            model=f"groq/{settings.groq_model}",
            messages=messages,
            output=output,
            latency_ms=latency_ms,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
        )

        return output

    async def generate_stream(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> AsyncIterator[str]:
        messages = self._build_messages(user_message, system_prompt, conversation_history)

        stream = await self._client.chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=settings.llm_temperature,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# ============== OpenAI Provider ==============

class OpenAIProvider(LLMProvider):
    """OpenAI провайдер - премиум качество."""

    def __init__(self):
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.openai_timeout, connect=10.0),
        )
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            http_client=http_client,
        )
        self._retry = create_retry_decorator()

    async def generate(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> str:
        messages = self._build_messages(user_message, system_prompt, conversation_history)
        start_time = time.time()

        @self._retry
        async def _call():
            response = await self._client.chat.completions.create(
                model=settings.openai_chat_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=settings.llm_temperature,
            )
            return response

        response = await _call()
        output = response.choices[0].message.content or ""
        latency_ms = (time.time() - start_time) * 1000

        # Log to Langfuse
        usage = response.usage
        trace_llm_generation(
            model=f"openai/{settings.openai_chat_model}",
            messages=messages,
            output=output,
            latency_ms=latency_ms,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
        )

        return output

    async def generate_stream(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> AsyncIterator[str]:
        messages = self._build_messages(user_message, system_prompt, conversation_history)

        stream = await self._client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=settings.llm_temperature,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# ============== Factory ==============

# Кеш провайдеров
_providers: dict[str, LLMProvider] = {}


def get_llm_provider(provider_type: str | None = None) -> LLMProvider:
    """
    Получить LLM провайдер.

    Args:
        provider_type: Тип провайдера (vllm, groq, openai).
                      Если None, используется settings.llm_provider.

    Returns:
        Инстанс LLM провайдера
    """
    provider_type = provider_type or settings.llm_provider

    if provider_type not in _providers:
        if provider_type == "vllm":
            _providers[provider_type] = VLLMProvider()
        elif provider_type == "personaplex":
            _providers[provider_type] = PersonaPlexProvider()
        elif provider_type == "groq":
            _providers[provider_type] = GroqProvider()
        elif provider_type == "openai":
            _providers[provider_type] = OpenAIProvider()
        else:
            raise ValueError(f"Unknown LLM provider: {provider_type}")

        logger.info(f"Initialized LLM provider: {provider_type}")

    return _providers[provider_type]


def clear_provider_cache():
    """Очистить кеш провайдеров (для тестов)."""
    global _providers
    _providers = {}
