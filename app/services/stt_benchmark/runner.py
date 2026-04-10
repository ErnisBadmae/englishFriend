"""Runner utilities for STT benchmark reports."""

from __future__ import annotations

import json
from pathlib import Path

from app.services.stt_benchmark.contracts import (
    STTBenchmarkCase,
    STTBenchmarkReport,
    STTBenchmarkResult,
    STTProviderSummary,
)
from app.services.stt_benchmark.scoring import evaluate_observation


def load_cases_from_json(path: str | Path) -> list[STTBenchmarkCase]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_cases = list(payload.get("cases", []) if isinstance(payload, dict) else [])
    return [STTBenchmarkCase.from_dict(item) for item in raw_cases]


def build_report(cases: list[STTBenchmarkCase]) -> STTBenchmarkReport:
    results: list[STTBenchmarkResult] = []
    for case in cases:
        for observation in case.observations:
            results.append(evaluate_observation(case, observation))

    provider_summary = summarize_by_provider(results)
    return STTBenchmarkReport(
        cases=cases,
        results=results,
        provider_summary=provider_summary,
    )


def summarize_by_provider(results: list[STTBenchmarkResult]) -> list[STTProviderSummary]:
    grouped: dict[str, list[STTBenchmarkResult]] = {}
    for result in results:
        grouped.setdefault(result.provider, []).append(result)

    summaries: list[STTProviderSummary] = []
    for provider, provider_results in grouped.items():
        case_count = len(provider_results)
        avg_overall_score = round(
            sum(item.score.overall_score for item in provider_results) / case_count,
            2,
        )
        latency_values = [item.latency_ms for item in provider_results if item.latency_ms is not None]
        avg_latency_ms = (
            round(sum(latency_values) / len(latency_values), 2)
            if latency_values
            else None
        )
        target_role_capture_rate = round(
            sum(1 for item in provider_results if item.score.target_role_captured) / case_count,
            4,
        )
        project_capture_rate = round(
            sum(1 for item in provider_results if item.score.project_signal_captured) / case_count,
            4,
        )
        usable_transcript_rate = round(
            sum(1 for item in provider_results if item.score.usable_transcript) / case_count,
            4,
        )
        fallback_rate = round(
            sum(1 for item in provider_results if item.score.fallback_used) / case_count,
            4,
        )
        summaries.append(
            STTProviderSummary(
                provider=provider,
                case_count=case_count,
                avg_overall_score=avg_overall_score,
                avg_latency_ms=avg_latency_ms,
                target_role_capture_rate=target_role_capture_rate,
                project_capture_rate=project_capture_rate,
                usable_transcript_rate=usable_transcript_rate,
                fallback_rate=fallback_rate,
            )
        )

    return sorted(
        summaries,
        key=lambda item: (-item.avg_overall_score, item.provider),
    )
