from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.graph_v2 import initialize_session_v2
from app.agent.nodes_v2.learning import _get_foundation_prompt, _matches_anchor, learning_node
from app.agent.state import AgentPhase, LearningModeEnum, create_initial_state
from app.services.ai.llm_provider import LLMEmptyContentError


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


def _technical_state(task_type: str = "metrics_explainer") -> dict:
    state = create_initial_state(user_id=1, session_id="technical-session")
    state["current_phase"] = AgentPhase.LEARNING_SESSION
    state["current_mode"] = LearningModeEnum.FREE_CONVERSATION
    state["confirmed_goal"] = "Get an ML role abroad"
    state["goal_setup_complete"] = True
    state["assessed_level"] = "B1"
    state["mission_task_type"] = task_type
    state["mission_title"] = "Explain one metric clearly"
    state["mission_reason"] = "You need to explain why a metric matters, not just name it."
    state["mission_success_signal"] = "You can explain what the metric measures and why you chose it."
    state["mission_linked_goal_context"] = "project_walkthrough"
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
async def test_initialize_session_v2_prefers_explicit_mission_contract_over_roadmap_inference():
    state = await initialize_session_v2(
        user_id=1,
        session_id="session-explicit",
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
        mission_task_type="project_walkthrough_drill",
        mission_title="Explain one recent ML project",
        mission_reason="Stay on project walkthrough instead of a foundation drill.",
        mission_success_signal="You can explain a project with metric and impact.",
        mission_linked_goal_context="project_walkthrough",
    )

    assert state["mission_task_type"] == "project_walkthrough_drill"
    assert state["mission_title"] == "Explain one recent ML project"
    assert state["mission_reason"] == "Stay on project walkthrough instead of a foundation drill."
    assert state["mission_success_signal"] == "You can explain a project with metric and impact."
    assert state["mission_linked_goal_context"] == "project_walkthrough"


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
async def test_learning_node_supportive_recovery_uses_example_for_help_request():
    state = _foundation_state()
    state["last_user_message"] = "sorry my english is very bad could you teach me"

    with patch(
        "app.agent.nodes_v2.learning.get_llm_provider",
        return_value=MagicMock(generate=AsyncMock()),
    ) as llm_patch, patch(
        "app.agent.nodes_v2.learning.get_prompt_service",
        return_value=MagicMock(log_usage=AsyncMock()),
    ), patch(
        "app.agent.nodes_v2.learning.get_pedagogy_logger",
        return_value=MagicMock(),
    ):
        updated = await learning_node(state)

    assert updated["low_signal_turn_streak"] == 1
    assert "no problem" in updated["pending_response"].lower()
    assert "example" in updated["pending_response"].lower()
    assert "what do you do now" in updated["pending_response"].lower()
    assert updated["last_intent"]["type"] == "support_request"
    assert updated["last_intent"]["policy_action"] == "simplify_with_example"
    llm_patch.return_value.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_learning_node_supportive_recovery_second_turn_prefers_composer_without_ending():
    state = _foundation_state()
    state["low_signal_turn_streak"] = 1
    state["last_user_message"] = "he cant explain english cause i dont know how can i say in english"

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
async def test_learning_node_empty_final_content_error_uses_mission_fallback():
    state = _foundation_state()
    state["last_user_message"] = "I work as a data scientist on ranking models."

    llm = MagicMock()
    llm.generate = AsyncMock(
        side_effect=LLMEmptyContentError(
            provider_name="llama_cpp",
            model="CPU Qwen 3.5 256k node3",
            finish_reason="length",
            has_reasoning=True,
            used_compat_retry=True,
        )
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


@pytest.mark.asyncio
async def test_learning_node_accepts_shift_to_next_step_anchor():
    state = _foundation_state()
    state["anchor_question_id"] = 1
    state["anchor_follow_up_pending"] = True
    state["last_user_message"] = "My next step is to improve grammar for project answers."

    llm = MagicMock()
    llm.generate = AsyncMock(
        return_value='{"action":"continue","response_text":"Good. Say it as one short plan: next step, skill, and why it matters.","should_end":false}'
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

    assert updated["anchor_question_id"] == 2
    assert updated["anchor_follow_up_pending"] is True
    assert "next mission" in updated["pending_response"].lower()
    assert "does that match what you want" in updated["pending_response"].lower()


def test_get_foundation_prompt_uses_coach_driven_next_step_instruction():
    state = _foundation_state()
    state["anchor_question_id"] = 2
    prompt = _get_foundation_prompt(state)

    assert "recap one concrete detail" in prompt.lower()
    assert "do not ask the learner to design the program" in prompt.lower()
    assert "what is your next step in our program" not in prompt.lower()
    assert "which skill do you want to improve first" not in prompt.lower()


def test_matches_recent_project_for_pet_project_language():
    assert _matches_anchor("recent_project", "I'm creating a pet project, an LLM mentor app.")


@pytest.mark.asyncio
async def test_learning_node_dedupes_repeated_anchor_question_with_paraphrase():
    state = _foundation_state()
    state["last_user_message"] = "I am building an LLM mentor app now."
    state["last_anchor_question_text"] = " what do you do now and what kind of ml work do you touch "

    llm = MagicMock()
    llm.generate = AsyncMock(
        return_value='{"action":"continue","response_text":"You are building an LLM mentor. What do you do now, and what kind of ML work do you touch?","should_end":false}'
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

    assert "what do you do now" not in updated["pending_response"].lower()
    assert "tell me briefly about your current role" in updated["pending_response"].lower()


@pytest.mark.asyncio
async def test_learning_node_marks_session_complete_after_next_step_follow_up():
    state = _foundation_state()
    state["anchor_question_id"] = 2
    state["anchor_follow_up_pending"] = True
    state["last_user_message"] = "Yes, focus on project answers first."

    llm = MagicMock()
    llm.generate = AsyncMock(
        return_value='{"action":"continue","response_text":"Good. Next mission will focus on a clearer project answer.","should_end":false}'
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

    assert updated["should_end_session"] is True
    assert updated["anchor_question_id"] == 2
    assert updated["anchor_follow_up_pending"] is False


@pytest.mark.asyncio
async def test_learning_node_uses_technical_mission_opener_without_llm():
    state = _technical_state()

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

    assert "technical explanation drill" in updated["pending_response"].lower()
    assert "metric" in updated["pending_response"].lower()
    llm.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_learning_node_technical_supportive_recovery_mentions_russian_help():
    state = _technical_state()
    state["last_user_message"] = "sorry my english is very bad could you teach me"

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

    assert updated["low_signal_turn_streak"] == 1
    assert "все нормально" in updated["pending_response"].lower()
    assert "example" in updated["pending_response"].lower()
    assert "metric" in updated["pending_response"].lower()


@pytest.mark.asyncio
async def test_learning_node_technical_empty_final_content_uses_technical_fallback():
    state = _technical_state("tradeoff_explanation_drill")
    state["mission_title"] = "Defend one trade-off decision"
    state["mission_reason"] = "You need a cleaner way to justify technical trade-offs under pressure."
    state["mission_success_signal"] = "You can compare two options and defend the choice."
    state["last_user_message"] = "The trade-off favored gradient boosting over logistic regression because recall mattered more."

    llm = MagicMock()
    llm.generate = AsyncMock(
        side_effect=LLMEmptyContentError(
            provider_name="llama_cpp",
            model="CPU Qwen 3.5 256k node3",
            finish_reason="length",
            has_reasoning=True,
            used_compat_retry=True,
        )
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

    assert "trade off" in updated["pending_response"].lower() or "trade-off" in updated["pending_response"].lower()
    assert "use simple english" in updated["pending_response"].lower()
