"""Router Node - Entry point that routes based on user state.

Routes to:
- onboarding: New users without confirmed goal
- learning: Users with goal and assessment
- session_end: When session end is requested
"""

import logging
from app.agent.state import AgentState, AgentPhase, add_decision_log
from app.services.pedagogy_logger import get_pedagogy_logger

logger = logging.getLogger(__name__)


async def router_node(state: AgentState) -> AgentState:
    """Route to appropriate node based on user state.

    Decision logic:
    1. Session end requested -> session_end
    2. New user without goal -> onboarding
    3. Has goal but no assessment -> onboarding (assessment only)
    4. Returning user with profile -> learning

    Args:
        state: Current agent state

    Returns:
        Updated state with _route field
    """
    pedagogy = get_pedagogy_logger(state["user_id"])

    is_new = state.get("is_new_user", True)
    has_goal = bool(state.get("confirmed_goal"))
    goal_setup_complete = state.get("goal_setup_complete", has_goal)
    has_assessment = bool(state.get("assessed_level"))
    should_end = state.get("should_end_session", False)

    # Decision 1: Session end requested
    if should_end:
        state["_route"] = "session_end"
        add_decision_log(
            state,
            node="router",
            action="route_session_end",
            reason="Session end requested",
        )
        logger.info(f"[Router] User {state['user_id']}: route=session_end (end requested)")
        return state

    # Decision 2: Missing or incomplete goal brief -> onboarding
    if (is_new and not has_goal) or not goal_setup_complete:
        state["_route"] = "onboarding"
        state["_skip_goal"] = False
        state["_skip_interests"] = True
        state["_skip_assessment"] = True if not goal_setup_complete else False

        pedagogy.log_phase_transition(
            user_id=state["user_id"],
            from_phase="start",
            to_phase="onboarding",
            reason="goal_setup_incomplete",
        )

        add_decision_log(
            state,
            node="router",
            action="route_onboarding_goal_setup",
            reason="User needs concrete goal setup before practice",
            data={"is_new": is_new, "has_goal": has_goal, "goal_setup_complete": goal_setup_complete},
        )
        logger.info(f"[Router] User {state['user_id']}: route=onboarding (goal setup)")
        return state

    # Decision 3: Has complete goal but no assessment -> assessment only
    if has_goal and not has_assessment:
        state["_route"] = "onboarding"
        state["_skip_goal"] = True
        state["_skip_interests"] = True
        state["_skip_assessment"] = False

        add_decision_log(
            state,
            node="router",
            action="route_onboarding_assessment",
            reason="User has goal but needs assessment",
            data={"has_goal": has_goal, "has_assessment": has_assessment, "goal_setup_complete": goal_setup_complete},
        )
        logger.info(f"[Router] User {state['user_id']}: route=onboarding (assessment only)")
        return state

    # Decision 4: Returning user with complete profile -> learning
    state["_route"] = "learning"
    state["current_phase"] = AgentPhase.LEARNING_SESSION

    pedagogy.log_phase_transition(
        user_id=state["user_id"],
        from_phase="start",
        to_phase="learning_session",
        reason="returning_user",
    )

    add_decision_log(
        state,
        node="router",
        action="route_learning",
        reason="Returning user with complete profile",
        data={"goal": state.get("confirmed_goal"), "level": state.get("assessed_level")},
    )
    logger.info(f"[Router] User {state['user_id']}: route=learning (returning user)")
    return state


def route_after_router(state: AgentState) -> str:
    """Conditional edge function after router.

    Args:
        state: Current agent state

    Returns:
        Next node name
    """
    route = state.get("_route", "learning")
    logger.info(
        f"[route_after_router] _route={route}, "
        f"is_new_user={state.get('is_new_user')}, "
        f"has_goal={bool(state.get('confirmed_goal'))}"
    )
    return route
