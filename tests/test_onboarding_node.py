import pytest

from app.agent.nodes_v2.onboarding import (
    _apply_onboarding_action,
    _coerce_goal_brief_state,
    _infer_goal_brief_from_message,
)
from app.agent.state import AgentPhase, create_initial_state


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

    assert updated["current_phase"] == AgentPhase.ONBOARDING
    assert "quick speaking baseline" in updated["pending_response"]


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
