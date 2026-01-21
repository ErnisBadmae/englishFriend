"""Mode Router Node - selects appropriate learning mode.

This node determines which learning mode to use based on:
1. Explicit user request
2. Due vocabulary count (FSRS)
3. Goal alignment (interview goal -> mock_interview)
4. Grammar error patterns
5. Default preference

The selection is logged for transparency.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.agent.state import AgentState, AgentPhase, LearningModeEnum, add_decision_log
from app.services.pedagogy_logger import get_pedagogy_logger
from app.services.ai.mode_prompts import LearningMode, build_mode_prompt, get_session_greeting

logger = logging.getLogger(__name__)


async def mode_router_node(state: AgentState) -> AgentState:
    """Node that selects the learning mode for the session.

    Selection priority:
    1. Explicit user request (if they asked for a specific mode)
    2. Due vocabulary > 10 -> vocabulary_drill
    3. Goal is interview-related -> mock_interview
    4. Recent grammar errors -> grammar_focus
    5. Default -> free_conversation or preferred_mode

    Args:
        state: Current agent state

    Returns:
        Updated agent state with selected mode
    """
    pedagogy = get_pedagogy_logger(state["user_id"])

    # Get context for selection
    goal = state.get("confirmed_goal", "General Fluency")
    due_vocab_count = state.get("due_vocabulary_count", 0)
    due_vocab_words = state.get("due_vocabulary_words", [])
    preferred_mode = state.get("preferred_mode", "free_conversation")
    last_assessment = state.get("last_assessment_date")
    total_sessions = state.get("roadmap", {}).get("sessions_completed", 0)

    selected_mode: LearningModeEnum
    reason: str
    context: dict = {
        "due_vocab": due_vocab_count,
        "goal": goal,
        "preferred_mode": preferred_mode,
    }

    # Priority 1: Check if user explicitly requested a mode
    user_message = state.get("last_user_message", "")
    requested_mode = _parse_user_mode_request(user_message)
    if requested_mode:
        selected_mode = requested_mode
        reason = "User explicitly requested this mode"
        context["trigger"] = "user_request"

    # Priority 2: Check if assessment is needed
    elif _needs_assessment(last_assessment, total_sessions):
        selected_mode = LearningModeEnum.ASSESSMENT
        reason = "Assessment needed (first session or > 30 days since last)"
        context["trigger"] = "assessment_needed"

    # Priority 3: Vocabulary review (FSRS)
    elif due_vocab_count >= 10:
        selected_mode = LearningModeEnum.VOCABULARY_DRILL
        reason = f"High vocabulary backlog ({due_vocab_count} words due)"
        context["trigger"] = "vocab_backlog"

    # Priority 4: Goal-based selection
    elif _is_interview_goal(goal):
        # For interview goals, prefer mock_interview but occasionally do vocab
        if due_vocab_count >= 5 and total_sessions % 3 == 2:
            selected_mode = LearningModeEnum.VOCABULARY_DRILL
            reason = f"Interview prep: periodic vocabulary review ({due_vocab_count} due)"
            context["trigger"] = "interview_vocab_cycle"
        else:
            selected_mode = LearningModeEnum.MOCK_INTERVIEW
            reason = f"Goal alignment: {goal} -> mock interview"
            context["trigger"] = "goal_alignment"

    # Priority 5: Grammar focus (if error patterns detected)
    elif _has_grammar_error_pattern(state.get("errors_detected", [])):
        selected_mode = LearningModeEnum.GRAMMAR_FOCUS
        reason = "Recurring grammar error patterns detected"
        context["trigger"] = "grammar_errors"

    # Priority 6: Default to preferred mode or free conversation
    else:
        if preferred_mode == "mock_interview":
            selected_mode = LearningModeEnum.MOCK_INTERVIEW
        elif preferred_mode == "vocabulary_drill" and due_vocab_count > 0:
            selected_mode = LearningModeEnum.VOCABULARY_DRILL
        else:
            selected_mode = LearningModeEnum.FREE_CONVERSATION
        reason = f"Default selection based on preference: {preferred_mode}"
        context["trigger"] = "default"

    # Store selection
    state["current_mode"] = selected_mode
    state["mode_reason"] = reason
    state["current_phase"] = AgentPhase.LEARNING_SESSION

    # Build system prompt for the selected mode
    system_prompt = _build_system_prompt(state, selected_mode)
    state["system_prompt"] = system_prompt

    # Generate greeting for the mode (if first turn in this mode)
    if state.get("turn_count", 0) == 0:
        greeting = get_session_greeting(
            LearningMode(selected_mode.value),
            state.get("username", "there"),
        )
        state["pending_response"] = greeting
        state["needs_user_input"] = True

    # Log the selection
    pedagogy.log_mode_selected(
        user_id=state["user_id"],
        mode=selected_mode.value,
        reason=reason,
        context=context,
    )

    add_decision_log(
        state,
        node="mode_router",
        action="mode_selected",
        reason=reason,
        data={
            "mode": selected_mode.value,
            "context": context,
        },
    )

    logger.info(f"[ModeRouter] Selected {selected_mode.value}: {reason}")
    return state


def _parse_user_mode_request(message: str) -> Optional[LearningModeEnum]:
    """Parse user message for explicit mode request.

    Args:
        message: User's message

    Returns:
        Requested mode or None
    """
    if not message:
        return None

    message_lower = message.lower()

    # Assessment keywords
    if any(kw in message_lower for kw in [
        "check my level", "assess", "test my english", "evaluate",
        "оценить", "проверить уровень",
    ]):
        return LearningModeEnum.ASSESSMENT

    # Mock interview keywords
    if any(kw in message_lower for kw in [
        "mock interview", "practice interview", "simulate interview",
        "interview practice", "собеседование", "интервью",
    ]):
        return LearningModeEnum.MOCK_INTERVIEW

    # Vocabulary keywords
    if any(kw in message_lower for kw in [
        "vocabulary", "vocab", "words", "review words",
        "повторить слова", "слова", "drill",
    ]):
        return LearningModeEnum.VOCABULARY_DRILL

    # Grammar keywords
    if any(kw in message_lower for kw in [
        "grammar", "грамматика", "grammar practice",
    ]):
        return LearningModeEnum.GRAMMAR_FOCUS

    # Free conversation keywords
    if any(kw in message_lower for kw in [
        "just chat", "free talk", "conversation",
        "просто поговорить", "разговор",
    ]):
        return LearningModeEnum.FREE_CONVERSATION

    return None


def _needs_assessment(last_assessment: Optional[str], total_sessions: int) -> bool:
    """Check if assessment is needed.

    Args:
        last_assessment: ISO date of last assessment
        total_sessions: Total sessions completed

    Returns:
        True if assessment needed
    """
    # First session ever
    if total_sessions == 0:
        return True

    # No assessment ever
    if not last_assessment:
        return total_sessions % 5 == 0  # Remind every 5 sessions

    # More than 30 days since last assessment
    try:
        last_date = datetime.fromisoformat(last_assessment)
        days_since = (datetime.utcnow() - last_date).days
        return days_since > 30
    except (ValueError, TypeError):
        return False


def _is_interview_goal(goal: Optional[str]) -> bool:
    """Check if goal is interview-related.

    Args:
        goal: Learning goal

    Returns:
        True if interview-related
    """
    if not goal:
        return False

    goal_lower = goal.lower()
    interview_keywords = [
        "interview", "интервью",
        "job", "работа",
        "ml", "machine learning",
        "data science", "data scientist",
        "software engineer", "developer",
        "ielts", "toefl",
    ]

    return any(kw in goal_lower for kw in interview_keywords)


def _has_grammar_error_pattern(errors: list) -> bool:
    """Check if there's a recurring grammar error pattern.

    Args:
        errors: List of detected errors

    Returns:
        True if patterns warrant grammar focus
    """
    if len(errors) < 3:
        return False

    # Count grammar errors
    grammar_errors = [e for e in errors if e.get("type") == "grammar"]
    return len(grammar_errors) >= 3


def _build_system_prompt(state: AgentState, mode: LearningModeEnum) -> str:
    """Build system prompt for the selected mode.

    Args:
        state: Current agent state
        mode: Selected learning mode

    Returns:
        System prompt string
    """
    # Build vocabulary list for prompt
    vocabulary_list = ""
    due_words = state.get("due_vocabulary_words", [])
    if due_words:
        vocabulary_list = "\n".join([f"- {word}" for word in due_words[:5]])

    # Get memory section
    memory_section = state.get("memory_section", "")

    # Get interests
    interests = state.get("confirmed_interests", [])
    interests_str = ", ".join(interests) if interests else "general topics"

    # Build prompt using existing mode_prompts
    return build_mode_prompt(
        mode=LearningMode(mode.value),
        username=state.get("username", "Student"),
        level=state.get("language_level", "B1"),
        goal=state.get("confirmed_goal", "improve English"),
        interests=interests_str,
        focus_area=state.get("focus_areas", ["general"])[0] if state.get("focus_areas") else "general",
        vocabulary_list=vocabulary_list,
        memory_section=memory_section,
    )


def route_to_mode(state: AgentState) -> str:
    """Conditional edge function to route to appropriate mode handler.

    Currently all modes use turn_processor, but this allows for
    future mode-specific handlers.

    Args:
        state: Current agent state

    Returns:
        Name of the next node
    """
    return "turn_processor"
