from typing import Any, Literal, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения."""

    # База данных
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/englishfriend_dev"
    )
    database_url_sync: str = (
        "postgresql://postgres:postgres@localhost:5432/englishfriend_dev"
    )

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

    # Private ML technical Telegram adapter
    ml_technical_telegram_bot_token: str = ""
    ml_technical_telegram_allowed_ids: str = ""
    ml_technical_telegram_timezone: str = "Europe/Moscow"
    ml_question_curator_enabled: bool = False
    ml_question_admin_enabled: bool = False
    ml_progress_review_append_enabled: bool = False
    # Career Inbox v0 (CAREER_TELEGRAM_COCKPIT_SPEC.md Slice A). Off by default;
    # owner opts in only after Slice A/B/C acceptance. Gates the "Входящие" /
    # "Добавить контакт или ответ" menu items only - existing career ledger
    # menu (Записать отправленный отклик / Мои отклики) is unaffected.
    career_inbox_enabled: bool = False
    # Career Cover Letter Draft v0 (career/CAREER_COVER_LETTER_DRAFT_SPEC.md).
    # Separate flag from career_inbox_enabled per spec: off by default, gates
    # only the "Черновик сопровода" button on a prepare card. LLM is an
    # untrusted drafter; approve never sends anything or creates an application.
    career_cover_letter_draft_enabled: bool = False

    @property
    def ml_technical_telegram_allowed_id_set(self) -> frozenset[int]:
        values: set[int] = set()
        for raw in self.ml_technical_telegram_allowed_ids.split(","):
            value = raw.strip()
            if value:
                values.add(int(value))
        return frozenset(values)

    # ======= LLM Provider =======
    # vllm - OpenAI-compatible endpoint (self-hosted or corporate)
    # llama_cpp - CPU fallback endpoint with large context
    # personaplex - vLLM-compatible remote endpoint
    # groq - external fast fallback
    # openai - external OpenAI API
    llm_provider: Literal["vllm", "llama_cpp", "personaplex", "groq", "openai"] = "vllm"

    # vLLM
    vllm_base_url: str = "http://192.168.0.18:8000/v1"
    vllm_api_key: str = "token-abc123"
    vllm_model: str = "Qwen3.6-35B-A3B-Q5-256K"
    vllm_timeout: int = 60
    vllm_max_retries: int = 3
    vllm_extra_body_json: str = '{"chat_template_kwargs": {"enable_thinking": false}}'

    # llama.cpp
    llama_cpp_base_url: str = "http://192.168.0.18:8000/v1"
    llama_cpp_api_key: str = ""
    llama_cpp_model: str = "qwen3.5-35b"
    llama_cpp_timeout: int = 120
    llama_cpp_response_mode: Literal["final_only", "raw"] = "final_only"
    llama_cpp_extra_body_json: str = ""

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
    llm_fallback_to_groq: bool = True
    vector_memory_enabled: bool = True

    # Career routing classifier rollout
    career_routing_classifier_mode: Literal[
        "off", "shadow", "gate", "mainline"
    ] = "shadow"
    career_routing_classifier_min_confidence: float = 0.72
    career_routing_classifier_max_tokens: int = 4096
    career_routing_classifier_timeout_seconds: float = 240.0
    career_routing_classifier_model_version: str = "active_llm"

    # TTS
    tts_voice: str = "american_female"

    # Experimental modular voice runtime
    realtime_runtime_enabled: bool = False

    # Backend STT
    stt_backend_default: Literal[
        "browser_vosk", "parakeet_v3", "composer"
    ] = "browser_vosk"
    parakeet_base_url: str = ""
    parakeet_api_key: str = ""
    parakeet_model: str = "parakeet-v3"
    parakeet_timeout: int = 30

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
