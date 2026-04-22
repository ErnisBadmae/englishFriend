from __future__ import annotations

import time
from typing import Any, Mapping

from app.agent.intent_policy.fast_rules import classify_fast_intent
from app.agent.intent_policy.types import IntentContext, IntentResult, IntentType
from app.core.metrics import (
    agent_intent_classifications_total,
    agent_intent_classifier_latency_seconds,
)

INTENT_CONFIDENCE_THRESHOLD = 0.6


def build_intent_context_from_state(state: Mapping[str, Any]) -> IntentContext:
    phase = state.get("current_phase")
    mode = state.get("current_mode")
    return IntentContext(
        phase=getattr(phase, "value", str(phase)) if phase is not None else None,
        current_mode=getattr(mode, "value", str(mode)) if mode is not None else None,
        mission_task_type=state.get("mission_task_type"),
        anchor_question_id=state.get("anchor_question_id"),
        anchor_follow_up_pending=bool(state.get("anchor_follow_up_pending", False)),
        goal_setup_complete=bool(state.get("goal_setup_complete", False)),
        assessment_step_index=state.get("assessment_step_index"),
        low_signal_turn_streak=int(state.get("low_signal_turn_streak", 0) or 0),
        last_question_type=state.get("last_question_type"),
    )


def classify_intent(text: str, context: IntentContext) -> IntentResult:
    started_at = time.perf_counter()
    result = classify_fast_intent(text, context)
    if result is None:
        result = IntentResult(
            type=IntentType.DIRECT_ANSWER,
            confidence=INTENT_CONFIDENCE_THRESHOLD,
            reason_codes=["fallback_direct_answer"],
            normalized_text=text,
            matched_anchor_id=context.anchor_question_id,
            classifier_source="fallback",
        )

    if result.confidence < INTENT_CONFIDENCE_THRESHOLD:
        result = IntentResult(
            type=IntentType.DIRECT_ANSWER,
            confidence=INTENT_CONFIDENCE_THRESHOLD,
            reason_codes=[*result.reason_codes, "low_confidence"],
            normalized_text=result.normalized_text or text,
            matched_anchor_id=result.matched_anchor_id,
            shift_target_anchor_id=result.shift_target_anchor_id,
            needs_composer_hint=result.needs_composer_hint,
            classifier_source="fallback",
        )

    latency_seconds = time.perf_counter() - started_at
    result.latency_ms = int(latency_seconds * 1000)
    agent_intent_classifications_total.labels(
        type=result.type.value,
        source=result.classifier_source,
    ).inc()
    agent_intent_classifier_latency_seconds.labels(
        source=result.classifier_source,
    ).observe(latency_seconds)
    return result
