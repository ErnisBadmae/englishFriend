from __future__ import annotations

from app.agent.intent_policy.types import IntentContext, IntentResult, IntentType


async def classify_intent_slow_path(text: str, context: IntentContext) -> IntentResult:
    """Placeholder for Phase 3 hybrid slow-path classifier.

    Until shadow-mode traces prove the fast path is insufficient, the slow path is a
    no-op that preserves current behavior by downgrading to direct_answer.
    """
    return IntentResult(
        type=IntentType.DIRECT_ANSWER,
        confidence=0.6,
        reason_codes=["slow_path_deferred"],
        normalized_text=text,
        matched_anchor_id=context.anchor_question_id,
        classifier_source="fallback",
    )
