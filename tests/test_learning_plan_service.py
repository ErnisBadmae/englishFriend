from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.learning_plan_service import LearningPlanService


@pytest.mark.asyncio
async def test_set_goal_creates_goal_brief_and_program_plan():
    db = AsyncMock()
    plan = MagicMock()
    plan.roadmap = {}
    plan.level_target = None

    service = LearningPlanService(db)
    service.get_or_create_plan = AsyncMock(return_value=plan)

    await service.set_goal(1, "I want an ML engineer job abroad")

    assert plan.roadmap["goal"] == "I want an ML engineer job abroad"
    assert plan.roadmap["goal_brief"]["target_role"] == "ML Engineer"
    assert plan.roadmap["goal_brief"]["status"] == "confirmed"
    assert plan.roadmap["program_plan"]["current_stage"] == "baseline_assessment"


@pytest.mark.asyncio
async def test_set_goal_keeps_generic_goal_incomplete():
    db = AsyncMock()
    plan = MagicMock()
    plan.roadmap = {}
    plan.level_target = None

    service = LearningPlanService(db)
    service.get_or_create_plan = AsyncMock(return_value=plan)

    await service.set_goal(1, "I want to improve my English")

    assert plan.roadmap["goal_brief"]["status"] == "incomplete"
    assert plan.roadmap["program_plan"]["current_stage"] == "goal_setup"


@pytest.mark.asyncio
async def test_record_assessment_builds_profile_and_foundation_stage():
    db = AsyncMock()
    plan = MagicMock()
    plan.roadmap = {
        "goal": "I want an ML engineer job abroad",
        "goal_brief": {
            "primary_goal": "I want an ML engineer job abroad",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "target_market": "international_company",
            "deadline_type": "open_ended",
            "main_contexts": ["interviews", "project_walkthrough"],
            "current_blockers": [],
            "motivation": "Use English to unlock a better career outcome.",
            "confidence": 0.9,
            "status": "confirmed",
            "summary": "summary",
        },
        "focus_areas": [],
        "milestones": [{"name": "Complete assessment", "type": "assessment", "done": False}],
    }

    service = LearningPlanService(db)
    service.get_or_create_plan = AsyncMock(return_value=plan)

    await service.record_assessment(
        1,
        assessed_level="B1",
        scores={"fluency": 0.48, "grammar": 0.44, "vocabulary": 0.52, "comprehension": 0.5},
    )

    assert plan.roadmap["proficiency_profile"]["cefr_level"] == "B1"
    assert plan.roadmap["proficiency_profile"]["goal_readiness"] is not None
    assert plan.roadmap["program_plan"]["current_stage"] == "foundation"


def test_get_goal_setup_missing_returns_human_labels():
    plan = MagicMock()
    plan.roadmap = {
        "goal": "Improve English",
        "goal_brief": {"primary_goal": "Improve English", "status": "incomplete"},
    }
    service = LearningPlanService(AsyncMock())

    missing = service.get_goal_setup_missing(plan)

    assert "target role" in missing
    assert "target company context" in missing
