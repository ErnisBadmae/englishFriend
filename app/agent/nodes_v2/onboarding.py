"""Onboarding Node - Unified LLM-driven onboarding flow.

Handles:
- Goal discovery and confirmation
- Interest extraction
- Quick assessment

Uses structured JSON output from LLM for decisions.
"""

import logging
import time
from typing import Optional

from app.agent.state import AgentState, AgentPhase, add_decision_log
from app.agent.response_parser import (
    parse_llm_response,
    extract_goal_from_action,
    extract_interests_from_action,
    extract_assessment_from_action,
)
from app.services.pedagogy_logger import get_pedagogy_logger
from app.services.prompt_service import get_prompt_service
from app.services.ai.llm_provider import get_llm_provider
from app.core.metrics import (
    agent_v2_llm_latency,
    agent_v2_parse_success,
    agent_v2_goal_detection,
    agent_guardrail_violations,
    agent_guardrail_fallbacks,
)
from app.agent.guardrails import (
    validate_and_sanitize,
    validate_confidence,
    CONFIDENCE_THRESHOLDS,
)

logger = logging.getLogger(__name__)


async def onboarding_node(state: AgentState) -> AgentState:
    """Unified onboarding: goal discovery + interests + assessment.

    Uses LLM with structured output to make decisions.

    Args:
        state: Current agent state

    Returns:
        Updated state
    """
    pedagogy = get_pedagogy_logger(state["user_id"])
    prompt_service = get_prompt_service()
    llm = get_llm_provider()

    user_message = state.get("last_user_message", "")
    user_id = state["user_id"]
    session_id = state.get("session_id", "")

    # Build state context for template
    template_context = _build_template_context(state)

    # Get and render prompt template
    rendered_prompt, template = await prompt_service.get_and_render(
        node_type="onboarding",
        user_id=user_id,
        state=template_context,
    )

    if not rendered_prompt:
        # Fallback to hardcoded prompt if no template
        logger.warning("[Onboarding] No template found, using fallback")
        rendered_prompt = _get_fallback_prompt(state)

    # Call LLM
    start_time = time.time()
    try:
        response = await llm.generate(
            user_message=user_message or "",
            system_prompt=rendered_prompt,
            max_tokens=500,
        )
        latency_ms = int((time.time() - start_time) * 1000)
        agent_v2_llm_latency.labels(node="onboarding").observe(latency_ms / 1000)

    except Exception as e:
        logger.error(f"[Onboarding] LLM error: {e}")
        state["pending_response"] = "I'm having trouble right now. Could you repeat that?"
        state["needs_user_input"] = True
        return state

    # Parse structured response
    parse_result = parse_llm_response(response, default_action="ask_goal")
    action = parse_result.action

    # Apply guardrails
    action, was_modified = validate_and_sanitize(
        response=response,
        node_type="onboarding",
        parsed_action=action,
        state=state,
    )

    if was_modified:
        agent_guardrail_fallbacks.labels(node="onboarding").inc()

    # Log metrics
    agent_v2_parse_success.labels(
        node="onboarding",
        success=str(parse_result.success).lower()
    ).inc()

    # Log usage for A/B analytics
    await prompt_service.log_usage(
        session_id=session_id,
        user_id=user_id,
        node_type="onboarding",
        template=template,
        variant=template.variant if template else "fallback",
        turn_number=state.get("turn_count", 0),
        llm_response=response,
        parsed_action=action,
        parse_success=parse_result.success,
        latency_ms=latency_ms,
    )

    # Apply action to state
    state = await _apply_onboarding_action(state, action, pedagogy)

    # Log decision
    add_decision_log(
        state,
        node="onboarding",
        action=action.get("action", "unknown"),
        reason=f"LLM decision (strategy={parse_result.strategy})",
        data={
            "parse_success": parse_result.success,
            "confidence": action.get("confidence"),
        },
    )

    logger.info(
        f"[Onboarding] User {user_id}: action={action.get('action')}, "
        f"parse_strategy={parse_result.strategy}"
    )

    return state


async def _apply_onboarding_action(
    state: AgentState,
    action: dict,
    pedagogy,
) -> AgentState:
    """Apply parsed LLM action to state.

    Args:
        state: Current state
        action: Parsed action dict
        pedagogy: Pedagogy logger

    Returns:
        Updated state
    """
    action_type = action.get("action", "")
    response_text = action.get("response_text", "")

    # Always set response
    state["pending_response"] = response_text
    state["needs_user_input"] = True
    state["current_phase"] = AgentPhase.ONBOARDING

    # Handle specific actions
    if action_type == "goal_confirmed":
        goal = extract_goal_from_action(action)
        if goal:
            state["confirmed_goal"] = goal
            state["goal_needs_confirmation"] = False

            agent_v2_goal_detection.labels(detected="true").inc()

            pedagogy.log_goal_confirmed(
                user_id=state["user_id"],
                goal=goal,
                user_response=state.get("last_user_message", ""),
            )
            logger.info(f"[Onboarding] Goal confirmed: {goal}")

    elif action_type == "confirm_goal":
        goal = extract_goal_from_action(action)
        if goal:
            # Check confidence threshold before confirming goal detection
            if validate_confidence(action, "goal_detection"):
                state["detected_goal"] = goal
                state["goal_needs_confirmation"] = True

                agent_v2_goal_detection.labels(detected="true").inc()

                pedagogy.log_goal_detected(
                    user_id=state["user_id"],
                    message=state.get("last_user_message", ""),
                    goal=goal,
                    confidence=action.get("confidence", 0.8),
                )
            else:
                # Confidence too low, keep asking
                logger.info(
                    f"[Onboarding] Goal confidence too low ({action.get('confidence', 0.5)}), "
                    f"threshold is {CONFIDENCE_THRESHOLDS['goal_detection']}"
                )
                agent_v2_goal_detection.labels(detected="false").inc()

    elif action_type == "goal_skipped":
        state["confirmed_goal"] = "General Fluency"
        state["goal_needs_confirmation"] = False

        pedagogy.log_goal_defaulted(
            user_id=state["user_id"],
            default_goal="General Fluency",
            reason="User skipped goal setting",
        )

    elif action_type == "interests_confirmed":
        interests = extract_interests_from_action(action)
        if interests:
            state["confirmed_interests"] = interests

            pedagogy.log_interests_detected(
                user_id=state["user_id"],
                interests=interests,
                source="llm_extraction",
            )

    elif action_type == "assessment_complete":
        level, scores = extract_assessment_from_action(action)
        if level:
            state["assessed_level"] = level
        if scores:
            state["assessment_scores"] = scores

        pedagogy.log_level_assessed(
            user_id=state["user_id"],
            level=level or "B1",
            scores=scores or {},
            confidence=1.0,
        )

    elif action_type == "transition_to_learning":
        state["current_phase"] = AgentPhase.LEARNING_SESSION

        pedagogy.log_phase_transition(
            user_id=state["user_id"],
            from_phase="onboarding",
            to_phase="learning_session",
            reason="onboarding_complete",
        )

    return state


def _build_template_context(state: AgentState) -> dict:
    """Build context dict for template rendering.

    Args:
        state: Agent state

    Returns:
        Context dict for Jinja2
    """
    return {
        "username": state.get("username", "Student"),
        "user_id": state.get("user_id"),
        "language_level": state.get("language_level", "B1"),
        "turn_count": state.get("turn_count", 0),
        "session_id": state.get("session_id", ""),
        "last_user_message": state.get("last_user_message", ""),
        "confirmed_goal": state.get("confirmed_goal"),
        "detected_goal": state.get("detected_goal"),
        "goal_needs_confirmation": state.get("goal_needs_confirmation", False),
        "confirmed_interests": state.get("confirmed_interests", []),
        "assessed_level": state.get("assessed_level"),
        "assessment_scores": state.get("assessment_scores", {}),
        "conversation_history": state.get("conversation_history", []),
        "is_new_user": state.get("is_new_user", True),
    }


def _get_fallback_prompt(state: AgentState) -> str:
    """Get fallback prompt when template not available."""
    username = state.get("username", "Student")
    has_goal = bool(state.get("confirmed_goal"))
    has_interests = len(state.get("confirmed_interests", [])) > 0

    if not has_goal:
        return f"""You are English Friend, a patient English tutor.
Student: {username}

Ask about their English learning goal. Be warm and friendly.
When they mention a goal, confirm it: "So you want to focus on [goal], is that right?"

Respond with JSON:
{{"action": "ask_goal" or "confirm_goal", "response_text": "your response", "extracted_data": {{"goal": "detected goal or null"}}}}"""

    elif not has_interests:
        return f"""You are English Friend.
Student: {username}, Goal: {state.get('confirmed_goal')}

Ask about their interests for personalization.

Respond with JSON:
{{"action": "ask_interests" or "interests_confirmed", "response_text": "your response", "extracted_data": {{"interests": ["list"]}}}}"""

    else:
        return f"""You are English Friend.
Student: {username}, Level: {state.get('language_level', 'B1')}

Ask 2-3 questions to assess their English level. Start simple, then increase difficulty.

Respond with JSON:
{{"action": "ask_assessment" or "assessment_complete", "response_text": "your response", "extracted_data": {{"assessed_level": "A1-C2"}}}}"""


def route_after_onboarding(state: AgentState) -> str:
    """Conditional edge function after onboarding.

    Routes to:
    - "wait_for_input": Pause graph, wait for user response (routes to END)
    - "learning": Transition to learning phase
    - "session_end": End session

    Args:
        state: Current agent state

    Returns:
        Next node name or "wait_for_input" to pause
    """
    # Check if we should end
    if state.get("should_end_session"):
        return "session_end"

    # Check if transitioning to learning
    phase = state.get("current_phase", AgentPhase.ONBOARDING)
    if phase == AgentPhase.LEARNING_SESSION:
        return "learning"

    # If we need user input, pause the graph (route to END)
    if state.get("needs_user_input", True):
        return "wait_for_input"

    # Continue onboarding (this shouldn't happen normally)
    return "wait_for_input"
