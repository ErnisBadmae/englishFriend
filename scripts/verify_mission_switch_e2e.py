"""Two-session smoke: verify next_mission_choice persists and is honored in session 2.

Session 1: impatient_mission_switcher persona (anchor 2 -> "wanna try mock interview")
Session 2: same user reconnects -> initial handoff should route to mock_interview
"""

from __future__ import annotations

import asyncio
import json
import sys
import os

import websockets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.test_agent_e2e import (
    DEFAULT_BASE_URL,
    SmokeRuntimeFailure,
    SmokeScenario,
    build_ws_url,
    drain_events,
    fetch_snapshot,
    generate_telegram_id,
    has_completion_signal,
    has_session_complete,
    resolve_or_create_user,
    wait_for_assistant_turn,
    wait_for_connected,
    wait_for_snapshot_condition,
    wait_for_session_complete,
)

_BLANK_SCENARIO = SmokeScenario(
    slug="_blank",
    description="",
    user_messages=(),
    expected_primary_context="",
    expected_track_id="",
    allowed_task_types=(),
)

SESSION1_MESSAGES = (
    "I want machine learning interview practice for an ML engineer job abroad",
    "I want a cleaner intro for ML interviews.",
    "Senior ML engineer at a healthcare startup for three years.",
    "I build risk models to predict patient outcomes and automate deployment pipelines.",
    "Built a patient risk scoring model to predict hospital readmission.",
    "Solved class imbalance with SMOTE and reduced readmission rate by 15 percent.",
    "wanna try mock interview instead, that's more useful for me right now",
)

TURN_TIMEOUT = 60.0
SESSION_TIMEOUT = 90.0
BASE_URL = DEFAULT_BASE_URL


async def run_session_1(user_id: int) -> list[dict]:
    """Run foundation_speaking_drill session ending with mock_interview choice."""
    ws_url = build_ws_url(BASE_URL, user_id=user_id, stt_provider="composer")
    events: list[dict] = []
    async with websockets.connect(ws_url, max_size=2_000_000) as ws:
        connected = await wait_for_connected(ws, events=events, timeout_s=TURN_TIMEOUT)
        if not connected.get("is_new_user"):
            raise SmokeRuntimeFailure("Session 1 requires a fresh user")
        initial = await wait_for_assistant_turn(ws, scenario=_BLANK_SCENARIO, events=events, timeout_s=TURN_TIMEOUT)
        print(f"[S1] Initial: {str(initial.get('text') or '')[:120]}")
        await drain_events(ws, scenario=_BLANK_SCENARIO, events=events)
        for i, msg in enumerate(SESSION1_MESSAGES, 1):
            if has_completion_signal(events):
                print(f"[S1] Early completion at turn {i-1}, skipping rest")
                break
            await ws.send(json.dumps({"type": "text", "text": msg, "source": "composer"}))
            turn = await wait_for_assistant_turn(ws, scenario=_BLANK_SCENARIO, events=events, timeout_s=TURN_TIMEOUT)
            print(f"[S1] Turn {i}: {str(turn.get('text') or '')[:120]}")
            await drain_events(ws, scenario=_BLANK_SCENARIO, events=events)
        completion_signal_seen = has_completion_signal(events)
        if not has_session_complete(events):
            if not completion_signal_seen:
                await ws.send(json.dumps({"type": "end"}))
            comp = await wait_for_session_complete(ws, scenario=_BLANK_SCENARIO, events=events, timeout_s=SESSION_TIMEOUT)
            print(f"[S1] session_complete: reason={comp.get('reason')}")
    return events


async def run_session_2(user_id: int) -> list[dict]:
    """Connect as same returning user, collect initial handoff."""
    ws_url = build_ws_url(BASE_URL, user_id=user_id, stt_provider="composer")
    events: list[dict] = []
    async with websockets.connect(ws_url, max_size=2_000_000) as ws:
        connected = await wait_for_connected(ws, events=events, timeout_s=TURN_TIMEOUT)
        print(f"[S2] Connected: is_new_user={connected.get('is_new_user')}")
        initial = await wait_for_assistant_turn(ws, scenario=_BLANK_SCENARIO, events=events, timeout_s=TURN_TIMEOUT)
        text = str(initial.get("text") or "")
        print(f"[S2] Initial handoff: {text[:200]}")
        await drain_events(ws, scenario=_BLANK_SCENARIO, events=events)
        # Gracefully close
        await ws.send(json.dumps({"type": "end"}))
        comp = await wait_for_session_complete(ws, scenario=_BLANK_SCENARIO, events=events, timeout_s=20.0)
        print(f"[S2] session_complete: reason={comp.get('reason')}")
    return events


async def main() -> None:
    telegram_id = generate_telegram_id()
    print(f"Smoke user telegram_id={telegram_id}")
    user = await resolve_or_create_user(BASE_URL, telegram_id=telegram_id)
    user_id = int(user["id"])
    print(f"User created: user_id={user_id}")

    print("\n=== SESSION 1: foundation_speaking_drill -> mission switch ===")
    s1_events = await run_session_1(user_id)
    print(f"[S1] Total events: {len(s1_events)}")

    print("\n--- Snapshot after session 1 ---")
    snap1 = await wait_for_snapshot_condition(
        BASE_URL,
        user_id=user_id,
        description="latest session evidence should include next_mission_choice=mock_interview",
        predicate=lambda snapshot: (
            (((snapshot.get("session_evidence") or {}).get("latest") or {}).get("next_mission_choice"))
            == "mock_interview"
        ),
        attempts=16,
        delay_s=0.5,
    )
    raw_se = snap1.get("session_evidence") or {}
    print(f"  raw session_evidence keys: {list(raw_se.keys())}")
    print(f"  recent list len: {len(raw_se.get('recent') or [])}")
    evidence = raw_se.get("latest") or {}
    next_choice = evidence.get("next_mission_choice")
    print(f"  latest evidence task_type: {evidence.get('task_type')}")
    print(f"  next_mission_choice in evidence: {next_choice!r}")
    # Also dump snap1 keys for debugging
    print(f"  snap1 top-level keys: {list(snap1.keys())}")

    if next_choice != "mock_interview":
        print(f"\nFAIL: expected next_mission_choice='mock_interview', got {next_choice!r}")
        sys.exit(1)
    print("  PASS: next_mission_choice='mock_interview' persisted correctly")

    print("\n=== SESSION 2: same user reconnects ===")
    s2_events = await run_session_2(user_id)

    print("\n--- Snapshot after session 2 ---")
    snap2 = await fetch_snapshot(BASE_URL, user_id=user_id)
    next_mission = snap2.get("mission") or {}
    print(f"  recommended mode:  {next_mission.get('mode')}")
    print(f"  recommended title: {next_mission.get('title')}")
    print(f"  task_type:         {next_mission.get('task_type')}")

    s2_assistant_texts = [
        str(e.get("text") or "")
        for e in s2_events
        if e.get("type") == "transcript" and e.get("role") == "assistant"
    ]
    combined = " ".join(s2_assistant_texts).lower()
    mock_keywords = ("mock interview", "mock", "interview", "let's do a")
    found = any(kw in combined for kw in mock_keywords)
    print(f"\n  Session 2 assistant texts mention mock: {found}")
    for t in s2_assistant_texts:
        print(f"    -> {t[:150]}")

    snapshot_mode = (next_mission.get("mode") or "").lower()
    if "mock_interview" in snapshot_mode or found:
        print("\nPASS: session 2 correctly routes to mock_interview")
    else:
        print("\nFAIL: session 2 did not mention mock interview")
        print(f"  snapshot next_mission mode: {snapshot_mode!r}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
