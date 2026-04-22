from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.program_snapshot_service import (
    ProgramSnapshotService,
    build_latest_assessment,
    build_improvement_signals,
    build_setup_state,
    extract_focus_areas,
    recommend_next_mission,
)


def test_build_latest_assessment_prefers_proficiency_profile():
    roadmap = {
        "last_assessment": "2026-03-31T10:00:00",
        "proficiency_profile": {
            "cefr_level": "B1",
            "fluency": 5.2,
            "grammar_accuracy": 4.8,
            "professional_vocabulary": 5.6,
            "listening_comprehension": 5.1,
            "goal_readiness": 4.9,
            "confidence": 0.71,
            "status": "provisional",
            "provisional": True,
            "source": "embedded_first_mission",
            "critical_gaps": ["Structured interview answers"],
        },
    }

    latest = build_latest_assessment(roadmap)

    assert latest is not None
    assert latest["level"] == "B1"
    assert latest["goal_readiness"] == 4.9
    assert latest["status"] == "provisional"
    assert latest["provisional"] is True
    assert latest["source"] == "embedded_first_mission"
    assert latest["critical_gaps"] == ["Structured interview answers"]


def test_extract_focus_areas_prefers_descriptions():
    roadmap = {
        "focus_areas": [
            {"area": "behavioral_questions", "description": "STAR answers"},
            {"area": "technical_vocabulary"},
        ]
    }
    assert extract_focus_areas(roadmap) == ["STAR answers", "technical_vocabulary"]


def test_recommend_next_mission_requires_goal_setup_before_anything_else():
    mission = recommend_next_mission(
        goal_brief={"primary_goal": "Improve English", "status": "incomplete"},
        program_plan=None,
        due_count=9,
        error_patterns=[],
        has_assessment=False,
    )

    assert mission["mode"] == "guided_setup"
    assert mission["launch_mode"] is None
    assert mission["task_type"] == "goal_setup"
    assert mission["estimated_minutes"] == 4


def test_recommend_next_mission_starts_first_useful_mission_after_draft_goal():
    mission = recommend_next_mission(
        goal_brief={
            "primary_goal": "Get an ML role abroad",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "target_market": "international_company",
            "deadline_type": "medium_3_6m",
            "main_contexts": ["interviews"],
            "status": "draft",
        },
        program_plan={"current_stage": "first_useful_mission", "weekly_focus": []},
        due_count=0,
        error_patterns=[],
        has_assessment=False,
    )

    assert mission["mode"] == "free_conversation"
    assert mission["launch_mode"] == "free_conversation"
    # primary_context=interviews → foundation speaking drill, not a
    # domain-driven technical walkthrough.
    assert mission["task_type"] == "foundation_speaking_drill"
    assert "baseline" in mission["why_now"].lower()


def test_recommend_next_mission_prefers_vocab_when_latest_interview_gap_is_vocab():
    mission = recommend_next_mission(
        goal_brief={
            "primary_goal": "Get a software role abroad",
            "target_role": "Software Engineer",
            "domain": "software_engineering",
            "target_market": "international_company",
            "deadline_type": "medium_3_6m",
            "main_contexts": ["interviews", "project_walkthrough"],
            "status": "confirmed",
        },
        program_plan={"current_stage": "career_scenarios", "weekly_focus": ["Explain architecture trade-offs"]},
        due_count=0,
        error_patterns=[],
        has_assessment=True,
        weakest_interview_area="vocabulary",
    )

    assert mission["mode"] == "vocabulary_drill"
    assert mission["from_interview"] is True
    assert mission["task_type"] == "vocabulary_reinforcement"


def test_recommend_next_mission_maps_structure_gap_to_star_drill():
    mission = recommend_next_mission(
        goal_brief={
            "primary_goal": "Get an ML role abroad",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "target_market": "international_company",
            "deadline_type": "medium_3_6m",
            "main_contexts": ["interviews", "project_walkthrough"],
            "status": "confirmed",
        },
        program_plan={"current_stage": "career_scenarios", "weekly_focus": ["Explain trade-offs clearly"]},
        due_count=8,
        error_patterns=[],
        has_assessment=True,
        weakest_interview_area="structure",
    )

    assert mission["mode"] == "mock_interview"
    assert mission["from_interview"] is True
    assert mission["interview_track_id"] == "hr_intro"
    assert mission["success_signal"]


def test_recommend_next_mission_maps_accuracy_gap_to_grammar_focus():
    mission = recommend_next_mission(
        goal_brief={
            "primary_goal": "Get an ML role abroad",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "target_market": "international_company",
            "deadline_type": "medium_3_6m",
            "main_contexts": ["interviews", "project_walkthrough"],
            "status": "confirmed",
        },
        program_plan={"current_stage": "career_scenarios", "weekly_focus": ["Explain trade-offs clearly"]},
        due_count=0,
        error_patterns=[],
        has_assessment=True,
        weakest_interview_area="accuracy",
    )

    assert mission["mode"] == "free_conversation"
    assert mission["linked_skill_gap"] == "grammar_accuracy"
    assert mission["task_type"] == "grammar_rescue"


def test_recommend_next_mission_uses_foundation_stage_for_speaking_drill():
    mission = recommend_next_mission(
        goal_brief={
            "primary_goal": "Get an ML role abroad",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "target_market": "international_company",
            "deadline_type": "medium_3_6m",
            "main_contexts": ["interviews", "project_walkthrough"],
            "status": "confirmed",
        },
        program_plan={
            "current_stage": "foundation",
            "weekly_focus": ["Build short, accurate answers about your background"],
            "preferred_mode": "free_conversation",
        },
        due_count=0,
        error_patterns=[{"label": "articles", "count": 5}],
        has_assessment=True,
        weakest_interview_area=None,
        session_evidence=[{"mission_type": "free_conversation"}],
        interview_runs_count=1,
    )

    assert mission["mode"] == "free_conversation"
    assert "foundation" in mission["linked_goal_context"]
    assert mission["estimated_minutes"] == 9


def test_recommend_next_mission_repeats_when_same_issue_plateaus():
    mission = recommend_next_mission(
        goal_brief={
            "primary_goal": "Get an ML role abroad",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "target_market": "international_company",
            "deadline_type": "medium_3_6m",
            "main_contexts": ["project_walkthrough", "interviews"],
            "status": "confirmed",
        },
        program_plan={
            "current_stage": "career_scenarios",
            "weekly_focus": ["Explain one project with trade-offs and impact"],
            "preferred_mode": "free_conversation",
        },
        due_count=0,
        error_patterns=[],
        has_assessment=True,
        session_evidence=[
            {
                "mission_type": "free_conversation",
                "mode": "free_conversation",
                "task_type": "project_walkthrough_drill",
                "mission_title": "Walk through one technical project",
                "linked_goal_context": "project_walkthrough",
                "outcome_score": 0.48,
                "weakness_tags": ["impact is still vague"],
                "adaptation_hint": "Repeat the same drill once more and stay narrow around impact is still vague.",
                "duration_minutes": 10,
            },
            {
                "mission_type": "free_conversation",
                "mode": "free_conversation",
                "task_type": "project_walkthrough_drill",
                "mission_title": "Walk through one technical project",
                "linked_goal_context": "project_walkthrough",
                "outcome_score": 0.47,
                "weakness_tags": ["impact is still vague"],
                "duration_minutes": 10,
            },
        ],
        interview_runs_count=1,
    )

    assert mission["task_type"] == "project_walkthrough_drill"
    assert mission["repeat_vs_advance"] == "repeat"
    assert mission["evidence_source"] == "repeated_main_issue"
    assert "impact is still vague" in mission["reason"].lower()


def test_recommend_next_mission_marks_advance_when_recent_score_improves():
    mission = recommend_next_mission(
        goal_brief={
            "primary_goal": "Get an ML role abroad",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "target_market": "international_company",
            "deadline_type": "medium_3_6m",
            "main_contexts": ["interviews", "project_walkthrough"],
            "status": "confirmed",
        },
        program_plan={
            "current_stage": "foundation",
            "weekly_focus": ["Build short, accurate answers about your background"],
            "preferred_mode": "free_conversation",
        },
        due_count=0,
        error_patterns=[],
        has_assessment=True,
        session_evidence=[
            {
                "mission_type": "free_conversation",
                "mode": "free_conversation",
                "task_type": "foundation_speaking_drill",
                "mission_title": "Run a foundation speaking drill",
                "outcome_score": 0.71,
                "weakness_tags": ["article usage"],
            },
            {
                "mission_type": "free_conversation",
                "mode": "free_conversation",
                "task_type": "foundation_speaking_drill",
                "mission_title": "Run a foundation speaking drill",
                "outcome_score": 0.55,
                "weakness_tags": ["article usage"],
            },
        ],
        interview_runs_count=1,
    )

    assert mission["task_type"] == "foundation_speaking_drill"
    assert mission["repeat_vs_advance"] == "advance"
    assert mission["adaptation_reason"]


@pytest.mark.parametrize(
    ("main_contexts", "expected_task_type", "expected_context"),
    [
        (["workplace_communication", "project_walkthrough"], "stakeholder_explanation_drill", "workplace_communication"),
        (["interviews", "project_walkthrough"], "foundation_speaking_drill", "interviews"),
        (["project_walkthrough", "interviews"], "technical_project_walkthrough", "project_walkthrough"),
    ],
)
def test_recommend_next_mission_entry_respects_primary_context(main_contexts, expected_task_type, expected_context):
    mission = recommend_next_mission(
        goal_brief={
            "primary_goal": "Get an ML role abroad",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "target_market": "international_company",
            "deadline_type": "medium_3_6m",
            "main_contexts": main_contexts,
            "status": "confirmed",
        },
        program_plan={
            "current_stage": "foundation",
            "weekly_focus": ["Start with the primary scenario that matters most right now"],
            "preferred_mode": "free_conversation",
        },
        due_count=0,
        error_patterns=[],
        has_assessment=True,
        weakest_interview_area=None,
        interview_pack={
            "recommended_track": "project_walkthrough",
            "recommended_track_title": "Project Walkthrough",
            "summary": "Stale pack should not override the first mission.",
        },
        session_evidence=[{"mission_type": "assessment"}],
        interview_runs_count=0,
    )

    assert mission["task_type"] == expected_task_type
    assert mission["linked_goal_context"] == expected_context


def test_recommend_next_mission_uses_metrics_drill_for_ml_foundation_focus():
    mission = recommend_next_mission(
        goal_brief={
            "primary_goal": "Get an ML role abroad",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "target_market": "international_company",
            "deadline_type": "medium_3_6m",
            "main_contexts": ["interviews", "project_walkthrough"],
            "status": "confirmed",
        },
        program_plan={
            "current_stage": "foundation",
            "weekly_focus": ["Explain metrics and why you chose them"],
            "preferred_mode": "free_conversation",
        },
        due_count=0,
        error_patterns=[],
        has_assessment=True,
        weakest_interview_area=None,
        interview_pack=None,
        session_evidence=[{"mission_type": "free_conversation"}],
        interview_runs_count=1,
    )

    assert mission["mode"] == "free_conversation"
    assert mission["task_type"] == "metrics_explainer"
    assert "metric" in mission["title"].lower()


def test_recommend_next_mission_uses_tradeoff_drill_for_ml_scenario_focus():
    mission = recommend_next_mission(
        goal_brief={
            "primary_goal": "Get an ML role abroad",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "target_market": "international_company",
            "deadline_type": "medium_3_6m",
            "main_contexts": ["interviews", "project_walkthrough"],
            "status": "confirmed",
        },
        program_plan={
            "current_stage": "career_scenarios",
            "weekly_focus": ["Defend ML decisions with trade-offs, metrics, and impact"],
            "preferred_mode": "mock_interview",
        },
        due_count=0,
        error_patterns=[],
        has_assessment=True,
        weakest_interview_area=None,
        interview_pack=None,
        session_evidence=[{"mission_type": "free_conversation"}],
        interview_runs_count=1,
    )

    assert mission["mode"] == "free_conversation"
    assert mission["task_type"] == "tradeoff_explanation_drill"
    assert "trade" in mission["reason"].lower()


def test_recommend_next_mission_prefers_stakeholder_drill_for_workplace_first_context():
    mission = recommend_next_mission(
        goal_brief={
            "primary_goal": "Speak better in an international ML team",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "target_market": "international_company",
            "deadline_type": "open_ended",
            "main_contexts": ["workplace_communication", "project_walkthrough"],
            "status": "confirmed",
        },
        program_plan={
            "current_stage": "foundation",
            "weekly_focus": ["Defend ML decisions with trade-offs, metrics, and impact"],
            "preferred_mode": "free_conversation",
        },
        due_count=0,
        error_patterns=[],
        has_assessment=True,
        weakest_interview_area=None,
        interview_pack={
            "summary": "Interview prep for ML Engineer.",
            "top_blockers": ["Need clear project walkthroughs with metrics and trade-offs"],
            "must_answer_questions": ["Why are you a strong fit for this ML Engineer role?"],
            "project_story_prompts": ["Explain one ML project: business problem, model choice, metric, trade-offs, impact."],
        },
    )

    assert mission["mode"] == "free_conversation"
    assert mission["task_type"] == "stakeholder_explanation_drill"
    assert mission["linked_goal_context"] == "workplace_communication"


def test_recommend_next_mission_maps_workplace_track_to_stakeholder_drill_for_career_stage():
    mission = recommend_next_mission(
        goal_brief={
            "primary_goal": "Speak better in an international ML team",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "target_market": "international_company",
            "deadline_type": "open_ended",
            "main_contexts": ["workplace_communication", "project_walkthrough"],
            "status": "confirmed",
        },
        program_plan={
            "current_stage": "career_scenarios",
            "weekly_focus": ["Practice standups, blockers, and stakeholder updates"],
            "preferred_mode": "mock_interview",
        },
        due_count=0,
        error_patterns=[],
        has_assessment=True,
        weakest_interview_area=None,
        interview_pack={
            "recommended_track": "workplace_communication",
            "recommended_track_title": "Workplace Communication",
            "summary": "Focus on clear stakeholder-facing updates.",
            "top_blockers": ["Need clearer stakeholder updates"],
        },
        session_evidence=[{"mission_type": "free_conversation"}],
        interview_runs_count=1,
    )

    assert mission["mode"] == "mock_interview"
    assert mission["interview_track_id"] == "workplace_communication"
    assert mission["task_type"] == "stakeholder_explanation_drill"
    assert mission["linked_goal_context"] == "workplace_communication"


def test_recommend_next_mission_uses_interview_pack_track_for_career_stage():
    mission = recommend_next_mission(
        goal_brief={
            "primary_goal": "Get an ML role abroad",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "target_market": "international_company",
            "deadline_type": "medium_3_6m",
            "main_contexts": ["interviews", "project_walkthrough"],
            "status": "confirmed",
        },
        program_plan={
            "current_stage": "career_scenarios",
            "weekly_focus": ["Explain one project with trade-offs and impact"],
            "preferred_mode": "mock_interview",
        },
        due_count=0,
        error_patterns=[],
        has_assessment=True,
        weakest_interview_area=None,
        interview_pack={
            "recommended_track": "project_walkthrough",
            "recommended_track_title": "Project Walkthrough",
            "summary": "ML Engineer role with focus on project explanation and stakeholder clarity.",
            "top_blockers": ["Need clear project walkthroughs with metrics and trade-offs"],
        },
        session_evidence=[{"mission_type": "free_conversation"}],
        interview_runs_count=1,
    )

    assert mission["mode"] == "mock_interview"
    assert mission["interview_track_id"] == "project_walkthrough"
    assert mission["task_type"] == "project_walkthrough_drill"
    assert "blocker" in mission["why_now"].lower()


def test_build_setup_state_guides_user_through_sequence():
    assert build_setup_state(goal_status="incomplete", assessment_complete=False) == "needs_goal"
    assert build_setup_state(goal_status="draft", assessment_complete=False) == "needs_first_mission"
    assert build_setup_state(goal_status="confirmed", assessment_complete=True) == "ready_for_program"


def test_build_improvement_signals_combines_product_evidence():
    signals = build_improvement_signals(
        interview_summary={
            "latest_run": {"delta_vs_previous": 0.8},
        },
        pronunciation_summary={
            "latest_score": 6.4,
            "focus": ["Short vowels still collapse in fast speech."],
        },
        session_evidence=[
            {
                "summary": "You practiced one guided mission.",
                "main_issue": "articles",
            }
        ],
        latest_assessment={"goal_readiness": 5.6},
        milestones=[{"name": "Complete assessment", "done": True}],
    )

    assert any("Interview score moved up 0.8" in item for item in signals)
    assert any("Speech signal is 6.4/10" in item for item in signals)
    assert any("articles" in item for item in signals)
    assert any("Complete assessment" in item for item in signals)


@pytest.mark.asyncio
async def test_get_snapshot_reconciles_stale_interview_pack_with_primary_context():
    db = AsyncMock()
    user = MagicMock(id=1, telegram_id=1001, username="learner", language_level="B1")
    db.get = AsyncMock(return_value=user)

    goal_brief = {
        "primary_goal": "Speak better in an international ML team",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["workplace_communication", "project_walkthrough"],
        "status": "confirmed",
    }
    program_plan = {
        "current_stage": "career_scenarios",
        "weekly_focus": ["Practice standups, blockers, and stakeholder updates"],
        "preferred_mode": "mock_interview",
    }
    stale_pack = {
        "recommended_track": "project_walkthrough",
        "recommended_track_title": "Project Walkthrough",
        "summary": "Stale pack summary",
        "top_blockers": ["Need one stronger interview answer before the next run."],
    }
    plan = MagicMock()
    plan.level_target = None
    plan.roadmap = {
        "goal": goal_brief["primary_goal"],
        "goal_brief": goal_brief,
        "program_plan": program_plan,
        "career_context": {"target_role": "ML Engineer"},
        "interview_pack": stale_pack,
        "last_assessment": "2026-03-31T10:00:00",
        "proficiency_profile": {
            "cefr_level": "B1",
            "goal_readiness": 6.1,
            "status": "confirmed",
            "provisional": False,
            "critical_gaps": [],
        },
        "session_evidence": [
            {
                "mission_type": "free_conversation",
                "mission_title": "Previous mission",
                "summary": "Already in the main loop.",
            }
        ],
        "interview_runs": [],
    }

    service = ProgramSnapshotService(db)
    service.learning_plan_service.get_or_create_plan = AsyncMock(return_value=plan)
    service.learning_plan_service.get_goal_brief = MagicMock(return_value=goal_brief)
    service.learning_plan_service.get_program_plan = MagicMock(return_value=program_plan)
    service.learning_plan_service.get_career_context = MagicMock(return_value={"target_role": "ML Engineer"})
    service.learning_plan_service.get_interview_pack = MagicMock(return_value=stale_pack)
    service.learning_plan_service.get_session_evidence = MagicMock(return_value=plan.roadmap["session_evidence"])
    service.learning_plan_service.get_goal = MagicMock(return_value=goal_brief["primary_goal"])
    service.learning_plan_service.get_current_level = MagicMock(return_value="B1")
    service.learning_plan_service.get_preferred_mode = MagicMock(return_value="mock_interview")
    service.learning_plan_service.get_goal_setup_missing = MagicMock(return_value=[])
    service.learning_plan_service.is_goal_setup_complete = MagicMock(return_value=True)
    service.learning_plan_service.get_session_count = MagicMock(return_value=1)
    service.learning_plan_service.get_recommended_vocabulary = MagicMock(return_value=[])

    service.vocabulary_service.get_vocabulary_stats = AsyncMock(return_value={"due_now": 0})
    service.vocabulary_service.get_due_cards = AsyncMock(return_value=[])
    service.xp_service.get_level_info = AsyncMock(return_value={"level": 1})
    service.streak_service.get_streak_info = AsyncMock(return_value={"current": 1})
    service._get_top_error_patterns = AsyncMock(return_value=[])
    service._get_recent_sessions = AsyncMock(return_value=[])
    service._get_total_sessions = AsyncMock(return_value=1)

    snapshot = await service.get_snapshot(1)

    assert snapshot is not None
    assert snapshot["goal"]["brief"]["main_contexts"][0] == "workplace_communication"
    assert snapshot["interview"]["recommended_track"]["id"] == "workplace_communication"
    assert snapshot["mission"]["interview_track_id"] == "workplace_communication"
    assert snapshot["mission"]["task_type"] == "stakeholder_explanation_drill"
    assert snapshot["mission"]["linked_goal_context"] == "workplace_communication"
