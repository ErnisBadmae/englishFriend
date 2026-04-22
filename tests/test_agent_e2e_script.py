import sys
from argparse import Namespace
from unittest.mock import AsyncMock

import pytest

from scripts.test_agent_e2e import (
    ROUTING_SCENARIO_SET,
    SCENARIOS,
    SmokeForbiddenTaskType,
    SmokeRuntimeFailure,
    SmokeSnapshotMismatch,
    assert_event_contract,
    assert_snapshot_contract,
    async_main,
    build_snapshot_url,
    build_user_create_url,
    build_user_lookup_url,
    build_ws_url,
    classify_failure,
    has_session_complete,
    parse_args,
    resolve_scenario_slugs,
)


def test_build_ws_url_uses_chat_v2_and_composer() -> None:
    url = build_ws_url("http://localhost:8000", user_id=123, stt_provider="composer")

    assert url == "ws://localhost:8000/api/v1/voice/chat/v2?user_id=123&stt_provider=composer"


def test_build_snapshot_url_uses_program_snapshot_path() -> None:
    url = build_snapshot_url("https://example.com/base", user_id=321)

    assert url == "https://example.com/base/api/v1/programs/321/snapshot"


def test_build_user_lookup_url_uses_telegram_identity_path() -> None:
    url = build_user_lookup_url("https://example.com/base", telegram_id=777)

    assert url == "https://example.com/base/api/v1/users/telegram/777"


def test_build_user_create_url_uses_users_collection() -> None:
    url = build_user_create_url("https://example.com/base")

    assert url == "https://example.com/base/api/v1/users/"


def test_routing_scenario_set_lists_all_three_canonical_scenarios() -> None:
    assert ROUTING_SCENARIO_SET == (
        "workplace_priority_regression",
        "interview_priority_regression",
        "project_priority_regression",
    )


def test_interview_priority_regression_contract_is_exact_entry_mission() -> None:
    scenario = SCENARIOS["interview_priority_regression"]

    assert scenario.expected_primary_context == "interviews"
    assert scenario.expected_track_id == "hr_intro"
    assert scenario.allowed_task_types == ("foundation_speaking_drill",)


def test_project_priority_regression_contract_is_exact_entry_mission() -> None:
    scenario = SCENARIOS["project_priority_regression"]

    assert scenario.expected_primary_context == "project_walkthrough"
    assert scenario.expected_track_id == "project_walkthrough"
    assert scenario.allowed_task_types == ("technical_project_walkthrough",)


def test_assert_event_contract_rejects_handshake_glitch() -> None:
    scenario = SCENARIOS["workplace_priority_regression"]

    event = {
        "type": "transcript",
        "role": "assistant",
        "text": "I'm having trouble right now. Could you repeat that?",
    }

    with pytest.raises(SmokeRuntimeFailure, match="forbidden substring"):
        assert_event_contract(event, scenario)


def test_assert_snapshot_contract_accepts_workplace_priority_snapshot() -> None:
    scenario = SCENARIOS["workplace_priority_regression"]
    snapshot = {
        "goal": {
            "brief": {
                "main_contexts": ["workplace_communication", "project_walkthrough"],
            }
        },
        "interview": {
            "recommended_track": {"id": "workplace_communication"},
        },
        "mission": {
            "task_type": "stakeholder_explanation_drill",
            "title": "Explain the project to a stakeholder",
        },
    }

    assert_snapshot_contract(snapshot, scenario)


def test_assert_snapshot_contract_accepts_interview_priority_entry_mission() -> None:
    scenario = SCENARIOS["interview_priority_regression"]
    snapshot = {
        "goal": {"brief": {"main_contexts": ["interviews", "project_walkthrough"]}},
        "interview": {"recommended_track": {"id": "hr_intro"}},
        "mission": {"task_type": "foundation_speaking_drill"},
    }

    assert_snapshot_contract(snapshot, scenario)


def test_assert_snapshot_contract_accepts_project_priority_entry_mission() -> None:
    scenario = SCENARIOS["project_priority_regression"]
    snapshot = {
        "goal": {"brief": {"main_contexts": ["project_walkthrough", "interviews"]}},
        "interview": {"recommended_track": {"id": "project_walkthrough"}},
        "mission": {"task_type": "technical_project_walkthrough"},
    }

    assert_snapshot_contract(snapshot, scenario)


def test_assert_snapshot_contract_rejects_task_type_outside_allowed_set() -> None:
    scenario = SCENARIOS["interview_priority_regression"]
    snapshot = {
        "goal": {"brief": {"main_contexts": ["interviews"]}},
        "interview": {"recommended_track": {"id": "hr_intro"}},
        "mission": {"task_type": "workplace_update_drill"},
    }

    with pytest.raises(SmokeSnapshotMismatch, match="Expected mission.task_type in"):
        assert_snapshot_contract(snapshot, scenario)


def test_assert_snapshot_contract_rejects_forbidden_task_type() -> None:
    scenario = SCENARIOS["workplace_priority_regression"]
    snapshot = {
        "goal": {"brief": {"main_contexts": ["workplace_communication"]}},
        "interview": {"recommended_track": {"id": "workplace_communication"}},
        "mission": {"task_type": "tradeoff_explanation_drill"},
    }

    with pytest.raises(SmokeForbiddenTaskType, match="explicitly forbidden"):
        assert_snapshot_contract(snapshot, scenario)


def test_classify_failure_returns_expected_labels() -> None:
    assert classify_failure(SmokeRuntimeFailure("boom")) == "runtime"
    assert classify_failure(SmokeSnapshotMismatch("boom")) == "snapshot_mismatch"
    assert classify_failure(SmokeForbiddenTaskType("boom")) == "forbidden_task_type"


def test_has_session_complete_detects_completion_event() -> None:
    events = [
        {"type": "connected"},
        {"type": "transcript", "role": "assistant", "text": "Hello"},
        {"type": "session_complete", "reason": "baseline_complete", "return_screen": "home"},
    ]

    assert has_session_complete(events) is True


def test_parse_args_defaults_to_single_workplace_scenario(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["test_agent_e2e.py"])

    args = parse_args()

    assert args.scenario == "workplace_priority_regression"
    assert args.scenario_set is None


def test_parse_args_accepts_routing_scenario_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["test_agent_e2e.py", "--scenario-set", "routing"])

    args = parse_args()

    assert args.scenario is None
    assert args.scenario_set == "routing"


def test_resolve_scenario_slugs_returns_routing_set() -> None:
    args = Namespace(scenario=None, scenario_set="routing")

    assert resolve_scenario_slugs(args) == ROUTING_SCENARIO_SET


@pytest.mark.asyncio
async def test_async_main_runs_all_routing_scenarios_and_aggregates_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scripts.test_agent_e2e.parse_args",
        lambda: Namespace(
            scenario=None,
            scenario_set="routing",
            base_url="http://localhost:8000",
            telegram_id=None,
            turn_timeout=8.0,
            session_timeout=15.0,
        ),
    )
    mocked = AsyncMock(side_effect=[(True, "pass"), (True, "pass"), (True, "pass")])
    monkeypatch.setattr("scripts.test_agent_e2e.run_cli_scenario", mocked)
    monkeypatch.setattr("scripts.test_agent_e2e.generate_telegram_id", lambda: 999000111)

    exit_code = await async_main()

    assert exit_code == 0
    assert mocked.await_count == 3


@pytest.mark.asyncio
async def test_async_main_returns_nonzero_when_any_routing_scenario_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scripts.test_agent_e2e.parse_args",
        lambda: Namespace(
            scenario=None,
            scenario_set="routing",
            base_url="http://localhost:8000",
            telegram_id=None,
            turn_timeout=8.0,
            session_timeout=15.0,
        ),
    )
    mocked = AsyncMock(
        side_effect=[
            (True, "pass"),
            (False, "snapshot_mismatch"),
            (True, "pass"),
        ]
    )
    monkeypatch.setattr("scripts.test_agent_e2e.run_cli_scenario", mocked)
    monkeypatch.setattr("scripts.test_agent_e2e.generate_telegram_id", lambda: 999000222)

    exit_code = await async_main()

    assert exit_code == 1
    assert mocked.await_count == 3
