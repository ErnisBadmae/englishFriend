"""Session End Node - Cleanup, XP calculation, and farewell.

Handles:
- Session summary generation
- XP calculation
- Farewell message
- Data persistence
"""

import logging
import time
from typing import Optional

from app.agent.state import AgentState, AgentPhase, add_decision_log
from app.agent.response_parser import parse_llm_response
from app.services.pedagogy_logger import get_pedagogy_logger
from app.services.prompt_service import get_prompt_service
from app.services.ai.llm_provider import LLMEmptyContentError, get_llm_provider
from app.core.metrics import (
    agent_v2_llm_latency,
    agent_v2_session_complete,
    agent_guardrail_fallbacks,
)
from app.agent.guardrails import validate_and_sanitize

logger = logging.getLogger(__name__)

# XP values
XP_PER_TURN = 5
XP_PER_CORRECTION = 2
XP_PER_VOCABULARY = 3
XP_BONUS_GOAL_SET = 20
XP_BONUS_ASSESSMENT = 30


async def session_end_node(state: AgentState) -> AgentState:
    """End session with summary and farewell.

    Args:
        state: Current agent state

    Returns:
        Updated state with farewell and XP
    """
    pedagogy = get_pedagogy_logger(state["user_id"])
    prompt_service = get_prompt_service()
    llm = get_llm_provider()

    user_id = state["user_id"]
    session_id = state.get("session_id", "")

    # Calculate XP
    xp_earned = _calculate_session_xp(state)
    state["xp_earned"] = xp_earned

    # Build template context
    template_context = _build_template_context(state)

    # Get and render farewell prompt
    rendered_prompt, template = await prompt_service.get_and_render(
        node_type="session_end",
        user_id=user_id,
        state=template_context,
    )

    if not rendered_prompt:
        logger.warning("[SessionEnd] No template found, using fallback")
        rendered_prompt = _get_fallback_prompt(state)

    # Call LLM for personalized farewell
    start_time = time.time()
    fallback_reason: Optional[str] = None
    try:
        response = await llm.generate(
            user_message="",
            system_prompt=rendered_prompt,
            max_tokens=200,
        )
        latency_ms = int((time.time() - start_time) * 1000)
        agent_v2_llm_latency.labels(node="session_end").observe(latency_ms / 1000)
    except LLMEmptyContentError as exc:
        logger.warning("[SessionEnd] Empty final content: %s", exc)
        response = None
        fallback_reason = "empty_final_content"
    except Exception as e:
        logger.error(f"[SessionEnd] LLM error: {e}")
        response = None
        fallback_reason = "llm_error"

    # Parse response or use fallback
    if response:
        parse_result = parse_llm_response(response, default_action="farewell")
        action = parse_result.action

        # Apply guardrails
        action, was_modified = validate_and_sanitize(
            response=response,
            node_type="session_end",
            parsed_action=action,
            state=state,
        )

        if was_modified:
            agent_guardrail_fallbacks.labels(node="session_end").inc()

        farewell = action.get("response_text", "")
        state["session_end_fallback_used"] = False
        state["session_end_fallback_reason"] = None
    else:
        farewell = _generate_simple_farewell(state)
        state["session_end_fallback_used"] = True
        state["session_end_fallback_reason"] = fallback_reason or "simple_farewell"

    # Log usage
    await prompt_service.log_usage(
        session_id=session_id,
        user_id=user_id,
        node_type="session_end",
        template=template,
        variant=template.variant if template else "fallback",
        turn_number=state.get("turn_count", 0),
        llm_response=response,
        parsed_action={"action": "farewell", "response_text": farewell},
        parse_success=True,
        latency_ms=latency_ms if response else 0,
    )

    # Set final state
    state["pending_response"] = farewell
    state["current_phase"] = AgentPhase.SESSION_END
    state["needs_user_input"] = False
    state["session_complete_reason"] = "session_end"
    state["session_complete_return_screen"] = "home"

    # Log session completion
    current_mode = state.get("current_mode")
    mode_str = current_mode.value if hasattr(current_mode, "value") else str(current_mode)
    turn_count_val = state.get("turn_count", 0)

    pedagogy.log_session_ended(
        user_id=user_id,
        session_id=session_id,
        turn_count=turn_count_val,
        duration_minutes=turn_count_val * 2,  # Rough estimate: 2 min per turn
        mode=mode_str,
    )

    # Metrics
    agent_v2_session_complete.labels(
        goal=state.get("confirmed_goal", "none"),
        level=state.get("language_level", "unknown"),
    ).inc()

    add_decision_log(
        state,
        node="session_end",
        action="farewell",
        reason="Session completed",
        data={
            "turns": state.get("turn_count", 0),
            "xp": xp_earned,
            "corrections": len(state.get("corrections_made", [])),
        },
    )

    logger.info(
        f"[SessionEnd] User {user_id}: session_id={session_id[:8]}, "
        f"turns={state.get('turn_count', 0)}, xp={xp_earned}"
    )

    return state


def _calculate_session_xp(state: AgentState) -> int:
    """Calculate XP earned in session.

    Args:
        state: Agent state

    Returns:
        Total XP earned
    """
    xp = 0

    # XP per turn
    turns = state.get("turn_count", 0)
    xp += turns * XP_PER_TURN

    # XP per correction made
    corrections = len(state.get("corrections_made", []))
    xp += corrections * XP_PER_CORRECTION

    # XP per vocabulary word practiced
    vocabulary = len(state.get("vocabulary_reviewed", []))
    xp += vocabulary * XP_PER_VOCABULARY

    # Bonus for setting goal
    if state.get("confirmed_goal") and state.get("is_new_user"):
        xp += XP_BONUS_GOAL_SET

    # Bonus for completing assessment
    if state.get("assessed_level") and state.get("is_new_user"):
        xp += XP_BONUS_ASSESSMENT

    return xp


def _build_template_context(state: AgentState) -> dict:
    """Build context dict for template rendering."""
    return {
        "username": state.get("username", "Student"),
        "user_id": state.get("user_id"),
        "turn_count": state.get("turn_count", 0),
        "current_mode": state.get("current_mode", "free_conversation"),
        "confirmed_goal": state.get("confirmed_goal"),
        "language_level": state.get("language_level", "B1"),
        "corrections_made": state.get("corrections_made", []),
        "vocabulary_reviewed": [
            v.get("word", v) if isinstance(v, dict) else v
            for v in state.get("vocabulary_reviewed", [])
        ],
        "xp_earned": state.get("xp_earned", 0),
        "session_id": state.get("session_id", ""),
    }


def _get_fallback_prompt(state: AgentState) -> str:
    """Get fallback prompt when template not available."""
    username = state.get("username", "Student")
    turns = state.get("turn_count", 0)
    corrections = len(state.get("corrections_made", []))

    return f"""You are English Friend saying goodbye after a practice session.

Session summary:
- Student: {username}
- Turns: {turns}
- Corrections: {corrections}

Generate a warm, encouraging farewell (3-4 sentences) that:
1. Thanks them for practicing
2. Mentions something they did well
3. Encourages them to come back

Respond with JSON:
{{"action": "farewell", "response_text": "your farewell message"}}"""


def _generate_simple_farewell(state: AgentState) -> str:
    """Generate simple farewell without LLM."""
    username = state.get("username", "there")
    turns = state.get("turn_count", 0)

    if turns > 10:
        return (
            f"Great session, {username}! We had a really productive conversation. "
            f"Keep up the excellent work, and I'll see you next time!"
        )
    elif turns > 5:
        return (
            f"Nice practice, {username}! You're making good progress. "
            f"See you soon for more English practice!"
        )
    else:
        return (
            f"Thanks for chatting, {username}! "
            f"Come back anytime to practice more English!"
        )
