"""Фабрика AI провайдеров."""

from app.core.config import settings
from app.services.ai.base import AIProvider


def get_ai_provider() -> AIProvider:
    """Получить AI провайдер на основе конфига."""
    if settings.ai_provider == "openai_realtime":
        from app.services.ai.openai_realtime import OpenAIRealtimeProvider
        return OpenAIRealtimeProvider()
    elif settings.ai_provider == "whisper_pipeline":
        from app.services.ai.whisper_pipeline import WhisperPipelineProvider
        return WhisperPipelineProvider()
    else:
        raise ValueError(f"Unknown AI provider: {settings.ai_provider}")
