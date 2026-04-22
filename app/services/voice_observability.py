"""Shared observability helpers for voice sessions and live debugging."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

from app.core.metrics import (
    voice_persistence_total,
    voice_stage_latency_seconds,
    voice_turn_events_total,
)
from app.core.observability import set_request_context


def _safe_preview(value: Any, limit: int = 80) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return str(value)
    if isinstance(value, list):
        return json.dumps(value[:5], ensure_ascii=True)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=True, default=str)
    return _safe_preview(value)


@dataclass(slots=True)
class VoiceSessionScope:
    runtime: str
    session_id: str
    user_id: int
    agent_version: Optional[str] = None
    mission_task_type: Optional[str] = None
    stt_provider: Optional[str] = None


@dataclass(slots=True)
class VoiceTurnEnvelope:
    runtime: str
    session_id: str
    user_id: int
    turn_id: Optional[str] = None
    turn_index: Optional[int] = None
    phase: Optional[str] = None
    mode: Optional[str] = None
    mission_task_type: Optional[str] = None
    agent_version: Optional[str] = None
    stt_provider: Optional[str] = None


def bind_voice_context(
    scope: VoiceSessionScope,
    *,
    turn_id: Optional[str] = None,
) -> str:
    """Bind current voice scope to request context for log correlation."""
    return set_request_context(
        user_id=scope.user_id,
        session_id=scope.session_id,
        turn_id=turn_id,
        runtime=scope.runtime,
    )


def make_turn_envelope(
    scope: VoiceSessionScope,
    *,
    turn_id: Optional[str] = None,
    turn_index: Optional[int] = None,
    phase: Optional[str] = None,
    mode: Optional[str] = None,
) -> VoiceTurnEnvelope:
    return VoiceTurnEnvelope(
        runtime=scope.runtime,
        session_id=scope.session_id,
        user_id=scope.user_id,
        turn_id=turn_id,
        turn_index=turn_index,
        phase=phase,
        mode=mode,
        mission_task_type=scope.mission_task_type,
        agent_version=scope.agent_version,
        stt_provider=scope.stt_provider,
    )


def enrich_ws_event(
    event: dict[str, Any],
    *,
    envelope: VoiceTurnEnvelope,
) -> dict[str, Any]:
    """Attach optional observability metadata to outbound websocket events."""
    payload = dict(event)
    payload.setdefault("runtime", envelope.runtime)
    if envelope.turn_id:
        payload.setdefault("turn_id", envelope.turn_id)
    if envelope.turn_index is not None:
        payload.setdefault("turn_index", envelope.turn_index)
    if envelope.phase:
        payload.setdefault("phase", envelope.phase)
    if envelope.mode:
        payload.setdefault("mode", envelope.mode)
    if envelope.agent_version:
        payload.setdefault("agent_version", envelope.agent_version)
    if envelope.stt_provider:
        payload.setdefault("stt_provider", envelope.stt_provider)
    return payload


def observe_voice_stage(*, runtime: str, stage: str, duration_seconds: float) -> None:
    voice_stage_latency_seconds.labels(runtime=runtime, stage=stage).observe(duration_seconds)


def record_voice_persistence(*, runtime: str, status: str) -> None:
    voice_persistence_total.labels(runtime=runtime, status=status).inc()


def log_voice_event(
    logger: logging.Logger,
    *,
    envelope: VoiceTurnEnvelope,
    layer: str,
    event: str,
    level: int = logging.INFO,
    latency_ms: Optional[float] = None,
    text: Optional[str] = None,
    **fields: Any,
) -> None:
    """Emit one structured voice event with a stable cross-layer envelope."""
    voice_turn_events_total.labels(
        runtime=envelope.runtime,
        layer=layer,
        event=event,
    ).inc()

    payload: dict[str, Any] = {
        "runtime": envelope.runtime,
        "layer": layer,
        "event": event,
        "session_id": envelope.session_id[:8],
        "user_id": envelope.user_id,
    }
    if envelope.turn_id:
        payload["turn_id"] = envelope.turn_id
    if envelope.turn_index is not None:
        payload["turn_index"] = envelope.turn_index
    if envelope.phase:
        payload["phase"] = envelope.phase
    if envelope.mode:
        payload["mode"] = envelope.mode
    if envelope.mission_task_type:
        payload["mission_task_type"] = envelope.mission_task_type
    if envelope.agent_version:
        payload["agent_version"] = envelope.agent_version
    if envelope.stt_provider:
        payload["stt_provider"] = envelope.stt_provider
    if latency_ms is not None:
        payload["latency_ms"] = round(latency_ms, 2)
    if text is not None:
        payload["text_preview"] = _safe_preview(text)
        payload["char_count"] = len(text)

    for key, value in fields.items():
        if value is None:
            continue
        payload[key] = value

    body = " ".join(
        f"{key}={_format_value(value)}"
        for key, value in payload.items()
        if _format_value(value)
    )
    logger.log(level, "[VoiceObs] %s", body)
