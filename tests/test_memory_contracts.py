from datetime import datetime

from app.models.enums_and_dimensions import MemoryKind
from app.services.ai.memory_contracts import (
    MemoryCandidate,
    consolidate_memory_candidates,
    normalize_temporal_references,
)


def test_normalize_temporal_references_rewrites_relative_dates():
    result = normalize_temporal_references(
        "Yesterday I improved the deployment pipeline.",
        reference_time=datetime(2026, 4, 9, 12, 0, 0),
    )

    assert result == "on 2026-04-08 I improved the deployment pipeline."


def test_consolidate_memory_candidates_drops_duplicates_and_reports_conflicts():
    existing = [
        type(
            "MemoryStub",
            (),
            {
                "kind": MemoryKind.FACT,
                "content": "Student works as a data analyst",
            },
        )()
    ]
    candidates = [
        MemoryCandidate(
            kind=MemoryKind.FACT,
            content="Student works as a data analyst",
            salience=0.8,
        ),
        MemoryCandidate(
            kind=MemoryKind.FACT,
            content="Student works as an ML engineer",
            salience=0.9,
        ),
    ]

    result = consolidate_memory_candidates(
        candidates=candidates,
        existing_memories=existing,
        reference_time=datetime(2026, 4, 9, 12, 0, 0),
    )

    assert result.dropped_duplicates == ["Student works as a data analyst"]
    assert len(result.accepted_candidates) == 1
    assert result.accepted_candidates[0].content == "Student works as an ML engineer"
    assert len(result.conflicts) == 1
    assert result.conflicts[0].slot == "current_role"
