import pytest

from app.agent.nodes_v2.onboarding import (
    _apply_onboarding_action,
    _build_assessment_followup_question,
    _coerce_goal_brief_state,
    _infer_goal_brief_from_message,
    onboarding_node,
)
from app.agent.graph_v2 import initialize_session_v2
from app.agent.state import AgentPhase, LearningModeEnum, create_initial_state


def test_coerce_goal_brief_marks_routing_ready_goal_as_draft():
    brief = _coerce_goal_brief_state(
        {
            "primary_goal": "Get an ML role abroad",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "target_market": "international_company",
            "main_contexts": ["interviews"],
        }
    )

    assert brief["status"] == "draft"


def test_infer_goal_brief_from_noisy_ml_input_creates_draft():
    brief = _infer_goal_brief_from_message(
        "wanna improve vocabulary machine learning and pass interview for job abroad"
    )

    assert brief is not None
    assert brief["target_role"] == "ML Engineer"
    assert brief["domain"] == "machine_learning"
    assert brief["target_market"] == "international_company"
    assert "interviews" in brief["main_contexts"]
    assert brief["status"] == "draft"


def test_infer_goal_brief_accepts_doesnt_matter_as_company_context():
    brief = _infer_goal_brief_from_message(
        "doesnt matter for me whatever company, I just want machine learning interview practice",
        {
            "primary_goal": "Get an ML role abroad",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "main_contexts": ["interviews"],
        },
    )

    assert brief is not None
    assert brief["target_market"] == "international_company"
    assert brief["status"] == "draft"


@pytest.mark.asyncio
async def test_transition_to_learning_moves_routing_ready_goal_to_assessment():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Get an ML role abroad",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "main_contexts": ["interviews"],
        "status": "incomplete",
    }
    state["confirmed_goal"] = "Get an ML role abroad"
    state["goal_setup_complete"] = False

    updated = await _apply_onboarding_action(
        state,
        {"action": "transition_to_learning", "response_text": "Let's begin."},
        pedagogy=None,
    )

    assert updated["current_phase"] == AgentPhase.ASSESSMENT
    assert "one short speaking baseline" in updated["pending_response"].lower()


@pytest.mark.asyncio
async def test_goal_skipped_keeps_draft_and_moves_to_assessment():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["last_user_message"] = "I want a machine learning job abroad and need interview English"
    state["goal_brief"] = {
        "primary_goal": "Build English for an international ML/AI role with stronger interview and project communication.",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews", "project_walkthrough"],
        "status": "draft",
    }
    state["goal_setup_complete"] = True

    updated = await _apply_onboarding_action(
        state,
        {"action": "goal_skipped", "response_text": "skip"},
        pedagogy=None,
    )

    assert updated["goal_brief"]["status"] == "draft"
    assert updated["goal_setup_complete"] is True
    assert "One quick baseline first" in updated["pending_response"]


@pytest.mark.asyncio
async def test_transition_to_learning_allows_draft_goal_with_assessment():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Get an ML role abroad",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews", "project_walkthrough"],
        "status": "draft",
    }
    state["detected_goal"] = "Get an ML role abroad"
    state["goal_setup_complete"] = True
    state["assessed_level"] = "B1"

    updated = await _apply_onboarding_action(
        state,
        {"action": "transition_to_learning", "response_text": "Let's begin."},
        pedagogy=None,
    )

    assert updated["current_phase"] == AgentPhase.LEARNING_SESSION


def test_build_assessment_followup_question_is_short_for_draft_goal():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Get an ML role abroad",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews", "project_walkthrough"],
        "status": "draft",
    }

    prompt = _build_assessment_followup_question(state)

    assert "what do you do now?" in prompt.lower()
    assert "what role are you aiming for" not in prompt.lower()


@pytest.mark.asyncio
async def test_initialize_session_v2_treats_draft_goal_as_setup_complete():
    state = await initialize_session_v2(
        user_id=1,
        session_id="session-1",
        username="Student",
        is_new_user=False,
        language_level="B1",
        roadmap={
            "goal_brief": {
                "primary_goal": "Get an ML role abroad",
                "target_role": "ML Engineer",
                "domain": "machine_learning",
                "target_market": "international_company",
                "deadline_type": "open_ended",
                "main_contexts": ["interviews"],
                "status": "draft",
            }
        },
    )

    assert state["goal_setup_complete"] is True


@pytest.mark.asyncio
async def test_onboarding_baseline_counts_turns_and_updates_history():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Get an ML role abroad",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews", "project_walkthrough"],
        "status": "draft",
    }
    state["goal_setup_complete"] = True
    state["last_user_message"] = "I build machine learning models at work."

    updated = await onboarding_node(state)

    assert updated["turn_count"] == 1
    assert updated["current_mode"] == LearningModeEnum.ASSESSMENT
    assert updated["conversation_history"][0]["role"] == "user"
    assert updated["conversation_history"][-1]["role"] == "assistant"
    assert "what role do you want" in updated["pending_response"].lower()


@pytest.mark.asyncio
async def test_onboarding_meta_answer_produces_provisional_baseline_instead_of_loop():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Get an ML role abroad",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews", "project_walkthrough"],
        "status": "draft",
    }
    state["goal_setup_complete"] = True
    state["current_mode"] = LearningModeEnum.ASSESSMENT
    state["assessment_step_index"] = 1
    state["assessment_answers"] = {"current_role": "I build machine learning models at work."}
    state["last_user_message"] = "I am waiting that you prepare my program."

    updated = await onboarding_node(state)

    assert updated["assessed_level"] in {"A2", "B1"}
    assert updated["baseline_provisional"] is True
    assert updated["assessment_status"] == "provisional"
    assert "what do you do now?" not in updated["pending_response"].lower()
