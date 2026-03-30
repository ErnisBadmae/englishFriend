from collections import Counter
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.core_tables import Correction, Feedback, Session, User
from app.services.ai.vocabulary_service import VocabularyService
from app.services.gamification import StreakService, XPService
from app.services.interview_service import build_interview_summary
from app.services.learning_plan_service import LearningPlanService


def build_latest_assessment(roadmap: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not roadmap:
        return None

    history = roadmap.get("assessment_history") or []
    if history:
        latest = history[-1]
        return {
            "date": latest.get("date"),
            "level": latest.get("level"),
            "scores": latest.get("scores") or {},
            "notes": latest.get("notes"),
        }

    current_level = roadmap.get("current_level")
    if not current_level:
        return None

    return {
        "date": roadmap.get("last_assessment"),
        "level": current_level,
        "scores": {},
        "notes": None,
    }


def extract_focus_areas(roadmap: Optional[dict[str, Any]], limit: int = 3) -> list[str]:
    if not roadmap:
        return []

    focus_areas = roadmap.get("focus_areas") or []
    result: list[str] = []
    for item in focus_areas:
        if isinstance(item, dict):
            area = item.get("description") or item.get("area")
            if area:
                result.append(str(area))
        elif item:
            result.append(str(item))

    return result[:limit]


def recommend_next_mission(
    goal: Optional[str],
    preferred_mode: Optional[str],
    due_count: int,
    error_patterns: list[dict[str, Any]],
    has_assessment: bool,
) -> dict[str, str]:
    goal_lower = (goal or "").lower()
    preferred_mode = preferred_mode or "free_conversation"

    if not has_assessment:
        return {
            "mode": "assessment",
            "title": "Take your baseline assessment",
            "reason": "You need a starting level before the coach can route practice well.",
        }

    if due_count >= 5:
        return {
            "mode": "vocabulary_drill",
            "title": "Clear your review queue",
            "reason": f"You have {due_count} vocabulary cards due right now.",
        }

    if "interview" in goal_lower or preferred_mode == "mock_interview":
        return {
            "mode": "mock_interview",
            "title": "Run one interview mission",
            "reason": "Your current goal is career-oriented, so interview fluency is the fastest path to value.",
        }

    if error_patterns:
        return {
            "mode": "free_conversation",
            "title": "Do a grammar rescue session",
            "reason": f"Your most frequent issue right now is {error_patterns[0]['label']}.",
        }

    return {
        "mode": preferred_mode,
        "title": "Do a focused speaking session",
        "reason": "You are ready for another guided practice session.",
    }


class ProgramSnapshotService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.learning_plan_service = LearningPlanService(db)
        self.vocabulary_service = VocabularyService(db)
        self.xp_service = XPService(db)
        self.streak_service = StreakService(db)

    async def get_snapshot(self, user_id: int) -> Optional[dict[str, Any]]:
        user = await self.db.get(User, user_id)
        if not user:
            return None

        plan = await self.learning_plan_service.get_or_create_plan(user_id)
        roadmap = plan.roadmap or {}
        interview_runs = roadmap.get("interview_runs") or []

        vocabulary_stats = await self.vocabulary_service.get_vocabulary_stats(user_id)
        due_cards = await self.vocabulary_service.get_due_cards(user_id, limit=5)
        xp_info = await self.xp_service.get_level_info(user_id)
        streak_info = await self.streak_service.get_streak_info(user_id)
        error_patterns = await self._get_top_error_patterns(user_id)
        recent_sessions = await self._get_recent_sessions(user_id)
        total_sessions = await self._get_total_sessions(user_id)
        latest_assessment = build_latest_assessment(roadmap)
        preferred_mode = self.learning_plan_service.get_preferred_mode(plan)
        goal = self.learning_plan_service.get_goal(plan)
        interview_summary = build_interview_summary(interview_runs, goal=goal)
        mission = recommend_next_mission(
            goal=goal,
            preferred_mode=preferred_mode,
            due_count=vocabulary_stats["due_now"],
            error_patterns=error_patterns,
            has_assessment=latest_assessment is not None,
        )

        if mission["mode"] == "mock_interview":
            recommended_track = interview_summary["recommended_track"]
            mission = {
                "mode": "mock_interview",
                "title": f"Run {recommended_track['title']}",
                "reason": (
                    "Career-focused practice is your highest-leverage next step right now."
                    if interview_summary["completed_runs"] == 0
                    else f"Your next best drill is {recommended_track['title'].lower()} to keep interview readiness moving."
                ),
            }

        return {
            "user": {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "language_level": user.language_level,
            },
            "goal": {
                "text": goal,
                "preferred_mode": preferred_mode,
                "target_level": plan.level_target,
                "focus_areas": extract_focus_areas(roadmap),
            },
            "assessment": latest_assessment,
            "mission": mission,
            "gamification": {
                "xp": xp_info,
                "streak": streak_info,
            },
            "interview": interview_summary,
            "vocabulary": {
                "stats": vocabulary_stats,
                "due_preview": [
                    {
                        "id": card.id,
                        "word": card.word,
                        "translation": card.translation,
                        "example_sentence": card.example_sentence,
                        "due_at": card.due_at,
                        "state": card.fsrs_state,
                    }
                    for card in due_cards
                ],
            },
            "progress": {
                "sessions_completed": max(total_sessions, self.learning_plan_service.get_session_count(plan)),
                "milestones": roadmap.get("milestones") or [],
                "recommended_vocabulary": self.learning_plan_service.get_recommended_vocabulary(plan)[:8],
                "top_error_patterns": error_patterns,
                "recent_sessions": recent_sessions,
            },
        }

    async def _get_total_sessions(self, user_id: int) -> int:
        result = await self.db.execute(
            select(func.count(Session.id)).where(Session.user_id == user_id)
        )
        return int(result.scalar() or 0)

    async def _get_top_error_patterns(self, user_id: int, limit: int = 5) -> list[dict[str, Any]]:
        stmt = (
            select(Correction.rule_tag, func.count(Correction.id).label("count"))
            .join(Session, Correction.session_id == Session.id)
            .where(Session.user_id == user_id)
            .where(Correction.rule_tag.is_not(None))
            .group_by(Correction.rule_tag)
            .order_by(func.count(Correction.id).desc(), Correction.rule_tag.asc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        if rows:
            return [
                {"label": str(row.rule_tag).replace("_", " "), "count": int(row.count)}
                for row in rows
                if row.rule_tag
            ]

        fallback_stmt = (
            select(Correction.explanation_md)
            .join(Session, Correction.session_id == Session.id)
            .where(Session.user_id == user_id)
            .order_by(Session.started_at.desc())
            .limit(30)
        )
        fallback_result = await self.db.execute(fallback_stmt)
        counter = Counter()
        for explanation in fallback_result.scalars().all():
            if not explanation:
                continue
            first_line = explanation.splitlines()[0].strip()
            if first_line:
                counter[first_line[:80]] += 1

        return [
            {"label": label, "count": count}
            for label, count in counter.most_common(limit)
        ]

    async def _get_recent_sessions(self, user_id: int, limit: int = 3) -> list[dict[str, Any]]:
        stmt = (
            select(Session)
            .options(selectinload(Session.feedback), selectinload(Session.corrections))
            .where(Session.user_id == user_id)
            .order_by(Session.started_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        sessions = list(result.scalars().all())

        feedback_stmt = (
            select(Feedback)
            .join(Session, Feedback.session_id == Session.id)
            .where(Session.user_id == user_id)
            .order_by(Session.started_at.desc())
            .limit(limit)
        )
        feedback_result = await self.db.execute(feedback_stmt)
        feedback_by_session = {feedback.session_id: feedback for feedback in feedback_result.scalars().all()}

        items: list[dict[str, Any]] = []
        for session in sessions:
            feedback = feedback_by_session.get(session.id)
            duration_minutes = None
            if session.ended_at:
                duration_minutes = max(
                    1,
                    int((session.ended_at - session.started_at).total_seconds() // 60 or 1),
                )

            items.append(
                {
                    "id": session.id,
                    "started_at": session.started_at,
                    "ended_at": session.ended_at,
                    "duration_minutes": duration_minutes,
                    "corrections_count": len(session.corrections or []),
                    "summary": feedback.summary_md if feedback and feedback.summary_md else None,
                }
            )

        return items
