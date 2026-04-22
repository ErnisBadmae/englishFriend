from __future__ import annotations

from dataclasses import dataclass

from app.agent.intent_policy.types import IntentType


@dataclass(frozen=True, slots=True)
class IntentSpec:
    type: IntentType
    description: str
    shadow_policy_action: str
    fast_path_supported: bool


INTENT_TAXONOMY_V1: tuple[IntentSpec, ...] = (
    IntentSpec(IntentType.DIRECT_ANSWER, "Normal content answer that can stay on the standard LLM path.", "llm_turn", False),
    IntentSpec(IntentType.LOW_SIGNAL_NOISE, "Noisy or filler-heavy utterance with too little reliable meaning.", "simplify_or_composer", True),
    IntentSpec(IntentType.SUPPORT_REQUEST, "User explicitly asks for help, simplification, or says they cannot answer in English.", "simplify_with_example", True),
    IntentSpec(IntentType.LEXICAL_CONFUSION, "User asks what a word means or says they do not understand a term.", "lexical_rescue", True),
    IntentSpec(IntentType.ANSWER_SHIFT_NEXT_ANCHOR, "User answers the next anchor instead of the currently asked anchor.", "allow_shift", False),
    IntentSpec(IntentType.META_PROGRESS, "User signals continue/skip/proceed instead of answering content.", "deterministic_advance", True),
    IntentSpec(IntentType.OFF_TOPIC, "User response is unrelated to the current bounded mission.", "soft_redirect", False),
    IntentSpec(IntentType.END_REQUEST, "User explicitly wants to stop or finish the session.", "clean_session_end", True),
)


INTENT_SPEC_BY_TYPE = {spec.type: spec for spec in INTENT_TAXONOMY_V1}

