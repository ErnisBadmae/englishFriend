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
from app.services.pronunciation_assessment_service import build_pronunciation_summary

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
        "task_type": "hr_intro_drill",
        "expected_outcome": "One tighter STAR-style answer you can reuse in future interviews.",
        "estimated_minutes": 10,
        "success_signal": "Your answer has a clear situation, action, and result.",
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
        "task_type": "vocabulary_reinforcement",
        "expected_outcome": "Stronger recall of role-specific terms in live speaking.",
        "estimated_minutes": 8,
        "success_signal": "You can use at least 3 due words in full answers without hesitation.",
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
        "task_type": "grammar_rescue",
        "expected_outcome": "Cleaner sentence control in high-value career answers.",
        "estimated_minutes": 9,
        "success_signal": "The same grammar issue appears less often in your next answer.",
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
        "task_type": "workplace_update_drill",
        "expected_outcome": "A shorter, more decisive workplace-style update.",
        "estimated_minutes": 8,
        "success_signal": "You can explain done / next / blocked without trailing off.",
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
        "task_type": "project_walkthrough_drill",
        "expected_outcome": "One clearer project explanation with trade-offs and impact.",
        "estimated_minutes": 10,
        "success_signal": "You can explain the project in one clean flow without drifting.",
    },
}


def _mission_payload(
    *,
    mode: str,
    launch_mode: Optional[str],
    title: str,
    reason: str,
    why_now: str,
    linked_goal_context: Optional[str],
    linked_skill_gap: Optional[str],
    task_type: str,
    expected_outcome: str,
    estimated_minutes: int,
    success_signal: str,
    from_interview: bool = False,
    interview_track_id: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "launch_mode": launch_mode,
        "title": title,
        "reason": reason,
        "why_now": why_now,
        "linked_goal_context": linked_goal_context,
        "linked_skill_gap": linked_skill_gap,
        "from_interview": from_interview,
        "interview_track_id": interview_track_id,
        "task_type": task_type,
        "expected_outcome": expected_outcome,
        "estimated_minutes": estimated_minutes,
        "success_signal": success_signal,
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
            "status": profile.get("status") or ("provisional" if profile.get("provisional") else "confirmed"),
            "provisional": bool(profile.get("provisional")),
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
            "status": "confirmed",
            "provisional": False,
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


def build_setup_state(goal_status: Optional[str], assessment_complete: bool) -> str:
    if goal_status not in {"draft", "confirmed"}:
        return "needs_goal"
    if not assessment_complete:
        return "needs_assessment"
    return "ready_for_program"


def build_setup_progress(goal_brief: Optional[dict[str, Any]], assessment: Optional[dict[str, Any]]) -> int:
    filled_slots = 0
    total_slots = 7
    goal_brief = goal_brief or {}
    for key in ("primary_goal", "target_role", "domain", "target_market", "deadline_type"):
        if goal_brief.get(key):
            filled_slots += 1
    if goal_brief.get("main_contexts"):
        filled_slots += 1
    if assessment:
        filled_slots += 1
    return int(round((filled_slots / total_slots) * 100))


def build_next_question_type(goal_status: Optional[str], assessment: Optional[dict[str, Any]]) -> str:
    if goal_status not in {"draft", "confirmed"}:
        return "goal_setup"
    if not assessment:
        return "baseline"
    return "mission"


def build_improvement_signals(
    interview_summary: dict[str, Any],
    pronunciation_summary: dict[str, Any],
    session_evidence: list[dict[str, Any]],
    latest_assessment: Optional[dict[str, Any]],
    milestones: list[dict[str, Any]],
) -> list[str]:
    signals: list[str] = []

    latest_run = interview_summary.get("latest_run")
    if isinstance(latest_run, dict) and latest_run.get("delta_vs_previous") not in (None, 0):
        delta = float(latest_run["delta_vs_previous"])
        direction = "up" if delta > 0 else "down"
        signals.append(f"Interview score moved {direction} {abs(delta):.1f} vs the previous run.")

    if pronunciation_summary.get("latest_score") is not None:
        latest_score = float(pronunciation_summary["latest_score"])
        focus = (pronunciation_summary.get("focus") or [])
        if focus:
            signals.append(f"Speech signal is {latest_score:.1f}/10; current pronunciation focus: {focus[0]}.")
        else:
            signals.append(f"Speech signal is {latest_score:.1f}/10 from recent spoken answers.")

    latest_evidence = session_evidence[0] if session_evidence else None
    if isinstance(latest_evidence, dict):
        main_issue = latest_evidence.get("main_issue")
        if main_issue:
            signals.append(f"Latest mission surfaced one repeatable issue: {main_issue}.")
        elif latest_evidence.get("summary"):
            signals.append(str(latest_evidence["summary"]))

    completed_milestones = [
        str(item.get("name"))
        for item in milestones
        if isinstance(item, dict) and item.get("done") and item.get("name")
    ]
    if completed_milestones:
        signals.append(f"Completed milestone: {completed_milestones[-1]}.")

    if latest_assessment and latest_assessment.get("goal_readiness") is not None:
        signals.append(f"Current goal readiness sits at {float(latest_assessment['goal_readiness']):.1f}/10.")

    return signals[:4]


def recommend_next_mission(
    goal_brief: Optional[dict[str, Any]],
    program_plan: Optional[dict[str, Any]],
    due_count: int,
    error_patterns: list[dict[str, Any]],
    has_assessment: bool,
    weakest_interview_area: Optional[str] = None,
    interview_pack: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    if not goal_brief or goal_brief.get("status") not in {"draft", "confirmed"}:
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
        return _mission_payload(
            mode="guided_setup",
            launch_mode=None,
            title="Complete your goal setup",
            reason="Turn your goal into a clear career-English target.",
            why_now=why_now,
            linked_goal_context="goal_setup",
            linked_skill_gap=None,
            task_type="goal_setup",
            expected_outcome="A confirmed goal brief with role, context, and timeline.",
            estimated_minutes=4,
            success_signal="Your target role, company context, and practice situations are locked in.",
        )

    if not has_assessment:
        return _mission_payload(
            mode="assessment",
            launch_mode="assessment",
            title="Take your baseline assessment",
            reason="You need a measured starting point before the coach can route practice well.",
            why_now="Without a baseline, the program cannot know whether to focus on fluency, grammar, or career scenarios first.",
            linked_goal_context="baseline",
            linked_skill_gap=None,
            task_type="baseline_assessment",
            expected_outcome="A clear starting level and the first program stage.",
            estimated_minutes=8,
            success_signal="You finish with a CEFR estimate and a first mission tied to your goal.",
        )

    if weakest_interview_area and weakest_interview_area in _WEAKEST_AREA_MISSIONS:
        return dict(_WEAKEST_AREA_MISSIONS[weakest_interview_area])

    current_stage = (program_plan or {}).get("current_stage")
    weekly_focus = (program_plan or {}).get("weekly_focus") or []
    if (
        interview_pack
        and current_stage in {"career_scenarios", "target_role_simulation"}
        and interview_pack.get("recommended_track")
    ):
        track_id = str(interview_pack.get("recommended_track"))
        track_title = str(interview_pack.get("recommended_track_title") or "Career Mission")
        blockers = interview_pack.get("top_blockers") or []
        mission_title = f"Run {track_title}"
        reason = str(
            interview_pack.get("summary")
            or (weekly_focus[0] if weekly_focus else "Practice the most likely interview theme for your target role.")
        )
        why_now = "This is the most interview-relevant speaking drill for your current target role and vacancy context."
        linked_goal_context = {
            "hr_intro": "interviews",
            "project_walkthrough": "project_walkthrough",
            "workplace_communication": "workplace_communication",
        }.get(track_id, "interviews")
        success_signal = "You finish with one answer strong enough to reuse in a real interview."
        if blockers:
            why_now = f"Main blocker right now: {blockers[0]}"
        if track_id == "project_walkthrough":
            success_signal = "You can explain one project with problem, trade-offs, metric, and impact."
        elif track_id == "workplace_communication":
            success_signal = "You can deliver a clear done / next / blocked update without drifting."
        return _mission_payload(
            mode="mock_interview",
            launch_mode="mock_interview",
            title=mission_title,
            reason=reason,
            why_now=why_now,
            linked_goal_context=linked_goal_context,
            linked_skill_gap=None,
            task_type={
                "hr_intro": "hr_intro_drill",
                "project_walkthrough": "project_walkthrough_drill",
                "workplace_communication": "workplace_update_drill",
            }.get(track_id, "career_mission"),
            expected_outcome="One stronger answer for the most likely interview scenario.",
            estimated_minutes=10,
            success_signal=success_signal,
            interview_track_id=track_id,
        )

    if due_count >= 5:
        return _mission_payload(
            mode="vocabulary_drill",
            launch_mode="vocabulary_drill",
            title="Clear your review queue",
            reason=f"You have {due_count} vocabulary cards due right now.",
            why_now="Keeping recall fresh prevents new practice from collapsing under forgotten vocabulary.",
            linked_goal_context="vocabulary",
            linked_skill_gap="professional_vocabulary",
            task_type="vocabulary_reinforcement",
            expected_outcome=f"At least {min(5, due_count)} due words reinforced in context.",
            estimated_minutes=7,
            success_signal="Your due queue shrinks and the same words feel easier in live speaking.",
        )

    if current_stage == "foundation":
        return _mission_payload(
            mode="free_conversation",
            launch_mode="free_conversation",
            title="Run a foundation speaking drill",
            reason=weekly_focus[0] if weekly_focus else "Stabilize grammar and fluency before higher-pressure scenarios.",
            why_now="Your baseline says the fastest path forward is cleaner spoken English under low pressure.",
            linked_goal_context="foundation",
            linked_skill_gap="grammar_accuracy" if error_patterns else "fluency",
            task_type="foundation_speaking_drill",
            expected_outcome="One cleaner career-related answer with fewer avoidable slips.",
            estimated_minutes=9,
            success_signal="You can answer in English with fewer corrections and clearer delivery.",
        )

    if current_stage in {"career_scenarios", "target_role_simulation"}:
        return _mission_payload(
            mode="mock_interview",
            launch_mode="mock_interview",
            title="Run one career mission",
            reason=weekly_focus[0] if weekly_focus else "Career-focused speaking is your highest-leverage next step.",
            why_now="The current stage of the program is about practicing real work and interview situations, not generic chatting.",
            linked_goal_context=(goal_brief.get("main_contexts") or ["interviews"])[0],
            linked_skill_gap=weakest_interview_area,
            task_type="career_mission",
            expected_outcome="One realistic career scenario completed with score and next focus.",
            estimated_minutes=10,
            success_signal="You finish one track with concrete feedback and a clearer next step.",
        )

    if error_patterns:
        return _mission_payload(
            mode="free_conversation",
            launch_mode="free_conversation",
            title="Do a grammar rescue session",
            reason=f"Your most frequent issue right now is {error_patterns[0]['label']}.",
            why_now="Cleaning up the most common error gives immediate lift across all future speaking tasks.",
            linked_goal_context="grammar",
            linked_skill_gap=error_patterns[0]["label"],
            task_type="grammar_rescue",
            expected_outcome="Fewer repeats of the most common spoken error.",
            estimated_minutes=8,
            success_signal="That same grammar issue appears less often in the next mission.",
        )

    return _mission_payload(
        mode=(program_plan or {}).get("preferred_mode") or "free_conversation",
        launch_mode=(program_plan or {}).get("preferred_mode") or "free_conversation",
        title="Do a focused speaking session",
        reason=weekly_focus[0] if weekly_focus else "You are ready for another guided practice session.",
        why_now="This keeps momentum on the current stage of your program.",
        linked_goal_context=(goal_brief.get("main_contexts") or ["general_fluency"])[0],
        linked_skill_gap=None,
        task_type="guided_speaking_session",
        expected_outcome="One useful practice repetition tied to your current stage.",
        estimated_minutes=8,
        success_signal="You finish with one clearer improvement target for the next session.",
    )


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
        career_context = self.learning_plan_service.get_career_context(plan)
        interview_pack = self.learning_plan_service.get_interview_pack(plan)
        interview_runs = roadmap.get("interview_runs") or []

        vocabulary_stats = await self.vocabulary_service.get_vocabulary_stats(user_id)
        due_cards = await self.vocabulary_service.get_due_cards(user_id, limit=5)
        xp_info = await self.xp_service.get_level_info(user_id)
        streak_info = await self.streak_service.get_streak_info(user_id)
        error_patterns = await self._get_top_error_patterns(user_id)
        recent_sessions = await self._get_recent_sessions(user_id)
        total_sessions = await self._get_total_sessions(user_id)
        session_evidence = self.learning_plan_service.get_session_evidence(plan)

        latest_assessment = build_latest_assessment(roadmap)
        goal = self.learning_plan_service.get_goal(plan)
        weakest_interview_area = roadmap.get("weakest_interview_area")
        interview_summary = build_interview_summary(interview_runs, goal=goal)
        interview_summary["weakest_area"] = weakest_interview_area
        interview_summary["interview_focus"] = roadmap.get("interview_focus") or []
        interview_summary["last_track"] = roadmap.get("last_interview_track")
        pronunciation_summary = build_pronunciation_summary(roadmap.get("pronunciation_assessments") or [])

        mission = recommend_next_mission(
            goal_brief=goal_brief,
            program_plan=program_plan,
            due_count=vocabulary_stats["due_now"],
            error_patterns=error_patterns,
            has_assessment=latest_assessment is not None,
            weakest_interview_area=weakest_interview_area,
            interview_pack=interview_pack,
        )
        if mission["mode"] == "mock_interview" and not mission.get("from_interview"):
            recommended_track = interview_summary["recommended_track"]
            mission["title"] = f"Run {recommended_track['title']}"
            mission["reason"] = recommended_track["subtitle"]
            mission["interview_track_id"] = recommended_track["id"]
            mission["task_type"] = {
                "hr_intro": "hr_intro_drill",
                "project_walkthrough": "project_walkthrough_drill",
                "workplace_communication": "workplace_update_drill",
            }.get(recommended_track["id"], "career_mission")

        goal_status = (goal_brief or {}).get("status")
        goal_complete = self.learning_plan_service.is_goal_setup_complete(plan)
        assessment_complete = latest_assessment is not None
        setup_state = build_setup_state(goal_status, assessment_complete)
        setup_progress = build_setup_progress(goal_brief, latest_assessment)
        next_question_type = build_next_question_type(goal_status, latest_assessment)
        latest_paid_intent = roadmap.get("latest_paid_intent")
        show_paid_cta = bool(
            assessment_complete
            and interview_pack
            and not latest_paid_intent
            and (interview_summary.get("completed_runs", 0) >= 1 or len(session_evidence) >= 2)
        )

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
                "draft_available": bool(goal_brief and goal_brief.get("status") in {"draft", "confirmed"}),
            },
            "assessment": latest_assessment,
            "program": program_plan,
            "career_context": career_context,
            "interview_pack": interview_pack,
            "mission": mission,
            "gamification": {"xp": xp_info, "streak": streak_info},
            "interview": interview_summary,
            "pronunciation": pronunciation_summary,
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
                "improvement_signals": build_improvement_signals(
                    interview_summary=interview_summary,
                    pronunciation_summary=pronunciation_summary,
                    session_evidence=session_evidence,
                    latest_assessment=latest_assessment,
                    milestones=roadmap.get("milestones") or [],
                ),
            },
            "session_evidence": {
                "latest": session_evidence[0] if session_evidence else None,
                "recent": session_evidence[:5],
            },
            "setup": {
                "goal_complete": goal_complete,
                "assessment_complete": assessment_complete,
                "needs_attention": setup_state != "ready_for_program",
                "state": setup_state,
                "next_question_type": next_question_type,
                "progress": setup_progress,
            },
            "monetization": {
                "show_paid_cta": show_paid_cta,
                "paid_intent_submitted": latest_paid_intent is not None,
                "latest_paid_intent_at": latest_paid_intent.get("submitted_at") if isinstance(latest_paid_intent, dict) else None,
                "latest_paid_intent_context": latest_paid_intent.get("source") if isinstance(latest_paid_intent, dict) else None,
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
