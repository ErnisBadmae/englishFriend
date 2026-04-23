from __future__ import annotations

import re
from typing import Any, Literal, Optional

GoalBriefMode = Literal["routing", "full"]

SUPPORTED_GOAL_CONTEXTS: tuple[str, ...] = (
    "interviews",
    "workplace_communication",
    "project_walkthrough",
)

_CONTEXT_ALIASES: dict[str, str] = {
    "interview": "interviews",
    "interviews": "interviews",
    "job interview": "interviews",
    "job interviews": "interviews",
    "mock interview": "interviews",
    "hr interview": "interviews",
    "technical interview": "interviews",
    "behavioral interview": "interviews",
    "behavioural interview": "interviews",
    "interview preparation": "interviews",
    "self introduction": "interviews",
    "self intro": "interviews",
    "workplace": "workplace_communication",
    "workplace english": "workplace_communication",
    "workplace communication": "workplace_communication",
    "work communication": "workplace_communication",
    "team communication": "workplace_communication",
    "manager communication": "workplace_communication",
    "stakeholder communication": "workplace_communication",
    "client communication": "workplace_communication",
    "client meeting": "workplace_communication",
    "client presentation": "workplace_communication",
    "team meetings": "workplace_communication",
    "standup": "workplace_communication",
    "status update": "workplace_communication",
    "project": "project_walkthrough",
    "projects": "project_walkthrough",
    "project walkthrough": "project_walkthrough",
    "project walk through": "project_walkthrough",
    "technical project": "project_walkthrough",
    "technical walkthrough": "project_walkthrough",
    "project presentation": "project_walkthrough",
    "research project": "project_walkthrough",
    "system design": "project_walkthrough",
}

_GOAL_BRIEF_ROUTING_FIELDS: tuple[str, ...] = (
    "primary_goal",
    "target_role",
    "domain",
    "main_contexts",
)

_GOAL_BRIEF_ENRICHMENT_FIELDS: tuple[str, ...] = (
    "target_market",
    "deadline_type",
)

_GOAL_BRIEF_FIELD_LABELS: dict[str, str] = {
    "primary_goal": "goal",
    "target_role": "target role",
    "domain": "domain",
    "main_contexts": "practice context",
    "target_market": "target company context",
    "deadline_type": "timeline",
}


def _normalize_context_label(value: Any) -> str:
    source = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    source = re.sub(r"[^a-z0-9\s]", " ", source)
    return " ".join(source.split())


def normalize_goal_brief_context(value: Any) -> Optional[str]:
    """Return a canonical practice-context enum, or None for unsupported text."""
    raw = str(value or "").strip().lower()
    if raw in SUPPORTED_GOAL_CONTEXTS:
        return raw
    return _CONTEXT_ALIASES.get(_normalize_context_label(value))


def normalize_goal_brief_contexts(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    seen: set[str] = set()
    contexts: list[str] = []
    for value in values:
        canonical = normalize_goal_brief_context(value)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        contexts.append(canonical)
    return contexts


def normalize_goal_brief(goal_brief: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Normalize contract-owned fields while preserving unrelated metadata."""
    normalized = dict(goal_brief or {})
    if "main_contexts" in normalized:
        normalized["main_contexts"] = normalize_goal_brief_contexts(
            normalized.get("main_contexts")
        )
    return normalized


def goal_brief_required_fields(*, mode: GoalBriefMode = "routing") -> tuple[str, ...]:
    if mode == "full":
        return (*_GOAL_BRIEF_ROUTING_FIELDS, *_GOAL_BRIEF_ENRICHMENT_FIELDS)
    return _GOAL_BRIEF_ROUTING_FIELDS


def goal_brief_missing_keys(
    goal_brief: Optional[dict[str, Any]],
    *,
    mode: GoalBriefMode = "routing",
) -> list[str]:
    goal_brief = normalize_goal_brief(goal_brief)
    missing: list[str] = []
    for key in goal_brief_required_fields(mode=mode):
        value = goal_brief.get(key)
        if key == "main_contexts":
            if not value:
                missing.append(key)
            continue
        if not value:
            missing.append(key)
    return missing


def goal_brief_missing_labels(
    goal_brief: Optional[dict[str, Any]],
    *,
    mode: GoalBriefMode = "routing",
) -> list[str]:
    return [_GOAL_BRIEF_FIELD_LABELS[key] for key in goal_brief_missing_keys(goal_brief, mode=mode)]


def is_goal_brief_routing_ready(goal_brief: Optional[dict[str, Any]]) -> bool:
    goal_brief = normalize_goal_brief(goal_brief)
    contexts = goal_brief.get("main_contexts") or []
    return bool(
        goal_brief.get("primary_goal")
        and goal_brief.get("target_role")
        and goal_brief.get("domain")
        and contexts
        and "general_fluency" not in contexts
    )


def is_goal_brief_complete(goal_brief: Optional[dict[str, Any]]) -> bool:
    return is_goal_brief_routing_ready(goal_brief) and not goal_brief_missing_keys(
        goal_brief,
        mode="full",
    )


def goal_brief_setup_progress(
    goal_brief: Optional[dict[str, Any]],
    *,
    assessment_complete: bool,
) -> int:
    goal_brief = normalize_goal_brief(goal_brief)
    filled_slots = 0
    total_slots = len(goal_brief_required_fields(mode="full")) + 1  # + assessment

    for key in goal_brief_required_fields(mode="full"):
        value = goal_brief.get(key)
        if key == "main_contexts":
            if value:
                filled_slots += 1
            continue
        if value:
            filled_slots += 1

    if assessment_complete:
        filled_slots += 1

    return int(round((filled_slots / total_slots) * 100))
