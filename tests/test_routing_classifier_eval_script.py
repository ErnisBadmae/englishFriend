from argparse import Namespace

import pytest

from scripts.run_routing_classifier_eval import (
    build_lexical_goal_brief,
    evaluate_scenario,
    resolve_scenario_slugs,
    summarize_reports,
)
from scripts.run_product_synthetic_eval import (
    EXPANDED_SCENARIO_SET,
    LIVE_TESTER_SCENARIO_SET,
    MAINLINE_SCENARIOS,
)


def test_resolve_scenario_slugs_supports_eval_tiers() -> None:
    assert resolve_scenario_slugs(Namespace(scenario=None, scenario_set="expanded")) == EXPANDED_SCENARIO_SET
    assert resolve_scenario_slugs(Namespace(scenario=None, scenario_set="live_tester")) == LIVE_TESTER_SCENARIO_SET
    assert resolve_scenario_slugs(Namespace(scenario="project_tradeoff_story", scenario_set="mainline")) == (
        "project_tradeoff_story",
    )


def test_build_lexical_goal_brief_uses_existing_routing_policy() -> None:
    scenario = MAINLINE_SCENARIOS["project_tradeoff_story"]

    goal_brief, scores = build_lexical_goal_brief(scenario)

    assert goal_brief is not None
    assert goal_brief["main_contexts"][0] == "project_walkthrough"
    assert scores["project_walkthrough"] > 0


@pytest.mark.asyncio
async def test_expected_fixture_classifier_shadow_keeps_lexical_decision() -> None:
    scenario = MAINLINE_SCENARIOS["interview_self_intro_gap"]

    report = await evaluate_scenario(
        scenario,
        classifier_source="expected_fixture",
        arbiter_mode="shadow",
        min_confidence=0.72,
    )

    assert report.expected_primary_context == "interviews"
    assert report.classifier_primary_context == "interviews"
    assert report.classifier_match is True
    assert report.arbiter_applied_source == "legacy"
    assert report.arbiter_match is True


@pytest.mark.asyncio
async def test_expected_fixture_classifier_gate_applies_only_when_legacy_ambiguous() -> None:
    scenario = MAINLINE_SCENARIOS["stt_noise_interview"]

    report = await evaluate_scenario(
        scenario,
        classifier_source="expected_fixture",
        arbiter_mode="gate",
        min_confidence=0.72,
    )

    assert report.classifier_primary_context == "interviews"
    assert report.arbiter_match is True
    assert report.arbiter_applied_source in {"legacy", "classifier"}


def test_summarize_reports_counts_disagreements_and_rates() -> None:
    class _Report:
        lexical_match = True
        classifier_match = True
        classifier_semantic_safe = True
        classifier_failure_category = None
        arbiter_match = True
        arbiter_disagreement = False
        arbiter_ambiguous_legacy = False
        classifier_status = "classified"

    class _Miss:
        lexical_match = False
        classifier_match = None
        classifier_semantic_safe = None
        classifier_failure_category = None
        arbiter_match = False
        arbiter_disagreement = True
        arbiter_ambiguous_legacy = True
        classifier_status = "error"

    summary = summarize_reports([_Report(), _Miss()])  # type: ignore[list-item]

    assert summary["total"] == 2
    assert summary["lexical_match_rate"] == 0.5
    assert summary["classifier_match_rate"] == 1.0
    assert summary["semantic_slot_validity"] == 1.0
    assert summary["arbiter_match_rate"] == 0.5
    assert summary["disagreements"] == 1
    assert summary["ambiguous_legacy"] == 1
    assert summary["critical_inversions"] == 0
    assert summary["classifier_errors"] == 1
