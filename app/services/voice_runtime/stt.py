"""Speech-to-text adapters for the modular voice runtime."""

from __future__ import annotations

from app.services.voice_runtime.base import STTEvent, STTProvider


class PassthroughTextSTTProvider(STTProvider):
    """Treat client-provided text as a normalized final transcript."""

    async def transcribe_text(
        self,
        text: str,
        *,
        user_id: int,
        session_id: str,
    ) -> STTEvent:
        del user_id, session_id
        return STTEvent(type="final", text=text, confidence=1.0)
