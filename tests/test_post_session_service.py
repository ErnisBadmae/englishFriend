from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai.llm_provider import LLMEmptyContentError
from app.services.ai.post_session_service import PostSessionService


@pytest.mark.asyncio
async def test_post_session_returns_safe_empty_result_on_empty_final_content():
    db = MagicMock()

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

    vocabulary_service = MagicMock()
    vocabulary_service.create_card = AsyncMock()

    learning_plan_service = MagicMock()
    learning_plan_service.record_assessment = AsyncMock()
    learning_plan_service.set_goal = AsyncMock()

    with patch("app.services.ai.post_session_service.get_llm_provider", return_value=llm), patch(
        "app.services.ai.post_session_service.VocabularyService",
        return_value=vocabulary_service,
    ), patch(
        "app.services.ai.post_session_service.LearningPlanService",
        return_value=learning_plan_service,
    ):
        service = PostSessionService(db)
        result = await service.process_session_end(
            user_id=1,
            session_id="post-session-1",
            conversation_history=[
                {"role": "user", "content": "I work as a data scientist."},
                {"role": "assistant", "content": "Tell me about one project."},
            ],
            current_mode="free_conversation",
            session_context={},
        )

    assert result == {
        "cards_created": 0,
        "level_assessed": None,
        "goal_updated": False,
        "xp_bonus": 0,
        "recommendations": [],
    }
    vocabulary_service.create_card.assert_not_called()
    learning_plan_service.record_assessment.assert_not_called()
    learning_plan_service.set_goal.assert_not_called()
