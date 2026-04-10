"""Абстракция LLM провайдеров для голосового ментора.

Поддерживаемые провайдеры:
- vLLM: OpenAI-compatible endpoint
- llama.cpp: CPU endpoint с большим контекстом
- PersonaPlex: vLLM-compatible remote endpoint
- Groq: внешний быстрый fallback
- OpenAI: внешний API
"""

from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional

import httpx
from openai import AsyncOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.metrics import llm_response_anomalies_total
from app.core.observability import (
    get_langfuse,
    get_request_id,
    get_runtime,
    get_session_id,
    get_turn_id,
    get_user_id,
)

logger = logging.getLogger(__name__)


INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?)",
    r"disregard\s+(all\s+)?(previous|above|prior)",
    r"forget\s+(everything|all|your)\s+(you|instructions?)",
    r"you\s+are\s+now\s+(a|an|DAN|evil)",
    r"pretend\s+(you're|you\s+are)\s+(not|a)",
    r"act\s+as\s+(if|though)\s+you",
    r"system\s*:\s*",
    r"<\|?system\|?>",
]

_injection_regex = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


def sanitize_user_input(text: str) -> str:
    """Базовая санитизация пользовательского ввода."""
    if not text:
        return text

    if _injection_regex.search(text):
        logger.warning("Potential prompt injection detected: %s...", text[:100])
        text = _injection_regex.sub("[filtered]", text)

    text = re.sub(r"(assistant|system|user)\s*:", "", text, flags=re.IGNORECASE)
    return text.strip()


RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.ReadTimeout,
)

FINAL_ONLY_SYSTEM_SUFFIX = (
    "Return only the final answer for the user. "
    "Do not output reasoning, hidden analysis, or chain-of-thought. "
    "If JSON is requested, return only valid JSON with no markdown fences."
)

FINAL_ONLY_RETRY_SUFFIX = (
    "Your previous response contained no final answer. "
    "Return ONLY the final answer now. "
    "Do not output reasoning or thinking. "
    "If JSON is requested, return only valid JSON."
)

DEFAULT_VLLM_MODEL = "Qwen/Qwen2.5-7B-Instruct-AWQ"


class LLMEmptyContentError(RuntimeError):
    """Raised when a provider returns no final assistant content."""

    def __init__(
        self,
        *,
        provider_name: str,
        model: str,
        finish_reason: Optional[str] = None,
        has_reasoning: bool = False,
        used_compat_retry: bool = False,
    ) -> None:
        self.provider_name = provider_name
        self.model = model
        self.finish_reason = finish_reason
        self.has_reasoning = has_reasoning
        self.used_compat_retry = used_compat_retry
        super().__init__(
            f"[{provider_name}] Empty final content from model={model}, "
            f"finish_reason={finish_reason or 'unknown'}, "
            f"has_reasoning={has_reasoning}, compat_retry={used_compat_retry}"
        )


@dataclass
class NormalizedLLMResponse:
    """Normalized completion payload across provider SDKs."""

    content: str
    finish_reason: Optional[str] = None
    reasoning_content: str = ""
    usage: Any = None

    @property
    def has_reasoning(self) -> bool:
        return bool(self.reasoning_content.strip())


def create_retry_decorator(max_retries: int | None = None):
    """Создать декоратор retry с настройками из конфига."""
    retries = max_retries or settings.llm_max_retries
    return retry(
        stop=stop_after_attempt(retries),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        before_sleep=lambda retry_state: logger.warning(
            "LLM request failed, retrying (%s/%s): %s",
            retry_state.attempt_number,
            retries,
            retry_state.outcome.exception(),
        ),
    )


def _string_or_none(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def _extract_text_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                continue
            text = getattr(item, "text", None)
            if isinstance(text, str):
                parts.append(text)
        return "".join(parts)
    return ""


def _get_extra_text(obj: Any, field_name: str) -> str:
    if obj is None:
        return ""
    if isinstance(obj, dict):
        value = obj.get(field_name)
        return value if isinstance(value, str) else ""

    direct_value = getattr(obj, field_name, None)
    if isinstance(direct_value, str):
        return direct_value

    model_extra = getattr(obj, "model_extra", None)
    if isinstance(model_extra, dict):
        extra_value = model_extra.get(field_name)
        if isinstance(extra_value, str):
            return extra_value

    return ""


def _normalize_completion_response(response: Any) -> NormalizedLLMResponse:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return NormalizedLLMResponse(content="", usage=getattr(response, "usage", None))

    choice = choices[0]
    message = getattr(choice, "message", None)
    return NormalizedLLMResponse(
        content=_extract_text_content(getattr(message, "content", None)),
        finish_reason=_string_or_none(getattr(choice, "finish_reason", None)),
        reasoning_content=_get_extra_text(message, "reasoning_content") or _get_extra_text(choice, "reasoning_content"),
        usage=getattr(response, "usage", None),
    )


def _parse_extra_body_json(raw_json: str, *, provider_name: str) -> Optional[dict[str, Any]]:
    if not raw_json or not raw_json.strip():
        return None

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        logger.warning("[%s] Invalid extra body JSON ignored: %s", provider_name, exc)
        return None

    if not isinstance(parsed, dict):
        logger.warning("[%s] extra body JSON must be an object", provider_name)
        return None

    return parsed


def _is_missing_model_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "does not exist" in message or "notfounderror" in message or "unknown model" in message


def trace_llm_generation(
    model: str,
    messages: list[dict],
    output: str,
    latency_ms: float,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    trace_name: str = "llm_generate",
    metadata: Optional[dict[str, Any]] = None,
):
    """Log LLM generation to Langfuse."""
    langfuse = get_langfuse()
    if langfuse is None:
        return

    request_id = get_request_id()
    user_id = get_user_id()
    session_id = get_session_id()
    turn_id = get_turn_id()
    runtime = get_runtime()

    try:
        trace = langfuse.trace(
            name=trace_name,
            id=f"{request_id}-llm" if request_id else None,
            user_id=str(user_id) if user_id else None,
            session_id=session_id,
            metadata={
                "request_id": request_id,
                "session_id": session_id,
                "turn_id": turn_id,
                "runtime": runtime,
            },
        )

        usage = {}
        if input_tokens is not None:
            usage["input"] = input_tokens
        if output_tokens is not None:
            usage["output"] = output_tokens

        trace_metadata = {"latency_ms": round(latency_ms, 2)}
        if metadata:
            trace_metadata.update(metadata)
        if turn_id:
            trace_metadata["turn_id"] = turn_id
        if runtime:
            trace_metadata["runtime"] = runtime

        trace.generation(
            name="completion",
            model=model,
            input=messages,
            output=output,
            usage=usage if usage else None,
            metadata=trace_metadata,
        )
    except Exception as exc:
        logger.warning("Failed to log to Langfuse: %s", exc)


class LLMProvider(ABC):
    """Абстрактный LLM провайдер."""

    @abstractmethod
    async def generate(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> str:
        """Сгенерировать ответ."""

    @abstractmethod
    async def generate_stream(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> AsyncIterator[str]:
        """Потоковая генерация ответа."""

    def _build_messages(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
    ) -> list[dict]:
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)

        clean_message = sanitize_user_input(user_message)
        messages.append({"role": "user", "content": clean_message})
        return messages


class OpenAICompatibleProvider(LLMProvider):
    """Базовый провайдер для OpenAI-compatible chat endpoints."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int,
        provider_name: str,
        max_retries: int | None = None,
        disable_env_proxy: bool = True,
        response_mode: str = "raw",
        request_extra_body: Optional[dict[str, Any]] = None,
        supports_final_only: bool = False,
    ):
        self._provider_name = provider_name
        self._model = model
        self._retry = create_retry_decorator(max_retries)
        self._response_mode = response_mode
        self._request_extra_body = request_extra_body or {}
        self._supports_final_only = supports_final_only
        self._client = AsyncOpenAI(
            api_key=api_key or "EMPTY",
            base_url=base_url,
            http_client=httpx.AsyncClient(
                timeout=httpx.Timeout(timeout, connect=10.0),
                trust_env=not disable_env_proxy,
            ),
        )

    def _prepare_system_prompt(self, system_prompt: str, *, compat_retry: bool = False) -> str:
        if not self._supports_final_only or self._response_mode != "final_only":
            return system_prompt

        suffix = FINAL_ONLY_RETRY_SUFFIX if compat_retry else FINAL_ONLY_SYSTEM_SUFFIX
        return f"{system_prompt.rstrip()}\n\n{suffix}"

    def _build_create_kwargs(
        self,
        *,
        messages: list[dict],
        max_tokens: int,
        stream: bool,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model or self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": settings.llm_temperature,
            "stream": stream,
        }
        if self._request_extra_body:
            kwargs["extra_body"] = self._request_extra_body
        return kwargs

    async def _call_completion(
        self,
        *,
        messages: list[dict],
        max_tokens: int,
    ) -> Any:
        @self._retry
        async def _call():
            return await self._client.chat.completions.create(
                **self._build_create_kwargs(messages=messages, max_tokens=max_tokens, stream=False)
            )
        try:
            return await _call()
        except Exception as exc:
            if (
                self._provider_name == "vllm"
                and self._model != DEFAULT_VLLM_MODEL
                and _is_missing_model_error(exc)
            ):
                logger.warning(
                    "[%s] Model %s is unavailable, retrying with canonical fallback %s",
                    self._provider_name,
                    self._model,
                    DEFAULT_VLLM_MODEL,
                )
                raw_response = await self._client.chat.completions.create(
                    **self._build_create_kwargs(
                        messages=messages,
                        max_tokens=max_tokens,
                        stream=False,
                        model=DEFAULT_VLLM_MODEL,
                    )
                )
                self._model = DEFAULT_VLLM_MODEL
                return raw_response
            raise

    def _trace_generation(
        self,
        *,
        messages: list[dict],
        response: NormalizedLLMResponse,
        latency_ms: float,
        used_compat_retry: bool,
    ) -> None:
        usage = response.usage
        trace_llm_generation(
            model=f"{self._provider_name}/{self._model}",
            messages=messages,
            output=response.content,
            latency_ms=latency_ms,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
            metadata={
                "finish_reason": response.finish_reason,
                "has_reasoning": response.has_reasoning,
                "compat_retry_used": used_compat_retry,
            },
        )

    def _raise_empty_content(
        self,
        *,
        response: NormalizedLLMResponse,
        used_compat_retry: bool,
    ) -> None:
        raise LLMEmptyContentError(
            provider_name=self._provider_name,
            model=self._model,
            finish_reason=response.finish_reason,
            has_reasoning=response.has_reasoning,
            used_compat_retry=used_compat_retry,
        )

    async def generate(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> str:
        start_time = time.time()
        used_compat_retry = False

        messages = self._build_messages(
            user_message,
            self._prepare_system_prompt(system_prompt),
            conversation_history,
        )
        raw_response = await self._call_completion(messages=messages, max_tokens=max_tokens)
        normalized = _normalize_completion_response(raw_response)

        if not normalized.content.strip():
            llm_response_anomalies_total.labels(
                provider=self._provider_name,
                anomaly="empty_final_content",
            ).inc()
            if normalized.has_reasoning:
                llm_response_anomalies_total.labels(
                    provider=self._provider_name,
                    anomaly="reasoning_only",
                ).inc()

            logger.warning(
                "[%s] Empty final content from model=%s finish_reason=%s has_reasoning=%s",
                self._provider_name,
                self._model,
                normalized.finish_reason or "unknown",
                normalized.has_reasoning,
            )

            if self._supports_final_only and self._response_mode == "final_only" and normalized.has_reasoning:
                llm_response_anomalies_total.labels(
                    provider=self._provider_name,
                    anomaly="compat_retry",
                ).inc()
                used_compat_retry = True
                retry_messages = self._build_messages(
                    user_message,
                    self._prepare_system_prompt(system_prompt, compat_retry=True),
                    conversation_history,
                )
                raw_response = await self._call_completion(messages=retry_messages, max_tokens=max_tokens)
                normalized = _normalize_completion_response(raw_response)
                messages = retry_messages

                if not normalized.content.strip():
                    llm_response_anomalies_total.labels(
                        provider=self._provider_name,
                        anomaly="compat_retry_failed",
                    ).inc()
                    if normalized.has_reasoning:
                        llm_response_anomalies_total.labels(
                            provider=self._provider_name,
                            anomaly="reasoning_only",
                        ).inc()

                    latency_ms = (time.time() - start_time) * 1000
                    self._trace_generation(
                        messages=messages,
                        response=normalized,
                        latency_ms=latency_ms,
                        used_compat_retry=used_compat_retry,
                    )
                    self._raise_empty_content(response=normalized, used_compat_retry=used_compat_retry)
            else:
                latency_ms = (time.time() - start_time) * 1000
                self._trace_generation(
                    messages=messages,
                    response=normalized,
                    latency_ms=latency_ms,
                    used_compat_retry=used_compat_retry,
                )
                self._raise_empty_content(response=normalized, used_compat_retry=used_compat_retry)

        latency_ms = (time.time() - start_time) * 1000
        self._trace_generation(
            messages=messages,
            response=normalized,
            latency_ms=latency_ms,
            used_compat_retry=used_compat_retry,
        )
        return normalized.content

    async def generate_stream(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> AsyncIterator[str]:
        messages = self._build_messages(
            user_message,
            self._prepare_system_prompt(system_prompt),
            conversation_history,
        )
        stream = await self._client.chat.completions.create(
            **self._build_create_kwargs(messages=messages, max_tokens=max_tokens, stream=True)
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class VLLMProvider(OpenAICompatibleProvider):
    """OpenAI-compatible vLLM endpoint."""

    def __init__(self):
        super().__init__(
            base_url=settings.vllm_base_url,
            api_key=settings.vllm_api_key,
            model=settings.vllm_model,
            timeout=settings.vllm_timeout,
            provider_name="vllm",
            max_retries=settings.vllm_max_retries,
            disable_env_proxy=True,
            response_mode="raw",
        )


class LlamaCppProvider(OpenAICompatibleProvider):
    """CPU llama.cpp endpoint с большим контекстом."""

    def __init__(self):
        super().__init__(
            base_url=settings.llama_cpp_base_url,
            api_key=settings.llama_cpp_api_key,
            model=settings.llama_cpp_model,
            timeout=settings.llama_cpp_timeout,
            provider_name="llama_cpp",
            max_retries=settings.llm_max_retries,
            disable_env_proxy=True,
            response_mode=settings.llama_cpp_response_mode,
            request_extra_body=_parse_extra_body_json(
                settings.llama_cpp_extra_body_json,
                provider_name="llama_cpp",
            ),
            supports_final_only=True,
        )


class PersonaPlexProvider(OpenAICompatibleProvider):
    """PersonaPlex text endpoint via vLLM-compatible API."""

    def __init__(self):
        if not settings.personaplex_base_url:
            raise ValueError(
                "PERSONAPLEX_BASE_URL is not set. "
                "Set it to your cloud endpoint URL (for example https://xxx.ngrok-free.app/v1)"
            )
        super().__init__(
            base_url=settings.personaplex_base_url,
            api_key=settings.personaplex_api_key,
            model=settings.personaplex_model,
            timeout=settings.personaplex_timeout,
            provider_name="personaplex",
            max_retries=settings.llm_max_retries,
            disable_env_proxy=True,
            response_mode="raw",
        )


class GroqProvider(LLMProvider):
    """Groq провайдер."""

    def __init__(self):
        from groq import AsyncGroq

        self._client = AsyncGroq(
            api_key=settings.groq_api_key,
            timeout=settings.groq_timeout,
        )
        self._retry = create_retry_decorator()

    async def generate(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> str:
        messages = self._build_messages(user_message, system_prompt, conversation_history)
        start_time = time.time()

        @self._retry
        async def _call():
            return await self._client.chat.completions.create(
                model=settings.groq_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=settings.llm_temperature,
            )

        response = await _call()
        normalized = _normalize_completion_response(response)
        if not normalized.content.strip():
            llm_response_anomalies_total.labels(provider="groq", anomaly="empty_final_content").inc()
            logger.warning(
                "[groq] Empty final content from model=%s finish_reason=%s",
                settings.groq_model,
                normalized.finish_reason or "unknown",
            )
            latency_ms = (time.time() - start_time) * 1000
            usage = normalized.usage
            trace_llm_generation(
                model=f"groq/{settings.groq_model}",
                messages=messages,
                output=normalized.content,
                latency_ms=latency_ms,
                input_tokens=usage.prompt_tokens if usage else None,
                output_tokens=usage.completion_tokens if usage else None,
                metadata={
                    "finish_reason": normalized.finish_reason,
                    "has_reasoning": normalized.has_reasoning,
                    "compat_retry_used": False,
                },
            )
            raise LLMEmptyContentError(
                provider_name="groq",
                model=settings.groq_model,
                finish_reason=normalized.finish_reason,
                has_reasoning=normalized.has_reasoning,
                used_compat_retry=False,
            )
        latency_ms = (time.time() - start_time) * 1000

        usage = normalized.usage
        trace_llm_generation(
            model=f"groq/{settings.groq_model}",
            messages=messages,
            output=normalized.content,
            latency_ms=latency_ms,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
            metadata={
                "finish_reason": normalized.finish_reason,
                "has_reasoning": normalized.has_reasoning,
                "compat_retry_used": False,
            },
        )
        return normalized.content

    async def generate_stream(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: list[dict] | None = None,
        max_tokens: int = 150,
    ) -> AsyncIterator[str]:
        messages = self._build_messages(user_message, system_prompt, conversation_history)
        stream = await self._client.chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=settings.llm_temperature,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI провайдер."""

    def __init__(self):
        super().__init__(
            base_url="https://api.openai.com/v1",
            api_key=settings.openai_api_key,
            model=settings.openai_chat_model,
            timeout=settings.openai_timeout,
            provider_name="openai",
            max_retries=settings.llm_max_retries,
            disable_env_proxy=False,
            response_mode="raw",
        )


_providers: dict[str, LLMProvider] = {}


def get_llm_provider(provider_type: str | None = None) -> LLMProvider:
    """Получить LLM провайдер."""
    provider_type = provider_type or settings.llm_provider

    if provider_type not in _providers:
        if provider_type == "vllm":
            _providers[provider_type] = VLLMProvider()
        elif provider_type == "llama_cpp":
            _providers[provider_type] = LlamaCppProvider()
        elif provider_type == "personaplex":
            _providers[provider_type] = PersonaPlexProvider()
        elif provider_type == "groq":
            _providers[provider_type] = GroqProvider()
        elif provider_type == "openai":
            _providers[provider_type] = OpenAIProvider()
        else:
            raise ValueError(f"Unknown LLM provider: {provider_type}")

        logger.info("Initialized LLM provider: %s", provider_type)

    return _providers[provider_type]


def clear_provider_cache():
    """Очистить кеш провайдеров (для тестов)."""
    global _providers
    _providers = {}
