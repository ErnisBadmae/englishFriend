"""Per-turn user-intent classification — shadow / observational only.

Classifies the latest user turn (direct answer, support request, topic shift,
...) and records it on ``AgentState["last_intent"]`` for telemetry. This is
SHADOW MODE: nothing here drives routing or changes the response (see
``shadow_policy_action_for_intent``). Authoritative control flow lives elsewhere:
  - graph node routing (onboarding/learning/session_end): app/agent/nodes_v2/router.py
  - goal/career routing that feeds mission selection: app/services/routing/
"""

from app.agent.intent_policy.classifier import build_intent_context_from_state, classify_intent
from app.agent.intent_policy.types import IntentContext, IntentResult, IntentType

__all__ = [
    "IntentContext",
    "IntentResult",
    "IntentType",
    "build_intent_context_from_state",
    "classify_intent",
]
