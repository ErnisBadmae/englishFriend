from typing import Literal
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения"""

    # База данных
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/english_friend"
    database_url_sync: str = "postgresql://postgres:password@localhost:5432/english_friend"

    # API настройки
    api_title: str = "English Friend API"
    api_version: str = "3.0.0"
    debug: bool = True

    # CORS настройки
    allowed_origins: list = ["*"]

    # OpenAI
    openai_api_key: str = ""
    openai_realtime_model: str = "gpt-4o-realtime-preview-2024-12-17"
    openai_realtime_voice: str = "alloy"  # alloy, echo, shimmer, ash, ballad, coral, sage, verse
    openai_whisper_model: str = "whisper-1"
    openai_chat_model: str = "gpt-4o-mini"

    # AI провайдер: "openai_realtime" (премиум) или "whisper_pipeline" (бюджет)
    ai_provider: Literal["openai_realtime", "whisper_pipeline"] = "openai_realtime"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
