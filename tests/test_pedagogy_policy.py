from app.agent.intent_policy.types import IntentType
from app.agent.pedagogy_policy import PedagogyAction, shadow_policy_action_for_intent


def test_shadow_policy_action_map_matches_taxonomy():
    assert shadow_policy_action_for_intent(IntentType.DIRECT_ANSWER) == PedagogyAction.LLM_TURN.value
    assert shadow_policy_action_for_intent(IntentType.LOW_SIGNAL_NOISE) == PedagogyAction.SIMPLIFY_OR_COMPOSER.value
    assert shadow_policy_action_for_intent(IntentType.SUPPORT_REQUEST) == PedagogyAction.SIMPLIFY_WITH_EXAMPLE.value
    assert shadow_policy_action_for_intent(IntentType.LEXICAL_CONFUSION) == PedagogyAction.LEXICAL_RESCUE.value
    assert shadow_policy_action_for_intent(IntentType.ANSWER_SHIFT_NEXT_ANCHOR) == PedagogyAction.ALLOW_SHIFT.value
    assert shadow_policy_action_for_intent(IntentType.META_PROGRESS) == PedagogyAction.DETERMINISTIC_ADVANCE.value
    assert shadow_policy_action_for_intent(IntentType.OFF_TOPIC) == PedagogyAction.SOFT_REDIRECT.value
    assert shadow_policy_action_for_intent(IntentType.END_REQUEST) == PedagogyAction.CLEAN_SESSION_END.value
