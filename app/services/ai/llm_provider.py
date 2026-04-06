"""Абстракция LLM провайдеров для голосового ментора.

Поддерживаемые провайдеры:
- vLLM: OpenAI-compatible endpoint
- llama.cpp: CPU endpoint с большим контекстом
- PersonaPlex: vLLM-compatible remote endpoint
- Groq: внешний быстрый fallback
- OpenAI: внешний API
"""

from __future__ import annotations

import logging
import re
import time
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

import httpx
from openai import AsyncOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.observability import get_langfuse, get_request_id, get_user_id

logger = logging.getLogger(__name__)


INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?)",
    r"disregard\s+(all\s+)?(previous|above|prior)",
    r"forget\s+(everything|all|your)\s+(you|instructions?)",
    r"you\s+are\s+now\s+(a|an|DAN|evil)",
    r"pretend\s+(you're|you\s+are)\s+(not|a)",
    r"act\s+as\s+(if|though)\s+you",
    r"system\s*:\s*",
    r"<\|?system\|?>",
]

_injection_regex = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


def sanitize_user_input(text: str) -> str:
    """Базовая санитизация пользовательского ввода."""
    if not text:
        return text

    if _injection_regex.search(text):
        logger.warning("Potential prompt injection detected: %s...", text[:100])
        text = _injection_regex.sub("[filtered]", text)

    text = re.sub(r"(assistant|system|user)\s*:", "", text, flags=re.IGNORECASE)
    return text.strip()


RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.ReadTimeout,
)


def create_retry_decorator(max_retries: int | None = None):
    """Создать декоратор retry с настройками из конфига."""
    retries = max_retries or settings.llm_max_retries
    return retry(
        stop=stop_after_attempt(retries),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        before_sleep=lambda retry_state: logger.warning(
            "LLM request failed, retrying (%s/%s): %s",
            retry_state.attempt_number,
            retries,
            retry_state.outcome.exception(),
        ),
    )


def trace_llm_generation(
    model: str,
    messages: list[dict],
    output: str,
    latency_ms: float,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    trace_name: str = "llm_generate",
):
    """Log LLM generation to Langfuse."""
    langfuse = get_langfuse()
    if langfuse is None:
        return

    request_id = get_request_id()
    user_id = get_user_id()

    try:
        trace = langfuse.trace(
            name=trace_name,
            id=f"{request_id}-llm" if request_id else None,
            user_id=str(user_id) if user_id else None,
            metadata={"request_id": request_id},
        )

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
    except Exception as exc:
        logger.warning("Failed to log to Langfuse: %s", exc)


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

    @abstractmethod
    async def generate_stream(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> AsyncIterator[str]:
        """Потоковая генерация ответа."""

    def _build_messages(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
    ) -> list[dict]:
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)

        clean_message = sanitize_user_input(user_message)
        messages.append({"role": "user", "content": clean_message})
        return messages


class OpenAICompatibleProvider(LLMProvider):
    """Базовый провайдер для OpenAI-compatible chat endpoints."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int,
        provider_name: str,
        max_retries: int | None = None,
        disable_env_proxy: bool = True,
    ):
        self._provider_name = provider_name
        self._model = model
        self._retry = create_retry_decorator(max_retries)
        self._client = AsyncOpenAI(
            api_key=api_key or "EMPTY",
            base_url=base_url,
            http_client=httpx.AsyncClient(
                timeout=httpx.Timeout(timeout, connect=10.0),
                trust_env=not disable_env_proxy,
            ),
        )

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
            return await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=settings.llm_temperature,
            )

        response = await _call()
        output = response.choices[0].message.content or ""
        if not output.strip():
            logger.warning(
                "[%s] Empty final content from model=%s",
                self._provider_name,
                self._model,
            )
        latency_ms = (time.time() - start_time) * 1000

        usage = response.usage
        trace_llm_generation(
            model=f"{self._provider_name}/{self._model}",
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
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=settings.llm_temperature,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class VLLMProvider(OpenAICompatibleProvider):
    """OpenAI-compatible vLLM endpoint."""

    def __init__(self):
        super().__init__(
            base_url=settings.vllm_base_url,
            api_key=settings.vllm_api_key,
            model=settings.vllm_model,
            timeout=settings.vllm_timeout,
            provider_name="vllm",
            max_retries=settings.vllm_max_retries,
            disable_env_proxy=True,
        )


class LlamaCppProvider(OpenAICompatibleProvider):
    """CPU llama.cpp endpoint с большим контекстом."""

    def __init__(self):
        super().__init__(
            base_url=settings.llama_cpp_base_url,
            api_key=settings.llama_cpp_api_key,
            model=settings.llama_cpp_model,
            timeout=settings.llama_cpp_timeout,
            provider_name="llama_cpp",
            max_retries=settings.llm_max_retries,
            disable_env_proxy=True,
        )


class PersonaPlexProvider(OpenAICompatibleProvider):
    """PersonaPlex text endpoint via vLLM-compatible API."""

    def __init__(self):
        if not settings.personaplex_base_url:
            raise ValueError(
                "PERSONAPLEX_BASE_URL is not set. "
                "Set it to your cloud endpoint URL (for example https://xxx.ngrok-free.app/v1)"
            )
        super().__init__(
            base_url=settings.personaplex_base_url,
            api_key=settings.personaplex_api_key,
            model=settings.personaplex_model,
            timeout=settings.personaplex_timeout,
            provider_name="personaplex",
            max_retries=settings.llm_max_retries,
            disable_env_proxy=True,
        )


class GroqProvider(LLMProvider):
    """Groq провайдер."""

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
            return await self._client.chat.completions.create(
                model=settings.groq_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=settings.llm_temperature,
            )

        response = await _call()
        output = response.choices[0].message.content or ""
        if not output.strip():
            logger.warning("[groq] Empty final content from model=%s", settings.groq_model)
        latency_ms = (time.time() - start_time) * 1000

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


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI провайдер."""

    def __init__(self):
        super().__init__(
            base_url="https://api.openai.com/v1",
            api_key=settings.openai_api_key,
            model=settings.openai_chat_model,
            timeout=settings.openai_timeout,
            provider_name="openai",
            max_retries=settings.llm_max_retries,
            disable_env_proxy=False,
        )


_providers: dict[str, LLMProvider] = {}


def get_llm_provider(provider_type: str | None = None) -> LLMProvider:
    """Получить LLM провайдер."""
    provider_type = provider_type or settings.llm_provider

    if provider_type not in _providers:
        if provider_type == "vllm":
            _providers[provider_type] = VLLMProvider()
        elif provider_type == "llama_cpp":
            _providers[provider_type] = LlamaCppProvider()
        elif provider_type == "personaplex":
            _providers[provider_type] = PersonaPlexProvider()
        elif provider_type == "groq":
            _providers[provider_type] = GroqProvider()
        elif provider_type == "openai":
            _providers[provider_type] = OpenAIProvider()
        else:
            raise ValueError(f"Unknown LLM provider: {provider_type}")

        logger.info("Initialized LLM provider: %s", provider_type)

    return _providers[provider_type]


def clear_provider_cache():
    """Очистить кеш провайдеров (для тестов)."""
    global _providers
    _providers = {}
