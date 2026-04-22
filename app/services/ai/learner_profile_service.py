"""Compact learner profile and mission-scoped memory assembly."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums_and_dimensions import MemoryKind
from app.models.extended_tables import LearningPlan, Memory
from app.services.ai.memory_contracts import (
    LearnerProfileSummary,
    MissionMemoryContext,
    normalize_temporal_references,
)
from app.services.ai.memory_pipeline import MemoryPipeline
from app.services.learning_plan_service import LearningPlanService

logger = logging.getLogger(__name__)


def _dedupe(values: list[str], limit: Optional[int] = None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
        if limit and len(result) >= limit:
            break
    return result


class LearnerProfileService:
    """Build a compact learner profile from roadmap, evidence, and memory."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        learning_plan_service: Optional[LearningPlanService] = None,
        memory_pipeline: Optional[MemoryPipeline] = None,
    ) -> None:
        self._db = db
        self._learning_plan_service = learning_plan_service or LearningPlanService(db)
        self._memory_pipeline = memory_pipeline or MemoryPipeline(db)

    async def build_summary(
        self,
        *,
        user_id: int,
        plan: Optional[LearningPlan] = None,
    ) -> LearnerProfileSummary:
        plan = plan or await self._learning_plan_service.get_or_create_plan(user_id)
        roadmap = plan.roadmap or {}
        goal_brief = self._learning_plan_service.get_goal_brief(plan) or {}
        proficiency_profile = self._learning_plan_service.get_proficiency_profile(plan) or {}
        program_plan = self._learning_plan_service.get_program_plan(plan) or {}
        session_evidence = self._learning_plan_service.get_session_evidence(plan)
        memories = await self._load_memories(user_id)

        top_error_patterns = _dedupe(
            [memory.content for memory in memories if memory.kind == MemoryKind.ERROR_PATTERN]
            + [str(item.get("main_issue")) for item in session_evidence if item.get("main_issue")]
            + [str(item) for item in (proficiency_profile.get("critical_gaps") or [])],
            limit=3,
        )
        preferences = _dedupe(
            [memory.content for memory in memories if memory.kind == MemoryKind.PREFERENCE],
            limit=2,
        )

        latest_evidence = session_evidence[0] if session_evidence else {}
        current_stage = program_plan.get("current_stage")
        weekly_focus = program_plan.get("weekly_focus") or []
        active_mission_family = current_stage or (weekly_focus[0] if weekly_focus else None)

        last_updated = plan.updated_at.isoformat() if getattr(plan, "updated_at", None) else None
        goal_summary = goal_brief.get("summary") or roadmap.get("goal")

        return LearnerProfileSummary(
            goal_summary=normalize_temporal_references(goal_summary or ""),
            goal_status=goal_brief.get("status"),
            target_role=goal_brief.get("target_role"),
            target_market=goal_brief.get("target_market"),
            current_level=proficiency_profile.get("cefr_level") or roadmap.get("current_level"),
            level_confidence=self._coerce_float(proficiency_profile.get("confidence")),
            current_stage=current_stage,
            active_mission_family=active_mission_family,
            practice_contexts=_dedupe([str(item) for item in (goal_brief.get("main_contexts") or [])], limit=3),
            top_error_patterns=[normalize_temporal_references(item) for item in top_error_patterns],
            current_blockers=_dedupe(
                [str(item) for item in (goal_brief.get("current_blockers") or [])]
                + [str(item) for item in (proficiency_profile.get("critical_gaps") or [])],
                limit=3,
            ),
            preferences=[normalize_temporal_references(item) for item in preferences],
            latest_evidence_summary=normalize_temporal_references(str(latest_evidence.get("summary") or "")) or None,
            latest_evidence_issue=normalize_temporal_references(str(latest_evidence.get("main_issue") or "")) or None,
            last_updated=last_updated,
        )

    async def build_mission_context(
        self,
        *,
        user_id: int,
        mission_task_type: Optional[str] = None,
        mission_title: Optional[str] = None,
        mission_reason: Optional[str] = None,
        mission_success_signal: Optional[str] = None,
        mission_linked_goal_context: Optional[str] = None,
        current_message: Optional[str] = None,
        profile_summary: Optional[LearnerProfileSummary] = None,
        plan: Optional[LearningPlan] = None,
    ) -> MissionMemoryContext:
        profile = profile_summary or await self.build_summary(user_id=user_id, plan=plan)
        memories = await self._select_mission_memories(user_id, current_message=current_message)

        return MissionMemoryContext(
            learner_profile=profile,
            mission_task_type=mission_task_type,
            mission_title=mission_title,
            mission_reason=mission_reason,
            mission_success_signal=mission_success_signal,
            mission_linked_goal_context=mission_linked_goal_context,
            relevant_memories=memories,
        )

    async def _select_mission_memories(
        self,
        user_id: int,
        *,
        current_message: Optional[str] = None,
    ) -> list[str]:
        context = await self._memory_pipeline.get_relevant_context(user_id, current_message or "")
        memories = await self._load_memories(user_id)

        selected = _dedupe(
            [normalize_temporal_references(item) for item in context.relevant_memories]
            + [normalize_temporal_references(item) for item in context.goals[:2]]
            + [normalize_temporal_references(item) for item in context.error_patterns[:2]]
            + [
                normalize_temporal_references(memory.content)
                for memory in memories
                if memory.kind in {MemoryKind.EXPERIENCE, MemoryKind.FACT}
            ],
            limit=5,
        )
        return selected

    async def _load_memories(self, user_id: int, limit: int = 30) -> list[Memory]:
        stmt = (
            select(Memory)
            .where(Memory.user_id == user_id)
            .order_by(Memory.salience.desc(), Memory.last_refreshed.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _coerce_float(value: object) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            logger.debug("Could not coerce learner profile confidence=%r", value)
            return None


def create_learner_profile_service(
    db: AsyncSession,
    learning_plan_service: LearningPlanService,
    memory_pipeline: MemoryPipeline,
) -> LearnerProfileService:
    return LearnerProfileService(
        db,
        learning_plan_service=learning_plan_service,
        memory_pipeline=memory_pipeline,
    )
