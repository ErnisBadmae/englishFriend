"""Базовый интерфейс AI провайдера."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class VoiceSession:
    """Данные голосовой сессии."""
    session_id: str
    user_id: int
    system_prompt: str
    transcript: list[dict] = field(default_factory=list)  # [{"role": "user/assistant", "text": "..."}]


class AIProvider(ABC):
    """Абстрактный AI провайдер для голосовых диалогов."""

    @abstractmethod
    async def connect(self, session: VoiceSession) -> None:
        """Установить соединение с AI."""
        pass

    @abstractmethod
    async def send_audio(self, audio_chunk: bytes) -> None:
        """Отправить аудио чанк."""
        pass

    @abstractmethod
    async def receive(self) -> AsyncIterator[dict]:
        """
        Получить события от AI.

        Yields:
            {"type": "audio", "data": bytes}
            {"type": "transcript", "role": "user"|"assistant", "text": str, "is_final": bool}
            {"type": "error", "message": str}
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Закрыть соединение."""
        pass
