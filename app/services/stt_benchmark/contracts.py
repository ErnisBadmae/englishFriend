"""Contracts for product-oriented STT benchmarking."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class BenchmarkExpectations:
    """Expected semantic signals for one benchmark scenario."""

    target_role_terms: list[str] = field(default_factory=list)
    project_terms: list[str] = field(default_factory=list)
    technical_terms: list[str] = field(default_factory=list)
    required_phrases: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "BenchmarkExpectations":
        payload = payload or {}
        return cls(
            target_role_terms=list(payload.get("target_role_terms", []) or []),
            project_terms=list(payload.get("project_terms", []) or []),
            technical_terms=list(payload.get("technical_terms", []) or []),
            required_phrases=list(payload.get("required_phrases", []) or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class STTBenchmarkObservation:
    """One provider transcript captured for a benchmark case."""

    provider: str
    transcript: str
    latency_ms: float | None = None
    source: str | None = None
    fallback_used: bool = False
    session_id: str | None = None
    mission_task_type: str | None = None
    artifact_path: str | None = None
    notes: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "STTBenchmarkObservation":
        return cls(
            provider=str(payload.get("provider") or "unknown"),
            transcript=str(payload.get("transcript") or ""),
            latency_ms=float(payload["latency_ms"]) if payload.get("latency_ms") is not None else None,
            source=(str(payload["source"]) if payload.get("source") else None),
            fallback_used=bool(payload.get("fallback_used", False)),
            session_id=(str(payload["session_id"]) if payload.get("session_id") else None),
            mission_task_type=(
                str(payload["mission_task_type"])
                if payload.get("mission_task_type")
                else None
            ),
            artifact_path=(str(payload["artifact_path"]) if payload.get("artifact_path") else None),
            notes=(str(payload["notes"]) if payload.get("notes") else None),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class STTBenchmarkCase:
    """A product scenario plus one or more provider observations."""

    case_id: str
    scenario: str
    expected: BenchmarkExpectations = field(default_factory=BenchmarkExpectations)
    observations: list[STTBenchmarkObservation] = field(default_factory=list)
    notes: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "STTBenchmarkCase":
        return cls(
            case_id=str(payload.get("case_id") or ""),
            scenario=str(payload.get("scenario") or "unknown"),
            expected=BenchmarkExpectations.from_dict(payload.get("expected")),
            observations=[
                STTBenchmarkObservation.from_dict(item)
                for item in list(payload.get("observations", []) or [])
            ],
            notes=(str(payload["notes"]) if payload.get("notes") else None),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "scenario": self.scenario,
            "expected": self.expected.to_dict(),
            "observations": [item.to_dict() for item in self.observations],
            "notes": self.notes,
        }


@dataclass(slots=True)
class STTBenchmarkScore:
    """Deterministic score for one observation."""

    target_role_captured: bool
    project_signal_captured: bool
    technical_term_hits: int
    technical_term_total: int
    required_phrase_hits: int
    required_phrase_total: int
    usable_transcript: bool
    fallback_used: bool
    overall_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class STTBenchmarkResult:
    """Scored result for one provider inside one case."""

    case_id: str
    scenario: str
    provider: str
    transcript: str
    normalized_transcript: str
    latency_ms: float | None
    source: str | None
    session_id: str | None
    mission_task_type: str | None
    artifact_path: str | None
    notes: str | None
    score: STTBenchmarkScore

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["score"] = self.score.to_dict()
        return payload


@dataclass(slots=True)
class STTProviderSummary:
    """Aggregate provider view across cases."""

    provider: str
    case_count: int
    avg_overall_score: float
    avg_latency_ms: float | None
    target_role_capture_rate: float
    project_capture_rate: float
    usable_transcript_rate: float
    fallback_rate: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class STTBenchmarkReport:
    """Complete benchmark report."""

    cases: list[STTBenchmarkCase]
    results: list[STTBenchmarkResult]
    provider_summary: list[STTProviderSummary]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cases": [case.to_dict() for case in self.cases],
            "results": [result.to_dict() for result in self.results],
            "provider_summary": [summary.to_dict() for summary in self.provider_summary],
        }
