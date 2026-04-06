"""Tests for shared voice session lifecycle services."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.voice_session import (
    SessionBootstrapService,
    SessionPersistRequest,
    SessionPersistenceService,
    VoiceSessionDependencies,
)


def _session_dependencies():
    user_service = MagicMock()
    user_service.get_user = AsyncMock(
        return_value=MagicMock(username="alice", language_level="B2")
    )
    user_service.create_user = AsyncMock()

    learning_plan = MagicMock()
    learning_plan.roadmap = {"goal": "ML Engineer"}

    learning_plan_service = MagicMock()
    learning_plan_service.get_or_create_plan = AsyncMock(return_value=learning_plan)
    learning_plan_service.get_goal.return_value = "ML Engineer"
    learning_plan_service.get_current_level.return_value = "B2"
    learning_plan_service.get_session_count.return_value = 1
    learning_plan_service.increment_session_count = AsyncMock()
    learning_plan_service.record_assessment = AsyncMock()

    vocabulary_card = MagicMock(word="pipeline")
    vocabulary_service = MagicMock()
    vocabulary_service.get_due_cards = AsyncMock(return_value=[vocabulary_card])

    memory_pipeline = MagicMock()
    memory_pipeline.format_memory_for_prompt = AsyncMock(return_value="memory")
    memory_pipeline.process_conversation = AsyncMock()

    deps = VoiceSessionDependencies(
        user_service_factory=lambda db: user_service,
        learning_plan_service_factory=lambda db: learning_plan_service,
        vocabulary_service_factory=lambda db: vocabulary_service,
        memory_pipeline_factory=lambda db: memory_pipeline,
    )
    return deps, learning_plan_service, memory_pipeline


@pytest.mark.asyncio
async def test_bootstrap_service_loads_user_learning_vocab_and_memory():
    deps, _, _ = _session_dependencies()
    service = SessionBootstrapService(AsyncMock(), dependencies=deps)

    context = await service.build(user_id=42, session_id="session-42")

    assert context.session_id == "session-42"
    assert context.username == "alice"
    assert context.language_level == "B2"
    assert context.is_new_user is False
    assert context.confirmed_goal == "ML Engineer"
    assert context.due_vocabulary_count == 1
    assert context.due_vocabulary_words == ["pipeline"]
    assert context.memory_section == "memory"


@pytest.mark.asyncio
async def test_persistence_service_is_idempotent_within_one_session():
    deps, learning_plan_service, memory_pipeline = _session_dependencies()
    service = SessionPersistenceService(
        AsyncMock(),
        dependencies=deps,
        learning_plan_service=learning_plan_service,
        memory_pipeline=memory_pipeline,
    )

    request = SessionPersistRequest(
        status="completed",
        user_id=7,
        session_id="session-7",
        final_mode="mock_interview",
        existing_goal="ML Engineer",
        agent_state={"turn_count": 2},
        conversation_history=[{"role": "user", "content": "Answer"}],
        turn_count=2,
        corrections_made=[],
        vocabulary_reviewed=[],
    )

    with patch(
        "app.services.voice_session.service.persist_interview_run_if_needed",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.services.voice_session.service.persist_session_evidence_if_needed",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.services.voice_session.service.award_session_gamification",
        new=AsyncMock(),
    ):
        first = await service.persist(request)
        second = await service.persist(request)

    assert first.already_persisted is False
    assert second.already_persisted is True
    learning_plan_service.increment_session_count.assert_awaited_once()
    memory_pipeline.process_conversation.assert_awaited_once()
