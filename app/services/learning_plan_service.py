from __future__ import annotations

import logging
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.enums_and_dimensions import CEFRLevel
from app.models.extended_tables import LearningPlan

logger = logging.getLogger(__name__)


@dataclass
class GoalTemplate:
    goal: str
    focus_areas: list[dict[str, str]]
    milestones: list[dict[str, Any]]
    preferred_mode: str
    recommended_vocabulary: list[str]


GOAL_TEMPLATES = {
    "ml_interview": GoalTemplate(
        goal="ML/Data Science Interview Preparation",
        focus_areas=[
            {"area": "technical_vocabulary", "description": "ML terms and concepts"},
            {"area": "behavioral_questions", "description": "STAR method answers"},
            {"area": "explain_concepts", "description": "Explaining projects and decisions"},
            {"area": "project_walkthrough", "description": "Describing your work clearly"},
        ],
        milestones=[
            {"name": "Complete assessment", "type": "assessment", "done": False},
            {"name": "Master 50 ML terms", "type": "vocabulary", "target": 50, "progress": 0},
            {"name": "Complete 5 mock interviews", "type": "mock_interview", "target": 5, "count": 0},
        ],
        preferred_mode="mock_interview",
        recommended_vocabulary=[
            "deployment", "inference", "feature engineering", "overfitting", "pipeline",
            "scalability", "optimization", "architecture", "algorithm", "dataset",
        ],
    ),
    "software_interview": GoalTemplate(
        goal="Software Engineering Interview Preparation",
        focus_areas=[
            {"area": "technical_discussion", "description": "System design and trade-offs"},
            {"area": "behavioral_questions", "description": "Team collaboration stories"},
            {"area": "code_explanation", "description": "Walking through your projects"},
            {"area": "workplace_communication", "description": "Standups, blockers, updates"},
        ],
        milestones=[
            {"name": "Complete assessment", "type": "assessment", "done": False},
            {"name": "Master 40 tech terms", "type": "vocabulary", "target": 40, "progress": 0},
            {"name": "Complete 5 mock interviews", "type": "mock_interview", "target": 5, "count": 0},
        ],
        preferred_mode="mock_interview",
        recommended_vocabulary=[
            "scalability", "architecture", "microservices", "deployment", "debugging",
            "refactoring", "optimization", "dependency", "integration", "asynchronous",
        ],
    ),
    "general_fluency": GoalTemplate(
        goal="General English Fluency",
        focus_areas=[
            {"area": "conversation", "description": "Natural speaking flow"},
            {"area": "vocabulary", "description": "Expanding word range"},
            {"area": "grammar", "description": "Common mistake correction"},
        ],
        milestones=[
            {"name": "Complete assessment", "type": "assessment", "done": False},
            {"name": "Learn 100 new words", "type": "vocabulary", "target": 100, "progress": 0},
            {"name": "Practice 10 hours", "type": "practice", "target": 600, "minutes": 0},
        ],
        preferred_mode="free_conversation",
        recommended_vocabulary=[],
    ),
}


_LEVEL_BASELINE = {"A1": 2.0, "A2": 3.5, "B1": 5.0, "B2": 6.8, "C1": 8.3, "C2": 9.2}
_GOAL_BRIEF_REQUIRED_FIELDS = {
    "primary_goal": "goal",
    "target_role": "target role",
    "domain": "domain",
    "target_market": "target company context",
    "deadline_type": "timeline",
    "main_contexts": "practice contexts",
}
_ROLE_KEYWORDS = {
    "ml engineer": ("ML Engineer", "machine_learning"),
    "machine learning": ("ML Engineer", "machine_learning"),
    "ai engineer": ("ML Engineer", "machine_learning"),
    "artificial intelligence": ("ML Engineer", "machine_learning"),
    "data scientist": ("Data Scientist", "data_science"),
    "data science": ("Data Scientist", "data_science"),
    "software engineer": ("Software Engineer", "software_engineering"),
    "backend engineer": ("Backend Engineer", "software_engineering"),
    "frontend engineer": ("Frontend Engineer", "software_engineering"),
    "developer": ("Software Engineer", "software_engineering"),
    "engineer": ("Software Engineer", "software_engineering"),
}
_VACANCY_KEY_TERMS = {
    "machine_learning": [
        "machine learning", "ml", "model", "feature engineering", "inference",
        "deployment", "experiment", "evaluation", "dataset", "llm",
        "deep learning", "training", "pipeline", "metric", "monitoring",
    ],
    "software_engineering": [
        "architecture", "microservices", "api", "backend", "frontend",
        "scalability", "latency", "reliability", "testing", "deployment",
        "debugging", "distributed systems", "cloud", "performance",
    ],
}
_TRACK_LABELS = {
    "hr_intro": "HR Interview",
    "project_walkthrough": "Project Walkthrough",
    "workplace_communication": "Workplace Communication",
}


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat()


def _round_score(value: float) -> float:
    return round(max(1.0, min(10.0, value)), 1)


def _normalize_score(value: Any, fallback: float) -> float:
    if value is None:
        return fallback
    try:
        score = float(value)
    except (TypeError, ValueError):
        return fallback
    if score <= 1.0:
        score *= 10.0
    return _round_score(score)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def _humanize_key(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return str(value).replace("_", " ").strip()


class LearningPlanService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_plan(self, user_id: int) -> LearningPlan:
        result = await self.db.execute(select(LearningPlan).where(LearningPlan.user_id == user_id))
        plan = result.scalar_one_or_none()
        if plan:
            return plan

        plan = LearningPlan(
            user_id=user_id,
            roadmap={
                "goal": None,
                "goal_brief": None,
                "focus_areas": [],
                "milestones": [],
                "preferred_mode": "free_conversation",
                "sessions_completed": 0,
                "total_practice_minutes": 0,
                "assessment_history": [],
                "proficiency_profile": None,
                "program_plan": self._build_program_plan(
                    None,
                    None,
                    [],
                    "free_conversation",
                ),
                "career_context": None,
                "interview_pack": None,
                "paid_intents": [],
                "latest_paid_intent": None,
            },
        )
        self.db.add(plan)
        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def set_goal(
        self,
        user_id: int,
        goal_text: str,
        target_level: Optional[str] = None,
        goal_brief: Optional[dict[str, Any]] = None,
    ) -> LearningPlan:
        plan = await self.get_or_create_plan(user_id)
        template = self._match_goal_template(goal_text)
        roadmap = deepcopy(plan.roadmap or {})
        merged_goal_brief = self._build_goal_brief(goal_text, template, roadmap.get("goal_brief"), goal_brief)

        roadmap.update(
            {
                "goal": goal_text,
                "goal_template": template.goal if template else "custom",
                "goal_brief": merged_goal_brief,
                "focus_areas": template.focus_areas if template else roadmap.get("focus_areas", []),
                "milestones": template.milestones if template and not roadmap.get("milestones") else roadmap.get("milestones", []),
                "preferred_mode": template.preferred_mode if template else roadmap.get("preferred_mode", "free_conversation"),
                "recommended_vocabulary": template.recommended_vocabulary if template else roadmap.get("recommended_vocabulary", []),
                "created_at": roadmap.get("created_at") or _utcnow_iso(),
            }
        )
        roadmap["program_plan"] = self._build_program_plan(
            merged_goal_brief,
            roadmap.get("proficiency_profile"),
            roadmap.get("focus_areas") or [],
            roadmap.get("preferred_mode") or "free_conversation",
        )
        roadmap["career_context"] = self._build_career_context(
            goal_brief=merged_goal_brief,
            existing=roadmap.get("career_context"),
            vacancy_text=roadmap.get("vacancy_text"),
            interview_date=(roadmap.get("career_context") or {}).get("interview_date"),
        )
        roadmap["interview_pack"] = self._build_interview_pack(
            goal_brief=merged_goal_brief,
            proficiency_profile=roadmap.get("proficiency_profile"),
            interview_runs=roadmap.get("interview_runs") or [],
            career_context=roadmap.get("career_context"),
            recommended_vocabulary=roadmap.get("recommended_vocabulary") or [],
        )

        plan.roadmap = dict(roadmap)
        flag_modified(plan, "roadmap")
        if target_level:
            try:
                plan.level_target = CEFRLevel(target_level)
            except ValueError:
                logger.warning("Ignoring unknown target level: %s", target_level)
        plan.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def record_assessment(
        self,
        user_id: int,
        assessed_level: str,
        scores: Optional[dict[str, Any]] = None,
        notes: Optional[str] = None,
        provisional: bool = False,
        confidence_override: Optional[float] = None,
    ) -> LearningPlan:
        plan = await self.get_or_create_plan(user_id)
        roadmap = deepcopy(plan.roadmap or {})
        history = roadmap.get("assessment_history", [])
        history.append({"date": _utcnow_iso(), "level": assessed_level, "scores": scores or {}, "notes": notes})
        roadmap["assessment_history"] = history
        roadmap["current_level"] = assessed_level
        roadmap["last_assessment"] = _utcnow_iso()

        goal_brief = roadmap.get("goal_brief") or self._build_goal_brief(
            roadmap.get("goal") or "Career English",
            self._match_goal_template(roadmap.get("goal") or ""),
        )
        roadmap["goal_brief"] = goal_brief
        roadmap["proficiency_profile"] = self._build_proficiency_profile(
            assessed_level,
            scores or {},
            goal_brief,
            notes,
            provisional=provisional,
            confidence_override=confidence_override,
        )
        roadmap["program_plan"] = self._build_program_plan(
            goal_brief,
            roadmap["proficiency_profile"],
            roadmap.get("focus_areas") or [],
            roadmap.get("preferred_mode") or "free_conversation",
        )
        roadmap["career_context"] = self._build_career_context(
            goal_brief=goal_brief,
            existing=roadmap.get("career_context"),
            vacancy_text=roadmap.get("vacancy_text"),
            interview_date=(roadmap.get("career_context") or {}).get("interview_date"),
        )
        roadmap["interview_pack"] = self._build_interview_pack(
            goal_brief=goal_brief,
            proficiency_profile=roadmap["proficiency_profile"],
            interview_runs=roadmap.get("interview_runs") or [],
            career_context=roadmap.get("career_context"),
            recommended_vocabulary=roadmap.get("recommended_vocabulary") or [],
        )
        self._update_milestone(roadmap, "assessment", done=True)

        plan.roadmap = dict(roadmap)
        flag_modified(plan, "roadmap")
        plan.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def increment_session_count(
        self,
        user_id: int,
        mode: str,
        duration_minutes: int = 0,
    ) -> LearningPlan:
        plan = await self.get_or_create_plan(user_id)
        roadmap = deepcopy(plan.roadmap or {})
        roadmap["sessions_completed"] = roadmap.get("sessions_completed", 0) + 1
        roadmap["total_practice_minutes"] = roadmap.get("total_practice_minutes", 0) + duration_minutes
        if mode == "mock_interview":
            self._update_milestone(roadmap, "mock_interview", increment=1)
        self._update_milestone(roadmap, "practice", minutes=roadmap.get("total_practice_minutes", 0))

        plan.roadmap = dict(roadmap)
        flag_modified(plan, "roadmap")
        plan.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def add_vocabulary_progress(self, user_id: int, words_learned: int) -> LearningPlan:
        plan = await self.get_or_create_plan(user_id)
        roadmap = deepcopy(plan.roadmap or {})
        self._update_milestone(roadmap, "vocabulary", increment=words_learned)
        plan.roadmap = dict(roadmap)
        flag_modified(plan, "roadmap")
        plan.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def set_vacancy_context(
        self,
        user_id: int,
        vacancy_text: str,
        interview_date: Optional[str] = None,
    ) -> LearningPlan:
        plan = await self.get_or_create_plan(user_id)
        roadmap = deepcopy(plan.roadmap or {})
        vacancy_text = vacancy_text.strip()
        analysis = self._analyze_vacancy_text(vacancy_text)

        goal_text = roadmap.get("goal") or analysis["goal_text"]
        template = self._match_goal_template(goal_text)
        goal_brief = self._build_goal_brief(
            goal_text,
            template,
            roadmap.get("goal_brief"),
            {
                "primary_goal": roadmap.get("goal") or analysis["goal_text"],
                "target_role": analysis.get("target_role"),
                "domain": analysis.get("domain"),
                "target_market": analysis.get("target_market") or "international_company",
                "deadline_type": (roadmap.get("goal_brief") or {}).get("deadline_type") or "open_ended",
                "main_contexts": analysis.get("main_contexts") or ["interviews"],
                "current_blockers": analysis.get("current_blockers") or [],
            },
        )

        existing_vocab = roadmap.get("recommended_vocabulary") or []
        merged_vocab = _dedupe([*existing_vocab, *analysis.get("key_terms", [])])[:12]
        roadmap.update(
            {
                "goal": goal_text,
                "goal_brief": goal_brief,
                "preferred_mode": "mock_interview",
                "recommended_vocabulary": merged_vocab,
                "vacancy_text": vacancy_text,
                "vacancy_updated_at": _utcnow_iso(),
            }
        )
        roadmap["career_context"] = self._build_career_context(
            goal_brief=goal_brief,
            existing=roadmap.get("career_context"),
            vacancy_text=vacancy_text,
            interview_date=interview_date,
            analysis=analysis,
        )
        roadmap["interview_pack"] = self._build_interview_pack(
            goal_brief=goal_brief,
            proficiency_profile=roadmap.get("proficiency_profile"),
            interview_runs=roadmap.get("interview_runs") or [],
            career_context=roadmap.get("career_context"),
            recommended_vocabulary=merged_vocab,
            vacancy_analysis=analysis,
        )
        roadmap["program_plan"] = self._build_program_plan(
            goal_brief,
            roadmap.get("proficiency_profile"),
            roadmap.get("focus_areas") or [],
            roadmap.get("preferred_mode") or "mock_interview",
        )

        plan.roadmap = dict(roadmap)
        flag_modified(plan, "roadmap")
        plan.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def record_paid_intent(
        self,
        user_id: int,
        source: str,
        note: Optional[str] = None,
    ) -> dict[str, Any]:
        plan = await self.get_or_create_plan(user_id)
        roadmap = deepcopy(plan.roadmap or {})
        profile = roadmap.get("proficiency_profile") or {}
        payload = {
            "submitted_at": _utcnow_iso(),
            "source": source,
            "note": note,
            "goal": roadmap.get("goal"),
            "readiness_score": profile.get("goal_readiness"),
            "sessions_completed": roadmap.get("sessions_completed", 0),
            "interview_runs_completed": len(roadmap.get("interview_runs") or []),
        }
        existing = [
            dict(item)
            for item in (roadmap.get("paid_intents") or [])
            if isinstance(item, dict)
        ]
        roadmap["paid_intents"] = [payload, *existing][:20]
        roadmap["latest_paid_intent"] = payload

        plan.roadmap = dict(roadmap)
        flag_modified(plan, "roadmap")
        plan.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(plan)
        return payload

    async def record_session_evidence(
        self,
        *,
        user_id: int,
        session_id: str,
        mode: str,
        duration_minutes: int = 0,
        conversation_history: Optional[list[dict[str, Any]]] = None,
        corrections_made: Optional[list[dict[str, Any]] | int] = None,
        vocabulary_reviewed: Optional[list[dict[str, Any]]] = None,
        assessed_level: Optional[str] = None,
        assessment_scores: Optional[dict[str, Any]] = None,
        interview_run: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        plan = await self.get_or_create_plan(user_id)
        roadmap = deepcopy(plan.roadmap or {})
        existing_items = [
            dict(item)
            for item in (roadmap.get("session_evidence") or [])
            if isinstance(item, dict)
        ]
        for existing in existing_items:
            if existing.get("session_id") == session_id:
                return existing

        evidence = self._build_session_evidence(
            session_id=session_id,
            mode=mode,
            duration_minutes=duration_minutes,
            conversation_history=conversation_history or [],
            corrections_made=corrections_made,
            vocabulary_reviewed=vocabulary_reviewed or [],
            assessed_level=assessed_level,
            assessment_scores=assessment_scores or {},
            interview_run=interview_run,
        )
        if not evidence:
            return None

        roadmap["session_evidence"] = [evidence, *existing_items][:20]
        plan.roadmap = dict(roadmap)
        flag_modified(plan, "roadmap")
        plan.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(plan)
        return evidence

    def get_goal(self, plan: LearningPlan) -> Optional[str]:
        return (plan.roadmap or {}).get("goal")

    def get_goal_brief(self, plan: LearningPlan) -> Optional[dict[str, Any]]:
        roadmap = plan.roadmap or {}
        goal_brief = roadmap.get("goal_brief")
        if goal_brief:
            return goal_brief
        goal = roadmap.get("goal")
        if not goal:
            return None
        return self._build_goal_brief(goal, self._match_goal_template(goal))

    def is_goal_setup_complete(self, plan: LearningPlan) -> bool:
        goal_brief = self.get_goal_brief(plan)
        return bool(goal_brief and goal_brief.get("status") in {"draft", "confirmed"})

    def get_goal_setup_missing(self, plan: LearningPlan) -> list[str]:
        goal_brief = self.get_goal_brief(plan) or {}
        missing: list[str] = []
        for key, label in _GOAL_BRIEF_REQUIRED_FIELDS.items():
            if not goal_brief.get(key):
                missing.append(label)
        return missing

    def get_focus_areas(self, plan: LearningPlan) -> list[str]:
        areas = (plan.roadmap or {}).get("focus_areas", [])
        return [area.get("area", "") for area in areas if isinstance(area, dict)]

    def get_preferred_mode(self, plan: LearningPlan) -> str:
        return (plan.roadmap or {}).get("preferred_mode", "free_conversation")

    def get_last_assessment_date(self, plan: LearningPlan) -> Optional[datetime]:
        last_assessment = (plan.roadmap or {}).get("last_assessment")
        if not last_assessment:
            return None
        try:
            return datetime.fromisoformat(last_assessment)
        except ValueError:
            return None

    def get_current_level(self, plan: LearningPlan) -> Optional[str]:
        roadmap = plan.roadmap or {}
        return roadmap.get("current_level") or (roadmap.get("proficiency_profile") or {}).get("cefr_level")

    def get_session_count(self, plan: LearningPlan) -> int:
        return (plan.roadmap or {}).get("sessions_completed", 0)

    def get_recommended_vocabulary(self, plan: LearningPlan) -> list[str]:
        return (plan.roadmap or {}).get("recommended_vocabulary", [])

    def get_proficiency_profile(self, plan: LearningPlan) -> Optional[dict[str, Any]]:
        roadmap = plan.roadmap or {}
        profile = roadmap.get("proficiency_profile")
        if profile:
            return profile
        current_level = roadmap.get("current_level")
        if not current_level:
            return None
        return self._build_proficiency_profile(
            current_level,
            {},
            self.get_goal_brief(plan),
            None,
            provisional=False,
        )

    def get_program_plan(self, plan: LearningPlan) -> Optional[dict[str, Any]]:
        roadmap = plan.roadmap or {}
        goal_brief = self.get_goal_brief(plan)
        fallback_program = self._build_program_plan(
            goal_brief,
            self.get_proficiency_profile(plan),
            roadmap.get("focus_areas") or [],
            roadmap.get("preferred_mode") or "free_conversation",
        )
        program = roadmap.get("program_plan")
        if not program:
            return fallback_program
        return self._normalize_program_plan(program, fallback_program)

    def get_career_context(self, plan: LearningPlan) -> dict[str, Any]:
        roadmap = plan.roadmap or {}
        career_context = roadmap.get("career_context")
        if career_context:
            return career_context
        return self._build_career_context(
            goal_brief=self.get_goal_brief(plan),
            existing=None,
            vacancy_text=roadmap.get("vacancy_text"),
            interview_date=None,
        )

    def get_interview_pack(self, plan: LearningPlan) -> Optional[dict[str, Any]]:
        roadmap = plan.roadmap or {}
        interview_pack = roadmap.get("interview_pack")
        if interview_pack:
            return interview_pack
        goal_brief = self.get_goal_brief(plan)
        if not goal_brief or goal_brief.get("status") not in {"draft", "confirmed"}:
            return None
        return self._build_interview_pack(
            goal_brief=goal_brief,
            proficiency_profile=self.get_proficiency_profile(plan),
            interview_runs=roadmap.get("interview_runs") or [],
            career_context=self.get_career_context(plan),
            recommended_vocabulary=roadmap.get("recommended_vocabulary") or [],
        )

    def get_session_evidence(self, plan: LearningPlan) -> list[dict[str, Any]]:
        roadmap = plan.roadmap or {}
        return [
            dict(item)
            for item in (roadmap.get("session_evidence") or [])
            if isinstance(item, dict) and item.get("session_id")
        ]

    def _match_goal_template(self, goal_text: str) -> Optional[GoalTemplate]:
        goal_lower = goal_text.lower()
        if any(keyword in goal_lower for keyword in ["ml", "machine learning", "data science", "data scientist", " ai ", "artificial intelligence", "model"]):
            return GOAL_TEMPLATES["ml_interview"]
        if any(keyword in goal_lower for keyword in ["software", "developer", "engineer", "programming", "backend", "frontend"]):
            return GOAL_TEMPLATES["software_interview"]
        if any(keyword in goal_lower for keyword in ["interview", "job", "career", "abroad", "international", "remote"]):
            return GOAL_TEMPLATES["software_interview"]
        return GOAL_TEMPLATES["general_fluency"]

    def _update_milestone(
        self,
        roadmap: dict[str, Any],
        milestone_type: str,
        done: bool = False,
        increment: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        milestones = roadmap.get("milestones", [])
        for milestone in milestones:
            if not (isinstance(milestone, dict) and milestone.get("type") == milestone_type):
                continue
            if done:
                milestone["done"] = True
            if increment is not None:
                field = "progress" if milestone_type == "vocabulary" else "count"
                milestone[field] = milestone.get(field, 0) + increment
                target = milestone.get("target")
                if target and milestone[field] >= target:
                    milestone["done"] = True
            milestone.update(kwargs)
        roadmap["milestones"] = milestones

    def _build_goal_brief(
        self,
        goal_text: str,
        template: Optional[GoalTemplate],
        existing: Optional[dict[str, Any]] = None,
        incoming: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        merged = deepcopy(existing or {})
        if incoming:
            merged.update({key: value for key, value in incoming.items() if value not in (None, "", [])})

        role, domain = self._infer_role_and_domain(goal_text, template, merged)
        contexts = self._infer_contexts(goal_text, template, merged)
        target_market = merged.get("target_market") or self._infer_target_market(goal_text)
        deadline_type = merged.get("deadline_type") or self._infer_deadline_type(goal_text)
        blockers = merged.get("current_blockers") or self._infer_blockers(goal_text)

        brief = {
            "primary_goal": merged.get("primary_goal") or goal_text.strip(),
            "target_role": merged.get("target_role") or role,
            "domain": merged.get("domain") or domain,
            "target_market": target_market,
            "deadline_type": deadline_type,
            "main_contexts": _dedupe(merged.get("main_contexts") or contexts),
            "current_blockers": _dedupe(blockers),
            "motivation": merged.get("motivation") or "Use English to unlock a better career outcome.",
            "confidence": round(float(merged.get("confidence") or self._goal_confidence(goal_text, role, contexts)), 2),
        }
        if merged.get("confirmed_by_user") or merged.get("status") == "confirmed":
            brief["confirmed_by_user"] = True
        if self._is_goal_brief_complete(brief) and brief.get("confirmed_by_user"):
            brief["status"] = "confirmed"
        elif self._is_goal_brief_routing_ready(brief):
            brief["status"] = "draft"
        else:
            brief["status"] = "incomplete"
        brief["summary"] = self._build_goal_summary(brief)
        return brief

    def _analyze_vacancy_text(self, vacancy_text: str) -> dict[str, Any]:
        text = vacancy_text.lower()
        role, domain = self._infer_role_and_domain(vacancy_text, self._match_goal_template(vacancy_text), {})

        company_type = "international_product_company"
        if any(keyword in text for keyword in ["startup", "seed", "series a", "series b", "early-stage"]):
            company_type = "startup"
        elif any(keyword in text for keyword in ["enterprise", "b2b", "platform", "saas"]):
            company_type = "enterprise_software"
        elif any(keyword in text for keyword in ["research", "scientist", "applied scientist"]):
            company_type = "research_or_applied_ai"

        contexts = ["interviews"]
        if any(keyword in text for keyword in ["architecture", "design", "deploy", "deployment", "pipeline", "trade-off", "tradeoff", "stakeholder", "metric", "impact"]):
            contexts.append("project_walkthrough")
        if any(keyword in text for keyword in ["cross-functional", "communicate", "stakeholder", "collaborate", "present", "business"]):
            contexts.append("workplace_communication")

        domain_terms = _VACANCY_KEY_TERMS.get(domain or "software_engineering", [])
        key_terms = [
            term
            for term in domain_terms
            if term in text
        ]
        if not key_terms:
            key_terms = domain_terms[:6]

        role_label = role or "Software Engineer"
        summary_parts = [f"{role_label} role"]
        if domain == "machine_learning":
            summary_parts.append("with focus on ML projects, model decisions, and impact")
        elif "project_walkthrough" in contexts:
            summary_parts.append("with emphasis on technical project explanation")
        if company_type == "startup":
            summary_parts.append("in a startup environment")
        elif company_type == "enterprise_software":
            summary_parts.append("in an enterprise software context")
        else:
            summary_parts.append("for an international company")

        blockers = ["Need concise, credible interview answers"]
        if "project_walkthrough" in contexts:
            blockers.append("Need clear project walkthroughs with metrics and trade-offs")
        if "workplace_communication" in contexts:
            blockers.append("Need stronger stakeholder and workplace communication")

        return {
            "target_role": role_label,
            "domain": domain or "software_engineering",
            "company_type": company_type,
            "target_market": "international_company",
            "main_contexts": _dedupe(contexts),
            "key_terms": _dedupe(key_terms)[:8],
            "summary": " ".join(summary_parts).strip(),
            "goal_text": f"Prepare for {role_label} interviews in an international company",
            "current_blockers": blockers,
        }

    def _build_proficiency_profile(
        self,
        assessed_level: str,
        scores: dict[str, Any],
        goal_brief: Optional[dict[str, Any]],
        notes: Optional[str],
        *,
        provisional: bool = False,
        confidence_override: Optional[float] = None,
    ) -> dict[str, Any]:
        baseline = _LEVEL_BASELINE.get(assessed_level, 5.0)
        fluency = _normalize_score(scores.get("fluency"), baseline)
        grammar = _normalize_score(scores.get("grammar"), baseline)
        listening = _normalize_score(scores.get("comprehension"), baseline)
        vocabulary = _normalize_score(scores.get("vocabulary"), baseline)
        avg = _round_score((fluency + grammar + listening + vocabulary) / 4)
        computed_confidence = round(min(0.95, 0.55 + avg / 20), 2)
        if provisional:
            computed_confidence = min(computed_confidence, 0.55)
        if confidence_override is not None:
            computed_confidence = round(float(confidence_override), 2)
        return {
            "cefr_level": assessed_level,
            "confidence": computed_confidence,
            "fluency": fluency,
            "grammar_accuracy": grammar,
            "listening_comprehension": listening,
            "professional_vocabulary": vocabulary,
            "goal_readiness": self._estimate_goal_readiness(assessed_level, fluency, grammar, listening, vocabulary, goal_brief),
            "critical_gaps": self._build_critical_gaps(fluency, grammar, listening, vocabulary, goal_brief),
            "notes": notes,
            "status": "provisional" if provisional else "confirmed",
            "provisional": provisional,
            "updated_at": _utcnow_iso(),
        }

    def _build_program_plan(
        self,
        goal_brief: Optional[dict[str, Any]],
        proficiency_profile: Optional[dict[str, Any]],
        focus_areas: list[dict[str, Any]] | list[str],
        preferred_mode: str,
    ) -> dict[str, Any]:
        if not goal_brief:
            return {
                "title": "Complete your career English setup",
                "time_horizon_days": 90,
                "current_stage": "goal_setup",
                "stage_label": "Goal Setup",
                "weekly_focus": ["Clarify your target role and context"],
                "success_metric": "Turn a vague goal into a concrete target",
                "next_milestone": "Confirm your goal",
                "stages": [],
                "preferred_mode": "free_conversation",
                "focus_areas": [],
            }

        stage_id = "goal_setup"
        stage_label = "Goal Setup"
        weekly_focus = ["Clarify your target role, company context, and practice situations"]
        success_metric = "Complete setup so the coach can route practice correctly"
        next_milestone = "Confirm the goal brief"
        if goal_brief.get("status") in {"draft", "confirmed"} and not proficiency_profile:
            stage_id = "baseline_assessment"
            stage_label = "Baseline Assessment"
            weekly_focus = ["Measure your level before building practice intensity"]
            success_metric = "Get a reliable speaking baseline"
            next_milestone = "Complete the baseline assessment"
        elif goal_brief.get("status") in {"draft", "confirmed"} and proficiency_profile:
            readiness = float(proficiency_profile.get("goal_readiness") or 0.0)
            grammar = float(proficiency_profile.get("grammar_accuracy") or 0.0)
            fluency = float(proficiency_profile.get("fluency") or 0.0)
            if readiness < 5.5 or grammar < 5.5 or fluency < 5.5:
                stage_id = "foundation"
                stage_label = "Foundation for Career English"
                weekly_focus = self._build_foundation_focus(goal_brief)
                success_metric = "Speak more accurately in career-related situations"
                next_milestone = "Stabilize grammar, fluency, and core workplace answers"
            elif readiness < 7.2:
                stage_id = "career_scenarios"
                stage_label = "Career Scenario Practice"
                weekly_focus = self._build_scenario_focus(goal_brief)
                success_metric = "Handle common interview and workplace scenarios with structure"
                next_milestone = "Complete focused career scenario drills"
            else:
                stage_id = "target_role_simulation"
                stage_label = "Target Role Simulation"
                weekly_focus = self._build_simulation_focus(goal_brief)
                success_metric = "Perform close to real interview and workplace expectations"
                next_milestone = "Run target-role simulations and raise readiness"

        order = [
            ("goal_setup", "Goal Setup"),
            ("baseline_assessment", "Baseline Assessment"),
            ("foundation", "Foundation"),
            ("career_scenarios", "Career Scenarios"),
            ("target_role_simulation", "Target Role Simulation"),
        ]
        current_idx = next((idx for idx, item in enumerate(order) if item[0] == stage_id), 0)
        stages = []
        for idx, (item_id, label) in enumerate(order):
            status = "current" if idx == current_idx else ("completed" if idx < current_idx else "upcoming")
            stages.append({"id": item_id, "label": label, "status": status})

        return {
            "title": self._build_program_title(goal_brief),
            "time_horizon_days": 90,
            "current_stage": stage_id,
            "stage_label": stage_label,
            "weekly_focus": weekly_focus[:3],
            "success_metric": success_metric,
            "next_milestone": next_milestone,
            "stages": stages,
            "preferred_mode": "mock_interview" if stage_id in {"career_scenarios", "target_role_simulation"} else preferred_mode,
            "focus_areas": self._normalize_focus_areas(focus_areas),
        }

    def _normalize_program_plan(
        self,
        program_plan: dict[str, Any],
        fallback_program: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = dict(fallback_program)
        normalized.update(
            {
                key: value
                for key, value in program_plan.items()
                if value not in (None, "", [])
            }
        )

        for key in ("weekly_focus", "stages", "focus_areas"):
            value = program_plan.get(key)
            if isinstance(value, list) and value:
                normalized[key] = value

        return normalized

    def _build_career_context(
        self,
        *,
        goal_brief: Optional[dict[str, Any]],
        existing: Optional[dict[str, Any]],
        vacancy_text: Optional[str],
        interview_date: Optional[str],
        analysis: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        existing = deepcopy(existing or {})
        analysis = analysis or (self._analyze_vacancy_text(vacancy_text) if vacancy_text else {})
        return {
            "target_role": (goal_brief or {}).get("target_role") or analysis.get("target_role"),
            "company_type": existing.get("company_type") or analysis.get("company_type"),
            "interview_date": interview_date or existing.get("interview_date"),
            "target_market": (goal_brief or {}).get("target_market") or analysis.get("target_market"),
            "vacancy_present": bool(vacancy_text and vacancy_text.strip()),
            "vacancy_summary": analysis.get("summary") or existing.get("vacancy_summary"),
        }

    def _build_interview_pack(
        self,
        *,
        goal_brief: Optional[dict[str, Any]],
        proficiency_profile: Optional[dict[str, Any]],
        interview_runs: list[dict[str, Any]],
        career_context: Optional[dict[str, Any]],
        recommended_vocabulary: list[str],
        vacancy_analysis: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        if not goal_brief or goal_brief.get("status") not in {"draft", "confirmed"}:
            return None

        vacancy_analysis = vacancy_analysis or {}
        contexts = goal_brief.get("main_contexts") or []
        target_role = goal_brief.get("target_role") or (career_context or {}).get("target_role") or "your target role"
        recommended_track = "hr_intro"
        if "project_walkthrough" in contexts or goal_brief.get("domain") == "machine_learning":
            recommended_track = "project_walkthrough"
        elif "workplace_communication" in contexts:
            recommended_track = "workplace_communication"

        profile_gaps = list((proficiency_profile or {}).get("critical_gaps") or [])
        latest_run = interview_runs[-1] if interview_runs else None
        latest_focus = list((latest_run or {}).get("next_focus") or [])
        weakest_area = ((latest_run or {}).get("meta") or {}).get("weakest_area")
        if weakest_area:
            profile_gaps.insert(0, f"Latest interview weakness: {str(weakest_area).replace('_', ' ')}")
        top_blockers = _dedupe([*latest_focus, *profile_gaps])[:3]

        must_answer_questions = [
            f"Why are you a strong fit for this {target_role} role?",
            f"Walk me through one project that best proves you can do this {target_role} job.",
            "Tell me about a tough decision, trade-off, or blocker and how you handled it.",
        ]
        if recommended_track == "project_walkthrough":
            must_answer_questions[1] = "Walk me through one ML or technical project: problem, approach, trade-offs, metric, impact."
        if recommended_track == "workplace_communication":
            must_answer_questions[2] = "Give a clear workplace update: what is done, what is next, and what is blocked."

        project_story_prompts = [
            "Choose one project where your contribution changed the outcome.",
            "Explain one project in simple English: problem, action, result.",
        ]
        if goal_brief.get("domain") == "machine_learning":
            project_story_prompts = [
                "Explain one ML project: business problem, model choice, metric, trade-offs, impact.",
                "Describe one production or deployment decision and why it mattered.",
            ]

        key_terms = _dedupe([
            *list(vacancy_analysis.get("key_terms") or []),
            *recommended_vocabulary,
        ])[:8]

        return {
            "target_role": target_role,
            "must_answer_questions": must_answer_questions,
            "project_story_prompts": project_story_prompts,
            "key_terms": key_terms,
            "top_blockers": top_blockers or ["Need one stronger interview answer before the next run."],
            "recommended_track": recommended_track,
            "recommended_track_title": _TRACK_LABELS.get(recommended_track, "Career Mission"),
            "summary": (career_context or {}).get("vacancy_summary") or f"Interview prep for {target_role}.",
        }

    def _infer_role_and_domain(
        self,
        goal_text: str,
        template: Optional[GoalTemplate],
        goal_brief: dict[str, Any],
    ) -> tuple[Optional[str], Optional[str]]:
        goal_lower = goal_text.lower()
        for keyword, value in _ROLE_KEYWORDS.items():
            if keyword in goal_lower:
                return value
        if goal_brief.get("target_role") and goal_brief.get("domain"):
            return goal_brief["target_role"], goal_brief["domain"]
        if template is GOAL_TEMPLATES["ml_interview"]:
            return "ML Engineer", "machine_learning"
        if template is GOAL_TEMPLATES["software_interview"]:
            return "Software Engineer", "software_engineering"
        return None, None

    def _infer_contexts(
        self,
        goal_text: str,
        template: Optional[GoalTemplate],
        goal_brief: dict[str, Any],
    ) -> list[str]:
        if goal_brief.get("main_contexts"):
            return list(goal_brief["main_contexts"])
        goal_lower = goal_text.lower()
        contexts: list[str] = []
        if "interview" in goal_lower or "job" in goal_lower:
            contexts.append("interviews")
        if any(keyword in goal_lower for keyword in ["project", "architecture", "system design", "explain"]):
            contexts.append("project_walkthrough")
        if any(keyword in goal_lower for keyword in ["team", "meeting", "company", "abroad", "international", "remote"]):
            contexts.append("workplace_communication")
        if any(keyword in goal_lower for keyword in ["fluency", "speaking", "speak better"]):
            contexts.append("general_fluency")
        if not contexts and template in (GOAL_TEMPLATES["ml_interview"], GOAL_TEMPLATES["software_interview"]):
            contexts = ["interviews", "project_walkthrough", "workplace_communication"]
        return contexts or ["general_fluency"]

    def _infer_target_market(self, goal_text: str) -> Optional[str]:
        goal_lower = goal_text.lower()
        if any(keyword in goal_lower for keyword in ["abroad", "western", "international", "global", "remote", "interview", "job", "career"]):
            return "international_company"
        return None

    def _infer_deadline_type(self, goal_text: str) -> str:
        goal_lower = goal_text.lower()
        if re.search(r"\b(1|2|3)\s*(month|months)\b", goal_lower) or "soon" in goal_lower:
            return "urgent_1_3m"
        if re.search(r"\b(4|5|6)\s*(month|months)\b", goal_lower):
            return "medium_3_6m"
        return "open_ended"

    def _infer_blockers(self, goal_text: str) -> list[str]:
        goal_lower = goal_text.lower()
        blockers: list[str] = []
        if "interview" in goal_lower:
            blockers.append("Need structured answers under pressure")
        if any(keyword in goal_lower for keyword in ["job", "career", "abroad", "international"]):
            blockers.append("Need confident workplace English for international settings")
        return blockers

    def _goal_confidence(self, goal_text: str, role: Optional[str], contexts: list[str]) -> float:
        score = 0.45
        if role:
            score += 0.2
        if contexts and "general_fluency" not in contexts:
            score += 0.2
        if any(keyword in goal_text.lower() for keyword in ["job", "career", "interview", "abroad", "international"]):
            score += 0.1
        if any(keyword in goal_text.lower() for keyword in ["ml", "machine learning", "ai", "data scientist"]):
            score += 0.05
        return min(score, 0.95)

    def _is_goal_brief_routing_ready(self, goal_brief: dict[str, Any]) -> bool:
        return bool(
            goal_brief.get("primary_goal")
            and goal_brief.get("target_role")
            and goal_brief.get("domain")
            and goal_brief.get("target_market")
            and goal_brief.get("main_contexts")
            and "general_fluency" not in (goal_brief.get("main_contexts") or [])
        )

    def _is_goal_brief_complete(self, goal_brief: dict[str, Any]) -> bool:
        return bool(
            self._is_goal_brief_routing_ready(goal_brief)
            and goal_brief.get("deadline_type")
        )

    def _build_goal_summary(self, goal_brief: dict[str, Any]) -> str:
        role = goal_brief.get("target_role") or "target role"
        market = (goal_brief.get("target_market") or "context not set").replace("_", " ")
        contexts = ", ".join(item.replace("_", " ") for item in (goal_brief.get("main_contexts") or []))
        deadline = (goal_brief.get("deadline_type") or "open_ended").replace("_", " ")
        return f"Target {role} role in {market}. Focus: {contexts or 'to clarify'}. Timeline: {deadline}."

    def _estimate_goal_readiness(
        self,
        assessed_level: str,
        fluency: float,
        grammar: float,
        listening: float,
        vocabulary: float,
        goal_brief: Optional[dict[str, Any]],
    ) -> float:
        baseline = _LEVEL_BASELINE.get(assessed_level, 5.0)
        contexts = (goal_brief or {}).get("main_contexts") or []
        weighted = baseline * 0.35 + fluency * 0.2 + grammar * 0.2 + listening * 0.1 + vocabulary * 0.15
        if "project_walkthrough" in contexts or "interviews" in contexts:
            weighted = baseline * 0.25 + fluency * 0.15 + grammar * 0.2 + listening * 0.1 + vocabulary * 0.3
        if not (goal_brief or {}).get("target_role"):
            weighted -= 0.5
        return _round_score(weighted)

    def _build_critical_gaps(
        self,
        fluency: float,
        grammar: float,
        listening: float,
        vocabulary: float,
        goal_brief: Optional[dict[str, Any]],
    ) -> list[str]:
        gaps: list[tuple[float, str]] = [
            (fluency, "Fluency under pressure"),
            (grammar, "Grammar accuracy in speech"),
            (listening, "Listening comprehension in fast conversation"),
            (vocabulary, "Professional vocabulary for work and interviews"),
        ]
        if goal_brief and goal_brief.get("domain") == "machine_learning":
            gaps.append((vocabulary - 0.5, "Explaining ML projects, metrics, and trade-offs"))
        if goal_brief and "project_walkthrough" in (goal_brief.get("main_contexts") or []):
            gaps.append((vocabulary - 0.3, "Explaining projects with technical precision"))
        if goal_brief and "interviews" in (goal_brief.get("main_contexts") or []):
            gaps.append((fluency - 0.2, "Structured interview answers"))
        gaps.sort(key=lambda item: item[0])
        return [label for _, label in gaps[:3]]

    def _build_foundation_focus(self, goal_brief: dict[str, Any]) -> list[str]:
        focus = [
            "Build short, accurate answers about your background and current work",
            "Reduce grammar friction in spoken English",
            "Strengthen core workplace vocabulary",
        ]
        if goal_brief.get("domain") == "machine_learning":
            focus.append("Explain one ML project in simple English: problem, model, metric, impact")
        if "project_walkthrough" in (goal_brief.get("main_contexts") or []):
            focus.append("Practice explaining one project in simple, clear English")
        return _dedupe(focus)

    def _build_scenario_focus(self, goal_brief: dict[str, Any]) -> list[str]:
        focus: list[str] = []
        contexts = goal_brief.get("main_contexts") or []
        if "interviews" in contexts:
            focus.append("Run structured interview answers with STAR")
        if "project_walkthrough" in contexts:
            focus.append("Explain architecture, trade-offs, and impact")
        if "workplace_communication" in contexts:
            focus.append("Practice standups, blockers, and stakeholder updates")
        if goal_brief.get("domain") == "machine_learning":
            focus.append("Talk about datasets, models, metrics, and production decisions clearly")
        focus.append("Turn weak areas into repeatable speaking patterns")
        return _dedupe(focus)

    def _build_simulation_focus(self, goal_brief: dict[str, Any]) -> list[str]:
        role = goal_brief.get("target_role") or "your target role"
        focus = [
            f"Simulate realistic conversations for {role}",
            "Push for sharper vocabulary and cleaner delivery",
            "Build confidence in high-stakes career situations",
        ]
        if goal_brief.get("domain") == "machine_learning":
            focus.insert(1, "Defend ML decisions with trade-offs, metrics, and impact")
        return focus[:3]

    def _build_program_title(self, goal_brief: dict[str, Any]) -> str:
        role = goal_brief.get("target_role")
        domain = goal_brief.get("domain")
        if role and domain == "machine_learning":
            return "90-day ML career English roadmap"
        if role:
            return f"90-day {role} English roadmap"
        return "90-day career English roadmap"

    def _normalize_focus_areas(self, focus_areas: list[dict[str, Any]] | list[str]) -> list[str]:
        normalized: list[str] = []
        for item in focus_areas:
            if isinstance(item, dict):
                normalized.append(str(item.get("description") or item.get("area") or ""))
            else:
                normalized.append(str(item))
        return _dedupe(normalized)

    def _build_session_evidence(
        self,
        *,
        session_id: str,
        mode: str,
        duration_minutes: int,
        conversation_history: list[dict[str, Any]],
        corrections_made: Optional[list[dict[str, Any]] | int],
        vocabulary_reviewed: list[dict[str, Any]],
        assessed_level: Optional[str],
        assessment_scores: dict[str, Any],
        interview_run: Optional[dict[str, Any]],
    ) -> Optional[dict[str, Any]]:
        user_messages = [
            str(message.get("content") or "").strip()
            for message in conversation_history
            if message.get("role") == "user" and message.get("content")
        ]
        user_turns = len(user_messages)
        vocab_words = [
            str(item.get("word") or "").strip()
            for item in vocabulary_reviewed
            if isinstance(item, dict) and item.get("word")
        ]
        if isinstance(corrections_made, list):
            corrections = [item for item in corrections_made if isinstance(item, dict)]
            corrections_count = len(corrections)
        else:
            corrections = []
            corrections_count = int(corrections_made or 0)

        meaningful = bool(user_turns or corrections_count or vocab_words or assessed_level or interview_run)
        if not meaningful:
            return None

        mode_label = _humanize_key(mode) or "guided session"
        recorded_at = _utcnow_iso()

        if interview_run:
            overall = (interview_run.get("scores") or {}).get("overall")
            pronunciation = interview_run.get("pronunciation") or {}
            evidence_signals = []
            if overall is not None:
                evidence_signals.append(f"Interview score {overall}/10")
            if pronunciation.get("overall_score") is not None:
                evidence_signals.append(f"Speech signal {pronunciation['overall_score']}/10")
            if interview_run.get("delta_vs_previous") not in (None, 0):
                delta = float(interview_run["delta_vs_previous"])
                direction = "up" if delta > 0 else "down"
                evidence_signals.append(f"Interview trend {direction} {abs(delta):.1f}")
            return {
                "id": session_id,
                "session_id": session_id,
                "mission_type": mode,
                "mission_title": interview_run.get("track_title") or "Career interview run",
                "summary": interview_run.get("summary") or "Interview run saved with score and next focus.",
                "what_was_trained": interview_run.get("track_subtitle") or "Interview delivery under realistic pressure.",
                "what_went_well": (interview_run.get("strengths") or [])[:3],
                "main_issue": _humanize_key((interview_run.get("meta") or {}).get("weakest_area")) or "Interview delivery needs another repetition.",
                "next_focus": (interview_run.get("next_focus") or [])[:3],
                "evidence_signals": evidence_signals,
                "recorded_at": recorded_at,
                "duration_minutes": duration_minutes,
            }

        if mode == "assessment" or assessed_level:
            weakest_axis = self._find_weakest_assessment_axis(assessment_scores)
            next_focus = []
            if weakest_axis:
                next_focus.append(f"Start the first mission around {weakest_axis}.")
            next_focus.append("Use the next guided mission to collect stronger speaking evidence.")
            evidence_signals = [f"Baseline level {assessed_level or 'captured'}"]
            if weakest_axis:
                evidence_signals.append(f"Weakest axis: {weakest_axis}")
            return {
                "id": session_id,
                "session_id": session_id,
                "mission_type": "assessment",
                "mission_title": "Baseline assessment",
                "summary": f"Baseline captured at CEFR {assessed_level or 'level pending'}. The program can now route practice from real evidence.",
                "what_was_trained": "Measured your speaking baseline against the career goal.",
                "what_went_well": ["You completed the baseline flow and unlocked program routing."],
                "main_issue": weakest_axis or "Need more speaking evidence to isolate the weakest area.",
                "next_focus": next_focus[:3],
                "evidence_signals": evidence_signals,
                "recorded_at": recorded_at,
                "duration_minutes": duration_minutes,
            }

        if mode == "vocabulary_drill":
            vocab_count = len(vocab_words)
            return {
                "id": session_id,
                "session_id": session_id,
                "mission_type": mode,
                "mission_title": "Vocabulary reinforcement",
                "summary": f"You reinforced {vocab_count} job-relevant word{'s' if vocab_count != 1 else ''} in context.",
                "what_was_trained": "Active recall on vocabulary linked to your current program.",
                "what_went_well": [
                    "You cleared part of the review queue.",
                    "You kept vocabulary practice tied to speaking, not isolated memorization.",
                ][: 1 if vocab_count <= 0 else 2],
                "main_issue": "Keep using the reviewed words inside full answers, not one-word recall.",
                "next_focus": [
                    "Use the same words in one short career answer.",
                    "Revisit the next due cards before they pile up again.",
                ],
                "evidence_signals": [
                    f"{vocab_count} words reinforced",
                    f"{user_turns} speaking turn{'s' if user_turns != 1 else ''}",
                ],
                "recorded_at": recorded_at,
                "duration_minutes": duration_minutes,
            }

        correction_issue = self._extract_correction_issue(corrections)
        what_went_well = ["You completed a full guided speaking mission."]
        if user_turns >= 2:
            what_went_well.append("You stayed in English across multiple turns.")
        if corrections_count <= 2 and user_turns >= 2:
            what_went_well.append("Your answers stayed relatively clean under practice pressure.")

        next_focus = []
        if correction_issue:
            next_focus.append(f"Repeat one more drill focusing on {correction_issue}.")
        if vocab_words:
            next_focus.append(f"Reuse {vocab_words[0]} in your next answer.")
        next_focus.append("Keep answers short, clear, and tied to your target job context.")

        evidence_signals = [
            f"{user_turns} user turn{'s' if user_turns != 1 else ''}",
            f"{corrections_count} correction signal{'s' if corrections_count != 1 else ''}",
        ]
        if vocab_words:
            evidence_signals.append(f"{len(vocab_words)} vocabulary cue{'s' if len(vocab_words) != 1 else ''} reinforced")

        summary = "You completed a guided speaking mission with live coaching."
        if correction_issue:
            summary = f"You practiced {mode_label} and surfaced a repeatable issue around {correction_issue}."
        elif vocab_words:
            summary = f"You practiced {mode_label} and reinforced vocabulary in context."

        return {
            "id": session_id,
            "session_id": session_id,
            "mission_type": mode,
            "mission_title": _humanize_key(mode_label).title(),
            "summary": summary,
            "what_was_trained": self._describe_trained_area(mode),
            "what_went_well": what_went_well[:3],
            "main_issue": correction_issue or "Need more repetitions before a clear weak point emerges.",
            "next_focus": next_focus[:3],
            "evidence_signals": evidence_signals,
            "recorded_at": recorded_at,
            "duration_minutes": duration_minutes,
        }

    def _find_weakest_assessment_axis(self, assessment_scores: dict[str, Any]) -> Optional[str]:
        axes: list[tuple[str, float]] = []
        for key in ("fluency", "grammar", "vocabulary", "comprehension"):
            raw = assessment_scores.get(key)
            if raw is None:
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if value <= 1.0:
                value *= 10.0
            axes.append((_humanize_key(key) or key, value))
        if not axes:
            return None
        axes.sort(key=lambda item: item[1])
        return axes[0][0]

    def _extract_correction_issue(self, corrections: list[dict[str, Any]]) -> Optional[str]:
        if not corrections:
            return None
        first = corrections[0]
        label = first.get("type") or first.get("rule_tag") or first.get("label")
        return _humanize_key(str(label)) if label else "grammar accuracy"

    def _describe_trained_area(self, mode: str) -> str:
        if mode == "guided_setup":
            return "Clarified your goal and learning context."
        if mode == "free_conversation":
            return "Spoken English in a lower-pressure career context."
        return f"Guided {(_humanize_key(mode) or 'practice')} linked to your career program."


async def detect_goal_from_message(message: str) -> Optional[str]:
    import warnings

    warnings.warn(
        "detect_goal_from_message() is deprecated. Use LangGraph goal discovery instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    message_lower = message.lower()
    patterns = {
        "ML/Data Science Interview": [
            "ml interview", "machine learning", "data science", "data scientist", "ai interview", "ml",
        ],
        "Software Engineering Interview": [
            "software interview", "developer interview", "engineer interview", "coding interview",
            "software engineer", "backend", "frontend", "fullstack",
        ],
        "Job Interview": [
            "job interview", "find a job", "new job", "get a job", "prepare for interview", "interview prep",
        ],
        "IELTS/TOEFL Preparation": ["ielts", "toefl", "exam preparation", "english exam"],
        "Business English": ["business english", "corporate", "meetings", "presentations"],
        "General Fluency": ["fluency", "improve english", "practice speaking", "speak better", "learn english"],
    }
    for goal, keywords in patterns.items():
        if any(keyword in message_lower for keyword in keywords):
            return goal
    if "interview" in message_lower:
        return "Job Interview"
    return None
