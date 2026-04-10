"""Run a product-oriented STT benchmark report.

Usage:
    python scripts/run_stt_benchmark.py --cases tests/fixtures/stt_benchmark_cases.json

Or build a one-off case from a frontend debug export:
    python scripts/run_stt_benchmark.py \
      --voice-debug path/to/voice-debug-session.json \
      --case-id noisy-foundation-vosk \
      --scenario noisy_foundation \
      --target-role-term "data scientist" \
      --project-term "recommendation model" \
      --technical-term "recommendation" \
      --required-phrase "improve grammar"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.stt_benchmark import (  # noqa: E402
    BenchmarkExpectations,
    STTBenchmarkCase,
    build_report,
    load_cases_from_json,
    observation_from_voice_debug_snapshot,
)


def _build_single_case_from_args(args: argparse.Namespace) -> list[STTBenchmarkCase]:
    observation = observation_from_voice_debug_snapshot(
        args.voice_debug,
        provider=args.provider,
    )
    case = STTBenchmarkCase(
        case_id=args.case_id,
        scenario=args.scenario,
        expected=BenchmarkExpectations(
            target_role_terms=args.target_role_term or [],
            project_terms=args.project_term or [],
            technical_terms=args.technical_term or [],
            required_phrases=args.required_phrase or [],
        ),
        observations=[observation],
        notes="Generated from one frontend debug export",
    )
    return [case]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an STT benchmark report")
    parser.add_argument("--cases", help="Path to a benchmark cases JSON file")
    parser.add_argument("--voice-debug", help="Path to one frontend debug export JSON")
    parser.add_argument("--case-id", help="Case id for --voice-debug mode")
    parser.add_argument("--scenario", help="Scenario label for --voice-debug mode")
    parser.add_argument("--provider", help="Override provider label for --voice-debug mode")
    parser.add_argument(
        "--target-role-term",
        action="append",
        default=[],
        help="Expected target role term (repeatable)",
    )
    parser.add_argument(
        "--project-term",
        action="append",
        default=[],
        help="Expected project term (repeatable)",
    )
    parser.add_argument(
        "--technical-term",
        action="append",
        default=[],
        help="Expected technical term (repeatable)",
    )
    parser.add_argument(
        "--required-phrase",
        action="append",
        default=[],
        help="Expected required phrase (repeatable)",
    )
    parser.add_argument("--output", help="Optional path to write the report JSON")
    args = parser.parse_args()

    if bool(args.cases) == bool(args.voice_debug):
        parser.error("Provide exactly one of --cases or --voice-debug")
    if args.voice_debug and (not args.case_id or not args.scenario):
        parser.error("--voice-debug requires both --case-id and --scenario")
    return args


def main() -> int:
    args = _parse_args()
    if args.cases:
        cases = load_cases_from_json(args.cases)
    else:
        cases = _build_single_case_from_args(args)

    report = build_report(cases)
    payload = json.dumps(report.to_dict(), indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
        print(f"Wrote report to {args.output}")
    else:
        print(payload)

    if report.provider_summary:
        print("\nProvider summary:")
        for summary in report.provider_summary:
            latency = (
                f"{summary.avg_latency_ms:.2f}ms"
                if summary.avg_latency_ms is not None
                else "n/a"
            )
            print(
                f"- {summary.provider}: score={summary.avg_overall_score:.2f} "
                f"target={summary.target_role_capture_rate:.0%} "
                f"project={summary.project_capture_rate:.0%} "
                f"usable={summary.usable_transcript_rate:.0%} "
                f"fallback={summary.fallback_rate:.0%} "
                f"latency={latency}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
