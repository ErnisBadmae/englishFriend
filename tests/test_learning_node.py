from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.graph_v2 import initialize_session_v2
from app.agent.nodes_v2.learning import learning_node
from app.agent.state import AgentPhase, LearningModeEnum, create_initial_state


def _foundation_state() -> dict:
    state = create_initial_state(user_id=1, session_id="learning-session")
    state["current_phase"] = AgentPhase.LEARNING_SESSION
    state["current_mode"] = LearningModeEnum.FREE_CONVERSATION
    state["confirmed_goal"] = "Get an ML role abroad"
    state["goal_setup_complete"] = True
    state["assessed_level"] = "B1"
    state["mission_task_type"] = "foundation_speaking_drill"
    state["mission_title"] = "Run a foundation speaking drill"
    state["mission_reason"] = "Stabilize grammar and fluency before higher-pressure scenarios."
    state["mission_success_signal"] = "You can answer in English with fewer corrections and clearer delivery."
    state["mission_linked_goal_context"] = "foundation"
    return state


@pytest.mark.asyncio
async def test_initialize_session_v2_infers_foundation_mission_context():
    state = await initialize_session_v2(
        user_id=1,
        session_id="session-1",
        username="Student",
        is_new_user=False,
        language_level="B1",
        explicit_mode="free_conversation",
        roadmap={
            "program_plan": {
                "current_stage": "foundation",
                "weekly_focus": ["Stabilize grammar, fluency, and core workplace answers"],
            }
        },
    )

    assert state["mission_task_type"] == "foundation_speaking_drill"
    assert state["mission_title"] == "Run a foundation speaking drill"
    assert state["mission_linked_goal_context"] == "foundation"


@pytest.mark.asyncio
async def test_learning_node_uses_mission_opener_without_llm():
    state = _foundation_state()

    llm = MagicMock()
    llm.generate = AsyncMock()
    prompt_service = MagicMock()
    prompt_service.log_usage = AsyncMock()

    with patch("app.agent.nodes_v2.learning.get_llm_provider", return_value=llm), patch(
        "app.agent.nodes_v2.learning.get_prompt_service",
        return_value=prompt_service,
    ), patch(
        "app.agent.nodes_v2.learning.get_pedagogy_logger",
        return_value=MagicMock(),
    ):
        updated = await learning_node(state)

    assert "What do you do now" in updated["pending_response"]
    llm.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_learning_node_low_signal_turn_stays_on_anchor():
    state = _foundation_state()
    state["last_user_message"] = "as let us know watch your car"

    llm = MagicMock()
    llm.generate = AsyncMock()
    prompt_service = MagicMock()
    prompt_service.log_usage = AsyncMock()

    with patch("app.agent.nodes_v2.learning.get_llm_provider", return_value=llm), patch(
        "app.agent.nodes_v2.learning.get_prompt_service",
        return_value=prompt_service,
    ), patch(
        "app.agent.nodes_v2.learning.get_pedagogy_logger",
        return_value=MagicMock(),
    ):
        updated = await learning_node(state)

    assert updated["low_signal_turn_streak"] == 1
    assert "Let's stay with your current work" in updated["pending_response"]
    assert "What do you do now" in updated["pending_response"]
    llm.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_learning_node_second_low_signal_turn_prompts_for_composer():
    state = _foundation_state()
    state["low_signal_turn_streak"] = 1
    state["last_user_message"] = "now sorry one two three four five test"

    with patch(
        "app.agent.nodes_v2.learning.get_llm_provider",
        return_value=MagicMock(generate=AsyncMock()),
    ), patch(
        "app.agent.nodes_v2.learning.get_prompt_service",
        return_value=MagicMock(log_usage=AsyncMock()),
    ), patch(
        "app.agent.nodes_v2.learning.get_pedagogy_logger",
        return_value=MagicMock(),
    ):
        updated = await learning_node(state)

    assert updated["low_signal_turn_streak"] == 2
    assert "composer" in updated["pending_response"].lower()
    assert updated.get("should_end_session") is not True


@pytest.mark.asyncio
async def test_learning_node_empty_llm_content_uses_mission_fallback():
    state = _foundation_state()
    state["last_user_message"] = "I work as a data scientist on ranking models."

    llm = MagicMock()
    llm.generate = AsyncMock(return_value="")
    prompt_service = MagicMock()
    prompt_service.log_usage = AsyncMock()

    with patch("app.agent.nodes_v2.learning.get_llm_provider", return_value=llm), patch(
        "app.agent.nodes_v2.learning.get_prompt_service",
        return_value=prompt_service,
    ), patch(
        "app.agent.nodes_v2.learning.get_pedagogy_logger",
        return_value=MagicMock(),
    ):
        updated = await learning_node(state)

    assert "Let's keep it focused on your current work" in updated["pending_response"]
    assert "What do you do now" in updated["pending_response"]


@pytest.mark.asyncio
async def test_learning_node_advances_anchor_after_clear_answer():
    state = _foundation_state()
    state["last_user_message"] = "I work as a data scientist and build recommendation models."

    llm = MagicMock()
    llm.generate = AsyncMock(
        return_value='{"action":"continue","response_text":"Good. Tell me about one recent task from that work.","should_end":false}'
    )
    prompt_service = MagicMock()
    prompt_service.log_usage = AsyncMock()

    with patch("app.agent.nodes_v2.learning.get_llm_provider", return_value=llm), patch(
        "app.agent.nodes_v2.learning.get_prompt_service",
        return_value=prompt_service,
    ), patch(
        "app.agent.nodes_v2.learning.get_pedagogy_logger",
        return_value=MagicMock(),
    ):
        updated = await learning_node(state)

    assert updated["anchor_follow_up_pending"] is True
    assert updated["anchor_question_id"] == 0
    assert "recent task" in updated["pending_response"].lower()
