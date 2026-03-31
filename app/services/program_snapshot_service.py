from __future__ import annotations

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

_WEAKEST_AREA_MISSIONS: dict[str, dict[str, Any]] = {
    "structure": {
        "mode": "mock_interview",
        "launch_mode": "mock_interview",
        "title": "Run a STAR structure drill",
        "reason": "Structure was the weakest area in your latest interview run.",
        "why_now": "Cleaner structure makes every future interview answer easier to follow and easier to trust.",
        "linked_goal_context": "interviews",
        "linked_skill_gap": "structure",
        "interview_track_id": "hr_intro",
        "from_interview": True,
    },
    "vocabulary": {
        "mode": "vocabulary_drill",
        "launch_mode": "vocabulary_drill",
        "title": "Reinforce interview vocabulary",
        "reason": "Vocabulary was the weakest area in your latest interview run.",
        "why_now": "Tightening vocabulary now makes the next interview run noticeably easier.",
        "linked_goal_context": "interviews",
        "linked_skill_gap": "professional_vocabulary",
        "interview_track_id": None,
        "from_interview": True,
    },
    "accuracy": {
        "mode": "free_conversation",
        "launch_mode": "free_conversation",
        "title": "Run a grammar rescue drill",
        "reason": "Accuracy was the weakest area in your latest interview run.",
        "why_now": "Cleaning up grammar now raises credibility across interviews and workplace communication.",
        "linked_goal_context": "grammar",
        "linked_skill_gap": "grammar_accuracy",
        "interview_track_id": None,
        "from_interview": True,
    },
    "confidence": {
        "mode": "mock_interview",
        "launch_mode": "mock_interview",
        "title": "Build confidence with a workplace run",
        "reason": "Confidence was the weakest area in your latest interview run.",
        "why_now": "A shorter workplace-style run lowers pressure while training decisive speaking.",
        "linked_goal_context": "workplace_communication",
        "linked_skill_gap": "confidence",
        "interview_track_id": "workplace_communication",
        "from_interview": True,
    },
    "clarity": {
        "mode": "mock_interview",
        "launch_mode": "mock_interview",
        "title": "Practice clearer project explanations",
        "reason": "Clarity was the weakest area in your latest interview run.",
        "why_now": "Sharper project explanations transfer directly to interviews and real work conversations.",
        "linked_goal_context": "project_walkthrough",
        "linked_skill_gap": "clarity",
        "interview_track_id": "project_walkthrough",
        "from_interview": True,
    },
}


def build_latest_assessment(roadmap: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not roadmap:
        return None

    profile = roadmap.get("proficiency_profile") or {}
    if profile:
        return {
            "date": roadmap.get("last_assessment"),
            "level": profile.get("cefr_level"),
            "scores": {
                "fluency": profile.get("fluency"),
                "grammar": profile.get("grammar_accuracy"),
                "vocabulary": profile.get("professional_vocabulary"),
                "comprehension": profile.get("listening_comprehension"),
            },
            "notes": profile.get("notes"),
            "confidence": profile.get("confidence"),
            "goal_readiness": profile.get("goal_readiness"),
            "critical_gaps": profile.get("critical_gaps") or [],
            "skill_axes": {
                "fluency": profile.get("fluency"),
                "grammar_accuracy": profile.get("grammar_accuracy"),
                "listening_comprehension": profile.get("listening_comprehension"),
                "professional_vocabulary": profile.get("professional_vocabulary"),
            },
        }

    history = roadmap.get("assessment_history") or []
    if history:
        latest = history[-1]
        return {
            "date": latest.get("date"),
            "level": latest.get("level"),
            "scores": latest.get("scores") or {},
            "notes": latest.get("notes"),
            "confidence": None,
            "goal_readiness": None,
            "critical_gaps": [],
            "skill_axes": {},
        }
    return None


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
    goal_brief: Optional[dict[str, Any]],
    program_plan: Optional[dict[str, Any]],
    due_count: int,
    error_patterns: list[dict[str, Any]],
    has_assessment: bool,
    weakest_interview_area: Optional[str] = None,
) -> dict[str, Any]:
    if not goal_brief or goal_brief.get("status") != "confirmed":
        missing = []
        if goal_brief:
            if not goal_brief.get("target_role"):
                missing.append("target role")
            if not goal_brief.get("domain"):
                missing.append("domain")
            if not goal_brief.get("target_market"):
                missing.append("company context")
            if not goal_brief.get("deadline_type"):
                missing.append("timeline")
            if not goal_brief.get("main_contexts"):
                missing.append("practice context")
        why_now = "The coach still needs a concrete role and context before it can build a useful program."
        if missing:
            why_now = f"Missing: {', '.join(missing)}."
        return {
            "mode": "guided_setup",
            "launch_mode": None,
            "title": "Complete your goal setup",
            "reason": "Turn your goal into a clear career-English target.",
            "why_now": why_now,
            "linked_goal_context": "goal_setup",
            "linked_skill_gap": None,
            "from_interview": False,
            "interview_track_id": None,
        }

    if not has_assessment:
        return {
            "mode": "assessment",
            "launch_mode": "assessment",
            "title": "Take your baseline assessment",
            "reason": "You need a measured starting point before the coach can route practice well.",
            "why_now": "Without a baseline, the program cannot know whether to focus on fluency, grammar, or career scenarios first.",
            "linked_goal_context": "baseline",
            "linked_skill_gap": None,
            "from_interview": False,
            "interview_track_id": None,
        }

    if weakest_interview_area and weakest_interview_area in _WEAKEST_AREA_MISSIONS:
        return dict(_WEAKEST_AREA_MISSIONS[weakest_interview_area])

    if due_count >= 5:
        return {
            "mode": "vocabulary_drill",
            "launch_mode": "vocabulary_drill",
            "title": "Clear your review queue",
            "reason": f"You have {due_count} vocabulary cards due right now.",
            "why_now": "Keeping recall fresh prevents new practice from collapsing under forgotten vocabulary.",
            "linked_goal_context": "vocabulary",
            "linked_skill_gap": "professional_vocabulary",
            "from_interview": False,
            "interview_track_id": None,
        }

    current_stage = (program_plan or {}).get("current_stage")
    weekly_focus = (program_plan or {}).get("weekly_focus") or []
    if current_stage == "foundation":
        return {
            "mode": "free_conversation",
            "launch_mode": "free_conversation",
            "title": "Run a foundation speaking drill",
            "reason": weekly_focus[0] if weekly_focus else "Stabilize grammar and fluency before higher-pressure scenarios.",
            "why_now": "Your baseline says the fastest path forward is cleaner spoken English under low pressure.",
            "linked_goal_context": "foundation",
            "linked_skill_gap": "grammar_accuracy" if error_patterns else "fluency",
            "from_interview": False,
            "interview_track_id": None,
        }

    if current_stage in {"career_scenarios", "target_role_simulation"}:
        return {
            "mode": "mock_interview",
            "launch_mode": "mock_interview",
            "title": "Run one career mission",
            "reason": weekly_focus[0] if weekly_focus else "Career-focused speaking is your highest-leverage next step.",
            "why_now": "The current stage of the program is about practicing real work and interview situations, not generic chatting.",
            "linked_goal_context": (goal_brief.get("main_contexts") or ["interviews"])[0],
            "linked_skill_gap": weakest_interview_area,
            "from_interview": False,
            "interview_track_id": None,
        }

    if error_patterns:
        return {
            "mode": "free_conversation",
            "launch_mode": "free_conversation",
            "title": "Do a grammar rescue session",
            "reason": f"Your most frequent issue right now is {error_patterns[0]['label']}.",
            "why_now": "Cleaning up the most common error gives immediate lift across all future speaking tasks.",
            "linked_goal_context": "grammar",
            "linked_skill_gap": error_patterns[0]["label"],
            "from_interview": False,
            "interview_track_id": None,
        }

    return {
        "mode": (program_plan or {}).get("preferred_mode") or "free_conversation",
        "launch_mode": (program_plan or {}).get("preferred_mode") or "free_conversation",
        "title": "Do a focused speaking session",
        "reason": weekly_focus[0] if weekly_focus else "You are ready for another guided practice session.",
        "why_now": "This keeps momentum on the current stage of your program.",
        "linked_goal_context": (goal_brief.get("main_contexts") or ["general_fluency"])[0],
        "linked_skill_gap": None,
        "from_interview": False,
        "interview_track_id": None,
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
        goal_brief = self.learning_plan_service.get_goal_brief(plan)
        program_plan = self.learning_plan_service.get_program_plan(plan)
        interview_runs = roadmap.get("interview_runs") or []

        vocabulary_stats = await self.vocabulary_service.get_vocabulary_stats(user_id)
        due_cards = await self.vocabulary_service.get_due_cards(user_id, limit=5)
        xp_info = await self.xp_service.get_level_info(user_id)
        streak_info = await self.streak_service.get_streak_info(user_id)
        error_patterns = await self._get_top_error_patterns(user_id)
        recent_sessions = await self._get_recent_sessions(user_id)
        total_sessions = await self._get_total_sessions(user_id)

        latest_assessment = build_latest_assessment(roadmap)
        goal = self.learning_plan_service.get_goal(plan)
        weakest_interview_area = roadmap.get("weakest_interview_area")
        interview_summary = build_interview_summary(interview_runs, goal=goal)
        interview_summary["weakest_area"] = weakest_interview_area
        interview_summary["interview_focus"] = roadmap.get("interview_focus") or []
        interview_summary["last_track"] = roadmap.get("last_interview_track")

        mission = recommend_next_mission(
            goal_brief=goal_brief,
            program_plan=program_plan,
            due_count=vocabulary_stats["due_now"],
            error_patterns=error_patterns,
            has_assessment=latest_assessment is not None,
            weakest_interview_area=weakest_interview_area,
        )
        if mission["mode"] == "mock_interview" and not mission.get("from_interview"):
            recommended_track = interview_summary["recommended_track"]
            mission["title"] = f"Run {recommended_track['title']}"
            mission["reason"] = recommended_track["subtitle"]
            mission["interview_track_id"] = recommended_track["id"]

        return {
            "user": {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "language_level": self.learning_plan_service.get_current_level(plan) or user.language_level,
            },
            "goal": {
                "text": goal,
                "preferred_mode": self.learning_plan_service.get_preferred_mode(plan),
                "target_level": plan.level_target,
                "focus_areas": extract_focus_areas(roadmap),
                "brief": goal_brief,
                "missing_fields": self.learning_plan_service.get_goal_setup_missing(plan),
            },
            "assessment": latest_assessment,
            "program": program_plan,
            "mission": mission,
            "gamification": {"xp": xp_info, "streak": streak_info},
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
            "setup": {
                "goal_complete": self.learning_plan_service.is_goal_setup_complete(plan),
                "assessment_complete": latest_assessment is not None,
                "needs_attention": not self.learning_plan_service.is_goal_setup_complete(plan) or latest_assessment is None,
            },
        }

    async def _get_total_sessions(self, user_id: int) -> int:
        result = await self.db.execute(select(func.count(Session.id)).where(Session.user_id == user_id))
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
        return [
            {"label": str(row.rule_tag).replace("_", " "), "count": int(row.count)}
            for row in result.all()
            if row.rule_tag
        ]

    async def _get_recent_sessions(self, user_id: int, limit: int = 5) -> list[dict[str, Any]]:
        stmt = (
            select(Session)
            .options(selectinload(Session.corrections), selectinload(Session.feedback))
            .where(Session.user_id == user_id)
            .order_by(Session.started_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        sessions = result.scalars().all()
        response: list[dict[str, Any]] = []
        for session in sessions:
            feedback_items = [item.content for item in (session.feedback or []) if getattr(item, "content", None)]
            summary = feedback_items[0] if feedback_items else None
            response.append(
                {
                    "id": str(session.id),
                    "started_at": session.started_at,
                    "ended_at": session.ended_at,
                    "duration_minutes": session.duration_minutes,
                    "corrections_count": len(session.corrections or []),
                    "summary": summary,
                }
            )
        return response
