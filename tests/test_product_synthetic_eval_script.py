import sys
from argparse import Namespace
from unittest.mock import AsyncMock

import pytest

from scripts.test_agent_e2e import SmokeRuntimeFailure
from scripts.run_product_synthetic_eval import (
    EXPANDED_SCENARIO_SET,
    MAINLINE_SCENARIO_SET,
    MAINLINE_SCENARIOS,
    ScenarioCheck,
    ScenarioReport,
    async_main,
    evaluate_product_snapshot,
    parse_args,
    resolve_scenario_slugs,
)


def test_mainline_scenario_set_lists_three_canonical_first_value_scenarios() -> None:
    assert MAINLINE_SCENARIO_SET == (
        "workplace_first_value",
        "interview_first_value",
        "project_first_value",
    )


def test_expanded_scenario_set_adds_three_more_realistic_variants() -> None:
    assert EXPANDED_SCENARIO_SET == (
        "workplace_first_value",
        "interview_first_value",
        "project_first_value",
        "workplace_status_update",
        "project_tradeoff_story",
        "interview_self_intro_gap",
    )


def test_evaluate_product_snapshot_accepts_happy_workplace_path() -> None:
    scenario = MAINLINE_SCENARIOS["workplace_first_value"]
    snapshot = {
        "goal": {"brief": {"main_contexts": ["workplace_communication", "project_walkthrough"]}},
        "interview": {"recommended_track": {"id": "workplace_communication"}},
        "setup": {"state": "ready_for_program"},
        "assessment": {"source": "embedded_first_mission", "level": "B1"},
        "session_evidence": {
            "latest": {
                "task_type": "stakeholder_explanation_drill",
                "summary": "You completed a real guided mission.",
            }
        },
    }
    events = [
        {"type": "transcript", "role": "assistant", "text": "Let's start with a real mission. Explain your project to a non-technical stakeholder in simple English."},
        {"type": "session_complete", "reason": "completed", "return_screen": "home"},
    ]

    checks = evaluate_product_snapshot(snapshot=snapshot, events=events, scenario=scenario)

    assert all(check.passed for check in checks)


def test_evaluate_product_snapshot_flags_missing_embedded_assessment_source() -> None:
    scenario = MAINLINE_SCENARIOS["project_first_value"]
    snapshot = {
        "goal": {"brief": {"main_contexts": ["project_walkthrough", "interviews"]}},
        "interview": {"recommended_track": {"id": "project_walkthrough"}},
        "setup": {"state": "ready_for_program"},
        "assessment": {"source": "explicit_assessment", "level": "B1"},
        "session_evidence": {
            "latest": {
                "task_type": "technical_project_walkthrough",
                "summary": "You completed a real guided mission.",
            }
        },
    }
    events = [
        {"type": "transcript", "role": "assistant", "text": "Let's start with a real mission. Walk through one recent technical project: problem, approach, metric, and impact."},
        {"type": "session_complete", "reason": "completed", "return_screen": "home"},
    ]

    checks = evaluate_product_snapshot(snapshot=snapshot, events=events, scenario=scenario)
    check_map = {check.name: check for check in checks}

    assert check_map["assessment_source"].passed is False
    assert "explicit_assessment" in check_map["assessment_source"].detail


def test_evaluate_product_snapshot_accepts_farewell_only_completion_signal() -> None:
    scenario = MAINLINE_SCENARIOS["project_first_value"]
    snapshot = {
        "goal": {"brief": {"main_contexts": ["project_walkthrough", "interviews"]}},
        "interview": {"recommended_track": {"id": "project_walkthrough"}},
        "setup": {"state": "ready_for_program"},
        "assessment": {"source": "embedded_first_mission", "level": "B1"},
        "session_evidence": {
            "latest": {
                "task_type": "technical_project_walkthrough",
                "summary": "You completed a real guided mission.",
            }
        },
    }
    events = [
        {
            "type": "transcript",
            "role": "assistant",
            "phase": "session_end",
            "text": "Thanks for chatting. Come back anytime to practice more English!",
        },
    ]

    checks = evaluate_product_snapshot(snapshot=snapshot, events=events, scenario=scenario)
    check_map = {check.name: check for check in checks}

    assert check_map["completion_signal_seen"].passed is True


def test_parse_args_defaults_to_mainline_scenario_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["run_product_synthetic_eval.py"])

    args = parse_args()

    assert args.scenario is None
    assert args.scenario_set == "mainline"


def test_resolve_scenario_slugs_returns_single_scenario_when_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_product_synthetic_eval.py", "--scenario", "project_first_value"],
    )

    args = parse_args()

    assert resolve_scenario_slugs(args) == ("project_first_value",)


def test_resolve_scenario_slugs_returns_expanded_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_product_synthetic_eval.py", "--scenario-set", "expanded"],
    )

    args = parse_args()

    assert resolve_scenario_slugs(args) == EXPANDED_SCENARIO_SET


@pytest.mark.asyncio
async def test_async_main_returns_zero_when_all_reports_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scripts.run_product_synthetic_eval.parse_args",
        lambda: Namespace(
            scenario=None,
            scenario_set="mainline",
            base_url="http://localhost:8000",
            turn_timeout=20.0,
            session_timeout=15.0,
            output=None,
        ),
    )
    report = ScenarioReport(
        slug="workplace_first_value",
        description="desc",
        passed=True,
        score=100.0,
        user_id=1,
        telegram_id=2,
        checks=[ScenarioCheck(name="ok", passed=True, detail="ok")],
    )
    mocked = AsyncMock(side_effect=[report, report, report])
    monkeypatch.setattr("scripts.run_product_synthetic_eval.run_product_scenario", mocked)
    monkeypatch.setattr("scripts.run_product_synthetic_eval.generate_telegram_id", lambda: 999001)

    exit_code = await async_main()

    assert exit_code == 0
    assert mocked.await_count == 3


@pytest.mark.asyncio
async def test_async_main_returns_nonzero_when_any_report_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scripts.run_product_synthetic_eval.parse_args",
        lambda: Namespace(
            scenario=None,
            scenario_set="mainline",
            base_url="http://localhost:8000",
            turn_timeout=20.0,
            session_timeout=15.0,
            output=None,
        ),
    )
    passing = ScenarioReport(
        slug="workplace_first_value",
        description="desc",
        passed=True,
        score=100.0,
        user_id=1,
        telegram_id=2,
        checks=[ScenarioCheck(name="ok", passed=True, detail="ok")],
    )
    failing = ScenarioReport(
        slug="interview_first_value",
        description="desc",
        passed=False,
        score=55.0,
        user_id=1,
        telegram_id=2,
        checks=[ScenarioCheck(name="assessment_source", passed=False, detail="missing")],
    )
    mocked = AsyncMock(side_effect=[passing, failing, passing])
    monkeypatch.setattr("scripts.run_product_synthetic_eval.run_product_scenario", mocked)
    monkeypatch.setattr("scripts.run_product_synthetic_eval.generate_telegram_id", lambda: 999002)

    exit_code = await async_main()

    assert exit_code == 1
    assert mocked.await_count == 3


@pytest.mark.asyncio
async def test_async_main_treats_expanded_runtime_failure_as_advisory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scripts.run_product_synthetic_eval.parse_args",
        lambda: Namespace(
            scenario=None,
            scenario_set="expanded",
            base_url="http://localhost:8000",
            turn_timeout=20.0,
            session_timeout=15.0,
            output=None,
        ),
    )

    def _report(slug: str) -> ScenarioReport:
        return ScenarioReport(
            slug=slug,
            description="desc",
            passed=True,
            score=100.0,
            user_id=1,
            telegram_id=2,
            checks=[ScenarioCheck(name="ok", passed=True, detail="ok")],
        )

    mocked = AsyncMock(
        side_effect=[
            _report("workplace_first_value"),
            _report("interview_first_value"),
            _report("project_first_value"),
            _report("workplace_status_update"),
            SmokeRuntimeFailure("expanded-only runtime failure"),
            _report("interview_self_intro_gap"),
        ]
    )
    monkeypatch.setattr("scripts.run_product_synthetic_eval.run_product_scenario", mocked)
    monkeypatch.setattr("scripts.run_product_synthetic_eval.generate_telegram_id", lambda: 999003)

    exit_code = await async_main()

    assert exit_code == 0
    assert mocked.await_count == 6


@pytest.mark.asyncio
async def test_async_main_explicit_single_scenario_failure_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scripts.run_product_synthetic_eval.parse_args",
        lambda: Namespace(
            scenario="project_tradeoff_story",
            scenario_set=None,
            base_url="http://localhost:8000",
            turn_timeout=20.0,
            session_timeout=15.0,
            output=None,
        ),
    )

    mocked = AsyncMock(side_effect=SmokeRuntimeFailure("single scenario failed"))
    monkeypatch.setattr("scripts.run_product_synthetic_eval.run_product_scenario", mocked)
    monkeypatch.setattr("scripts.run_product_synthetic_eval.generate_telegram_id", lambda: 999004)

    exit_code = await async_main()

    assert exit_code == 1
    assert mocked.await_count == 1
