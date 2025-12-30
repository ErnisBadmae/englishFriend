"""Бюджетный провайдер: Whisper STT + GPT-4o-mini + edge-tts."""

from typing import AsyncIterator

from app.services.ai.base import AIProvider, VoiceSession


class WhisperPipelineProvider(AIProvider):
    """
    Бюджетный провайдер (~$0.15/сессия вместо $1.60).

    Pipeline: Whisper API -> GPT-4o-mini -> edge-tts

    TODO: Реализовать после MVP на OpenAI Realtime.
    """

    async def connect(self, session: VoiceSession) -> None:
        raise NotImplementedError("WhisperPipelineProvider not implemented yet")

    async def send_audio(self, audio_chunk: bytes) -> None:
        raise NotImplementedError("WhisperPipelineProvider not implemented yet")

    async def receive(self) -> AsyncIterator[dict]:
        raise NotImplementedError("WhisperPipelineProvider not implemented yet")
        yield  # type: ignore

    async def disconnect(self) -> None:
        pass
