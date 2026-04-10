"""Artifact ingestion helpers for STT benchmark inputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.stt_benchmark.contracts import STTBenchmarkObservation


def load_voice_debug_snapshot(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Voice debug snapshot must be a JSON object")
    return payload


def observation_from_voice_debug_snapshot(
    path: str | Path,
    *,
    provider: str | None = None,
) -> STTBenchmarkObservation:
    snapshot = load_voice_debug_snapshot(path)
    session = snapshot.get("session", {}) or {}
    events = list(snapshot.get("events", []) or [])

    transcripts: list[str] = []
    sources: list[str] = []
    fallback_used = False

    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("source") != "websocket" or event.get("event") != "ws_text_sent":
            continue
        data = event.get("data", {}) or {}
        if not isinstance(data, dict):
            continue
        text = str(data.get("text") or data.get("textPreview") or "").strip()
        if not text:
            continue
        transcripts.append(text)
        source = str(data.get("source") or "").strip()
        if source:
            sources.append(source)
        if source == "composer":
            fallback_used = True

    source_value = None
    if len(set(sources)) == 1:
        source_value = sources[0]
    elif sources:
        source_value = "mixed"

    transcript = " ".join(transcripts).strip()
    provider_name = (
        provider
        or str(session.get("sttProvider") or session.get("stt_provider") or "unknown")
    )

    return STTBenchmarkObservation(
        provider=provider_name,
        transcript=transcript,
        source=source_value,
        fallback_used=fallback_used,
        session_id=(
            str(session.get("sessionId") or session.get("session_id"))
            if session.get("sessionId") or session.get("session_id")
            else None
        ),
        mission_task_type=(
            str(session.get("missionTaskType") or session.get("mission_task_type"))
            if session.get("missionTaskType") or session.get("mission_task_type")
            else None
        ),
        artifact_path=str(Path(path)),
        notes="Observation derived from frontend debug export",
    )
