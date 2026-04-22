from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional


class IntentType(str, Enum):
    DIRECT_ANSWER = "direct_answer"
    LOW_SIGNAL_NOISE = "low_signal_noise"
    SUPPORT_REQUEST = "support_request"
    LEXICAL_CONFUSION = "lexical_confusion"
    ANSWER_SHIFT_NEXT_ANCHOR = "answer_shift_next_anchor"
    META_PROGRESS = "meta_progress"
    OFF_TOPIC = "off_topic"
    END_REQUEST = "end_request"


@dataclass(slots=True)
class IntentContext:
    phase: Optional[str] = None
    current_mode: Optional[str] = None
    mission_task_type: Optional[str] = None
    anchor_question_id: Optional[int] = None
    anchor_follow_up_pending: bool = False
    goal_setup_complete: bool = False
    assessment_step_index: Optional[int] = None
    low_signal_turn_streak: int = 0
    last_question_type: Optional[str] = None


@dataclass(slots=True)
class IntentResult:
    type: IntentType
    confidence: float
    reason_codes: list[str] = field(default_factory=list)
    normalized_text: str = ""
    matched_anchor_id: Optional[int] = None
    shift_target_anchor_id: Optional[int] = None
    needs_composer_hint: bool = False
    classifier_source: Literal["fast_rule", "llm", "fallback"] = "fallback"
    latency_ms: int = 0

    def to_payload(self, *, policy_action: Optional[str] = None, shadow_mode: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "type": self.type.value,
            "confidence": round(self.confidence, 3),
            "reason_codes": list(self.reason_codes),
            "normalized_text": self.normalized_text,
            "matched_anchor_id": self.matched_anchor_id,
            "shift_target_anchor_id": self.shift_target_anchor_id,
            "needs_composer_hint": self.needs_composer_hint,
            "classifier_source": self.classifier_source,
            "latency_ms": self.latency_ms,
            "shadow_mode": shadow_mode,
        }
        if policy_action:
            payload["policy_action"] = policy_action
        return payload
