"""CLI smoke runner for the real /chat/v2 flow.

This script intentionally targets the live backend and the currently configured
LLM path. The first scenario is a narrow regression smoke for workplace-first
onboarding and mission routing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse
from uuid import uuid4

import httpx
import websockets


DEFAULT_BASE_URL = "http://localhost:8000"


class SmokeFailure(RuntimeError):
    """Raised when the live smoke violates an explicit contract."""


class SmokeRuntimeFailure(SmokeFailure):
    """Raised when the live smoke fails before snapshot contract validation."""


class SmokeSnapshotMismatch(SmokeFailure):
    """Raised when the live snapshot violates the expected routing contract."""


class SmokeForbiddenTaskType(SmokeSnapshotMismatch):
    """Raised when the live snapshot returns an explicitly forbidden task type."""


@dataclass(frozen=True)
class SmokeScenario:
    slug: str
    description: str
    user_messages: tuple[str, ...]
    expected_primary_context: str
    expected_track_id: str
    allowed_task_types: tuple[str, ...]
    forbidden_task_types: tuple[str, ...] = ()
    forbidden_assistant_substrings: tuple[str, ...] = ()


SCENARIOS: dict[str, SmokeScenario] = {
    "workplace_priority_regression": SmokeScenario(
        slug="workplace_priority_regression",
        description="Workplace-first onboarding should route to workplace track and stakeholder mission.",
        user_messages=(
            "speaking better in an international team",
            "ML engineer job abroad",
            "now i am just learning ml theory and try to learn some math theorems and building pet project",
            "ML engineer job abroad",
            "building ai agent and created RAG pipeline",
        ),
        expected_primary_context="workplace_communication",
        expected_track_id="workplace_communication",
        allowed_task_types=("stakeholder_explanation_drill",),
        forbidden_task_types=("tradeoff_explanation_drill",),
        forbidden_assistant_substrings=(
            "i'm having trouble right now",
            "server error. please refresh the page.",
        ),
    ),
    "interview_priority_regression": SmokeScenario(
        slug="interview_priority_regression",
        description="Interview-first onboarding should keep interviews primary and recommend hr_intro.",
        user_messages=(
            "I want machine learning interview practice for a job abroad",
            "I work as a data analyst now",
            "ML engineer",
            "My recent project was churn prediction for e-commerce",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        allowed_task_types=("foundation_speaking_drill",),
        forbidden_assistant_substrings=(
            "i'm having trouble right now",
            "server error. please refresh the page.",
        ),
    ),
    "project_priority_regression": SmokeScenario(
        slug="project_priority_regression",
        description="Project-first onboarding should keep project walkthrough primary and recommend project track.",
        user_messages=(
            "I want to explain my machine learning projects more clearly for an ML engineer job abroad",
            "I work as a data analyst now",
            "ML engineer",
            "I built a RAG pipeline and explained tradeoff between latency and answer quality",
        ),
        expected_primary_context="project_walkthrough",
        expected_track_id="project_walkthrough",
        allowed_task_types=("technical_project_walkthrough",),
        forbidden_assistant_substrings=(
            "i'm having trouble right now",
            "server error. please refresh the page.",
        ),
    ),
}

ROUTING_SCENARIO_SET = (
    "workplace_priority_regression",
    "interview_priority_regression",
    "project_priority_regression",
)


def build_ws_url(base_url: str, *, user_id: int, stt_provider: str = "composer") -> str:
    parsed = urlparse(base_url.rstrip("/"))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    path = f"{parsed.path.rstrip('/')}/api/v1/voice/chat/v2"
    query = urlencode({"user_id": user_id, "stt_provider": stt_provider})
    return urlunparse((scheme, parsed.netloc, path, "", query, ""))


def build_snapshot_url(base_url: str, *, user_id: int) -> str:
    parsed = urlparse(base_url.rstrip("/"))
    path = f"{parsed.path.rstrip('/')}/api/v1/programs/{user_id}/snapshot"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def build_user_lookup_url(base_url: str, *, telegram_id: int) -> str:
    parsed = urlparse(base_url.rstrip("/"))
    path = f"{parsed.path.rstrip('/')}/api/v1/users/telegram/{telegram_id}"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def build_user_create_url(base_url: str) -> str:
    parsed = urlparse(base_url.rstrip("/"))
    path = f"{parsed.path.rstrip('/')}/api/v1/users/"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def generate_telegram_id() -> int:
    return 900_000_000 + (uuid4().int % 99_000_000)


async def resolve_or_create_user(base_url: str, *, telegram_id: int, timeout_s: float = 10.0) -> dict[str, Any]:
    lookup_url = build_user_lookup_url(base_url, telegram_id=telegram_id)
    create_url = build_user_create_url(base_url)

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        try:
            response = await client.get(lookup_url)
            if response.status_code == 200:
                payload = response.json()
                if not isinstance(payload, dict):
                    raise SmokeRuntimeFailure("Resolved user payload must be a JSON object")
                return payload
            if response.status_code != 404:
                raise SmokeRuntimeFailure(
                    f"User lookup failed for telegram_id={telegram_id}: HTTP {response.status_code} {response.text[:200]}"
                )
        except httpx.HTTPError as exc:
            raise SmokeRuntimeFailure(f"User lookup request failed: {exc}") from exc

        try:
            response = await client.post(
                create_url,
                json={
                    "telegram_id": telegram_id,
                    "username": f"smoke_{telegram_id}",
                    "language_level": "B1",
                },
            )
        except httpx.HTTPError as exc:
            raise SmokeRuntimeFailure(f"User create request failed: {exc}") from exc

        if response.status_code not in {200, 201}:
            raise SmokeRuntimeFailure(
                f"User create failed for telegram_id={telegram_id}: HTTP {response.status_code} {response.text[:200]}"
            )

        payload = response.json()
        if not isinstance(payload, dict):
            raise SmokeRuntimeFailure("Created user payload must be a JSON object")
        return payload


def event_summary(event: dict[str, Any]) -> str:
    event_type = str(event.get("type") or "unknown")
    role = str(event.get("role") or "")
    phase = str(event.get("phase") or "")
    mode = str(event.get("mode") or "")
    text = str(event.get("text") or event.get("message") or "").strip().replace("\n", " ")
    text = text[:120]
    parts = [event_type]
    if role:
        parts.append(f"role={role}")
    if phase:
        parts.append(f"phase={phase}")
    if mode:
        parts.append(f"mode={mode}")
    if text:
        parts.append(f"text={text}")
    return " | ".join(parts)


def assert_event_contract(event: dict[str, Any], scenario: SmokeScenario) -> None:
    event_type = str(event.get("type") or "")
    if event_type == "error":
        message = str(event.get("message") or "").strip()
        raise SmokeRuntimeFailure(f"Received websocket error: {message or 'unknown error'}")

    if event_type != "transcript" or str(event.get("role") or "") != "assistant":
        return

    assistant_text = str(event.get("text") or "").strip()
    normalized = assistant_text.lower()
    for needle in scenario.forbidden_assistant_substrings:
        if needle in normalized:
            raise SmokeRuntimeFailure(
                f"Assistant response matched forbidden substring '{needle}': {assistant_text}"
            )


def assert_snapshot_contract(snapshot: dict[str, Any], scenario: SmokeScenario) -> None:
    goal = snapshot.get("goal") or {}
    goal_brief = goal.get("brief") or {}
    mission = snapshot.get("mission") or {}
    interview = snapshot.get("interview") or {}
    recommended_track = interview.get("recommended_track") or {}

    main_contexts = goal_brief.get("main_contexts") or []
    primary_context = str(main_contexts[0] if main_contexts else "").strip()
    if primary_context != scenario.expected_primary_context:
        raise SmokeSnapshotMismatch(
            f"Expected primary context '{scenario.expected_primary_context}', got '{primary_context or 'missing'}'"
        )

    recommended_track_id = str(recommended_track.get("id") or "").strip()
    if recommended_track_id != scenario.expected_track_id:
        raise SmokeSnapshotMismatch(
            f"Expected recommended track '{scenario.expected_track_id}', got '{recommended_track_id or 'missing'}'"
        )

    task_type = str(mission.get("task_type") or "").strip()
    if task_type in scenario.forbidden_task_types:
        raise SmokeForbiddenTaskType(
            f"Mission task_type '{task_type}' is explicitly forbidden for this scenario"
        )

    if task_type not in scenario.allowed_task_types:
        allowed = ", ".join(scenario.allowed_task_types)
        raise SmokeSnapshotMismatch(
            f"Expected mission.task_type in ({allowed}), got '{task_type or 'missing'}'"
        )


async def receive_event(websocket: Any, timeout_s: float) -> dict[str, Any]:
    raw = await asyncio.wait_for(websocket.recv(), timeout=timeout_s)
    if not isinstance(raw, str):
        raise SmokeRuntimeFailure(f"Expected text websocket frame, got {type(raw).__name__}")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SmokeRuntimeFailure(f"Invalid JSON from websocket: {exc}") from exc
    if not isinstance(payload, dict):
        raise SmokeRuntimeFailure("Expected websocket event to be a JSON object")
    return payload


async def wait_for_connected(
    websocket: Any,
    *,
    events: list[dict[str, Any]],
    timeout_s: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SmokeRuntimeFailure("Timed out waiting for connected event")
        event = await receive_event(websocket, remaining)
        events.append(event)
        if str(event.get("type") or "") == "connected":
            return event


async def wait_for_assistant_turn(
    websocket: Any,
    *,
    scenario: SmokeScenario,
    events: list[dict[str, Any]],
    timeout_s: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SmokeRuntimeFailure("Timed out waiting for assistant transcript")
        event = await receive_event(websocket, remaining)
        events.append(event)
        assert_event_contract(event, scenario)
        if (
            str(event.get("type") or "") == "transcript"
            and str(event.get("role") or "") == "assistant"
            and str(event.get("text") or "").strip()
        ):
            return event


async def wait_for_session_complete(
    websocket: Any,
    *,
    scenario: SmokeScenario,
    events: list[dict[str, Any]],
    timeout_s: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SmokeRuntimeFailure("Timed out waiting for session_complete")
        event = await receive_event(websocket, remaining)
        events.append(event)
        assert_event_contract(event, scenario)
        if str(event.get("type") or "") == "session_complete":
            return event


async def drain_events(
    websocket: Any,
    *,
    scenario: SmokeScenario,
    events: list[dict[str, Any]],
    idle_timeout_s: float = 0.2,
) -> None:
    while True:
        try:
            event = await receive_event(websocket, idle_timeout_s)
        except (asyncio.TimeoutError, TimeoutError):
            return
        events.append(event)
        assert_event_contract(event, scenario)


async def fetch_snapshot(
    base_url: str,
    *,
    user_id: int,
    attempts: int = 6,
    delay_s: float = 0.5,
    timeout_s: float = 10.0,
) -> dict[str, Any]:
    url = build_snapshot_url(base_url, user_id=user_id)
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        last_error: str | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    payload = response.json()
                    if not isinstance(payload, dict):
                        raise SmokeRuntimeFailure("Snapshot response must be a JSON object")
                    return payload
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            except httpx.HTTPError as exc:
                last_error = str(exc)
            if attempt < attempts:
                await asyncio.sleep(delay_s)
        raise SmokeRuntimeFailure(f"Failed to fetch snapshot after {attempts} attempts: {last_error or 'unknown error'}")


def print_tail(events: list[dict[str, Any]], *, limit: int = 14) -> None:
    print("\nEvent tail:")
    for index, event in enumerate(events[-limit:], start=max(1, len(events) - limit + 1)):
        print(f"  [{index}] {event_summary(event)}")


def format_event_tail(events: list[dict[str, Any]], *, limit: int = 8) -> str:
    if not events:
        return "no events captured"
    return " || ".join(event_summary(event) for event in events[-limit:])


def has_session_complete(events: list[dict[str, Any]]) -> bool:
    return any(str(event.get("type") or "") == "session_complete" for event in events)


def print_snapshot_summary(snapshot: dict[str, Any]) -> None:
    goal_brief = ((snapshot.get("goal") or {}).get("brief") or {})
    interview = snapshot.get("interview") or {}
    recommended_track = interview.get("recommended_track") or {}
    mission = snapshot.get("mission") or {}
    print("\nSnapshot summary:")
    print(f"  primary_context: {(goal_brief.get('main_contexts') or [''])[0] if goal_brief.get('main_contexts') else ''}")
    print(f"  recommended_track: {recommended_track.get('id') or ''}")
    print(f"  mission_task_type: {mission.get('task_type') or ''}")
    print(f"  mission_title: {mission.get('title') or ''}")


def classify_failure(exc: SmokeFailure) -> str:
    if isinstance(exc, SmokeForbiddenTaskType):
        return "forbidden_task_type"
    if isinstance(exc, SmokeSnapshotMismatch):
        return "snapshot_mismatch"
    return "runtime"


async def run_scenario(
    *,
    base_url: str,
    scenario: SmokeScenario,
    telegram_id: int,
    turn_timeout_s: float,
    session_timeout_s: float,
) -> dict[str, Any]:
    user = await resolve_or_create_user(base_url, telegram_id=telegram_id)
    resolved_user_id = int(user.get("id") or 0)
    if resolved_user_id <= 0:
        raise SmokeRuntimeFailure(f"Resolved user payload has invalid id: {user}")

    ws_url = build_ws_url(base_url, user_id=resolved_user_id, stt_provider="composer")
    snapshot_user_id = resolved_user_id
    events: list[dict[str, Any]] = []
    completion_seen = False

    try:
        async with websockets.connect(ws_url, max_size=2_000_000) as websocket:
            connected = await wait_for_connected(websocket, events=events, timeout_s=turn_timeout_s)
            if not bool(connected.get("is_new_user")):
                raise SmokeRuntimeFailure("Smoke scenario requires a fresh user, but connected payload was not marked as new")

            initial_assistant = await wait_for_assistant_turn(
                websocket,
                scenario=scenario,
                events=events,
                timeout_s=turn_timeout_s,
            )
            print(f"Initial assistant: {str(initial_assistant.get('text') or '').strip()[:140]}")
            await drain_events(websocket, scenario=scenario, events=events)

            for index, message in enumerate(scenario.user_messages, start=1):
                if has_session_complete(events):
                    completion_seen = True
                    break
                payload = {"type": "text", "text": message, "source": "composer"}
                await websocket.send(json.dumps(payload))
                assistant = await wait_for_assistant_turn(
                    websocket,
                    scenario=scenario,
                    events=events,
                    timeout_s=turn_timeout_s,
                )
                assistant_text = str(assistant.get("text") or "").strip()
                print(f"Turn {index} assistant: {assistant_text[:140]}")
                await drain_events(websocket, scenario=scenario, events=events)

            completion_seen = completion_seen or has_session_complete(events)
            if not completion_seen:
                completion_event = await wait_for_session_complete(
                    websocket,
                    scenario=scenario,
                    events=events,
                    timeout_s=session_timeout_s,
                )
                completion_seen = True
                print(f"Session complete: reason={completion_event.get('reason')}, return_screen={completion_event.get('return_screen')}")

            if not completion_seen:
                raise SmokeRuntimeFailure("Scenario finished without session_complete")

    except websockets.exceptions.WebSocketException as exc:
        raise SmokeRuntimeFailure(
            f"Websocket flow failed after {len(events)} events: {exc}. "
            f"Tail: {format_event_tail(events)}"
        ) from exc
    except OSError as exc:
        raise SmokeRuntimeFailure(
            f"Could not connect to {ws_url}. Make sure the backend is running and reachable. Details: {exc}"
        ) from exc

    snapshot = await fetch_snapshot(base_url, user_id=snapshot_user_id)
    assert_snapshot_contract(snapshot, scenario)
    return {
        "events": events,
        "snapshot": snapshot,
        "user_id": snapshot_user_id,
        "telegram_id": telegram_id,
        "ws_url": ws_url,
        "user": user,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a real websocket smoke against /api/v1/voice/chat/v2.")
    parser.add_argument(
        "--scenario",
        default=None,
        choices=sorted(SCENARIOS),
        help="Smoke scenario to execute.",
    )
    parser.add_argument(
        "--scenario-set",
        default=None,
        choices=("routing",),
        help="Named scenario set to execute sequentially.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Backend base URL. Default: http://localhost:8000",
    )
    parser.add_argument(
        "--telegram-id",
        type=int,
        default=None,
        help="Optional Telegram/dev identity used for resolve-or-create before websocket startup.",
    )
    parser.add_argument(
        "--turn-timeout",
        type=float,
        default=8.0,
        help="Timeout in seconds for connected and assistant-turn waits.",
    )
    parser.add_argument(
        "--session-timeout",
        type=float,
        default=15.0,
        help="Timeout in seconds for waiting on session_complete.",
    )
    args = parser.parse_args()
    if not args.scenario and not args.scenario_set:
        args.scenario = "workplace_priority_regression"
    return args


def resolve_scenario_slugs(args: argparse.Namespace) -> tuple[str, ...]:
    if args.scenario_set == "routing":
        return ROUTING_SCENARIO_SET
    return (args.scenario,)


def print_run_header(*, scenario: SmokeScenario, base_url: str, telegram_id: int) -> None:
    print("=" * 72)
    print("chat_v2 live smoke")
    print("=" * 72)
    print(f"scenario: {scenario.slug}")
    print(f"description: {scenario.description}")
    print(f"base_url: {base_url}")
    print(f"telegram_id: {telegram_id}")


async def run_cli_scenario(
    *,
    base_url: str,
    scenario: SmokeScenario,
    telegram_id: int,
    turn_timeout_s: float,
    session_timeout_s: float,
) -> tuple[bool, str]:
    print_run_header(scenario=scenario, base_url=base_url, telegram_id=telegram_id)

    try:
        result = await run_scenario(
            base_url=base_url,
            scenario=scenario,
            telegram_id=telegram_id,
            turn_timeout_s=turn_timeout_s,
            session_timeout_s=session_timeout_s,
        )
    except SmokeFailure as exc:
        failure_kind = classify_failure(exc)
        print(f"\nFAIL [{failure_kind}]: {exc}")
        return False, failure_kind
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        print(f"\nUNEXPECTED ERROR: {exc}")
        return False, "unexpected"

    print(f"resolved_user_id: {result['user_id']}")
    print_snapshot_summary(result["snapshot"])
    print_tail(result["events"])
    print("\nPASS: live smoke contracts satisfied")
    return True, "pass"


async def async_main() -> int:
    args = parse_args()
    scenario_slugs = resolve_scenario_slugs(args)

    if len(scenario_slugs) == 1:
        scenario = SCENARIOS[scenario_slugs[0]]
        telegram_id = args.telegram_id or generate_telegram_id()
        ok, _ = await run_cli_scenario(
            base_url=args.base_url,
            scenario=scenario,
            telegram_id=telegram_id,
            turn_timeout_s=args.turn_timeout,
            session_timeout_s=args.session_timeout,
        )
        return 0 if ok else 1

    print("=" * 72)
    print("chat_v2 live routing smoke")
    print("=" * 72)
    print(f"scenario_set: {args.scenario_set}")
    print(f"base_url: {args.base_url}")
    print(f"scenario_count: {len(scenario_slugs)}")

    results: list[tuple[str, bool, str]] = []
    for slug in scenario_slugs:
        print()
        scenario = SCENARIOS[slug]
        telegram_id = generate_telegram_id()
        ok, status = await run_cli_scenario(
            base_url=args.base_url,
            scenario=scenario,
            telegram_id=telegram_id,
            turn_timeout_s=args.turn_timeout,
            session_timeout_s=args.session_timeout,
        )
        results.append((slug, ok, status))

    print("\nRouting suite summary:")
    for slug, ok, status in results:
        verdict = "PASS" if ok else "FAIL"
        print(f"  {verdict} {slug} ({status})")

    return 0 if all(ok for _, ok, _ in results) else 1


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
