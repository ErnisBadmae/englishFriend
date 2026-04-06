"""Tests for the experimental modular voice runtime."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.state import AgentPhase, LearningModeEnum
from app.services.voice_session import BootstrapContext, SessionCompletion
from app.services.voice_runtime.controller import VoiceRuntimeDependencies, VoiceSessionController
from app.services.voice_runtime.stt import PassthroughTextSTTProvider
from app.services.voice_runtime.turn_detection import ExplicitMessageTurnDetector
from app.services.voice_runtime.tts import EdgeTTSTTSProvider


def _mock_dependencies() -> VoiceRuntimeDependencies:
    user_service = MagicMock()
    learning_plan_service = MagicMock()
    learning_plan_service.increment_session_count = AsyncMock()
    learning_plan_service.record_assessment = AsyncMock()
    vocabulary_service = MagicMock()
    memory_pipeline = MagicMock()
    memory_pipeline.process_conversation = AsyncMock()
    memory_pipeline.format_memory_for_prompt = AsyncMock(return_value="")

    return VoiceRuntimeDependencies(
        user_service_factory=lambda db: user_service,
        learning_plan_service_factory=lambda db: learning_plan_service,
        vocabulary_service_factory=lambda db: vocabulary_service,
        memory_pipeline_factory=lambda db: memory_pipeline,
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

    controller = VoiceSessionController(
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
        "app.services.voice_runtime.controller.run_agent_turn_v2",
        new=AsyncMock(return_value=next_state),
    ):
        outcome = await controller.handle_message({"type": "text", "text": "Hi"})

    assert outcome.should_close is False
    assert outcome.status is None
    assert outcome.events[0] == {"type": "transcript", "role": "user", "text": "Hi"}
    assert any(
        event.get("type") == "phase_changed" and event.get("phase") == "learning_session"
        for event in outcome.events
    )
    assert any(
        event.get("type") == "transcript"
        and event.get("role") == "assistant"
        and "project you shipped" in event.get("text", "")
        for event in outcome.events
    )
    assert any(event.get("type") == "audio" for event in outcome.events)


@pytest.mark.asyncio
async def test_controller_explicit_end_runs_farewell_and_persists_state():
    deps = VoiceRuntimeDependencies(
        user_service_factory=lambda db: MagicMock(),
        learning_plan_service_factory=lambda db: MagicMock(),
        vocabulary_service_factory=lambda db: MagicMock(),
        memory_pipeline_factory=lambda db: MagicMock(),
    )

    tts_provider = MagicMock()
    tts_provider.synthesize = AsyncMock(return_value=b"bye-audio")

    controller = VoiceSessionController(
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
    }

    with patch(
        "app.services.voice_runtime.controller.run_agent_turn_v2",
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
    controller._persistence_service.persist.assert_awaited_once()


@pytest.mark.asyncio
async def test_controller_initialize_passes_explicit_mission_contract_to_bootstrap():
    controller = VoiceSessionController(
        db=AsyncMock(),
        user_id=11,
        mode="free_conversation",
        interview_track=None,
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
        "app.services.voice_runtime.controller.run_agent_turn_v2",
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
    )
