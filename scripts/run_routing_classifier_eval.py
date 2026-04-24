"""Offline eval for the career routing classifier and arbiter.

This runner does not open the live websocket and does not mutate product state.
It compares:
- lexical routing baseline,
- optional semantic classifier output,
- arbiter decision under shadow/gate/mainline modes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.services.routing.career_classifier import (
    CareerRoutingClassifierResult,
    ClassifierMode,
    LLMCareerRoutingClassifier,
    arbitrate_career_routing,
)
from app.services.routing.goal_routing import resolve_goal_routing, score_context_signals
from scripts.run_product_synthetic_eval import (
    EXPANDED_SCENARIO_SET,
    LIVE_TESTER_SCENARIO_SET,
    MAINLINE_SCENARIO_SET,
    MAINLINE_SCENARIOS,
    ProductSyntheticScenario,
)

ClassifierSource = Literal["llm", "none", "expected_fixture"]


@dataclass(slots=True)
class RoutingClassifierScenarioReport:
    slug: str
    description: str
    expected_primary_context: str
    lexical_primary_context: Optional[str]
    lexical_match: bool
    lexical_context_scores: dict[str, int]
    classifier_status: str
    classifier_primary_context: Optional[str] = None
    classifier_confidence: Optional[float] = None
    classifier_match: Optional[bool] = None
    classifier_semantic_safe: Optional[bool] = None
    classifier_semantic_violations: list[str] = field(default_factory=list)
    classifier_intent_action: Optional[str] = None
    classifier_audience: Optional[str] = None
    classifier_artifact_focus: Optional[str] = None
    classifier_job_process_stage: Optional[str] = None
    classifier_reason_codes: list[str] = field(default_factory=list)
    classifier_evidence_spans: list[str] = field(default_factory=list)
    classifier_failure_category: Optional[str] = None
    arbiter_mode: str = "shadow"
    arbiter_applied_source: str = "fallback"
    arbiter_primary_context: Optional[str] = None
    arbiter_match: bool = False
    arbiter_disagreement: bool = False
    arbiter_ambiguous_legacy: bool = False
    arbiter_applied_classifier: bool = False
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RoutingClassifierEvalReport:
    generated_at: str
    scenario_set: str
    classifier_source: str
    arbiter_mode: str
    min_confidence: float
    reports: list[RoutingClassifierScenarioReport]

    def to_dict(self) -> dict[str, Any]:
        summary = summarize_reports(self.reports)
        return {
            "generated_at": self.generated_at,
            "scenario_set": self.scenario_set,
            "classifier_source": self.classifier_source,
            "arbiter_mode": self.arbiter_mode,
            "min_confidence": self.min_confidence,
            "summary": summary,
            "reports": [report.to_dict() for report in self.reports],
        }


def build_transcript(scenario: ProductSyntheticScenario) -> str:
    return "\n".join(scenario.user_messages)


def _primary_from_goal_brief(goal_brief: Optional[dict[str, Any]]) -> Optional[str]:
    contexts = (goal_brief or {}).get("main_contexts") or []
    if not contexts:
        return None
    return str(contexts[0] or "").strip().lower() or None


def build_lexical_goal_brief(scenario: ProductSyntheticScenario) -> tuple[Optional[dict[str, Any]], dict[str, int]]:
    transcript = build_transcript(scenario)
    profile = resolve_goal_routing(conversation_history=[
        {"role": "user", "content": message}
        for message in scenario.user_messages
    ])
    scores = score_context_signals(transcript)
    if not any(score > 0 for score in scores.values()):
        return None, scores
    return {
        "main_contexts": list(profile.main_contexts),
        "routing_decision_source": profile.decision_source,
    }, scores


def _semantic_fixture_slots(primary_context: str) -> dict[str, Any]:
    if primary_context == "interviews":
        return {
            "intent_action": "interview_practice",
            "audience": "recruiter_interviewer",
            "artifact_focus": "self_intro_or_interview_answer",
            "job_process_stage": "interview_process",
        }
    if primary_context == "workplace_communication":
        return {
            "intent_action": "explain_work_to_team",
            "audience": "team_manager_stakeholder",
            "artifact_focus": "work_update",
            "job_process_stage": "current_workplace",
        }
    return {
        "intent_action": "project_walkthrough",
        "audience": "technical_or_hiring_audience",
        "artifact_focus": "project_architecture_tradeoff_impact",
        "job_process_stage": "project_story_preparation",
    }


def build_expected_fixture_classifier(scenario: ProductSyntheticScenario) -> CareerRoutingClassifierResult:
    semantic_slots = _semantic_fixture_slots(scenario.expected_primary_context)
    return CareerRoutingClassifierResult(
        primary_context=scenario.expected_primary_context,
        confidence=1.0,
        requires_confirmation=False,
        reason_codes=("expected_fixture",),
        evidence_spans=list(scenario.user_messages[:2]),
        classifier_source="fallback",
        model_version="expected_fixture",
        **semantic_slots,
    )


async def classify_for_scenario(
    scenario: ProductSyntheticScenario,
    *,
    classifier_source: ClassifierSource,
) -> tuple[Optional[CareerRoutingClassifierResult], str, Optional[str]]:
    if classifier_source == "none":
        return None, "not_run", None
    if classifier_source == "expected_fixture":
        return build_expected_fixture_classifier(scenario), "classified", None

    transcript = build_transcript(scenario)
    try:
        result = await asyncio.wait_for(
            LLMCareerRoutingClassifier().classify(
                transcript_text=transcript,
                latest_user_message=scenario.user_messages[-1],
                existing_goal_brief={},
            ),
            timeout=float(settings.career_routing_classifier_timeout_seconds),
        )
    except Exception as exc:
        return None, "error", f"{type(exc).__name__}: {exc}"

    status = "classified" if result.primary_context else "no_primary"
    return result, status, None


def _classifier_failure_category(
    *,
    scenario: ProductSyntheticScenario,
    classifier_result: Optional[CareerRoutingClassifierResult],
) -> Optional[str]:
    if not classifier_result or not classifier_result.primary_context:
        return None
    if classifier_result.primary_context == scenario.expected_primary_context:
        return None

    violations = set(classifier_result.semantic_validation.violations)
    if "job_market_bias" in violations or (
        classifier_result.primary_context == "interviews"
        and classifier_result.target_market
    ):
        return "job_market_bias"
    if "audience_ignored" in violations or (
        classifier_result.primary_context == "project_walkthrough"
        and classifier_result.audience
        and any(
            marker in classifier_result.audience
            for marker in ("team", "manager", "stakeholder", "client", "colleague")
        )
    ):
        return "audience_ignored"
    if "domain_bias" in violations or classifier_result.domain_mentions:
        return "domain_bias"
    if violations:
        return sorted(violations)[0]
    return "label_mismatch"


async def evaluate_scenario(
    scenario: ProductSyntheticScenario,
    *,
    classifier_source: ClassifierSource,
    arbiter_mode: ClassifierMode,
    min_confidence: float,
) -> RoutingClassifierScenarioReport:
    transcript = build_transcript(scenario)
    lexical_goal_brief, lexical_scores = build_lexical_goal_brief(scenario)
    lexical_primary = _primary_from_goal_brief(lexical_goal_brief)
    classifier_result, classifier_status, error = await classify_for_scenario(
        scenario,
        classifier_source=classifier_source,
    )

    decision = arbitrate_career_routing(
        existing_goal_brief={},
        lexical_goal_brief=lexical_goal_brief,
        classifier_result=classifier_result,
        transcript_text=transcript,
        mode=arbiter_mode,
        min_confidence=min_confidence,
    )
    arbiter_primary = _primary_from_goal_brief(decision.goal_brief_update)
    semantic_validation = (
        classifier_result.semantic_validation if classifier_result else None
    )

    return RoutingClassifierScenarioReport(
        slug=scenario.slug,
        description=scenario.description,
        expected_primary_context=scenario.expected_primary_context,
        lexical_primary_context=lexical_primary,
        lexical_match=lexical_primary == scenario.expected_primary_context,
        lexical_context_scores=lexical_scores,
        classifier_status=classifier_status,
        classifier_primary_context=(
            classifier_result.primary_context if classifier_result else None
        ),
        classifier_confidence=(
            round(float(classifier_result.confidence), 3)
            if classifier_result
            else None
        ),
        classifier_match=(
            classifier_result.primary_context == scenario.expected_primary_context
            if classifier_result and classifier_result.primary_context
            else None
        ),
        classifier_semantic_safe=(
            semantic_validation.safe if semantic_validation else None
        ),
        classifier_semantic_violations=(
            list(semantic_validation.violations) if semantic_validation else []
        ),
        classifier_intent_action=(
            classifier_result.intent_action if classifier_result else None
        ),
        classifier_audience=classifier_result.audience if classifier_result else None,
        classifier_artifact_focus=(
            classifier_result.artifact_focus if classifier_result else None
        ),
        classifier_job_process_stage=(
            classifier_result.job_process_stage if classifier_result else None
        ),
        classifier_reason_codes=list(classifier_result.reason_codes) if classifier_result else [],
        classifier_evidence_spans=list(classifier_result.evidence_spans) if classifier_result else [],
        classifier_failure_category=_classifier_failure_category(
            scenario=scenario,
            classifier_result=classifier_result,
        ),
        arbiter_mode=arbiter_mode,
        arbiter_applied_source=decision.applied_source,
        arbiter_primary_context=arbiter_primary,
        arbiter_match=arbiter_primary == scenario.expected_primary_context,
        arbiter_disagreement=decision.disagreement,
        arbiter_ambiguous_legacy=decision.ambiguous_legacy,
        arbiter_applied_classifier=decision.applied_classifier,
        error=error,
    )


def summarize_reports(reports: list[RoutingClassifierScenarioReport]) -> dict[str, Any]:
    total = len(reports)
    if total == 0:
        return {
            "total": 0,
            "lexical_match_rate": 0.0,
            "classifier_match_rate": None,
            "ambiguous_classifier_match_rate": None,
            "semantic_slot_validity": None,
            "arbiter_match_rate": 0.0,
            "disagreements": 0,
            "ambiguous_legacy": 0,
            "critical_inversions": 0,
            "classifier_errors": 0,
            "failure_categories": {},
        }

    classifier_evaluable = [
        report
        for report in reports
        if report.classifier_match is not None
    ]
    ambiguous_classifier_evaluable = [
        report
        for report in classifier_evaluable
        if report.arbiter_ambiguous_legacy
    ]
    semantic_evaluable = [
        report
        for report in reports
        if report.classifier_semantic_safe is not None
    ]
    failure_categories: dict[str, int] = {}
    for report in reports:
        if not report.classifier_failure_category:
            continue
        failure_categories[report.classifier_failure_category] = (
            failure_categories.get(report.classifier_failure_category, 0) + 1
        )
    return {
        "total": total,
        "lexical_matches": sum(1 for report in reports if report.lexical_match),
        "lexical_match_rate": round(
            sum(1 for report in reports if report.lexical_match) / total,
            3,
        ),
        "classifier_matches": sum(
            1 for report in classifier_evaluable if report.classifier_match
        ),
        "classifier_match_rate": (
            round(
                sum(1 for report in classifier_evaluable if report.classifier_match)
                / len(classifier_evaluable),
                3,
            )
            if classifier_evaluable
            else None
        ),
        "ambiguous_classifier_match_rate": (
            round(
                sum(1 for report in ambiguous_classifier_evaluable if report.classifier_match)
                / len(ambiguous_classifier_evaluable),
                3,
            )
            if ambiguous_classifier_evaluable
            else None
        ),
        "semantic_slot_validity": (
            round(
                sum(1 for report in semantic_evaluable if report.classifier_semantic_safe)
                / len(semantic_evaluable),
                3,
            )
            if semantic_evaluable
            else None
        ),
        "arbiter_matches": sum(1 for report in reports if report.arbiter_match),
        "arbiter_match_rate": round(
            sum(1 for report in reports if report.arbiter_match) / total,
            3,
        ),
        "disagreements": sum(1 for report in reports if report.arbiter_disagreement),
        "ambiguous_legacy": sum(1 for report in reports if report.arbiter_ambiguous_legacy),
        "critical_inversions": sum(
            1
            for report in reports
            if report.lexical_match and report.classifier_match is False
        ),
        "classifier_errors": sum(1 for report in reports if report.classifier_status == "error"),
        "failure_categories": dict(sorted(failure_categories.items())),
    }


def resolve_scenario_slugs(args: argparse.Namespace) -> tuple[str, ...]:
    if args.scenario:
        return (args.scenario,)
    if args.scenario_set == "mainline":
        return MAINLINE_SCENARIO_SET
    if args.scenario_set == "expanded":
        return EXPANDED_SCENARIO_SET
    if args.scenario_set == "live_tester":
        return LIVE_TESTER_SCENARIO_SET
    return tuple(MAINLINE_SCENARIOS.keys())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run offline lexical/classifier/arbiter eval for career routing."
    )
    parser.add_argument("--scenario", choices=sorted(MAINLINE_SCENARIOS), default=None)
    parser.add_argument(
        "--scenario-set",
        choices=("mainline", "expanded", "live_tester", "all"),
        default="expanded",
    )
    parser.add_argument(
        "--classifier-source",
        choices=("llm", "none", "expected_fixture"),
        default="llm",
        help="Use llm for real shadow eval; expected_fixture is deterministic for policy dry-runs.",
    )
    parser.add_argument(
        "--arbiter-mode",
        choices=("shadow", "gate", "mainline"),
        default="shadow",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=float(settings.career_routing_classifier_min_confidence),
    )
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--fail-on-arbiter-mismatch",
        action="store_true",
        help="Exit 1 if any arbiter result misses expected primary context.",
    )
    return parser.parse_args()


def print_report(report: RoutingClassifierEvalReport) -> None:
    payload = report.to_dict()
    summary = payload["summary"]
    print("=" * 72)
    print("career routing classifier offline eval")
    print("=" * 72)
    print(f"scenario_set: {report.scenario_set}")
    print(f"classifier_source: {report.classifier_source}")
    print(f"arbiter_mode: {report.arbiter_mode}")
    print(f"total: {summary['total']}")
    print(f"lexical_match_rate: {summary['lexical_match_rate']:.1%}")
    if summary["classifier_match_rate"] is None:
        print("classifier_match_rate: n/a")
    else:
        print(f"classifier_match_rate: {summary['classifier_match_rate']:.1%}")
    if summary["ambiguous_classifier_match_rate"] is None:
        print("ambiguous_classifier_match_rate: n/a")
    else:
        print(
            "ambiguous_classifier_match_rate: "
            f"{summary['ambiguous_classifier_match_rate']:.1%}"
        )
    if summary["semantic_slot_validity"] is None:
        print("semantic_slot_validity: n/a")
    else:
        print(f"semantic_slot_validity: {summary['semantic_slot_validity']:.1%}")
    print(f"arbiter_match_rate: {summary['arbiter_match_rate']:.1%}")
    print(f"disagreements: {summary['disagreements']}")
    print(f"ambiguous_legacy: {summary['ambiguous_legacy']}")
    print(f"critical_inversions: {summary['critical_inversions']}")
    print(f"classifier_errors: {summary['classifier_errors']}")
    print(f"failure_categories: {summary['failure_categories']}")
    print("-" * 72)
    for item in report.reports:
        status = "OK" if item.arbiter_match else "MISS"
        print(
            f"{status} {item.slug}: expected={item.expected_primary_context}, "
            f"lexical={item.lexical_primary_context}, "
            f"classifier={item.classifier_primary_context}, "
            f"arbiter={item.arbiter_primary_context}, "
            f"applied={item.arbiter_applied_source}, "
            f"ambiguous={item.arbiter_ambiguous_legacy}, "
            f"semantic_safe={item.classifier_semantic_safe}"
        )
        if item.classifier_failure_category:
            print(f"  classifier_failure_category: {item.classifier_failure_category}")
        if item.classifier_semantic_violations:
            print(f"  semantic_violations: {item.classifier_semantic_violations}")
        if item.error:
            print(f"  classifier_error: {item.error}")


async def async_main() -> int:
    args = parse_args()
    slugs = resolve_scenario_slugs(args)
    reports: list[RoutingClassifierScenarioReport] = []
    for slug in slugs:
        scenario = MAINLINE_SCENARIOS[slug]
        reports.append(
            await evaluate_scenario(
                scenario,
                classifier_source=args.classifier_source,
                arbiter_mode=args.arbiter_mode,
                min_confidence=args.min_confidence,
            )
        )

    report = RoutingClassifierEvalReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        scenario_set=args.scenario_set if not args.scenario else "custom",
        classifier_source=args.classifier_source,
        arbiter_mode=args.arbiter_mode,
        min_confidence=args.min_confidence,
        reports=reports,
    )
    print_report(report)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"saved: {output_path}")

    if args.fail_on_arbiter_mismatch and any(not item.arbiter_match for item in reports):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
