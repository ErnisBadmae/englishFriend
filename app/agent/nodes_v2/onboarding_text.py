"""Stateless text helpers for the onboarding node.

Pure functions over raw user text and goal-brief dicts: STT-noise
normalization, substring signal matching, context ordering, and role/domain
inference. No agent state is read or mutated here; these helpers are shared
by the onboarding goal-brief and baseline-assessment logic.
"""

import re
from typing import Any, Optional

from app.agent.nodes_v2.onboarding_patterns import (
    _ASSESSMENT_AFFIRMATION_PREFIX_RE,
    _ML_SIGNAL_PATTERNS,
    _ROLE_DOMAIN_PATTERNS,
    _STT_NOISE_REPLACEMENTS,
)
from app.services.routing.goal_routing import score_context_signals


def _normalize_user_message(message: Optional[str]) -> str:
    source = (message or "").lower().replace("-", " ")
    normalized = f" {source} "
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    for noise, replacement in _STT_NOISE_REPLACEMENTS:
        normalized = re.sub(rf"\b{re.escape(noise)}\b", replacement, normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return f" {normalized} "


def _normalize_assessment_answer(message: Optional[str]) -> str:
    normalized = _normalize_user_message(message).strip()
    if not normalized:
        return ""
    previous = None
    while normalized and previous != normalized:
        previous = normalized
        normalized = _ASSESSMENT_AFFIRMATION_PREFIX_RE.sub("", normalized).strip()
    return normalized


def _has_any_signal(message: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in message for pattern in patterns)


def _count_signal_hits(message: str, patterns: tuple[str, ...]) -> int:
    return sum(1 for pattern in patterns if pattern in message)


def _dedupe_text(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = str(item or "").strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def _order_main_contexts(
    contexts: list[str],
    *,
    normalized_message: str,
    cumulative_text: Optional[str] = None,
) -> list[str]:
    """Order ``contexts`` by cumulative signal score.

    ``cumulative_text`` — concatenated onboarding transcript. When provided,
    scoring is done across the whole transcript, not just the latest reply.
    This is the core fix for second-turn context drift.
    """
    unique_contexts = _dedupe_text(contexts)
    if not unique_contexts:
        return []

    scoring_text = cumulative_text if cumulative_text is not None else normalized_message
    signal_scores = score_context_signals(scoring_text)
    existing_order = {value: index for index, value in enumerate(unique_contexts)}

    return sorted(
        unique_contexts,
        key=lambda value: (
            signal_scores.get(value, 0),
            -existing_order.get(value, 999),  # earlier position wins on tie
        ),
        reverse=True,
    )


def _infer_role_domain_from_message(
    normalized_message: str,
) -> tuple[Optional[str], Optional[str]]:
    for pattern, role_label, domain in _ROLE_DOMAIN_PATTERNS:
        if pattern in normalized_message:
            return role_label, domain
    if _has_any_signal(normalized_message, _ML_SIGNAL_PATTERNS):
        return "ML Engineer", "machine_learning"
    return None, None


def _build_primary_goal_from_brief(goal_brief: dict[str, Any]) -> str:
    target_role = str(goal_brief.get("target_role") or "international role").strip()
    primary_context = str(((goal_brief.get("main_contexts") or [None])[0]) or "").strip().lower()

    if primary_context == "workplace_communication":
        return f"Build English for clearer workplace communication as a {target_role} in an international company."
    if primary_context == "project_walkthrough":
        return f"Build English to explain {target_role} projects clearly in an international company."
    return f"Build English for {target_role} interviews in an international company."
