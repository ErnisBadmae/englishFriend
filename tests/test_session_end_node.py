from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.nodes_v2.session_end import session_end_node
from app.agent.state import AgentPhase, LearningModeEnum, create_initial_state
from app.services.ai.llm_provider import LLMEmptyContentError


@pytest.mark.asyncio
async def test_session_end_empty_final_content_uses_simple_farewell():
    state = create_initial_state(user_id=1, session_id="session-end-1")
    state["username"] = "Student"
    state["turn_count"] = 6
    state["current_phase"] = AgentPhase.LEARNING_SESSION
    state["current_mode"] = LearningModeEnum.FREE_CONVERSATION

    prompt_service = MagicMock()
    prompt_service.get_and_render = AsyncMock(
        return_value=("Farewell prompt", MagicMock(variant="default"))
    )
    prompt_service.log_usage = AsyncMock()

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

    pedagogy = MagicMock()
    pedagogy.log_session_ended = MagicMock()

    with patch("app.agent.nodes_v2.session_end.get_prompt_service", return_value=prompt_service), patch(
        "app.agent.nodes_v2.session_end.get_llm_provider",
        return_value=llm,
    ), patch(
        "app.agent.nodes_v2.session_end.get_pedagogy_logger",
        return_value=pedagogy,
    ):
        updated = await session_end_node(state)

    assert "Nice practice, Student!" in updated["pending_response"]
    assert updated["current_phase"] == AgentPhase.SESSION_END
    assert updated["session_end_fallback_used"] is True
    assert updated["session_end_fallback_reason"] == "empty_final_content"
    prompt_service.log_usage.assert_awaited_once()
