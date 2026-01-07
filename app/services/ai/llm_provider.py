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
"""

import re
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator

import httpx
from openai import AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.core.config import settings

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

        @self._retry
        async def _call():
            response = await self._client.chat.completions.create(
                model=settings.vllm_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=settings.llm_temperature,
            )
            return response.choices[0].message.content or ""

        return await _call()

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

        @self._retry
        async def _call():
            response = await self._client.chat.completions.create(
                model=settings.groq_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=settings.llm_temperature,
            )
            return response.choices[0].message.content or ""

        return await _call()

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

        @self._retry
        async def _call():
            response = await self._client.chat.completions.create(
                model=settings.openai_chat_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=settings.llm_temperature,
            )
            return response.choices[0].message.content or ""

        return await _call()

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
