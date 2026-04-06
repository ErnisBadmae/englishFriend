"""TTS adapters for the modular voice runtime."""

from __future__ import annotations

from app.services.ai.tts_service import TTSService, get_tts_service
from app.services.voice_runtime.base import TTSProvider


class EdgeTTSTTSProvider(TTSProvider):
    """Adapter around the existing edge-tts service."""

    def __init__(self, service: TTSService | None = None) -> None:
        self._service = service or get_tts_service()

    async def synthesize(self, text: str) -> bytes:
        return await self._service.synthesize(text)
