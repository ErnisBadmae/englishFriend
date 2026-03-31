import pytest

from app.agent.nodes_v2.onboarding import _apply_onboarding_action, _coerce_goal_brief_state
from app.agent.state import AgentPhase, create_initial_state


def test_coerce_goal_brief_requires_domain_and_timeline():
    brief = _coerce_goal_brief_state(
        {
            "primary_goal": "Get an ML role abroad",
            "target_role": "ML Engineer",
            "target_market": "international_company",
            "main_contexts": ["interviews"],
        }
    )

    assert brief["status"] == "incomplete"


@pytest.mark.asyncio
async def test_transition_to_learning_is_blocked_until_goal_setup_complete():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Get an ML role abroad",
        "target_role": "ML Engineer",
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
    assert "Which domain should the program optimize for" in updated["pending_response"]
