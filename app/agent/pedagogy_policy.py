from __future__ import annotations

from enum import Enum

from app.agent.intent_policy.taxonomy import INTENT_SPEC_BY_TYPE
from app.agent.intent_policy.types import IntentType


class PedagogyAction(str, Enum):
    LLM_TURN = "llm_turn"
    SIMPLIFY_OR_COMPOSER = "simplify_or_composer"
    SIMPLIFY_WITH_EXAMPLE = "simplify_with_example"
    LEXICAL_RESCUE = "lexical_rescue"
    ALLOW_SHIFT = "allow_shift"
    DETERMINISTIC_ADVANCE = "deterministic_advance"
    SOFT_REDIRECT = "soft_redirect"
    CLEAN_SESSION_END = "clean_session_end"


def shadow_policy_action_for_intent(intent_type: IntentType) -> str:
    spec = INTENT_SPEC_BY_TYPE[intent_type]
    return spec.shadow_policy_action
