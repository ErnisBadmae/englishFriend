from typing import Any, Literal, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения."""

    # База данных
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/englishfriend_dev"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/englishfriend_dev"

    # Database pool
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_pre_ping: bool = True

    # API
    api_title: str = "English Friend API"
    api_version: str = "3.0.0"
    debug: bool = False

    # CORS
    allowed_origins: list[str] = [
        "*",
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # Proxy
    proxy_url: Optional[str] = None

    # ======= LLM Provider =======
    # vllm - OpenAI-compatible endpoint (self-hosted or corporate)
    # llama_cpp - CPU fallback endpoint with large context
    # personaplex - vLLM-compatible remote endpoint
    # groq - external fast fallback
    # openai - external OpenAI API
    llm_provider: Literal["vllm", "llama_cpp", "personaplex", "groq", "openai"] = "vllm"

    # vLLM
    vllm_base_url: str = "http://localhost:8000/v1"
    vllm_api_key: str = ""
    vllm_model: str = "Qwen/Qwen2.5-7B-Instruct-AWQ"
    vllm_timeout: int = 60
    vllm_max_retries: int = 3

    # llama.cpp
    llama_cpp_base_url: str = "http://localhost:8001/v1"
    llama_cpp_api_key: str = ""
    llama_cpp_model: str = "qwen3.5-35b"
    llama_cpp_timeout: int = 120

    # PersonaPlex text endpoint
    personaplex_base_url: str = ""
    personaplex_model: str = "PersonaPlex"
    personaplex_api_key: str = ""
    personaplex_timeout: int = 90

    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_timeout: int = 30

    # OpenAI
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_timeout: int = 30

    # Shared LLM / RAG
    llm_temperature: float = 0.7
    llm_max_retries: int = 3
    vector_memory_enabled: bool = True

    # TTS
    tts_voice: str = "american_female"

    # Experimental modular voice runtime
    realtime_runtime_enabled: bool = False

    # Pronunciation assessment
    pronunciation_provider: Literal["heuristic", "azure"] = "heuristic"
    pronunciation_locale: str = "en-US"
    azure_speech_key: str = ""
    azure_speech_region: str = ""

    # Langfuse
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_enabled: bool = True

    # PersonaPlex speech-to-speech
    personaplex_enabled: bool = False
    personaplex_host: str = "192.168.0.18"
    personaplex_port: int = 8998
    personaplex_ws_url: str = ""
    personaplex_default_voice: str = "NATM0"
    personaplex_quantization: Literal["fp16", "int8"] = "int8"
    personaplex_health_cache_ttl: int = 30

    @field_validator("personaplex_ws_url", mode="before")
    @classmethod
    def _build_personaplex_url(cls, v: str, info: Any) -> str:
        if v:
            return v
        host = info.data.get("personaplex_host", "192.168.0.18")
        port = info.data.get("personaplex_port", 8998)
        return f"ws://{host}:{port}/api/chat"

    # Legacy realtime settings
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
