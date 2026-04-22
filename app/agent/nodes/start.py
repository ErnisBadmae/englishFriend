"""Start node - routes new vs returning users.

This is the entry point to the LangGraph agent. It determines:
1. Is this a new user or returning user?
2. Does the user have an established goal?
3. What context should be loaded?

Based on these factors, it routes to the appropriate next node.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.agent.state import AgentState, AgentPhase, add_decision_log
from app.services.pedagogy_logger import get_pedagogy_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def start_node(state: AgentState) -> AgentState:
    """Entry point node that routes based on user status.

    Determines:
    - New user: Start onboarding flow (goal_discovery)
    - Returning user with goal: Go to mode_router
    - Returning user without goal: Go to goal_discovery

    Args:
        state: Current agent state

    Returns:
        Updated agent state with next phase set
    """
    pedagogy = get_pedagogy_logger(state["user_id"])

    # Log session start
    pedagogy.log_session_started(
        user_id=state["user_id"],
        session_id=state["session_id"],
        is_new_user=state["is_new_user"],
    )

    # Determine routing
    if state["is_new_user"]:
        # New user - start onboarding
        state["current_phase"] = AgentPhase.ONBOARDING
        add_decision_log(
            state,
            node="start",
            action="route_to_onboarding",
            reason="New user detected, starting onboarding flow",
        )
        pedagogy.log_phase_transition(
            user_id=state["user_id"],
            from_phase="start",
            to_phase="onboarding",
            reason="new_user",
        )

    elif not state.get("confirmed_goal"):
        # Returning user without confirmed goal
        state["current_phase"] = AgentPhase.GOAL_DISCOVERY
        add_decision_log(
            state,
            node="start",
            action="route_to_goal_discovery",
            reason="Returning user without confirmed goal",
        )
        pedagogy.log_phase_transition(
            user_id=state["user_id"],
            from_phase="start",
            to_phase="goal_discovery",
            reason="no_confirmed_goal",
        )

    else:
        # Returning user with goal - go directly to learning session
        state["current_phase"] = AgentPhase.LEARNING_SESSION
        add_decision_log(
            state,
            node="start",
            action="route_to_learning_session",
            reason=f"Returning user with goal: {state.get('confirmed_goal')}",
            data={
                "goal": state.get("confirmed_goal"),
                "level": state.get("language_level"),
                "sessions_count": state.get("total_sessions", 0),
            },
        )
        pedagogy.log_phase_transition(
            user_id=state["user_id"],
            from_phase="start",
            to_phase="learning_session",
            reason="returning_user_with_goal",
        )

    # Mark that we need user input before proceeding
    state["needs_user_input"] = False  # Start node doesn't need input

    logger.info(f"[StartNode] User {state['user_id']}: "
                f"is_new={state['is_new_user']}, "
                f"goal={state.get('confirmed_goal')}, "
                f"-> {state['current_phase'].value}")

    return state


def route_after_start(state: AgentState) -> str:
    """Conditional edge function to route after start node.

    Args:
        state: Current agent state

    Returns:
        Name of the next node to execute
    """
    phase = state.get("current_phase", AgentPhase.START)

    if phase == AgentPhase.ONBOARDING:
        return "goal_discovery"  # New users go to goal discovery first
    elif phase == AgentPhase.GOAL_DISCOVERY:
        return "goal_discovery"
    elif phase == AgentPhase.LEARNING_SESSION:
        return "mode_router"
    else:
        # Default to goal discovery
        return "goal_discovery"
