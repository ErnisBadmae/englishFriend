"""Tests for shared voice session lifecycle services."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ai.memory_contracts import LearnerProfileSummary, MissionMemoryContext
from app.services.ai.memory_pipeline import MemoryProcessingOutcome
from app.services.voice_session import (
    BootstrapContext,
    SessionBootstrapService,
    SessionPersistRequest,
    SessionPersistenceService,
    VoiceSessionDependencies,
)
from app.services.voice_session.service import UnknownSessionUserError


def _session_dependencies():
    user_service = MagicMock()
    user_service.get_user = AsyncMock(
        return_value=MagicMock(id=42, telegram_id=4242, username="alice", language_level="B2")
    )
    user_service.get_user_by_telegram_id = AsyncMock(return_value=None)
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
    memory_pipeline.process_conversation_with_outcome = AsyncMock(
        return_value=MemoryProcessingOutcome(saved_memories=[], status="noop", reason="no_messages")
    )

    learner_profile_service = MagicMock()
    learner_profile_service.build_summary = AsyncMock(
        return_value=LearnerProfileSummary(
            goal_summary="ML Engineer abroad",
            current_level="B2",
            current_stage="foundation",
        )
    )
    learner_profile_service.build_mission_context = AsyncMock(
        return_value=MissionMemoryContext(
            learner_profile=LearnerProfileSummary(
                goal_summary="ML Engineer abroad",
                current_level="B2",
                current_stage="foundation",
            ),
            relevant_memories=["Built recommendation systems"],
        )
    )

    deps = VoiceSessionDependencies(
        user_service_factory=lambda db: user_service,
        learning_plan_service_factory=lambda db: learning_plan_service,
        vocabulary_service_factory=lambda db: vocabulary_service,
        memory_pipeline_factory=lambda db: memory_pipeline,
        learner_profile_service_factory=lambda db, lps, mp: learner_profile_service,
    )
    return deps, learning_plan_service, memory_pipeline, learner_profile_service


def test_session_persist_request_from_agent_state_only_carries_new_assessment():
    request = SessionPersistRequest.from_agent_state(
        status="completed",
        user_id=7,
        session_id="session-7",
        final_mode="free_conversation",
        runtime="chat_v2",
        existing_goal="ML Engineer",
        agent_state={
            "assessed_level": "B1",
            "assessment_scores": {"fluency": 5.0},
            "baseline_provisional": True,
            "baseline_confidence": 0.5,
        },
    )

    assert request.assessed_level is None
    assert request.assessment_source is None

    explicit_request = SessionPersistRequest.from_agent_state(
        status="completed",
        user_id=7,
        session_id="session-7",
        final_mode="assessment",
        runtime="chat_v2",
        existing_goal="ML Engineer",
        agent_state={
            "assessed_level": "B1",
            "assessment_scores": {"fluency": 5.0},
            "baseline_provisional": True,
            "baseline_confidence": 0.5,
            "assessment_source": "explicit_assessment",
        },
    )

    assert explicit_request.assessed_level == "B1"
    assert explicit_request.assessment_source == "explicit_assessment"


@pytest.mark.asyncio
async def test_bootstrap_service_loads_user_learning_vocab_and_memory():
    deps, _, _, _ = _session_dependencies()
    service = SessionBootstrapService(AsyncMock(), dependencies=deps)

    context = await service.build(user_id=42, session_id="session-42")

    assert context.session_id == "session-42"
    assert context.user_id == 42
    assert context.telegram_id == 4242
    assert context.username == "alice"
    assert context.language_level == "B2"
    assert context.is_new_user is False
    assert context.confirmed_goal == "ML Engineer"
    assert context.due_vocabulary_count == 1
    assert context.due_vocabulary_words == ["pipeline"]
    assert "Learner profile" in context.memory_section
    assert "Built recommendation systems" in context.memory_section
    assert context.learner_profile_summary is not None
    assert context.mission_memory_context is not None


@pytest.mark.asyncio
async def test_bootstrap_service_resolves_existing_internal_user_id():
    deps, learning_plan_service, _, learner_profile_service = _session_dependencies()
    service = SessionBootstrapService(AsyncMock(), dependencies=deps)

    context = await service.build(user_id=42, session_id="session-internal")

    assert context.user_id == 42
    assert context.telegram_id == 4242
    learning_plan_service.get_or_create_plan.assert_awaited_once_with(42)
    learner_profile_service.build_summary.assert_awaited_once()
    assert learner_profile_service.build_summary.await_args.kwargs["user_id"] == 42


@pytest.mark.asyncio
async def test_bootstrap_service_rejects_telegram_id_used_as_internal_id():
    """A telegram_id that is not a users.id must not open a session."""
    deps, learning_plan_service, _, _ = _session_dependencies()
    user_service = deps.user_service_factory(None)
    user_service.get_user = AsyncMock(return_value=None)
    user_service.get_user_by_telegram_id = AsyncMock(
        return_value=MagicMock(id=123, telegram_id=900123, username="tg-user", language_level="B1")
    )
    service = SessionBootstrapService(AsyncMock(), dependencies=deps)

    with pytest.raises(UnknownSessionUserError):
        await service.build(user_id=900123, session_id="session-tg")

    learning_plan_service.get_or_create_plan.assert_not_awaited()


@pytest.mark.asyncio
async def test_bootstrap_service_fails_closed_for_unknown_user_without_side_effects():
    deps, learning_plan_service, _, _ = _session_dependencies()
    user_service = deps.user_service_factory(None)
    user_service.get_user = AsyncMock(return_value=None)
    user_service.get_user_by_telegram_id = AsyncMock(return_value=None)
    service = SessionBootstrapService(AsyncMock(), dependencies=deps)

    with pytest.raises(UnknownSessionUserError):
        await service.build(user_id=999999, session_id="session-unknown")

    user_service.create_user.assert_not_awaited()
    learning_plan_service.get_or_create_plan.assert_not_awaited()


@pytest.mark.asyncio
async def test_bootstrap_service_rolls_back_after_learning_context_error():
    deps, learning_plan_service, _, _ = _session_dependencies()
    db = AsyncMock()
    learning_plan_service.get_or_create_plan = AsyncMock(side_effect=RuntimeError("db failed"))
    service = SessionBootstrapService(db, dependencies=deps)

    context = await service.build(user_id=42, session_id="session-error")

    assert context.session_id == "session-error"
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_initialize_agent_state_prefers_resolved_context_user_id():
    deps, _, _, learner_profile_service = _session_dependencies()
    service = SessionBootstrapService(AsyncMock(), dependencies=deps)

    bootstrap_context = BootstrapContext(
        session_id="resolved-session",
        user_id=123,
        username="alice",
        language_level="B2",
        is_new_user=True,
        confirmed_goal="ML Engineer",
        confirmed_interests=[],
        roadmap={"goal_brief": None},
        due_vocabulary_count=0,
        due_vocabulary_words=[],
        memory_section="",
        learner_profile_summary=LearnerProfileSummary(goal_summary="ML Engineer abroad"),
        mission_memory_context=MissionMemoryContext(relevant_memories=["Built recommendation systems"]),
    )

    with patch("app.services.voice_session.service.initialize_session_v2", new=AsyncMock(return_value={"user_id": 123})) as init_v2:
        await service.initialize_agent_state(
            user_id=900123,
            context=bootstrap_context,
            use_v2_agent=True,
            runtime="chat_v2",
            stt_provider="composer",
        )

    assert learner_profile_service.build_mission_context.await_args.kwargs["user_id"] == 123
    assert init_v2.await_args.kwargs["user_id"] == 123


@pytest.mark.asyncio
async def test_initialize_agent_state_uses_v2_even_when_legacy_flag_is_false():
    deps, _, _, learner_profile_service = _session_dependencies()
    service = SessionBootstrapService(AsyncMock(), dependencies=deps)

    bootstrap_context = BootstrapContext(
        session_id="session-1",
        user_id=42,
        username="student",
        language_level="B1",
        is_new_user=True,
        confirmed_goal="ML Engineer",
        confirmed_interests=[],
        roadmap={"goal_brief": None},
        due_vocabulary_count=0,
        due_vocabulary_words=[],
        memory_section="",
        learner_profile_summary=LearnerProfileSummary(goal_summary="ML Engineer abroad"),
        mission_memory_context=MissionMemoryContext(relevant_memories=["Built recommendation systems"]),
    )

    with patch(
        "app.services.voice_session.service.initialize_session_v2",
        new=AsyncMock(return_value={"user_id": 42}),
    ) as init_v2:
        await service.initialize_agent_state(
            user_id=42,
            context=bootstrap_context,
            use_v2_agent=False,
            runtime="chat_v2",
            stt_provider="composer",
        )

    assert learner_profile_service.build_mission_context.await_args.kwargs["user_id"] == 42
    init_v2.assert_awaited_once()


@pytest.mark.asyncio
async def test_persistence_service_is_idempotent_within_one_session():
    deps, learning_plan_service, memory_pipeline, _ = _session_dependencies()
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
        runtime="chat_v2",
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
    memory_pipeline.process_conversation_with_outcome.assert_awaited_once()


@pytest.mark.asyncio
async def test_persistence_service_persists_evidence_before_gamification():
    deps, learning_plan_service, memory_pipeline, _ = _session_dependencies()
    service = SessionPersistenceService(
        AsyncMock(),
        dependencies=deps,
        learning_plan_service=learning_plan_service,
        memory_pipeline=memory_pipeline,
    )

    request = SessionPersistRequest(
        status="completed",
        user_id=9,
        session_id="session-9",
        final_mode="foundation",
        runtime="chat_v2",
        existing_goal="ML Engineer",
        agent_state={"turn_count": 3},
        conversation_history=[{"role": "user", "content": "Answer"}],
        turn_count=3,
        corrections_made=[],
        vocabulary_reviewed=[],
    )

    call_order: list[str] = []

    async def _persist_interview(*args, **kwargs):
        call_order.append("interview")
        return None

    async def _persist_evidence(*args, **kwargs):
        call_order.append("evidence")
        return {"id": "evidence-1"}

    async def _award_gamification(*args, **kwargs):
        call_order.append("gamification")

    with patch(
        "app.services.voice_session.service.persist_interview_run_if_needed",
        new=AsyncMock(side_effect=_persist_interview),
    ), patch(
        "app.services.voice_session.service.persist_session_evidence_if_needed",
        new=AsyncMock(side_effect=_persist_evidence),
    ), patch(
        "app.services.voice_session.service.award_session_gamification",
        new=AsyncMock(side_effect=_award_gamification),
    ):
        completion = await service.persist(request)

    assert completion.error is None
    assert call_order == ["interview", "evidence", "gamification"]


@pytest.mark.asyncio
async def test_persistence_service_captures_embedded_baseline_from_first_useful_mission():
    deps, learning_plan_service, memory_pipeline, _ = _session_dependencies()
    service = SessionPersistenceService(
        AsyncMock(),
        dependencies=deps,
        learning_plan_service=learning_plan_service,
        memory_pipeline=memory_pipeline,
    )

    request = SessionPersistRequest(
        status="completed",
        user_id=10,
        session_id="session-10",
        final_mode="free_conversation",
        runtime="chat_v2",
        existing_goal="ML Engineer",
        agent_state={
            "turn_count": 3,
            "roadmap": {"goal_brief": {"target_role": "ML Engineer"}},
            "mission_task_type": "technical_project_walkthrough",
        },
        conversation_history=[
            {"role": "assistant", "content": "Walk through one recent project."},
            {"role": "user", "content": "I built a churn model for e-commerce."},
            {"role": "assistant", "content": "What was the result?"},
            {"role": "user", "content": "We improved recall and reduced missed risky users."},
        ],
        turn_count=3,
        corrections_made=[],
        vocabulary_reviewed=[],
    )

    with patch(
        "app.services.voice_session.service.persist_interview_run_if_needed",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.services.voice_session.service.persist_session_evidence_if_needed",
        new=AsyncMock(return_value={"id": "evidence-1"}),
    ) as persist_evidence, patch(
        "app.services.voice_session.service.award_session_gamification",
        new=AsyncMock(),
    ):
        completion = await service.persist(request)

    assert completion.error is None
    learning_plan_service.record_assessment.assert_awaited_once()
    record_kwargs = learning_plan_service.record_assessment.await_args.kwargs
    assert record_kwargs["source"] == "embedded_first_mission"
    assert record_kwargs["assessed_level"] in {"A2", "B1"}
    evidence_kwargs = persist_evidence.await_args.kwargs
    assert evidence_kwargs["assessment_source"] == "embedded_first_mission"
    assert evidence_kwargs["assessed_level"] in {"A2", "B1"}


@pytest.mark.asyncio
async def test_persistence_service_soft_fails_memory_extraction_without_top_level_error(caplog):
    caplog.set_level("INFO")
    deps, learning_plan_service, memory_pipeline, _ = _session_dependencies()
    memory_pipeline.process_conversation_with_outcome = AsyncMock(
        return_value=MemoryProcessingOutcome(
            saved_memories=[],
            status="soft_failed",
            reason="provider_connection_error",
            error_type="ConnectError",
            error="Connection error.",
        )
    )
    service = SessionPersistenceService(
        AsyncMock(),
        dependencies=deps,
        learning_plan_service=learning_plan_service,
        memory_pipeline=memory_pipeline,
    )

    request = SessionPersistRequest(
        status="completed",
        user_id=11,
        session_id="session-soft-fail",
        final_mode="foundation",
        runtime="chat_v2",
        existing_goal="ML Engineer",
        agent_state={"turn_count": 2},
        conversation_history=[{"role": "user", "content": "Answer"}],
        turn_count=2,
        corrections_made=[],
        vocabulary_reviewed=[],
    )

    with patch(
        "app.services.voice_session.service.persist_interview_run_if_needed",
        new=AsyncMock(return_value={"id": "interview-1"}),
    ), patch(
        "app.services.voice_session.service.persist_session_evidence_if_needed",
        new=AsyncMock(return_value={"id": "evidence-1"}),
    ), patch(
        "app.services.voice_session.service.award_session_gamification",
        new=AsyncMock(),
    ):
        completion = await service.persist(request)

    assert completion.error is None
    learning_plan_service.increment_session_count.assert_awaited_once()
    memory_pipeline.process_conversation_with_outcome.assert_awaited_once()
    messages = [record.getMessage() for record in caplog.records]
    assert any("memory_extraction_skipped" in message for message in messages)
    assert any("persistence_completed" in message for message in messages)
    assert all("persistence_failed" not in message for message in messages)


@pytest.mark.asyncio
async def test_persistence_service_keeps_unexpected_memory_bug_diagnosable(caplog):
    caplog.set_level("INFO")
    deps, learning_plan_service, memory_pipeline, _ = _session_dependencies()
    memory_pipeline.process_conversation_with_outcome = AsyncMock(
        return_value=MemoryProcessingOutcome(
            saved_memories=[],
            status="failed",
            reason="unexpected_exception",
            error_type="ValueError",
            error="boom",
        )
    )
    service = SessionPersistenceService(
        AsyncMock(),
        dependencies=deps,
        learning_plan_service=learning_plan_service,
        memory_pipeline=memory_pipeline,
    )

    request = SessionPersistRequest(
        status="completed",
        user_id=12,
        session_id="session-memory-bug",
        final_mode="foundation",
        runtime="chat_v2",
        existing_goal="ML Engineer",
        agent_state={"turn_count": 2},
        conversation_history=[{"role": "user", "content": "Answer"}],
        turn_count=2,
        corrections_made=[],
        vocabulary_reviewed=[],
    )

    with patch(
        "app.services.voice_session.service.persist_interview_run_if_needed",
        new=AsyncMock(return_value={"id": "interview-1"}),
    ), patch(
        "app.services.voice_session.service.persist_session_evidence_if_needed",
        new=AsyncMock(return_value={"id": "evidence-1"}),
    ), patch(
        "app.services.voice_session.service.award_session_gamification",
        new=AsyncMock(),
    ):
        completion = await service.persist(request)

    assert completion.error is None
    messages = [record.getMessage() for record in caplog.records]
    assert any("memory_extraction_failed" in message for message in messages)
    assert any("persistence_completed" in message for message in messages)
