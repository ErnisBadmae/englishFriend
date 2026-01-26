"""Helper functions to simplify voice.py and reduce code duplication."""

import logging
from typing import Optional, Tuple
from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai.mode_prompts import LearningMode, build_mode_prompt
from app.services.ai.mode_selector import SessionContext, select_learning_mode, get_focus_area_for_mode
from app.services.learning_plan_service import LearningPlanService
from app.services.ai.post_session_service import create_initial_vocabulary_cards
from app.services.gamification import XPService, StreakService
from app.services.gamification.xp_service import XPEventKind
from app.services.data_flow_logger import data_logger

logger = logging.getLogger(__name__)


async def handle_goal_setting(
    goal_text: str,
    user_id: int,
    db: AsyncSession,
    learning_plan_service: LearningPlanService,
    session_context: SessionContext,
    websocket: WebSocket,
) -> Tuple[Optional[LearningMode], Optional[str]]:
    """Handle goal setting and return updated mode and focus area.

    This consolidates all goal-setting logic including:
    - Updating learning plan
    - Logging goal detection
    - Creating vocabulary cards
    - Selecting new mode
    - Sending WebSocket response
    """
    try:
        learning_plan = await learning_plan_service.set_goal(user_id, goal_text)
        session_context.goal = goal_text

        # Log goal setting
        data_logger.log_goal_detected(
            user_id=user_id,
            message=f"set_goal: {goal_text}",
            detected_goal=goal_text,
        )
        data_logger.log_postgres_write(
            table="learning_plan",
            operation="UPDATE",
            data={"goal": goal_text},
            user_id=user_id,
        )

        # Create initial vocabulary cards
        recommended_vocab = learning_plan_service.get_recommended_vocabulary(learning_plan)
        if recommended_vocab:
            cards_created = await create_initial_vocabulary_cards(
                db, user_id, goal_text, recommended_vocab
            )
            logger.info(f"Created {cards_created} initial vocab cards for goal")

        # Select new mode
        current_mode = select_learning_mode(session_context)
        focus_area = get_focus_area_for_mode(current_mode, session_context)

        await websocket.send_json({
            "type": "goal_set",
            "goal": goal_text,
            "mode": current_mode.value,
            "message": f"Great! I'll help you with {goal_text}. Let's start!",
        })
        logger.info(f"Goal set: {goal_text}, mode: {current_mode.value}")
        return current_mode, focus_area
    except Exception as e:
        logger.error(f"Error setting goal: {e}")
        return None, None


def rebuild_system_prompt(
    current_mode: LearningMode,
    session_context: SessionContext,
    focus_area: str,
    vocabulary_list: str,
    memory_section: str = "",
) -> str:
    """Rebuild system prompt with current context.

    This consolidates all the parameters needed to build a mode prompt,
    reducing duplication across multiple call sites.
    """
    return build_mode_prompt(
        mode=current_mode,
        username=session_context.username,
        level=session_context.language_level,
        goal=session_context.goal or "improve English",
        interests="technology, career development",
        focus_area=focus_area,
        vocabulary_list=vocabulary_list,
        memory_section=memory_section,
    )


async def award_session_gamification(
    db: AsyncSession,
    user_id: int,
    session_id: str,
) -> None:
    """Award XP and update streak for session completion.

    This consolidates all gamification logic that happens at session end:
    - Streak check-in
    - Base session XP
    - Streak bonus
    - First session bonus
    - Comeback bonus

    Used in both normal session end and disconnect handlers.
    """
    try:
        xp_service = XPService(db)
        streak_service = StreakService(db)

        # Check-in for streak
        streak_result = await streak_service.check_in(user_id)
        logger.info(f"Streak: {streak_result['streak']} (max: {streak_result['max_streak']})")

        # XP for session completion
        await xp_service.award_xp(user_id, XPEventKind.SESSION_COMPLETE, session_id=session_id)

        # Streak bonus
        if streak_result["streak"] > 1:
            await xp_service.award_xp(
                user_id,
                XPEventKind.STREAK_BONUS,
                session_id=session_id,
                multiplier=streak_result["streak"],
            )
            logger.info(f"Streak bonus: +{streak_result['streak'] * 5} XP")

        # First session bonus
        if await xp_service.check_first_session(user_id):
            await xp_service.award_xp(user_id, XPEventKind.FIRST_SESSION, session_id=session_id)
            logger.info("First session bonus: +50 XP")

        # Comeback bonus
        if streak_result.get("is_comeback"):
            await xp_service.award_xp(user_id, XPEventKind.COMEBACK, session_id=session_id)
            logger.info("Comeback bonus: +20 XP")

    except Exception as e:
        logger.warning(f"Gamification error: {e}")
