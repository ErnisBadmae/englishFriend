"""Tests for the experimental modular voice runtime."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.graph_v2 import initialize_session_v2, run_agent_turn_v2
from app.agent.state import AgentPhase, LearningModeEnum
from app.services.ai.memory_contracts import LearnerProfileSummary, MissionMemoryContext
from app.services.voice_session import BootstrapContext, SessionCompletion
from app.services.conversation_runtime.controller import ConversationRuntimeDependencies, ConversationController
from app.services.conversation_runtime.stt import ParakeetSTTProvider, PassthroughTextSTTProvider
from app.services.conversation_runtime.turn_detection import ExplicitMessageTurnDetector
from app.services.conversation_runtime.tts import EdgeTTSTTSProvider


def _mock_dependencies() -> ConversationRuntimeDependencies:
    user_service = MagicMock()
    learning_plan_service = MagicMock()
    learning_plan_service.increment_session_count = AsyncMock()
    learning_plan_service.record_assessment = AsyncMock()
    vocabulary_service = MagicMock()
    memory_pipeline = MagicMock()
    memory_pipeline.process_conversation = AsyncMock()
    memory_pipeline.format_memory_for_prompt = AsyncMock(return_value="")
    learner_profile_service = MagicMock()
    learner_profile_service.build_summary = AsyncMock(
        return_value=LearnerProfileSummary(goal_summary="ML Engineer abroad")
    )
    learner_profile_service.build_mission_context = AsyncMock(
        return_value=MissionMemoryContext(relevant_memories=["Goal: ML Engineer abroad"])
    )

    return ConversationRuntimeDependencies(
        user_service_factory=lambda db: user_service,
        learning_plan_service_factory=lambda db: learning_plan_service,
        vocabulary_service_factory=lambda db: vocabulary_service,
        memory_pipeline_factory=lambda db: memory_pipeline,
        learner_profile_service_factory=lambda db, lps, mp: learner_profile_service,
    )


def test_explicit_turn_detector_classifies_messages():
    detector = ExplicitMessageTurnDetector()

    commit = detector.detect({"type": "text", "text": " hello "})
    assert commit.disposition == "commit"
    assert commit.text == "hello"

    end = detector.detect({"type": "end"})
    assert end.disposition == "end"

    ignored = detector.detect({"type": "noop"})
    assert ignored.disposition == "ignore"


@pytest.mark.asyncio
async def test_passthrough_text_stt_provider_returns_final_text():
    provider = PassthroughTextSTTProvider()
    event = await provider.transcribe_text("Interview practice", user_id=1, session_id="s1")

    assert event.type == "final"
    assert event.text == "Interview practice"
    assert event.confidence == 1.0


@pytest.mark.asyncio
async def test_parakeet_stt_provider_normalizes_transcription_payload():
    response = MagicMock()
    response.json.return_value = {
        "text": "Explain one trade-off decision",
        "confidence": 0.87,
        "language": "en",
    }
    response.raise_for_status = MagicMock()

    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post = AsyncMock(return_value=response)

    with patch("app.services.conversation_runtime.stt.httpx.AsyncClient", return_value=client):
        provider = ParakeetSTTProvider(base_url="http://parakeet.local")
        event = await provider.transcribe_audio(
            b"audio-bytes",
            content_type="audio/webm",
            user_id=1,
            session_id="s1",
        )

    assert event.type == "final"
    assert event.text == "Explain one trade-off decision"
    assert event.confidence == 0.87
    assert event.language == "en"


@pytest.mark.asyncio
async def test_edge_tts_provider_delegates_to_existing_service():
    service = MagicMock()
    service.synthesize = AsyncMock(return_value=b"audio")

    provider = EdgeTTSTTSProvider(service=service)
    audio = await provider.synthesize("Hello")

    assert audio == b"audio"
    service.synthesize.assert_awaited_once_with("Hello")


@pytest.mark.asyncio
async def test_controller_processes_text_turn_with_phase_change_and_audio():
    tts_provider = MagicMock()
    tts_provider.synthesize = AsyncMock(return_value=b"audio")

    controller = ConversationController(
        db=AsyncMock(),
        user_id=1,
        mode=None,
        interview_track=None,
        transport=MagicMock(),
        stt_provider=PassthroughTextSTTProvider(),
        tts_provider=tts_provider,
        turn_detector=ExplicitMessageTurnDetector(),
        dependencies=_mock_dependencies(),
        use_v2_agent=True,
    )
    controller._context.confirmed_goal = "ML interviews"
    controller._context.session_id = "session-1"
    controller._agent_state = {
        "current_phase": AgentPhase.ONBOARDING,
        "current_mode": LearningModeEnum.FREE_CONVERSATION,
        "turn_count": 0,
        "conversation_history": [],
        "corrections_made": [],
        "vocabulary_reviewed": [],
        "should_end_session": False,
    }

    next_state = {
        "pending_response": "Tell me about a project you shipped.",
        "current_phase": AgentPhase.LEARNING_SESSION,
        "current_mode": LearningModeEnum.MOCK_INTERVIEW,
        "turn_count": 1,
        "conversation_history": [{"role": "user", "content": "Hi"}],
        "corrections_made": [],
        "vocabulary_reviewed": [],
        "should_end_session": False,
    }

    with patch(
        "app.services.conversation_runtime.controller.run_agent_turn_v2",
        new=AsyncMock(return_value=next_state),
    ):
        outcome = await controller.handle_message({"type": "text", "text": "Hi"})

    assert outcome.should_close is False
    assert outcome.status is None
    assert outcome.events[0]["type"] == "transcript"
    assert outcome.events[0]["role"] == "user"
    assert outcome.events[0]["text"] == "Hi"
    assert outcome.events[0]["runtime"] == "realtime"
    assert outcome.events[0]["turn_id"] == "t1"
    assert outcome.events[0]["turn_index"] == 1
    assert any(
        event.get("type") == "phase_changed"
        and event.get("phase") == "learning_session"
        and event.get("turn_id") == "t1"
        for event in outcome.events
    )
    assert any(
        event.get("type") == "transcript"
        and event.get("role") == "assistant"
        and "project you shipped" in event.get("text", "")
        and event.get("runtime") == "realtime"
        and event.get("turn_id") == "t1"
        for event in outcome.events
    )
    assert any(
        event.get("type") == "audio"
        and event.get("runtime") == "realtime"
        and event.get("turn_id") == "t1"
        for event in outcome.events
    )


@pytest.mark.asyncio
async def test_controller_explicit_end_runs_farewell_and_persists_state():
    deps = ConversationRuntimeDependencies(
        user_service_factory=lambda db: MagicMock(),
        learning_plan_service_factory=lambda db: MagicMock(),
        vocabulary_service_factory=lambda db: MagicMock(),
        memory_pipeline_factory=lambda db: MagicMock(),
    )

    tts_provider = MagicMock()
    tts_provider.synthesize = AsyncMock(return_value=b"bye-audio")

    controller = ConversationController(
        db=AsyncMock(),
        user_id=7,
        mode=None,
        interview_track=None,
        transport=MagicMock(),
        stt_provider=PassthroughTextSTTProvider(),
        tts_provider=tts_provider,
        turn_detector=ExplicitMessageTurnDetector(),
        dependencies=deps,
        use_v2_agent=True,
    )
    controller._context.confirmed_goal = "International ML role"
    controller._context.session_id = "session-end"
    controller._final_mode = "mock_interview"
    controller._agent_state = {
        "current_phase": AgentPhase.LEARNING_SESSION,
        "current_mode": LearningModeEnum.MOCK_INTERVIEW,
        "turn_count": 2,
        "conversation_history": [{"role": "user", "content": "Answer"}],
        "corrections_made": [],
        "vocabulary_reviewed": [],
        "should_end_session": False,
    }
    controller._persistence_service.persist = AsyncMock(
        return_value=SessionCompletion(status="completed")
    )

    farewell_state = {
        "pending_response": "Nice work today. Let's continue tomorrow.",
        "current_phase": AgentPhase.SESSION_END,
        "current_mode": LearningModeEnum.MOCK_INTERVIEW,
        "turn_count": 2,
        "conversation_history": [{"role": "user", "content": "Answer"}],
        "corrections_made": [],
        "vocabulary_reviewed": [],
        "should_end_session": True,
        "session_complete_reason": "session_end",
        "session_complete_return_screen": "home",
    }

    with patch(
        "app.services.conversation_runtime.controller.run_agent_turn_v2",
        new=AsyncMock(return_value=farewell_state),
    ):
        outcome = await controller.handle_message({"type": "end"})

    assert outcome.should_close is True
    assert outcome.status == "completed"
    assert any(
        event.get("type") == "transcript"
        and event.get("role") == "assistant"
        and "Nice work today" in event.get("text", "")
        for event in outcome.events
    )
    finishing_index = next(
        index for index, event in enumerate(outcome.events) if event.get("type") == "session_finishing"
    )
    complete_index = next(
        index for index, event in enumerate(outcome.events) if event.get("type") == "session_complete"
    )
    assert finishing_index < complete_index
    controller._persistence_service.persist.assert_awaited_once()


@pytest.mark.asyncio
async def test_controller_regular_turn_emits_finishing_before_completion_when_agent_ends_session():
    tts_provider = MagicMock()
    tts_provider.synthesize = AsyncMock(return_value=b"audio")

    controller = ConversationController(
        db=AsyncMock(),
        user_id=8,
        mode=None,
        interview_track=None,
        transport=MagicMock(),
        stt_provider=PassthroughTextSTTProvider(),
        tts_provider=tts_provider,
        turn_detector=ExplicitMessageTurnDetector(),
        dependencies=_mock_dependencies(),
        use_v2_agent=True,
    )
    controller._context.confirmed_goal = "ML interviews"
    controller._context.session_id = "session-finish"
    controller._agent_state = {
        "current_phase": AgentPhase.LEARNING_SESSION,
        "current_mode": LearningModeEnum.MOCK_INTERVIEW,
        "turn_count": 0,
        "conversation_history": [],
        "corrections_made": [],
        "vocabulary_reviewed": [],
        "should_end_session": False,
    }
    controller._persistence_service.persist = AsyncMock(
        return_value=SessionCompletion(status="completed")
    )

    next_state = {
        "pending_response": "Great. We have enough for today.",
        "current_phase": AgentPhase.SESSION_END,
        "current_mode": LearningModeEnum.MOCK_INTERVIEW,
        "turn_count": 1,
        "conversation_history": [{"role": "user", "content": "Hi"}],
        "corrections_made": [],
        "vocabulary_reviewed": [],
        "should_end_session": True,
        "session_complete_reason": "session_end",
        "session_complete_return_screen": "home",
    }

    with patch(
        "app.services.conversation_runtime.controller.run_agent_turn_v2",
        new=AsyncMock(return_value=next_state),
    ):
        outcome = await controller.handle_message({"type": "text", "text": "Hi"})

    assert outcome.should_close is True
    assert outcome.status == "completed"
    finishing_index = next(
        index for index, event in enumerate(outcome.events) if event.get("type") == "session_finishing"
    )
    complete_index = next(
        index for index, event in enumerate(outcome.events) if event.get("type") == "session_complete"
    )
    assert finishing_index < complete_index
    controller._persistence_service.persist.assert_awaited_once()


@pytest.mark.asyncio
async def test_controller_initialize_passes_explicit_mission_contract_to_bootstrap():
    controller = ConversationController(
        db=AsyncMock(),
        user_id=11,
        mode="free_conversation",
        interview_track=None,
        stt_provider_name="browser_vosk",
        mission_task_type="foundation_speaking_drill",
        mission_title="Run a foundation speaking drill",
        mission_reason="Stabilize grammar before interviews.",
        mission_success_signal="One cleaner career answer.",
        mission_linked_goal_context="foundation",
        transport=MagicMock(),
        stt_provider=PassthroughTextSTTProvider(),
        tts_provider=MagicMock(synthesize=AsyncMock(return_value=b"audio")),
        turn_detector=ExplicitMessageTurnDetector(),
        dependencies=_mock_dependencies(),
        use_v2_agent=True,
    )
    controller._bootstrap_service.build = AsyncMock(
        return_value=BootstrapContext(session_id="mission-session")
    )
    controller._bootstrap_service.initialize_agent_state = AsyncMock(
        return_value={
            "current_phase": AgentPhase.START,
            "current_mode": LearningModeEnum.FREE_CONVERSATION,
        }
    )

    with patch(
        "app.services.conversation_runtime.controller.run_agent_turn_v2",
        new=AsyncMock(
            return_value={
                "pending_response": "What do you do now?",
                "current_phase": AgentPhase.LEARNING_SESSION,
                "current_mode": LearningModeEnum.FREE_CONVERSATION,
            }
        ),
    ):
        await controller.initialize()

    controller._bootstrap_service.initialize_agent_state.assert_awaited_once_with(
        user_id=11,
        context=controller._context,
        use_v2_agent=True,
        explicit_mode="free_conversation",
        interview_track_id=None,
        mission_task_type="foundation_speaking_drill",
        mission_title="Run a foundation speaking drill",
        mission_reason="Stabilize grammar before interviews.",
        mission_success_signal="One cleaner career answer.",
        mission_linked_goal_context="foundation",
        runtime="realtime",
        stt_provider="browser_vosk",
    )


@pytest.mark.asyncio
async def test_controller_initialize_connected_payload_contains_runtime_metadata():
    controller = ConversationController(
        db=AsyncMock(),
        user_id=5,
        mode=None,
        interview_track=None,
        stt_provider_name="browser_vosk",
        transport=MagicMock(),
        stt_provider=PassthroughTextSTTProvider(),
        tts_provider=MagicMock(synthesize=AsyncMock(return_value=b"audio")),
        turn_detector=ExplicitMessageTurnDetector(),
        dependencies=_mock_dependencies(),
        use_v2_agent=True,
    )
    controller._bootstrap_service.build = AsyncMock(
        return_value=BootstrapContext(
            session_id="session-init",
            is_new_user=True,
            due_vocabulary_count=2,
        )
    )
    controller._bootstrap_service.initialize_agent_state = AsyncMock(
        return_value={
            "current_phase": AgentPhase.START,
            "current_mode": LearningModeEnum.FREE_CONVERSATION,
        }
    )

    with patch(
        "app.services.conversation_runtime.controller.run_agent_turn_v2",
        new=AsyncMock(
            return_value={
                "pending_response": "Hello there",
                "current_phase": AgentPhase.START,
                "current_mode": LearningModeEnum.FREE_CONVERSATION,
            }
        ),
    ):
        outcome = await controller.initialize()

    connected = outcome.events[0]
    assert connected["type"] == "connected"
    assert connected["session_id"] == "session-init"
    assert connected["runtime"] == "realtime"
    assert connected["agent_version"] == "v2"
    assert connected["stt_provider"] == "browser_vosk"


@pytest.mark.asyncio
async def test_controller_initialize_uses_resolved_user_id_from_bootstrap_context():
    controller = ConversationController(
        db=AsyncMock(),
        user_id=900123,
        mode=None,
        interview_track=None,
        stt_provider_name="browser_vosk",
        transport=MagicMock(),
        stt_provider=PassthroughTextSTTProvider(),
        tts_provider=MagicMock(synthesize=AsyncMock(return_value=b"audio")),
        turn_detector=ExplicitMessageTurnDetector(),
        dependencies=_mock_dependencies(),
        use_v2_agent=True,
    )
    controller._bootstrap_service.build = AsyncMock(
        return_value=BootstrapContext(session_id="resolved-init", user_id=77, telegram_id=900123)
    )
    controller._bootstrap_service.initialize_agent_state = AsyncMock(
        return_value={
            "current_phase": AgentPhase.START,
            "current_mode": LearningModeEnum.FREE_CONVERSATION,
        }
    )

    with patch(
        "app.services.conversation_runtime.controller.run_agent_turn_v2",
        new=AsyncMock(
            return_value={
                "pending_response": "Hello there",
                "current_phase": AgentPhase.START,
                "current_mode": LearningModeEnum.FREE_CONVERSATION,
            }
        ),
    ):
        await controller.initialize()

    controller._bootstrap_service.initialize_agent_state.assert_awaited_once_with(
        user_id=77,
        context=controller._context,
        use_v2_agent=True,
        explicit_mode=None,
        interview_track_id=None,
        mission_task_type=None,
        mission_title=None,
        mission_reason=None,
        mission_success_signal=None,
        mission_linked_goal_context=None,
        runtime="realtime",
        stt_provider="browser_vosk",
    )


@pytest.mark.asyncio
async def test_controller_survives_tts_failure_without_error_event():
    tts_provider = MagicMock()
    tts_provider.synthesize = AsyncMock(side_effect=RuntimeError("tts offline"))

    controller = ConversationController(
        db=AsyncMock(),
        user_id=1,
        mode=None,
        interview_track=None,
        transport=MagicMock(),
        stt_provider=PassthroughTextSTTProvider(),
        tts_provider=tts_provider,
        turn_detector=ExplicitMessageTurnDetector(),
        dependencies=_mock_dependencies(),
        use_v2_agent=True,
    )
    controller._context.confirmed_goal = "ML interviews"
    controller._context.session_id = "session-tts"
    controller._agent_state = {
        "current_phase": AgentPhase.ONBOARDING,
        "current_mode": LearningModeEnum.FREE_CONVERSATION,
        "turn_count": 0,
        "conversation_history": [],
        "corrections_made": [],
        "vocabulary_reviewed": [],
        "should_end_session": False,
    }

    next_state = {
        "pending_response": "Tell me about your current role.",
        "current_phase": AgentPhase.ONBOARDING,
        "current_mode": LearningModeEnum.FREE_CONVERSATION,
        "turn_count": 1,
        "conversation_history": [{"role": "user", "content": "Hi"}],
        "corrections_made": [],
        "vocabulary_reviewed": [],
        "should_end_session": False,
    }

    with patch(
        "app.services.conversation_runtime.controller.run_agent_turn_v2",
        new=AsyncMock(return_value=next_state),
    ):
        outcome = await controller.handle_message({"type": "text", "text": "Hi"})

    assert any(
        event.get("type") == "transcript"
        and event.get("role") == "assistant"
        and "current role" in event.get("text", "")
        for event in outcome.events
    )
    assert not any(event.get("type") == "error" for event in outcome.events)
    assert not any(event.get("type") == "audio" for event in outcome.events)


@pytest.mark.asyncio
async def test_controller_skips_tts_for_text_only_sessions():
    tts_provider = MagicMock()
    tts_provider.synthesize = AsyncMock(return_value=b"audio")

    controller = ConversationController(
        db=AsyncMock(),
        user_id=1,
        mode=None,
        interview_track=None,
        stt_provider_name="composer",
        text_only=True,
        transport=MagicMock(),
        stt_provider=PassthroughTextSTTProvider(),
        tts_provider=tts_provider,
        turn_detector=ExplicitMessageTurnDetector(),
        dependencies=_mock_dependencies(),
        use_v2_agent=True,
    )
    controller._context.confirmed_goal = "ML interviews"
    controller._context.session_id = "session-composer"
    controller._agent_state = {
        "current_phase": AgentPhase.ONBOARDING,
        "current_mode": LearningModeEnum.FREE_CONVERSATION,
        "turn_count": 0,
        "conversation_history": [],
        "corrections_made": [],
        "vocabulary_reviewed": [],
        "should_end_session": False,
    }

    next_state = {
        "pending_response": "Type your current role in one sentence.",
        "current_phase": AgentPhase.ONBOARDING,
        "current_mode": LearningModeEnum.FREE_CONVERSATION,
        "turn_count": 1,
        "conversation_history": [{"role": "user", "content": "Hi"}],
        "corrections_made": [],
        "vocabulary_reviewed": [],
        "should_end_session": False,
    }

    with patch(
        "app.services.conversation_runtime.controller.run_agent_turn_v2",
        new=AsyncMock(return_value=next_state),
    ):
        outcome = await controller.handle_message({"type": "text", "text": "Hi", "source": "composer"})

    assert any(
        event.get("type") == "transcript"
        and event.get("role") == "assistant"
        and "current role" in event.get("text", "")
        for event in outcome.events
    )
    assert not any(event.get("type") == "audio" for event in outcome.events)
    tts_provider.synthesize.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_facing_first_turn_onboarding_connection_glitch_degrades_cleanly():
    state = await initialize_session_v2(
        user_id=1,
        session_id="session-first-turn",
        username="Student",
        is_new_user=True,
    )
    state = await run_agent_turn_v2(state)

    llm = MagicMock()
    llm.generate = AsyncMock(
        side_effect=[
            RuntimeError("Connection error."),
            RuntimeError("Connection error."),
        ]
    )

    with patch("app.agent.nodes_v2.onboarding.get_llm_provider", return_value=llm), patch(
        "app.agent.nodes_v2.onboarding.get_prompt_service",
        return_value=MagicMock(log_usage=AsyncMock()),
    ), patch(
        "app.agent.nodes_v2.onboarding.get_pedagogy_logger",
        return_value=MagicMock(),
    ), patch(
        "app.agent.nodes_v2.onboarding.analyze_onboarding_turn",
        AsyncMock(return_value=None),
    ):
        updated = await run_agent_turn_v2(
            state,
            user_message="speaking better in an international team",
        )

    assert updated["needs_user_input"] is True
    assert "i'm having trouble right now" not in updated["pending_response"].lower()
    assert "workplace communication" in updated["pending_response"].lower()
    assert llm.generate.await_count == 2
