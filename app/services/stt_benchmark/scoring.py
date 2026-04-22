"""Deterministic scoring for STT benchmark observations."""

from __future__ import annotations

import re

from app.services.stt_benchmark.contracts import (
    STTBenchmarkCase,
    STTBenchmarkObservation,
    STTBenchmarkResult,
    STTBenchmarkScore,
)

NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")
WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    lowered = (text or "").lower().strip()
    cleaned = NON_ALNUM_RE.sub(" ", lowered)
    return WHITESPACE_RE.sub(" ", cleaned).strip()


def _count_hits(text: str, terms: list[str]) -> int:
    normalized_text = normalize_text(text)
    hits = 0
    for term in {normalize_text(item) for item in terms if item and normalize_text(item)}:
        if term in normalized_text:
            hits += 1
    return hits


def _has_any(text: str, terms: list[str]) -> bool:
    if not terms:
        return True
    return _count_hits(text, terms) > 0


def _is_usable_transcript(text: str) -> bool:
    normalized = normalize_text(text)
    return len(normalized.split()) >= 3


def evaluate_observation(
    case: STTBenchmarkCase,
    observation: STTBenchmarkObservation,
) -> STTBenchmarkResult:
    normalized_transcript = normalize_text(observation.transcript)
    target_role_captured = _has_any(
        observation.transcript,
        case.expected.target_role_terms,
    )
    project_signal_captured = _has_any(
        observation.transcript,
        case.expected.project_terms,
    )
    technical_term_hits = _count_hits(
        observation.transcript,
        case.expected.technical_terms,
    )
    technical_term_total = len(
        {normalize_text(item) for item in case.expected.technical_terms if normalize_text(item)}
    )
    required_phrase_hits = _count_hits(
        observation.transcript,
        case.expected.required_phrases,
    )
    required_phrase_total = len(
        {normalize_text(item) for item in case.expected.required_phrases if normalize_text(item)}
    )
    usable_transcript = _is_usable_transcript(observation.transcript)

    technical_ratio = (
        technical_term_hits / technical_term_total
        if technical_term_total > 0
        else 1.0
    )
    required_ratio = (
        required_phrase_hits / required_phrase_total
        if required_phrase_total > 0
        else 1.0
    )
    overall_score = (
        (25.0 if target_role_captured else 0.0)
        + (25.0 if project_signal_captured else 0.0)
        + (20.0 * technical_ratio)
        + (20.0 * required_ratio)
        + (10.0 if usable_transcript else 0.0)
        - (10.0 if observation.fallback_used else 0.0)
    )
    overall_score = max(0.0, round(overall_score, 2))

    score = STTBenchmarkScore(
        target_role_captured=target_role_captured,
        project_signal_captured=project_signal_captured,
        technical_term_hits=technical_term_hits,
        technical_term_total=technical_term_total,
        required_phrase_hits=required_phrase_hits,
        required_phrase_total=required_phrase_total,
        usable_transcript=usable_transcript,
        fallback_used=observation.fallback_used,
        overall_score=overall_score,
    )

    return STTBenchmarkResult(
        case_id=case.case_id,
        scenario=case.scenario,
        provider=observation.provider,
        transcript=observation.transcript,
        normalized_transcript=normalized_transcript,
        latency_ms=observation.latency_ms,
        source=observation.source,
        session_id=observation.session_id,
        mission_task_type=observation.mission_task_type,
        artifact_path=observation.artifact_path,
        notes=observation.notes,
        score=score,
    )
