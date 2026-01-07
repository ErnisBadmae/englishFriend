from typing import Literal, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения"""

    # База данных - берётся из .env, дефолт для docker-compose
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/englishfriend_dev"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/englishfriend_dev"

    # API настройки
    api_title: str = "English Friend API"
    api_version: str = "3.0.0"
    debug: bool = True

    # CORS настройки
    allowed_origins: list = ["*"]

    # Proxy (для России)
    proxy_url: Optional[str] = None

    # ======= LLM Provider (для /chat endpoint) =======
    # vllm - свой сервер (по умолчанию, для разработки)
    # groq - бесплатно 30 req/min (для демо)
    # openai - премиум
    llm_provider: Literal["vllm", "groq", "openai"] = "vllm"

    # vLLM настройки (свой сервер)
    vllm_base_url: str = "http://192.168.0.88:8000/v1"
    vllm_model: str = "Qwen/Qwen2.5-7B-Instruct-AWQ"
    vllm_timeout: int = 60  # секунды
    vllm_max_retries: int = 3

    # Groq API (бесплатно, быстро ~200ms)
    # Получить ключ: https://console.groq.com/keys
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_timeout: int = 30  # секунды

    # OpenAI
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_timeout: int = 30  # секунды

    # ======= Общие LLM параметры =======
    llm_temperature: float = 0.7
    llm_max_retries: int = 3

    # ======= TTS настройки (edge-tts - бесплатно) =======
    # Доступные голоса: american_female, american_male, british_female, british_male, australian_female
    tts_voice: str = "american_female"

    # ======= Legacy настройки (для /stream endpoint) =======
    openai_realtime_model: str = "gpt-4o-realtime-preview-2024-12-17"
    openai_realtime_voice: str = "alloy"
    openai_whisper_model: str = "whisper-1"
    hume_api_key: str = ""
    hume_secret_key: str = ""
    ai_provider: Literal["hume_evi", "openai_realtime", "whisper_pipeline"] = "hume_evi"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
