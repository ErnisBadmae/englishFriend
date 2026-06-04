"""Authoritative goal / career routing for onboarding and mission selection.

The product-truth routing layer: turns user input into a routed career
goal-brief (target role, domain, primary context). Two complementary parts,
combined by the arbiter:
  - goal_routing.py      — deterministic/lexical: scope gate + context-signal scoring
  - career_classifier.py — optional LLM classifier + arbiter (merges lexical + LLM)

The resulting goal_brief feeds ``recommend_next_mission`` — the single owner of
the "next mission" decision — in app/services/program_snapshot_service.py.
Not to be confused with per-turn shadow intent telemetry
(app/agent/intent_policy/) or graph node routing (app/agent/nodes_v2/router.py).
"""

from app.services.routing.career_classifier import (
    CareerRoutingArbiterDecision,
    CareerRoutingClassifierResult,
    arbitrate_career_routing,
    classify_career_routing,
)
from app.services.routing.goal_routing import (
    GoalRoutingProfile,
    build_goal_routing_from_goal_brief,
    has_positive_context_signal,
    resolve_goal_routing,
    resolve_scope_status,
    score_context_signals,
)

__all__ = [
    "CareerRoutingArbiterDecision",
    "CareerRoutingClassifierResult",
    "GoalRoutingProfile",
    "arbitrate_career_routing",
    "build_goal_routing_from_goal_brief",
    "classify_career_routing",
    "has_positive_context_signal",
    "resolve_goal_routing",
    "resolve_scope_status",
    "score_context_signals",
]
