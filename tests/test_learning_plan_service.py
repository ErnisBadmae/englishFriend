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
    assert plan.roadmap["goal_brief"]["status"] == "draft"
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


@pytest.mark.asyncio
async def test_record_assessment_can_store_provisional_status():
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
            "status": "draft",
            "summary": "summary",
        },
        "focus_areas": [],
        "milestones": [{"name": "Complete assessment", "type": "assessment", "done": False}],
    }

    service = LearningPlanService(db)
    service.get_or_create_plan = AsyncMock(return_value=plan)

    await service.record_assessment(
        1,
        assessed_level="A2",
        scores={"fluency": 3.8, "grammar": 3.7, "vocabulary": 4.2, "comprehension": 4.5},
        provisional=True,
        confidence_override=0.44,
    )

    assert plan.roadmap["proficiency_profile"]["status"] == "provisional"
    assert plan.roadmap["proficiency_profile"]["provisional"] is True
    assert plan.roadmap["proficiency_profile"]["confidence"] == 0.44


def test_get_goal_setup_missing_returns_human_labels():
    plan = MagicMock()
    plan.roadmap = {
        "goal": "Improve English",
        "goal_brief": {"primary_goal": "Improve English", "status": "incomplete"},
    }
    service = LearningPlanService(AsyncMock())

    missing = service.get_goal_setup_missing(plan)

    assert "target role" in missing
    assert "domain" in missing
    assert "target company context" in missing
    assert "timeline" in missing


def test_get_program_plan_returns_default_shell_for_empty_roadmap():
    plan = MagicMock()
    plan.roadmap = {}
    service = LearningPlanService(AsyncMock())

    program = service.get_program_plan(plan)

    assert program is not None
    assert program["current_stage"] == "goal_setup"
    assert program["title"] == "Complete your career English setup"
    assert program["preferred_mode"] == "free_conversation"
    assert program["focus_areas"] == []


def test_get_program_plan_normalizes_legacy_shell_for_new_user():
    plan = MagicMock()
    plan.roadmap = {
        "preferred_mode": "free_conversation",
        "focus_areas": [],
        "program_plan": {
            "title": "Complete your career English setup",
            "time_horizon_days": 90,
            "current_stage": "goal_setup",
            "stage_label": "Goal Setup",
            "weekly_focus": ["Clarify your target role and context"],
            "success_metric": "Turn a vague goal into a concrete target",
            "next_milestone": "Confirm your goal",
            "stages": [],
        },
    }
    service = LearningPlanService(AsyncMock())

    program = service.get_program_plan(plan)

    assert program is not None
    assert program["preferred_mode"] == "free_conversation"
    assert program["focus_areas"] == []
    assert "stages" in program


@pytest.mark.asyncio
async def test_set_goal_requires_domain_and_timeline_before_completion():
    db = AsyncMock()
    plan = MagicMock()
    plan.roadmap = {}
    plan.level_target = None

    service = LearningPlanService(db)
    service.get_or_create_plan = AsyncMock(return_value=plan)

    await service.set_goal(
        1,
        "I want better English at work",
        goal_brief={
            "primary_goal": "Speak better at work",
            "target_role": "Specialist",
            "target_market": "international_company",
            "main_contexts": ["interviews", "project_walkthrough"],
        },
    )

    assert plan.roadmap["goal_brief"]["status"] == "incomplete"
    assert plan.roadmap["program_plan"]["current_stage"] == "goal_setup"


@pytest.mark.asyncio
async def test_set_goal_preserves_confirmed_status_when_user_confirmed():
    db = AsyncMock()
    plan = MagicMock()
    plan.roadmap = {}
    plan.level_target = None

    service = LearningPlanService(db)
    service.get_or_create_plan = AsyncMock(return_value=plan)

    await service.set_goal(
        1,
        "I want an ML engineer job abroad",
        goal_brief={
            "primary_goal": "Get an ML engineer role abroad",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "target_market": "international_company",
            "deadline_type": "medium_3_6m",
            "main_contexts": ["interviews", "project_walkthrough"],
            "confirmed_by_user": True,
        },
    )

    assert plan.roadmap["goal_brief"]["status"] == "confirmed"
    assert plan.roadmap["program_plan"]["current_stage"] == "baseline_assessment"


@pytest.mark.asyncio
async def test_record_session_evidence_saves_generic_guided_result():
    db = AsyncMock()
    plan = MagicMock()
    plan.roadmap = {}

    service = LearningPlanService(db)
    service.get_or_create_plan = AsyncMock(return_value=plan)

    evidence = await service.record_session_evidence(
        user_id=1,
        session_id="sess-1",
        mode="free_conversation",
        duration_minutes=8,
        conversation_history=[
            {"role": "assistant", "content": "Tell me about your work."},
            {"role": "user", "content": "I build machine learning pipelines."},
            {"role": "assistant", "content": "What was hard?"},
            {"role": "user", "content": "Explaining trade-offs clearly."},
        ],
        corrections_made=[{"type": "articles", "original": "a architecture", "corrected": "an architecture"}],
        vocabulary_reviewed=[{"word": "trade-off"}],
    )

    assert evidence is not None
    assert evidence["session_id"] == "sess-1"
    assert evidence["mission_type"] == "free_conversation"
    assert "articles" in str(evidence["main_issue"])
    assert plan.roadmap["session_evidence"][0]["session_id"] == "sess-1"


@pytest.mark.asyncio
async def test_record_session_evidence_deduplicates_by_session_id():
    db = AsyncMock()
    existing = {
        "id": "sess-1",
        "session_id": "sess-1",
        "mission_type": "assessment",
        "mission_title": "Baseline assessment",
        "summary": "Already saved",
        "what_was_trained": "Baseline",
        "what_went_well": [],
        "main_issue": None,
        "next_focus": [],
        "evidence_signals": [],
        "recorded_at": "2026-04-01T10:00:00",
        "duration_minutes": 6,
    }
    plan = MagicMock()
    plan.roadmap = {"session_evidence": [existing]}

    service = LearningPlanService(db)
    service.get_or_create_plan = AsyncMock(return_value=plan)

    evidence = await service.record_session_evidence(
        user_id=1,
        session_id="sess-1",
        mode="assessment",
        assessed_level="B1",
    )

    assert evidence == existing
    assert plan.roadmap["session_evidence"] == [existing]


@pytest.mark.asyncio
async def test_set_vacancy_context_builds_career_context_and_interview_pack():
    db = AsyncMock()
    plan = MagicMock()
    plan.roadmap = {
        "goal": "Prepare for an ML role abroad",
        "goal_brief": {
            "primary_goal": "Prepare for an ML role abroad",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "target_market": "international_company",
            "deadline_type": "open_ended",
            "main_contexts": ["interviews"],
            "status": "draft",
        },
        "recommended_vocabulary": ["deployment"],
    }
    plan.level_target = None

    service = LearningPlanService(db)
    service.get_or_create_plan = AsyncMock(return_value=plan)

    await service.set_vacancy_context(
        1,
        "We are hiring an ML Engineer to deploy machine learning models, explain trade-offs, "
        "work with cross-functional stakeholders, and own model performance in production.",
    )

    assert plan.roadmap["career_context"]["vacancy_present"] is True
    assert plan.roadmap["career_context"]["target_role"] == "ML Engineer"
    assert plan.roadmap["interview_pack"]["recommended_track"] == "project_walkthrough"
    assert "deployment" in plan.roadmap["interview_pack"]["key_terms"]
    assert plan.roadmap["preferred_mode"] == "mock_interview"


@pytest.mark.asyncio
async def test_record_paid_intent_stores_latest_signal():
    db = AsyncMock()
    plan = MagicMock()
    plan.roadmap = {
        "goal": "Prepare for an ML role abroad",
        "proficiency_profile": {"goal_readiness": 6.4},
        "sessions_completed": 3,
        "interview_runs": [{"id": "run-1"}],
    }

    service = LearningPlanService(db)
    service.get_or_create_plan = AsyncMock(return_value=plan)

    signal = await service.record_paid_intent(1, source="home_cta", note="Looks useful")

    assert signal["source"] == "home_cta"
    assert signal["readiness_score"] == 6.4
    assert plan.roadmap["latest_paid_intent"]["source"] == "home_cta"
    assert plan.roadmap["paid_intents"][0]["note"] == "Looks useful"
