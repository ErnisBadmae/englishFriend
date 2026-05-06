import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from scripts.verify_mission_switch_e2e import SESSION1_MESSAGES, run_session_1


class _FakeWebSocketContext:
    def __init__(self, websocket: MagicMock) -> None:
        self._websocket = websocket

    async def __aenter__(self) -> MagicMock:
        return self._websocket

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


@pytest.mark.asyncio
async def test_run_session_1_waits_for_real_session_complete_after_finishing_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    websocket = MagicMock()
    websocket.send = AsyncMock()

    monkeypatch.setattr(
        "scripts.verify_mission_switch_e2e.websockets.connect",
        lambda *args, **kwargs: _FakeWebSocketContext(websocket),
    )
    monkeypatch.setattr(
        "scripts.verify_mission_switch_e2e.wait_for_connected",
        AsyncMock(return_value={"is_new_user": True}),
    )
    monkeypatch.setattr(
        "scripts.verify_mission_switch_e2e.wait_for_assistant_turn",
        AsyncMock(
            side_effect=[
                {"type": "transcript", "role": "assistant", "text": "Initial"},
                *[
                    {"type": "transcript", "role": "assistant", "text": f"Turn {index}"}
                    for index in range(1, len(SESSION1_MESSAGES) + 1)
                ],
            ]
        ),
    )

    drain_count = {"value": 0}

    async def fake_drain(_websocket, *, scenario, events, idle_timeout_s=0.2) -> None:
        drain_count["value"] += 1
        if drain_count["value"] == len(SESSION1_MESSAGES) + 1:
            events.extend(
                [
                    {
                        "type": "session_finishing",
                        "reason": "session_end",
                        "return_screen": "home",
                        "pending_persistence": True,
                    },
                    {
                        "type": "transcript",
                        "role": "assistant",
                        "phase": "session_end",
                        "text": "Thanks for practicing today.",
                    },
                ]
            )

    monkeypatch.setattr("scripts.verify_mission_switch_e2e.drain_events", fake_drain)
    wait_for_session_complete = AsyncMock(
        return_value={"type": "session_complete", "reason": "session_end", "return_screen": "home"}
    )
    monkeypatch.setattr(
        "scripts.verify_mission_switch_e2e.wait_for_session_complete",
        wait_for_session_complete,
    )

    events = await run_session_1(user_id=42)

    wait_for_session_complete.assert_awaited_once()
    payloads = [json.loads(call.args[0]) for call in websocket.send.await_args_list]
    assert sum(1 for payload in payloads if payload.get("type") == "text") == len(SESSION1_MESSAGES)
    assert not any(payload.get("type") == "end" for payload in payloads)
    assert any(event.get("type") == "session_finishing" for event in events)
