"""Shared voice-session persistence helpers.

These helpers are application services used both by API entrypoints and the
shared voice session lifecycle service.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai.post_session_service import create_initial_vocabulary_cards
from app.services.gamification import StreakService, XPService
from app.services.gamification.xp_service import XPEventKind
from app.services.interview_service import InterviewService
from app.services.learning_plan_service import LearningPlanService

logger = logging.getLogger(__name__)


async def award_session_gamification(
    db: AsyncSession,
    user_id: int,
    session_id: str,
) -> None:
    """Award XP and update streak for session completion."""
    try:
        xp_service = XPService(db)
        streak_service = StreakService(db)

        streak_result = await streak_service.check_in(user_id)
        logger.info("Streak: %s (max: %s)", streak_result["streak"], streak_result["max_streak"])

        await xp_service.award_xp(user_id, XPEventKind.SESSION_COMPLETE, session_id=session_id)

        if streak_result["streak"] > 1:
            await xp_service.award_xp(
                user_id,
                XPEventKind.STREAK_BONUS,
                session_id=session_id,
                multiplier=streak_result["streak"],
            )
            logger.info("Streak bonus: +%s XP", streak_result["streak"] * 5)

        if await xp_service.check_first_session(user_id):
            await xp_service.award_xp(user_id, XPEventKind.FIRST_SESSION, session_id=session_id)
            logger.info("First session bonus: +50 XP")

        if streak_result.get("is_comeback"):
            await xp_service.award_xp(user_id, XPEventKind.COMEBACK, session_id=session_id)
            logger.info("Comeback bonus: +20 XP")

    except Exception as exc:
        try:
            await db.rollback()
        except Exception:
            logger.warning("Gamification rollback failed", exc_info=True)
        logger.warning("Gamification error: %s", exc)


async def persist_goal_state_if_needed(
    *,
    user_id: int,
    existing_goal: Optional[str],
    agent_state: dict,
    learning_plan_service: LearningPlanService,
) -> Optional[str]:
    """Persist a confirmed goal or routing-ready draft goal at session end."""
    if existing_goal:
        return None

    goal_brief = agent_state.get("goal_brief") or {}
    goal_status = goal_brief.get("status")
    goal_text = (
        agent_state.get("confirmed_goal")
        or agent_state.get("detected_goal")
        or goal_brief.get("primary_goal")
    )

    if not goal_text:
        return None

    if goal_status not in {"draft", "confirmed"} and not agent_state.get("confirmed_goal"):
        return None

    await learning_plan_service.set_goal(
        user_id,
        goal_text,
        goal_brief=goal_brief or None,
    )
    logger.info(
        "[GoalState] Persisted %s goal for user %s",
        goal_status or ("confirmed" if agent_state.get("confirmed_goal") else "detected"),
        user_id,
    )
    return goal_text


async def persist_interview_run_if_needed(
    db: AsyncSession,
    user_id: int,
    session_id: str,
    current_mode: str,
    interview_track_id: Optional[str],
    conversation_history: list[dict],
    corrections_made: int = 0,
    vocabulary_reviewed: Optional[list[dict]] = None,
) -> Optional[dict]:
    """Persist interview run at session end for meaningful mock interviews."""
    if current_mode != "mock_interview":
        return None

    user_messages = [m for m in conversation_history if m.get("role") == "user"]
    if len(user_messages) < 2:
        return None

    try:
        service = InterviewService(db)
        run = await service.record_run(
            user_id=user_id,
            session_id=session_id,
            conversation_history=conversation_history,
            corrections_count=corrections_made,
            reviewed_words=vocabulary_reviewed or [],
            track_id=interview_track_id,
        )
        logger.info(
            "[Interview] Persisted run %s for session %s, track=%s",
            run["id"],
            session_id,
            run["track_id"],
        )
        return run
    except Exception as exc:
        logger.warning(
            "[Interview] Failed to persist run for session %s: %s",
            session_id,
            exc,
        )
        return None


async def persist_session_evidence_if_needed(
    db: AsyncSession,
    user_id: int,
    session_id: str,
    current_mode: str,
    conversation_history: list[dict],
    mission_task_type: Optional[str] = None,
    mission_title: Optional[str] = None,
    mission_reason: Optional[str] = None,
    mission_linked_goal_context: Optional[str] = None,
    corrections_made: Optional[list[dict] | int] = None,
    vocabulary_reviewed: Optional[list[dict]] = None,
    duration_minutes: int = 0,
    assessed_level: Optional[str] = None,
    assessment_scores: Optional[dict] = None,
    assessment_source: Optional[str] = None,
    interview_run: Optional[dict] = None,
    next_mission_choice: Optional[str] = None,
) -> Optional[dict]:
    """Persist generic session evidence if there is enough signal to be useful."""
    user_messages = [m for m in conversation_history if m.get("role") == "user" and m.get("content")]
    has_signal = bool(
        user_messages
        or assessed_level
        or interview_run
        or corrections_made
        or vocabulary_reviewed
    )
    if not has_signal:
        return None

    try:
        service = LearningPlanService(db)
        evidence = await service.record_session_evidence(
            user_id=user_id,
            session_id=session_id,
            mode=current_mode,
            mission_task_type=mission_task_type,
            mission_title=mission_title,
            mission_reason=mission_reason,
            mission_linked_goal_context=mission_linked_goal_context,
            duration_minutes=duration_minutes,
            conversation_history=conversation_history,
            corrections_made=corrections_made,
            vocabulary_reviewed=vocabulary_reviewed or [],
            assessed_level=assessed_level,
            assessment_scores=assessment_scores or {},
            assessment_source=assessment_source,
            interview_run=interview_run,
            next_mission_choice=next_mission_choice,
        )
        if evidence:
            logger.info("[SessionEvidence] Persisted evidence for session %s", session_id)
        return evidence
    except Exception as exc:
        logger.warning(
            "[SessionEvidence] Failed to persist evidence for session %s: %s",
            session_id,
            exc,
        )
        return None


__all__ = [
    "award_session_gamification",
    "create_initial_vocabulary_cards",
    "persist_goal_state_if_needed",
    "persist_interview_run_if_needed",
    "persist_session_evidence_if_needed",
]
