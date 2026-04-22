"""Session End Node - handles session termination.

This node processes session end:
1. Generate farewell message
2. Trigger final memory extraction
3. Calculate XP and streak
4. Suggest next session mode
5. Log session summary
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.agent.state import AgentState, AgentPhase, LearningModeEnum, add_decision_log
from app.services.pedagogy_logger import get_pedagogy_logger

logger = logging.getLogger(__name__)


async def session_end_node(state: AgentState) -> AgentState:
    """Node that handles session termination.

    Prepares farewell message, triggers final data persistence,
    and suggests next session.

    Args:
        state: Current agent state

    Returns:
        Updated agent state with farewell
    """
    pedagogy = get_pedagogy_logger(state["user_id"])

    turn_count = state.get("turn_count", 0)
    current_mode = state.get("current_mode", LearningModeEnum.FREE_CONVERSATION)
    username = state.get("username", "there")

    # Calculate session duration estimate
    duration_minutes = turn_count * 2  # Rough estimate: 2 min per turn

    # Generate farewell message
    farewell = _generate_farewell(
        username=username,
        turn_count=turn_count,
        mode=current_mode,
        xp_earned=state.get("xp_earned", 0),
        vocabulary_reviewed=state.get("vocabulary_reviewed", []),
    )

    state["pending_response"] = farewell
    state["should_end_session"] = True

    # Mark final memories for extraction
    conversation_history = state.get("conversation_history", [])
    if conversation_history:
        state["new_memories_to_save"].append({
            "trigger": "session_end",
            "turn": turn_count,
            "recent_messages": conversation_history,
        })

    # Log session end
    pedagogy.log_session_ended(
        user_id=state["user_id"],
        session_id=state["session_id"],
        turn_count=turn_count,
        duration_minutes=duration_minutes,
        mode=current_mode.value,
    )

    add_decision_log(
        state,
        node="session_end",
        action="session_ended",
        reason="User ended session or disconnect",
        data={
            "turn_count": turn_count,
            "duration_minutes": duration_minutes,
            "mode": current_mode.value,
            "vocabulary_count": len(state.get("vocabulary_reviewed", [])),
        },
    )

    logger.info(f"[SessionEnd] Session ended for user {state['user_id']}: "
                f"{turn_count} turns, {duration_minutes} min, mode={current_mode.value}")

    return state


def _generate_farewell(
    username: str,
    turn_count: int,
    mode: LearningModeEnum,
    xp_earned: int,
    vocabulary_reviewed: list,
) -> str:
    """Generate personalized farewell message.

    Args:
        username: User's name
        turn_count: Number of conversation turns
        mode: Learning mode used
        xp_earned: XP earned this session
        vocabulary_reviewed: Words practiced

    Returns:
        Farewell message
    """
    # Base farewell
    farewell = f"Great practice session, {username}! "

    # Add mode-specific feedback
    if mode == LearningModeEnum.MOCK_INTERVIEW:
        farewell += "You did a nice job with the interview practice. "
    elif mode == LearningModeEnum.VOCABULARY_DRILL:
        if vocabulary_reviewed:
            word_count = len(vocabulary_reviewed)
            farewell += f"You reviewed {word_count} word{'s' if word_count != 1 else ''}. "
    elif mode == LearningModeEnum.ASSESSMENT:
        farewell += "Thanks for letting me assess your level. "
    else:
        farewell += "It was great chatting with you. "

    # Add encouragement based on turn count
    if turn_count >= 10:
        farewell += "That was a good long session - consistency is key to improvement! "
    elif turn_count >= 5:
        farewell += "Nice session! "

    # XP feedback (if gamification is active)
    if xp_earned > 0:
        farewell += f"You earned {xp_earned} XP. "

    # Closing
    farewell += "See you next time!"

    return farewell


def _suggest_next_mode(state: AgentState) -> tuple[LearningModeEnum, str]:
    """Suggest mode for next session.

    Args:
        state: Current agent state

    Returns:
        Tuple of (suggested mode, reason)
    """
    current_mode = state.get("current_mode", LearningModeEnum.FREE_CONVERSATION)
    due_vocab_count = state.get("due_vocabulary_count", 0)
    goal = state.get("confirmed_goal", "")

    # After assessment - suggest mode aligned with goal
    if current_mode == LearningModeEnum.ASSESSMENT:
        if "interview" in goal.lower():
            return LearningModeEnum.MOCK_INTERVIEW, "Ready for some interview practice?"
        return LearningModeEnum.FREE_CONVERSATION, "Let's practice with conversation!"

    # After vocabulary - suggest practice mode
    if current_mode == LearningModeEnum.VOCABULARY_DRILL:
        if "interview" in goal.lower():
            return LearningModeEnum.MOCK_INTERVIEW, "Let's use those words in interview practice!"
        return LearningModeEnum.FREE_CONVERSATION, "Let's use those words in conversation!"

    # After interview - suggest vocab or more interview
    if current_mode == LearningModeEnum.MOCK_INTERVIEW:
        if due_vocab_count >= 5:
            return LearningModeEnum.VOCABULARY_DRILL, "Time to review some vocabulary!"
        return LearningModeEnum.MOCK_INTERVIEW, "Ready for another interview round?"

    # Default
    if due_vocab_count >= 10:
        return LearningModeEnum.VOCABULARY_DRILL, "You have words to review!"

    return LearningModeEnum.FREE_CONVERSATION, "Let's keep chatting!"
