"""Goal Discovery Node - discovers and confirms user's learning goal.

This node implements a multi-step goal discovery process:
1. Ask the user about their learning goal
2. Use LLM to extract the goal from their response
3. Ask for confirmation: "So you want to [goal], is that right?"
4. Handle confirmation (yes/no) or clarification

If the user doesn't want to specify a goal, default to "General Fluency".
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from app.agent.state import AgentState, AgentPhase, add_decision_log
from app.services.pedagogy_logger import get_pedagogy_logger
from app.services.ai.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)

# System prompt for goal extraction
GOAL_EXTRACTION_PROMPT = """You are analyzing a user's message to extract their English learning goal.

The user is learning English and may express goals like:
- Job/tech interviews (ML, Data Science, Software Engineering)
- IELTS/TOEFL exam preparation
- Business English
- General conversation/fluency
- Travel English
- Academic English

Extract the main goal from their message. If multiple goals are mentioned, pick the most specific one.

Respond with ONLY the goal category in one of these formats:
- "ML/Data Science Interview Preparation"
- "Software Engineering Interview Preparation"
- "Job Interview Preparation"
- "IELTS Preparation"
- "TOEFL Preparation"
- "Business English"
- "General Fluency"
- "Academic English"
- "Travel English"
- "NONE" (if no goal can be extracted)

User message: {message}

Goal:"""

# System prompt for confirmation detection
CONFIRMATION_DETECTION_PROMPT = """Analyze if the user is confirming or rejecting a statement.

The assistant asked: "So you want to {goal}, is that right?"
The user responded: "{response}"

Is the user:
- Confirming (saying yes, agreeing, affirming)
- Rejecting (saying no, disagreeing, correcting)
- Clarifying (providing more detail or a different goal)
- Skipping (wants to skip goal setting, just chat)

Respond with ONLY one word: CONFIRM, REJECT, CLARIFY, or SKIP

Response:"""


async def goal_discovery_node(state: AgentState) -> AgentState:
    """Node that discovers user's learning goal through conversation.

    This node has multiple sub-states:
    1. Initial ask (no detected_goal)
    2. Waiting for confirmation (goal_needs_confirmation=True)
    3. Processing confirmation/rejection

    Args:
        state: Current agent state

    Returns:
        Updated agent state
    """
    pedagogy = get_pedagogy_logger(state["user_id"])
    llm = get_llm_provider()

    user_message = state.get("last_user_message", "")

    # Sub-state 1: Initial greeting - ask about goal
    if not state.get("detected_goal") and not state.get("goal_needs_confirmation"):
        # First interaction - greet and ask about goal
        username = state.get("username", "there")
        greeting = (
            f"Hi {username}! Welcome to English Friend. "
            "I'm here to help you practice and improve your English through conversation. "
            "What brings you here today? What's your main goal for learning English?"
        )

        state["pending_response"] = greeting
        state["current_phase"] = AgentPhase.GOAL_DISCOVERY
        state["needs_user_input"] = True

        add_decision_log(
            state,
            node="goal_discovery",
            action="ask_initial_goal",
            reason="First interaction, asking about learning goal",
        )

        logger.info(f"[GoalDiscovery] Asking user {state['user_id']} about their goal")
        return state

    # Sub-state 2: User responded, extract goal
    if user_message and not state.get("goal_needs_confirmation"):
        # Try to extract goal from user's message
        detected_goal = await _extract_goal_from_message(llm, user_message)

        if detected_goal and detected_goal != "NONE":
            # Goal detected - ask for confirmation
            state["detected_goal"] = detected_goal
            state["goal_needs_confirmation"] = True

            confirmation_prompt = (
                f"Great! So you want to focus on {detected_goal}, is that right? "
                "If not, just tell me what you'd prefer."
            )

            state["pending_response"] = confirmation_prompt
            state["needs_user_input"] = True

            pedagogy.log_goal_detected(
                user_id=state["user_id"],
                message=user_message,
                goal=detected_goal,
                confidence=0.8,
            )
            pedagogy.log_goal_confirmation_requested(
                user_id=state["user_id"],
                goal=detected_goal,
                confirmation_prompt=confirmation_prompt,
            )

            add_decision_log(
                state,
                node="goal_discovery",
                action="detected_goal_ask_confirm",
                reason=f"Extracted goal '{detected_goal}' from message",
                data={"message": user_message[:100], "goal": detected_goal},
            )

            logger.info(f"[GoalDiscovery] Detected goal '{detected_goal}', asking confirmation")
            return state

        else:
            # Could not extract goal - ask more directly
            clarify_prompt = (
                "I'd love to help you! Could you tell me more specifically what you'd like to work on? "
                "For example: job interviews, exam preparation (IELTS/TOEFL), business English, "
                "or just general conversation practice?"
            )

            state["pending_response"] = clarify_prompt
            state["needs_user_input"] = True

            add_decision_log(
                state,
                node="goal_discovery",
                action="ask_clarification",
                reason="Could not extract clear goal from message",
                data={"message": user_message[:100]},
            )

            logger.info(f"[GoalDiscovery] Could not extract goal, asking for clarification")
            return state

    # Sub-state 3: Waiting for confirmation response
    if state.get("goal_needs_confirmation") and user_message:
        detected_goal = state.get("detected_goal", "")

        # Determine if user confirmed, rejected, or wants to skip
        confirmation_type = await _detect_confirmation(llm, detected_goal, user_message)

        if confirmation_type == "CONFIRM":
            # User confirmed - save and move on
            state["confirmed_goal"] = detected_goal
            state["goal_needs_confirmation"] = False
            state["current_phase"] = AgentPhase.INTEREST_PROBE

            response = (
                f"Perfect! I'll tailor our conversations to help you with {detected_goal}. "
                "Now, what topics do you enjoy talking about? "
                "This helps me make our practice more interesting for you."
            )

            state["pending_response"] = response
            state["needs_user_input"] = True

            pedagogy.log_goal_confirmed(
                user_id=state["user_id"],
                goal=detected_goal,
                user_response=user_message,
            )
            pedagogy.log_phase_transition(
                user_id=state["user_id"],
                from_phase="goal_discovery",
                to_phase="interest_probe",
                reason="goal_confirmed",
            )

            add_decision_log(
                state,
                node="goal_discovery",
                action="goal_confirmed",
                reason=f"User confirmed goal: {detected_goal}",
                data={"confirmed_goal": detected_goal},
            )

            logger.info(f"[GoalDiscovery] User confirmed goal: {detected_goal}")
            return state

        elif confirmation_type == "SKIP":
            # User wants to skip - use default goal
            default_goal = "General Fluency"
            state["confirmed_goal"] = default_goal
            state["goal_needs_confirmation"] = False
            state["current_phase"] = AgentPhase.LEARNING_SESSION

            response = (
                "No problem! Let's just chat and practice English together. "
                "I'll help you improve naturally through conversation. "
                "What would you like to talk about?"
            )

            state["pending_response"] = response
            state["needs_user_input"] = True

            pedagogy.log_goal_defaulted(
                user_id=state["user_id"],
                default_goal=default_goal,
                reason="User chose to skip goal setting",
            )
            pedagogy.log_phase_transition(
                user_id=state["user_id"],
                from_phase="goal_discovery",
                to_phase="learning_session",
                reason="user_skipped_goal",
            )

            add_decision_log(
                state,
                node="goal_discovery",
                action="goal_skipped",
                reason="User chose to skip goal setting",
                data={"default_goal": default_goal},
            )

            logger.info(f"[GoalDiscovery] User skipped, using default: {default_goal}")
            return state

        elif confirmation_type == "REJECT" or confirmation_type == "CLARIFY":
            # User rejected or wants to clarify - try to extract new goal
            new_goal = await _extract_goal_from_message(llm, user_message)

            if new_goal and new_goal != "NONE" and new_goal != detected_goal:
                # Found a new goal in their response
                state["detected_goal"] = new_goal

                response = (
                    f"I see! So you'd prefer to focus on {new_goal}, right?"
                )

                state["pending_response"] = response
                state["needs_user_input"] = True

                pedagogy.log_goal_rejected(
                    user_id=state["user_id"],
                    goal=detected_goal,
                    user_response=user_message,
                )
                pedagogy.log_goal_detected(
                    user_id=state["user_id"],
                    message=user_message,
                    goal=new_goal,
                    confidence=0.7,
                )

                add_decision_log(
                    state,
                    node="goal_discovery",
                    action="goal_rejected_new_detected",
                    reason=f"User rejected '{detected_goal}', detected new goal '{new_goal}'",
                    data={"old_goal": detected_goal, "new_goal": new_goal},
                )

                logger.info(f"[GoalDiscovery] Goal rejected, new goal detected: {new_goal}")
                return state

            else:
                # Could not extract new goal - ask again
                state["detected_goal"] = None
                state["goal_needs_confirmation"] = False

                response = (
                    "I want to make sure I understand correctly. "
                    "What would you like to focus on? For example: "
                    "preparing for job interviews, improving general conversation, "
                    "or preparing for an English exam?"
                )

                state["pending_response"] = response
                state["needs_user_input"] = True

                pedagogy.log_goal_rejected(
                    user_id=state["user_id"],
                    goal=detected_goal,
                    user_response=user_message,
                )

                add_decision_log(
                    state,
                    node="goal_discovery",
                    action="goal_rejected_ask_again",
                    reason="User rejected goal, could not extract new one",
                )

                logger.info(f"[GoalDiscovery] Goal rejected, asking again")
                return state

    # Fallback - should not reach here normally
    state["needs_user_input"] = True
    return state


async def _extract_goal_from_message(llm, message: str) -> Optional[str]:
    """Use LLM to extract learning goal from user message.

    Args:
        llm: LLM provider instance
        message: User's message

    Returns:
        Extracted goal or None
    """
    try:
        prompt = GOAL_EXTRACTION_PROMPT.format(message=message)

        response = await llm.generate(
            user_message=message,
            system_prompt=prompt,
            max_tokens=50,
        )

        # Clean up response
        goal = response.strip().strip('"').strip("'")

        # Validate it's one of our expected goals
        valid_goals = [
            "ML/Data Science Interview Preparation",
            "Software Engineering Interview Preparation",
            "Job Interview Preparation",
            "IELTS Preparation",
            "TOEFL Preparation",
            "Business English",
            "General Fluency",
            "Academic English",
            "Travel English",
        ]

        # Check for exact or partial match
        for valid_goal in valid_goals:
            if valid_goal.lower() in goal.lower() or goal.lower() in valid_goal.lower():
                return valid_goal

        # If response contains "interview", map to appropriate type
        if "interview" in goal.lower():
            if any(kw in message.lower() for kw in ["ml", "machine learning", "data"]):
                return "ML/Data Science Interview Preparation"
            elif any(kw in message.lower() for kw in ["software", "developer", "engineer"]):
                return "Software Engineering Interview Preparation"
            return "Job Interview Preparation"

        if goal == "NONE" or not goal:
            return None

        return goal

    except Exception as e:
        logger.warning(f"Error extracting goal: {e}")
        return None


async def _detect_confirmation(llm, goal: str, response: str) -> str:
    """Detect if user confirmed, rejected, or wants to clarify.

    Args:
        llm: LLM provider instance
        goal: The goal being confirmed
        response: User's response

    Returns:
        One of: CONFIRM, REJECT, CLARIFY, SKIP
    """
    # Quick pattern matching for common responses
    response_lower = response.lower().strip()

    # Clear confirmations
    if response_lower in ["yes", "yeah", "yep", "correct", "right", "exactly", "that's right"]:
        return "CONFIRM"
    if re.match(r"^(yes|yeah|yep|да|correct|right|sure|ok|okay)\b", response_lower):
        return "CONFIRM"

    # Clear rejections
    if response_lower in ["no", "nope", "not really", "not exactly"]:
        return "REJECT"

    # Skip indicators
    if any(kw in response_lower for kw in [
        "just chat", "just talk", "no goal", "skip", "doesn't matter",
        "don't know", "not sure", "whatever", "anything"
    ]):
        return "SKIP"

    # Use LLM for ambiguous cases
    try:
        prompt = CONFIRMATION_DETECTION_PROMPT.format(goal=goal, response=response)

        llm_response = await llm.generate(
            user_message=response,
            system_prompt=prompt,
            max_tokens=10,
        )

        result = llm_response.strip().upper()
        if result in ["CONFIRM", "REJECT", "CLARIFY", "SKIP"]:
            return result
        return "CLARIFY"  # Default to clarification

    except Exception as e:
        logger.warning(f"Error detecting confirmation: {e}")
        # Default based on simple heuristics
        if any(word in response_lower for word in ["yes", "right", "correct"]):
            return "CONFIRM"
        return "CLARIFY"


def route_after_goal_discovery(state: AgentState) -> str:
    """Conditional edge function to route after goal discovery.

    Args:
        state: Current agent state

    Returns:
        Name of the next node to execute
    """
    if state.get("confirmed_goal"):
        phase = state.get("current_phase", AgentPhase.GOAL_DISCOVERY)
        if phase == AgentPhase.INTEREST_PROBE:
            return "interest_probe"
        elif phase == AgentPhase.LEARNING_SESSION:
            return "mode_router"

    # Stay in goal discovery if not confirmed yet
    return "goal_discovery"
