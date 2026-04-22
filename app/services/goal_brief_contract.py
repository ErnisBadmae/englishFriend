from __future__ import annotations

from typing import Any, Literal, Optional

GoalBriefMode = Literal["routing", "full"]

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


def goal_brief_required_fields(*, mode: GoalBriefMode = "routing") -> tuple[str, ...]:
    if mode == "full":
        return (*_GOAL_BRIEF_ROUTING_FIELDS, *_GOAL_BRIEF_ENRICHMENT_FIELDS)
    return _GOAL_BRIEF_ROUTING_FIELDS


def goal_brief_missing_keys(
    goal_brief: Optional[dict[str, Any]],
    *,
    mode: GoalBriefMode = "routing",
) -> list[str]:
    goal_brief = goal_brief or {}
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
    goal_brief = goal_brief or {}
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
    goal_brief = goal_brief or {}
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
