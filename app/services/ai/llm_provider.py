"""Абстракция LLM провайдеров для голосового ментора.

Поддерживаемые провайдеры:
- vLLM (по умолчанию): Свой сервер, OpenAI-совместимый API
- Groq: Бесплатно 30 req/min, очень быстро (~200ms)
- OpenAI: Премиум качество

Все провайдеры используют OpenAI-совместимый API формат.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator
import httpx
from openai import AsyncOpenAI

from app.core.config import settings


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

    async def generate(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> str:
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        response = await self._client.chat.completions.create(
            model=settings.vllm_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
        )

        return response.choices[0].message.content or ""

    async def generate_stream(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> AsyncIterator[str]:
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        stream = await self._client.chat.completions.create(
            model=settings.vllm_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class GroqProvider(LLMProvider):
    """Groq провайдер - бесплатно, очень быстро (~200ms)."""

    def __init__(self):
        # Groq использует свой SDK, но мы можем использовать OpenAI клиент
        from groq import AsyncGroq
        self._client = AsyncGroq(api_key=settings.groq_api_key)

    async def generate(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> str:
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        response = await self._client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
        )

        return response.choices[0].message.content or ""

    async def generate_stream(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> AsyncIterator[str]:
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        stream = await self._client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class OpenAIProvider(LLMProvider):
    """OpenAI провайдер - премиум качество."""

    def __init__(self):
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> str:
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        response = await self._client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
        )

        return response.choices[0].message.content or ""

    async def generate_stream(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> AsyncIterator[str]:
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        stream = await self._client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


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

    return _providers[provider_type]
