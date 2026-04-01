from app.services.program_snapshot_service import (
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
            "critical_gaps": ["Structured interview answers"],
        },
    }

    latest = build_latest_assessment(roadmap)

    assert latest is not None
    assert latest["level"] == "B1"
    assert latest["goal_readiness"] == 4.9
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


def test_recommend_next_mission_requests_assessment_after_draft_goal():
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
        program_plan={"current_stage": "baseline_assessment", "weekly_focus": []},
        due_count=0,
        error_patterns=[],
        has_assessment=False,
    )

    assert mission["mode"] == "assessment"
    assert mission["launch_mode"] == "assessment"
    assert mission["task_type"] == "baseline_assessment"


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
    )

    assert mission["mode"] == "free_conversation"
    assert "foundation" in mission["linked_goal_context"]
    assert mission["estimated_minutes"] == 9


def test_build_setup_state_guides_user_through_sequence():
    assert build_setup_state(goal_status="incomplete", assessment_complete=False) == "needs_goal"
    assert build_setup_state(goal_status="draft", assessment_complete=False) == "needs_assessment"
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
