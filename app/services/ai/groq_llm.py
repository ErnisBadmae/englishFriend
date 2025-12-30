"""Groq API клиент для LLM (Llama-70B).

Преимущества:
- Бесплатный tier: 30 req/min, 6000 tokens/min
- Очень быстрый: ~200ms для ответа
- Качество Llama-70B сравнимо с GPT-4

Документация: https://console.groq.com/docs/quickstart
"""

from groq import AsyncGroq
from typing import AsyncIterator

from app.core.config import settings


class GroqLLMService:
    """Сервис для генерации ответов через Groq API."""

    def __init__(self):
        self._client: AsyncGroq | None = None

    @property
    def client(self) -> AsyncGroq:
        """Ленивая инициализация клиента."""
        if self._client is None:
            self._client = AsyncGroq(api_key=settings.groq_api_key)
        return self._client

    async def generate(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> str:
        """
        Сгенерировать ответ на сообщение пользователя.

        Args:
            user_message: Текст от пользователя (из Vosk STT)
            system_prompt: Системный промпт с контекстом
            conversation_history: История диалога [{"role": "user|assistant", "content": "..."}]
            max_tokens: Максимум токенов в ответе (короткие ответы для голоса)

        Returns:
            Текст ответа ментора
        """
        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": user_message})

        response = await self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Самая новая и быстрая модель
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,  # Немного креативности для естественного диалога
        )

        return response.choices[0].message.content or ""

    async def generate_stream(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> AsyncIterator[str]:
        """
        Потоковая генерация ответа (для будущей оптимизации).

        Позволяет начать TTS до завершения генерации LLM.
        """
        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": user_message})

        stream = await self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# Синглтон для переиспользования
_groq_service: GroqLLMService | None = None


def get_groq_service() -> GroqLLMService:
    """Получить инстанс Groq сервиса."""
    global _groq_service
    if _groq_service is None:
        _groq_service = GroqLLMService()
    return _groq_service
