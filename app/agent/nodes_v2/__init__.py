"""LangGraph Agent Nodes v2 - LLM-driven with structured outputs.

Simplified 4-node architecture:
1. router - Entry point, routes based on user state
2. onboarding - Unified goal + interests + assessment
3. learning - Mode-aware conversation with corrections
4. session_end - Cleanup and farewell
"""

from app.agent.nodes_v2.router import router_node, route_after_router
from app.agent.nodes_v2.onboarding import onboarding_node, route_after_onboarding
from app.agent.nodes_v2.learning import learning_node, route_after_learning
from app.agent.nodes_v2.session_end import session_end_node

__all__ = [
    "router_node",
    "route_after_router",
    "onboarding_node",
    "route_after_onboarding",
    "learning_node",
    "route_after_learning",
    "session_end_node",
]
