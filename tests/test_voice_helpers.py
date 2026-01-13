"""Unit tests for voice helper functions."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.api.voice_helpers import (
    handle_goal_setting,
    rebuild_system_prompt,
    award_session_gamification,
)
from app.services.ai.mode_prompts import LearningMode
from app.services.ai.mode_selector import SessionContext


@pytest.mark.asyncio
async def test_handle_goal_setting_success():
    """Test successful goal setting."""
    # Setup mocks
    user_id = 1
    goal_text = "ML interview preparation"
    db = AsyncMock()
    websocket = AsyncMock()

    learning_plan_service = MagicMock()
    learning_plan_service.set_goal = AsyncMock(return_value=MagicMock(
        roadmap={"recommended_vocabulary": ["algorithm", "data"]}
    ))
    learning_plan_service.get_recommended_vocabulary = MagicMock(
        return_value=["algorithm", "data"]
    )

    session_context = SessionContext(
        user_id=user_id,
        username="TestUser",
        language_level="B1",
    )

    # Mock create_initial_vocabulary_cards
    with patch('app.api.voice_helpers.create_initial_vocabulary_cards',
               new=AsyncMock(return_value=2)):
        # Call helper
        mode, focus_area = await handle_goal_setting(
            goal_text, user_id, db, learning_plan_service,
            session_context, websocket
        )

    # Assertions
    assert mode is not None
    assert isinstance(mode, LearningMode)
    assert focus_area is not None
    assert session_context.goal == goal_text
    learning_plan_service.set_goal.assert_called_once_with(user_id, goal_text)
    websocket.send_json.assert_called_once()


@pytest.mark.asyncio
async def test_handle_goal_setting_error():
    """Test goal setting handles errors gracefully."""
    # Setup mocks that will raise error
    user_id = 1
    goal_text = "test goal"
    db = AsyncMock()
    websocket = AsyncMock()

    learning_plan_service = MagicMock()
    learning_plan_service.set_goal = AsyncMock(side_effect=Exception("DB error"))

    session_context = SessionContext(
        user_id=user_id,
        username="TestUser",
        language_level="B1",
    )

    # Call helper - should not raise
    mode, focus_area = await handle_goal_setting(
        goal_text, user_id, db, learning_plan_service,
        session_context, websocket
    )

    # Should return None on error
    assert mode is None
    assert focus_area is None


def test_rebuild_system_prompt():
    """Test system prompt rebuilding."""
    session_context = SessionContext(
        user_id=1,
        username="TestUser",
        language_level="B2",
        goal="improve fluency",
    )

    prompt = rebuild_system_prompt(
        current_mode=LearningMode.FREE_CONVERSATION,
        session_context=session_context,
        focus_area="grammar",
        vocabulary_list="word1, word2",
        memory_section="User likes tech",
    )

    # Verify prompt contains key elements
    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "TestUser" in prompt or "B2" in prompt


@pytest.mark.asyncio
async def test_award_session_gamification():
    """Test session gamification awards."""
    # Setup mocks
    db = AsyncMock()
    user_id = 1
    session_id = "test-session-123"

    xp_service = MagicMock()
    xp_service.award_xp = AsyncMock()
    xp_service.check_first_session = AsyncMock(return_value=True)

    streak_service = MagicMock()
    streak_service.check_in = AsyncMock(return_value={
        "streak": 3,
        "max_streak": 5,
        "is_comeback": False,
    })

    # Mock service creation
    with patch('app.api.voice_helpers.XPService', return_value=xp_service):
        with patch('app.api.voice_helpers.StreakService', return_value=streak_service):
            # Call helper
            await award_session_gamification(db, user_id, session_id)

    # Verify all gamification steps were called
    streak_service.check_in.assert_called_once_with(user_id)
    assert xp_service.award_xp.call_count >= 3  # Session complete, streak bonus, first session


@pytest.mark.asyncio
async def test_award_session_gamification_handles_errors():
    """Test gamification handles service errors gracefully."""
    db = AsyncMock()
    user_id = 1
    session_id = "test-session"

    # Mock services that will fail
    with patch('app.api.voice_helpers.XPService', side_effect=Exception("XP error")):
        # Should not raise - errors are caught and logged
        await award_session_gamification(db, user_id, session_id)
        # If we get here, error was handled correctly
        assert True
