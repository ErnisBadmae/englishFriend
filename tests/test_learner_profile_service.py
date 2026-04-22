from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums_and_dimensions import MemoryKind
from app.services.ai.learner_profile_service import LearnerProfileService
from app.services.ai.memory_pipeline import MemoryContext


def _plan_mock():
    plan = MagicMock()
    plan.updated_at = datetime(2026, 4, 9, 9, 0, 0)
    plan.roadmap = {
        "goal": "Get an ML engineer role abroad",
        "goal_brief": {
            "summary": "Target ML Engineer role abroad with focus on interviews and project discussions.",
            "status": "draft",
            "target_role": "ML Engineer",
            "target_market": "Abroad",
            "main_contexts": ["Interview preparation", "Project discussions"],
            "current_blockers": ["Grammar accuracy in speech"],
        },
        "proficiency_profile": {
            "cefr_level": "B1",
            "confidence": 0.63,
            "critical_gaps": ["Fluency under pressure"],
        },
        "program_plan": {
            "current_stage": "foundation",
            "weekly_focus": ["Build short, accurate work answers"],
        },
        "session_evidence": [
            {
                "session_id": "sess-1",
                "summary": "You practiced one guided mission.",
                "main_issue": "articles",
            }
        ],
    }
    return plan


@pytest.mark.asyncio
async def test_build_summary_consolidates_plan_evidence_and_memory():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        MagicMock(kind=MemoryKind.PREFERENCE, content="Prefers short guided drills"),
        MagicMock(kind=MemoryKind.ERROR_PATTERN, content="Omits articles before nouns"),
        MagicMock(kind=MemoryKind.EXPERIENCE, content="Built a recommendation model for e-commerce"),
    ]
    db.execute = AsyncMock(return_value=result)

    learning_plan_service = MagicMock()
    learning_plan_service.get_or_create_plan = AsyncMock(return_value=_plan_mock())
    learning_plan_service.get_goal_brief.return_value = _plan_mock().roadmap["goal_brief"]
    learning_plan_service.get_proficiency_profile.return_value = _plan_mock().roadmap["proficiency_profile"]
    learning_plan_service.get_program_plan.return_value = _plan_mock().roadmap["program_plan"]
    learning_plan_service.get_session_evidence.return_value = _plan_mock().roadmap["session_evidence"]

    memory_pipeline = MagicMock()
    memory_pipeline.get_relevant_context = AsyncMock(
        return_value=MemoryContext(
            facts=[],
            preferences=["Prefers short guided drills"],
            goals=["Wants an ML engineer role abroad"],
            error_patterns=["Omits articles before nouns"],
            relevant_memories=[],
        )
    )

    service = LearnerProfileService(
        db,
        learning_plan_service=learning_plan_service,
        memory_pipeline=memory_pipeline,
    )

    summary = await service.build_summary(user_id=7)

    assert summary.target_role == "ML Engineer"
    assert summary.current_level == "B1"
    assert summary.current_stage == "foundation"
    assert summary.latest_evidence_issue == "articles"
    assert "Interview preparation" in summary.practice_contexts
    assert "Omits articles before nouns" in summary.top_error_patterns
    assert "Fluency under pressure" in summary.current_blockers


@pytest.mark.asyncio
async def test_build_mission_context_includes_profile_mission_and_relevant_memory():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = [
        MagicMock(kind=MemoryKind.EXPERIENCE, content="Built a fraud detection model in fintech"),
    ]
    db.execute = AsyncMock(return_value=result)

    learning_plan_service = MagicMock()
    learning_plan_service.get_or_create_plan = AsyncMock(return_value=_plan_mock())
    learning_plan_service.get_goal_brief.return_value = _plan_mock().roadmap["goal_brief"]
    learning_plan_service.get_proficiency_profile.return_value = _plan_mock().roadmap["proficiency_profile"]
    learning_plan_service.get_program_plan.return_value = _plan_mock().roadmap["program_plan"]
    learning_plan_service.get_session_evidence.return_value = _plan_mock().roadmap["session_evidence"]

    memory_pipeline = MagicMock()
    memory_pipeline.get_relevant_context = AsyncMock(
        return_value=MemoryContext(
            facts=[],
            preferences=[],
            goals=["Wants an ML engineer role abroad"],
            error_patterns=["Omits articles before nouns"],
            relevant_memories=["Built a fraud detection model in fintech"],
        )
    )

    service = LearnerProfileService(
        db,
        learning_plan_service=learning_plan_service,
        memory_pipeline=memory_pipeline,
    )

    context = await service.build_mission_context(
        user_id=7,
        mission_task_type="foundation_speaking_drill",
        mission_title="Run a foundation speaking drill",
        mission_reason="Build short, accurate work answers.",
        mission_success_signal="One cleaner career answer.",
        mission_linked_goal_context="foundation",
    )

    rendered = context.to_prompt_section()
    assert "Learner profile" in rendered
    assert "Current mission context" in rendered
    assert "Run a foundation speaking drill" in rendered
    assert "Built a fraud detection model in fintech" in rendered
