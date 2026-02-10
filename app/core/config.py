from typing import Any, Literal, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """Настройки приложения"""

    # База данных - берётся из .env, дефолт для docker-compose
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/englishfriend_dev"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/englishfriend_dev"

    # Database pool
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_pre_ping: bool = True

    # API настройки
    api_title: str = "English Friend API"
    api_version: str = "3.0.0"
    debug: bool = False

    # CORS настройки
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # Proxy (для России)
    proxy_url: Optional[str] = None

    # ======= LLM Provider (для /chat endpoint) =======
    # vllm - свой сервер (по умолчанию, для разработки)
    # personaplex - PersonaPlex через vLLM-совместимый API (Colab / облако)
    # groq - бесплатно 30 req/min (для демо)
    # openai - премиум
    llm_provider: Literal["vllm", "personaplex", "groq", "openai"] = "vllm"

    # vLLM настройки (свой сервер)
    vllm_base_url: str = "http://localhost:8000/v1"
    vllm_model: str = "Qwen/Qwen2.5-7B-Instruct-AWQ"
    vllm_timeout: int = 60  # секунды
    vllm_max_retries: int = 3

    # PersonaPlex настройки (vLLM-совместимый API в облаке)
    personaplex_base_url: str = ""  # e.g. https://xxx.ngrok-free.app/v1
    personaplex_model: str = "PersonaPlex"
    personaplex_api_key: str = ""  # если требуется
    personaplex_timeout: int = 90  # секунды (Colab может быть медленнее)

    # Groq API (бесплатно, быстро ~200ms)
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

    # ======= Langfuse Observability =======
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_enabled: bool = True

    # ======= PersonaPlex Speech-to-Speech (NVIDIA Moshi 7B) =======
    # Self-hosted on Linux server with RTX 5060 Ti (INT8 quantization)
    personaplex_enabled: bool = False
    personaplex_host: str = "192.168.0.88"
    personaplex_port: int = 8998
    personaplex_ws_url: str = ""  # Auto-computed if empty
    personaplex_timeout: float = 60.0
    personaplex_default_voice: str = "NATM0"  # Natural Male voice
    personaplex_quantization: Literal["fp16", "int8"] = "int8"
    personaplex_health_cache_ttl: int = 30  # seconds

    @field_validator("personaplex_ws_url", mode="before")
    @classmethod
    def _build_personaplex_url(cls, v: str, info: Any) -> str:
        if v:
            return v
        host = info.data.get("personaplex_host", "192.168.0.88")
        port = info.data.get("personaplex_port", 8998)
        return f"ws://{host}:{port}/api/chat"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
