"""Speech-to-text adapters for the modular voice runtime."""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.services.conversation_runtime.base import STTEvent, STTProvider


class PassthroughTextSTTProvider(STTProvider):
    """Treat client-provided text as a normalized final transcript."""

    provider_id = "passthrough_text"

    async def transcribe_text(
        self,
        text: str,
        *,
        user_id: int,
        session_id: str,
    ) -> STTEvent:
        del user_id, session_id
        return STTEvent(type="final", text=text, confidence=1.0)


class ParakeetSTTProvider(STTProvider):
    """Proxy audio transcription to an external Parakeet-compatible backend."""

    provider_id = "parakeet_v3"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self._base_url = (base_url or settings.parakeet_base_url).rstrip("/")
        self._api_key = api_key or settings.parakeet_api_key
        self._model = model or settings.parakeet_model
        self._timeout = timeout_seconds or settings.parakeet_timeout

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        *,
        content_type: str | None,
        user_id: int,
        session_id: str,
    ) -> STTEvent:
        if not self._base_url:
            raise RuntimeError("Parakeet base URL is not configured")

        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        files = {
            "file": (
                f"{session_id or 'session'}-audio.webm",
                audio_bytes,
                content_type or "audio/webm",
            ),
        }
        data = {
            "model": self._model,
            "user_id": str(user_id),
            "session_id": session_id,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/transcribe",
                data=data,
                files=files,
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()

        text = (
            str(payload.get("text") or payload.get("transcript") or "").strip()
        )
        if not text:
            raise RuntimeError("Parakeet returned an empty transcript")

        confidence = payload.get("confidence")
        language = payload.get("language")
        return STTEvent(
            type="final",
            text=text,
            confidence=float(confidence) if confidence is not None else None,
            language=str(language) if language else None,
            metadata={
                "provider": self.provider_id,
                "raw": payload,
            },
        )
