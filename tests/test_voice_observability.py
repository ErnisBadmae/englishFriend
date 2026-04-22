"""Unit tests for shared voice observability helpers."""

from app.core.observability import (
    clear_request_context,
    get_runtime,
    get_session_id,
    get_turn_id,
    get_user_id,
)
from app.services.voice_observability import (
    VoiceSessionScope,
    bind_voice_context,
    enrich_ws_event,
    make_turn_envelope,
)


def test_bind_voice_context_sets_runtime_session_user_and_turn():
    scope = VoiceSessionScope(
        runtime="chat_v2",
        session_id="session-123",
        user_id=77,
        agent_version="v2",
        mission_task_type="foundation_speaking_drill",
        stt_provider="browser_vosk",
    )

    bind_voice_context(scope, turn_id="t3")

    assert get_runtime() == "chat_v2"
    assert get_session_id() == "session-123"
    assert get_user_id() == 77
    assert get_turn_id() == "t3"

    clear_request_context()


def test_enrich_ws_event_attaches_optional_observability_metadata():
    scope = VoiceSessionScope(
        runtime="realtime",
        session_id="session-456",
        user_id=5,
        agent_version="v2",
        mission_task_type="project_walkthrough_drill",
        stt_provider="browser_vosk",
    )
    envelope = make_turn_envelope(
        scope,
        turn_id="t1",
        turn_index=1,
        phase="learning_session",
        mode="free_conversation",
    )

    payload = enrich_ws_event(
        {"type": "transcript", "role": "assistant", "text": "Hello"},
        envelope=envelope,
    )

    assert payload["runtime"] == "realtime"
    assert payload["turn_id"] == "t1"
    assert payload["turn_index"] == 1
    assert payload["phase"] == "learning_session"
    assert payload["mode"] == "free_conversation"
    assert payload["agent_version"] == "v2"
    assert payload["stt_provider"] == "browser_vosk"
