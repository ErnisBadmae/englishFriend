"""Internal contracts for compact learner memory and consolidation."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable, Optional

from app.models.enums_and_dimensions import MemoryKind


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_temporal_references(
    text: str,
    *,
    reference_time: Optional[datetime] = None,
) -> str:
    """Replace relative time words with absolute dates for stable memory."""
    if not text:
        return ""

    ref = reference_time or datetime.now(UTC)
    replacements = {
        r"\btoday\b": f"on {ref.date().isoformat()}",
        r"\byesterday\b": f"on {(ref - timedelta(days=1)).date().isoformat()}",
        r"\btomorrow\b": f"on {(ref + timedelta(days=1)).date().isoformat()}",
        r"\blast week\b": f"in the week of {(ref - timedelta(days=7)).date().isoformat()}",
        r"\bnext week\b": f"in the week of {(ref + timedelta(days=7)).date().isoformat()}",
    }

    normalized = text
    for pattern, replacement in replacements.items():
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

    return _normalize_whitespace(normalized)


def _memory_key(kind: MemoryKind, content: str) -> tuple[str, str]:
    return kind.value, _normalize_whitespace(content).lower()


def _extract_conflict_slot(kind: MemoryKind, content: str) -> Optional[str]:
    normalized = content.lower()

    fact_slots = (
        (r"\b(name is|student'?s name is)\b", "name"),
        (r"\b(works as|is a|current role is)\b", "current_role"),
        (r"\b(works at|employer is|company is)\b", "employer"),
        (r"\b(from|lives in|country is)\b", "location"),
    )
    goal_slots = (
        (r"\b(target role is|wants to become|wants an?\b.*\bjob|wants a\b.*\brole)\b", "target_role"),
        (r"\b(abroad|international company|startup|enterprise)\b", "target_market"),
    )

    patterns = fact_slots if kind == MemoryKind.FACT else goal_slots if kind == MemoryKind.GOAL else ()
    for pattern, slot in patterns:
        if re.search(pattern, normalized):
            return slot
    return None


@dataclass
class MemoryCandidate:
    """Validated candidate memory before saving."""

    kind: MemoryKind
    content: str
    salience: float
    meta: dict[str, Any] = field(default_factory=dict)

    def normalized(self, *, reference_time: Optional[datetime] = None) -> "MemoryCandidate":
        return MemoryCandidate(
            kind=self.kind,
            content=normalize_temporal_references(self.content, reference_time=reference_time),
            salience=self.salience,
            meta=dict(self.meta),
        )


@dataclass
class MemoryConflict:
    """Detected semantic collision between memory candidates."""

    slot: str
    existing_content: str
    new_content: str
    resolution: str


@dataclass
class MemoryConsolidationResult:
    """Outcome of lightweight memory consolidation before persistence."""

    accepted_candidates: list[MemoryCandidate] = field(default_factory=list)
    dropped_duplicates: list[str] = field(default_factory=list)
    conflicts: list[MemoryConflict] = field(default_factory=list)


@dataclass
class LearnerProfileSummary:
    """Compact, stable learner profile used as prompt memory."""

    goal_summary: Optional[str] = None
    goal_status: Optional[str] = None
    target_role: Optional[str] = None
    target_market: Optional[str] = None
    current_level: Optional[str] = None
    level_confidence: Optional[float] = None
    current_stage: Optional[str] = None
    active_mission_family: Optional[str] = None
    practice_contexts: list[str] = field(default_factory=list)
    top_error_patterns: list[str] = field(default_factory=list)
    current_blockers: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)
    latest_evidence_summary: Optional[str] = None
    latest_evidence_issue: Optional[str] = None
    last_updated: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def render_prompt(self) -> str:
        lines: list[str] = []
        if self.goal_summary:
            lines.append(f"- Goal: {self.goal_summary}")
        elif self.target_role:
            lines.append(f"- Target role: {self.target_role}")

        if self.current_level:
            if self.level_confidence is not None:
                lines.append(f"- Current level: {self.current_level} (confidence {self.level_confidence:.2f})")
            else:
                lines.append(f"- Current level: {self.current_level}")

        if self.current_stage:
            lines.append(f"- Current stage: {self.current_stage}")
        if self.active_mission_family:
            lines.append(f"- Mission family: {self.active_mission_family}")
        if self.practice_contexts:
            lines.append(f"- Practice contexts: {', '.join(self.practice_contexts[:3])}")
        if self.current_blockers:
            lines.append(f"- Current blockers: {', '.join(self.current_blockers[:3])}")
        if self.top_error_patterns:
            lines.append(f"- Recurring issues: {', '.join(self.top_error_patterns[:3])}")
        if self.preferences:
            lines.append(f"- Preferences: {', '.join(self.preferences[:2])}")
        if self.latest_evidence_issue:
            lines.append(f"- Latest evidence issue: {self.latest_evidence_issue}")
        elif self.latest_evidence_summary:
            lines.append(f"- Latest evidence: {self.latest_evidence_summary}")
        if self.last_updated:
            lines.append(f"- Profile updated: {self.last_updated}")

        if not lines:
            return ""
        return "## Learner profile\n" + "\n".join(lines)


@dataclass
class MissionMemoryContext:
    """Bounded memory context for one mission/session."""

    learner_profile: Optional[LearnerProfileSummary] = None
    mission_task_type: Optional[str] = None
    mission_title: Optional[str] = None
    mission_reason: Optional[str] = None
    mission_success_signal: Optional[str] = None
    mission_linked_goal_context: Optional[str] = None
    relevant_memories: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.learner_profile:
            payload["learner_profile"] = self.learner_profile.to_dict()
        return payload

    def to_prompt_section(self) -> str:
        sections: list[str] = []
        if self.learner_profile:
            rendered_profile = self.learner_profile.render_prompt()
            if rendered_profile:
                sections.append(rendered_profile)

        mission_lines: list[str] = []
        if self.mission_title:
            mission_lines.append(f"- Title: {self.mission_title}")
        if self.mission_task_type:
            mission_lines.append(f"- Task type: {self.mission_task_type}")
        if self.mission_reason:
            mission_lines.append(f"- Why now: {self.mission_reason}")
        if self.mission_success_signal:
            mission_lines.append(f"- Success signal: {self.mission_success_signal}")
        if self.mission_linked_goal_context:
            mission_lines.append(f"- Goal context: {self.mission_linked_goal_context}")
        if mission_lines:
            sections.append("## Current mission context\n" + "\n".join(mission_lines))

        if self.relevant_memories:
            memory_lines = "\n".join(f"- {item}" for item in self.relevant_memories[:5])
            sections.append("## Relevant memory for this mission\n" + memory_lines)

        return "\n\n".join(section for section in sections if section)


def consolidate_memory_candidates(
    *,
    candidates: Iterable[MemoryCandidate],
    existing_memories: Iterable[Any],
    reference_time: Optional[datetime] = None,
) -> MemoryConsolidationResult:
    """Normalize and deduplicate candidates before persistence."""
    result = MemoryConsolidationResult()

    existing_index: dict[tuple[str, str], Any] = {}
    existing_slots: dict[tuple[str, str], str] = {}
    for memory in existing_memories:
        kind = getattr(memory, "kind", None)
        content = getattr(memory, "content", "")
        if not kind or not content:
            continue
        normalized_content = normalize_temporal_references(content, reference_time=reference_time)
        existing_index[_memory_key(kind, normalized_content)] = memory
        slot = _extract_conflict_slot(kind, normalized_content)
        if slot:
            existing_slots[(kind.value, slot)] = normalized_content

    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        normalized_candidate = candidate.normalized(reference_time=reference_time)
        key = _memory_key(normalized_candidate.kind, normalized_candidate.content)
        if key in seen or key in existing_index:
            result.dropped_duplicates.append(normalized_candidate.content)
            continue
        seen.add(key)

        slot = _extract_conflict_slot(normalized_candidate.kind, normalized_candidate.content)
        existing_slot_value = existing_slots.get((normalized_candidate.kind.value, slot)) if slot else None
        if slot and existing_slot_value and existing_slot_value.lower() != normalized_candidate.content.lower():
            result.conflicts.append(
                MemoryConflict(
                    slot=slot,
                    existing_content=existing_slot_value,
                    new_content=normalized_candidate.content,
                    resolution="keep_existing_for_profile",
                )
            )

        result.accepted_candidates.append(normalized_candidate)

    return result
