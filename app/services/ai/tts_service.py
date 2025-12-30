"""Edge-TTS сервис для синтеза речи.

Преимущества:
- Бесплатно (Microsoft Edge TTS)
- Качественные голоса (нейросетевые)
- Поддержка многих языков и акцентов

Документация: https://github.com/rany2/edge-tts
"""

import io
import edge_tts
from typing import AsyncIterator

from app.core.config import settings


class TTSService:
    """Сервис синтеза речи через edge-tts."""

    # Качественные английские голоса
    VOICES = {
        "american_female": "en-US-JennyNeural",      # Дружелюбный женский
        "american_male": "en-US-GuyNeural",          # Спокойный мужской
        "british_female": "en-GB-SoniaNeural",       # Британский женский
        "british_male": "en-GB-RyanNeural",          # Британский мужской
        "australian_female": "en-AU-NatashaNeural",  # Австралийский женский
    }

    def __init__(self, voice: str | None = None):
        """
        Инициализация TTS сервиса.

        Args:
            voice: Ключ голоса из VOICES или полное имя голоса
        """
        self._voice = self._resolve_voice(voice or settings.tts_voice)

    def _resolve_voice(self, voice: str) -> str:
        """Преобразовать ключ голоса в полное имя."""
        return self.VOICES.get(voice, voice)

    async def synthesize(self, text: str) -> bytes:
        """
        Синтезировать текст в аудио.

        Args:
            text: Текст для синтеза

        Returns:
            MP3 аудио в байтах
        """
        communicate = edge_tts.Communicate(text, self._voice)

        audio_buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])

        return audio_buffer.getvalue()

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """
        Потоковый синтез речи.

        Позволяет начать воспроизведение до завершения синтеза.

        Yields:
            Чанки MP3 аудио
        """
        communicate = edge_tts.Communicate(text, self._voice)

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    async def get_available_voices(self) -> list[dict]:
        """Получить список доступных голосов."""
        voices = await edge_tts.list_voices()
        # Фильтруем только английские
        return [v for v in voices if v["Locale"].startswith("en-")]


# Синглтон для переиспользования
_tts_service: TTSService | None = None


def get_tts_service(voice: str | None = None) -> TTSService:
    """Получить инстанс TTS сервиса."""
    global _tts_service
    if _tts_service is None or voice:
        _tts_service = TTSService(voice)
    return _tts_service
