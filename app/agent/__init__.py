"""LangGraph-based agent for English Friend.

The single runtime engine is the simplified 4-node graph in
``app.agent.graph_v2`` (router -> onboarding -> learning -> session_end).
This package exposes only the shared state primitives; import the graph
runtime directly from ``app.agent.graph_v2``.
"""

from app.agent.state import AgentState, AgentPhase, LearningModeEnum

__all__ = [
    "AgentState",
    "AgentPhase",
    "LearningModeEnum",
]
