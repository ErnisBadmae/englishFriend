"""Canonical routing policy for career-English goals.

Single source of truth for three decisions:

1. Which ``primary_context`` describes the user's goal
   (``interviews`` | ``workplace_communication`` | ``project_walkthrough``).
2. Which ``recommended_track_id`` the program should start from
   (``hr_intro`` | ``workplace_communication`` | ``project_walkthrough``).
3. Which ``first_mission_task_type`` the first useful mission must be
   (``foundation_speaking_drill`` | ``stakeholder_explanation_drill`` |
   ``technical_project_walkthrough``).

All three are derived from the same mapping so onboarding, program snapshot,
and interview-pack selection cannot drift apart.

Design invariants:

* ``primary_context`` is the source of truth for the first useful mission.
  ``domain`` and secondary contexts may influence wording or later mission
  routing, but they cannot change the first-mission ``task_type``.
* Once ``goal_brief.status`` is ``draft`` or ``confirmed``, ``primary_context``
  is sticky — a later turn cannot override it through keyword drift. The only
  way to move primary is an explicit user correction of the draft goal.
* Context scoring is cumulative. When the goal is still being built, the
  resolver sums signals across all user turns of the onboarding transcript,
  not just the latest reply.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from app.services.goal_brief_contract import (
    SUPPORTED_GOAL_CONTEXTS,
    normalize_goal_brief,
    normalize_goal_brief_context,
    normalize_goal_brief_contexts,
)


# ---------------------------------------------------------------------------
# Canonical signal patterns
# ---------------------------------------------------------------------------

# Interview signals are kept narrow and unambiguous.
INTERVIEW_SIGNAL_PATTERNS: tuple[str, ...] = (
    "interview",
    "interviews",
    "mock interview",
    "hr interview",
    "tell me about yourself",
    "recruiter",
    "self intro",
    "self-intro",
)

# Project signals describe talking about a specific piece of technical work.
# ``explain`` is intentionally NOT here — it collides with
# "explain to a non-technical stakeholder" which is a workplace scenario.
PROJECT_SIGNAL_PATTERNS: tuple[str, ...] = (
    "project",
    "projects",
    "architecture",
    "system design",
    "tradeoff",
    "trade off",
    "trade-off",
    "tradeoffs",
    "trade offs",
    "metric",
    "metrics",
    "impact",
    "latency",
    "pipeline",
    "model",
    "trained",
    "training",
    "walk through",
    "walkthrough",
)

# Workplace signals describe speaking to colleagues and stakeholders.
WORKPLACE_SIGNAL_PATTERNS: tuple[str, ...] = (
    "client",
    "client meeting",
    "client presentation",
    "product manager",
    "product managers",
    "operations",
    "cross functional",
    "cross-functional",
    "status update",
    "standup",
    "stand up",
    "stand-up",
    "update",
    "present",
    "non technical",
    "non-technical",
    "jargon",
    "business",
    "manager",
    "stakeholder",
    "stakeholders",
    "team",
    "meeting",
    "speak with",
    "talk with",
    "colleague",
    "colleagues",
    "workplace",
)


# ---------------------------------------------------------------------------
# Mapping table: primary_context -> track and first mission
# ---------------------------------------------------------------------------

_PRIMARY_TO_TRACK: dict[str, str] = {
    "interviews": "hr_intro",
    "workplace_communication": "workplace_communication",
    "project_walkthrough": "project_walkthrough",
}

_PRIMARY_TO_FIRST_MISSION: dict[str, str] = {
    "interviews": "foundation_speaking_drill",
    "workplace_communication": "stakeholder_explanation_drill",
    "project_walkthrough": "technical_project_walkthrough",
}

# Safe defaults when no primary context can be inferred — lowest-pressure path.
_DEFAULT_PRIMARY_CONTEXT = "interviews"
_DEFAULT_TRACK_ID = _PRIMARY_TO_TRACK[_DEFAULT_PRIMARY_CONTEXT]
_DEFAULT_FIRST_MISSION = _PRIMARY_TO_FIRST_MISSION[_DEFAULT_PRIMARY_CONTEXT]

_SUPPORTED_PRIMARY = SUPPORTED_GOAL_CONTEXTS

_NEGATION_WINDOW_TOKENS = 6
_NEGATION_TOKENS = {
    "not",
    "no",
    "never",
    "without",
    "dont",
    "don't",
    "doesnt",
    "doesn't",
}
_NEGATION_PHRASES = (
    "do not",
    "does not",
    "rather than",
    "instead of",
    "not want",
    "dont want",
    "don't want",
)
_STT_NOISE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("intarview", "interview"),
    ("intarviews", "interviews"),
    ("practis", "practice"),
    ("practise", "practice"),
    ("prepear", "prepare"),
    ("preparashon", "preparation"),
    ("injineer", "engineer"),
    ("pozishon", "position"),
    ("abrod", "abroad"),
    ("jab", "job"),
    ("teknikal", "technical"),
    ("teknical", "technical"),
    ("internashenal", "international"),
    ("compny", "company"),
)


@dataclass(frozen=True)
class GoalRoutingProfile:
    """Resolved routing decision derived from a goal brief + transcript."""

    primary_context: str
    main_contexts: tuple[str, ...]
    recommended_track_id: str
    first_mission_task_type: str
    context_scores: dict[str, int] = field(default_factory=dict)
    decision_source: str = "cumulative_signals"


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    normalized = str(text).lower().replace("-", " ")
    normalized = re.sub(r"[^a-z0-9'\s]", " ", normalized)
    for source, target in _STT_NOISE_REPLACEMENTS:
        normalized = re.sub(rf"\b{re.escape(source)}\b", target, normalized)
    return " ".join(normalized.split())


def _split_signal_segments(text: str) -> list[str]:
    return [
        segment.strip()
        for segment in re.split(r"[\n.!?;]+", text)
        if segment.strip()
    ]


def _pattern_tokens(pattern: str) -> list[str]:
    return _normalize_text(pattern).split()


def _is_negated_match(tokens: list[str], start_index: int) -> bool:
    window = tokens[max(0, start_index - _NEGATION_WINDOW_TOKENS):start_index]
    if any(token in _NEGATION_TOKENS for token in window):
        return True
    prefix = " ".join(window)
    return any(phrase in prefix for phrase in _NEGATION_PHRASES)


def _segment_has_positive_pattern(segment: str, pattern: str) -> bool:
    tokens = segment.split()
    pattern_tokens = _pattern_tokens(pattern)
    if not tokens or not pattern_tokens or len(pattern_tokens) > len(tokens):
        return False
    width = len(pattern_tokens)
    for index in range(0, len(tokens) - width + 1):
        if tokens[index:index + width] != pattern_tokens:
            continue
        if _is_negated_match(tokens, index):
            continue
        return True
    return False


def _count_hits(text: str, patterns: Iterable[str]) -> int:
    segments = _split_signal_segments(text)
    return sum(
        1
        for pattern in patterns
        if any(_segment_has_positive_pattern(segment, pattern) for segment in segments)
    )


def has_positive_context_signal(text: str, context: str) -> bool:
    scores = score_context_signals(text)
    return scores.get(context, 0) > 0


def score_context_signals(text: str) -> dict[str, int]:
    """Return cumulative signal counts for each primary context."""
    normalized = _normalize_text(text)
    if not normalized:
        return {key: 0 for key in _SUPPORTED_PRIMARY}
    return {
        "interviews": _count_hits(normalized, INTERVIEW_SIGNAL_PATTERNS),
        "workplace_communication": _count_hits(normalized, WORKPLACE_SIGNAL_PATTERNS),
        "project_walkthrough": _count_hits(normalized, PROJECT_SIGNAL_PATTERNS),
    }


def _aggregate_transcript(
    conversation_history: Optional[list[dict[str, Any]]],
    last_user_message: Optional[str],
) -> str:
    parts: list[str] = []
    for entry in conversation_history or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("role") or "").lower() != "user":
            continue
        content = str(entry.get("content") or "").strip()
        if content:
            parts.append(content)
    tail = (last_user_message or "").strip()
    if tail and (not parts or parts[-1] != tail):
        parts.append(tail)
    return " \n ".join(parts)


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = str(value or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _order_contexts_by_score(
    contexts: Iterable[str],
    scores: dict[str, int],
) -> list[str]:
    existing = _dedupe(contexts)
    # Preserve original order as a stable tie-break signal.
    prior_index = {value: index for index, value in enumerate(existing)}
    return sorted(
        existing,
        key=lambda value: (
            scores.get(value, 0),
            -prior_index.get(value, 999),  # lower index first on tie
        ),
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _is_goal_routing_ready(goal_brief: Optional[dict[str, Any]]) -> bool:
    """Return True once the goal brief is locked enough to pin primary_context."""
    if not goal_brief:
        return False
    status = str(goal_brief.get("status") or "").strip().lower()
    contexts = [c for c in (goal_brief.get("main_contexts") or []) if c]
    return status in {"draft", "confirmed"} and bool(contexts)


def _pick_primary_from_scores(scores: dict[str, int]) -> Optional[str]:
    best_context: Optional[str] = None
    best_score = 0
    # Deterministic order if multiple scores tie.
    for context in _SUPPORTED_PRIMARY:
        score = scores.get(context, 0)
        if score > best_score:
            best_score = score
            best_context = context
    return best_context if best_score > 0 else None


def resolve_goal_routing(
    goal_brief: Optional[dict[str, Any]] = None,
    *,
    conversation_history: Optional[list[dict[str, Any]]] = None,
    last_user_message: Optional[str] = None,
) -> GoalRoutingProfile:
    """Return the canonical routing decision for the given goal state.

    ``goal_brief`` — current persisted brief (may be None or incomplete).
    ``conversation_history`` — onboarding transcript (list of ``{role, content}``
    dicts). Only ``role=user`` entries are used for cumulative scoring.
    ``last_user_message`` — fallback when history is empty but the latest
    message is already in ``state``.
    """

    goal_brief = normalize_goal_brief(goal_brief)

    transcript_text = _aggregate_transcript(conversation_history, last_user_message)
    scores = score_context_signals(transcript_text)

    # 1. Sticky: once the brief is routing-ready, its main_contexts win.
    if _is_goal_routing_ready(goal_brief):
        existing_contexts = [
            normalize_goal_brief_context(c)
            for c in (goal_brief.get("main_contexts") or [])
            if normalize_goal_brief_context(c)
        ]
        existing_contexts = _dedupe(existing_contexts)
        if existing_contexts:
            primary = existing_contexts[0]
            status = str(goal_brief.get("status") or "").lower()
            if status == "confirmed":
                decision_source = "user_confirmed"
            elif (
                str(goal_brief.get("routing_decision_source") or "").strip().lower()
                == "explicit_user_correction"
            ):
                decision_source = "explicit_user_correction"
            else:
                decision_source = "goal_brief_sticky"
            return _build_profile(
                primary_context=primary,
                main_contexts=existing_contexts,
                context_scores=scores,
                decision_source=decision_source,
            )

    # 2. Cumulative scoring picks the primary context.
    inferred = _pick_primary_from_scores(scores)
    if inferred:
        ordered = _order_contexts_by_score(
            [ctx for ctx, score in scores.items() if score > 0],
            scores,
        )
        if inferred not in ordered:
            ordered.insert(0, inferred)
        return _build_profile(
            primary_context=inferred,
            main_contexts=ordered,
            context_scores=scores,
            decision_source="cumulative_signals",
        )

    # 3. No signals yet — return the safe default.
    return _build_profile(
        primary_context=_DEFAULT_PRIMARY_CONTEXT,
        main_contexts=[_DEFAULT_PRIMARY_CONTEXT],
        context_scores=scores,
        decision_source="default",
    )


def build_goal_routing_from_goal_brief(
    goal_brief: Optional[dict[str, Any]],
) -> GoalRoutingProfile:
    """Derive a routing profile purely from a persisted goal brief.

    Used by snapshot/program services that do not have the onboarding
    transcript but already have a stable ``main_contexts``.
    """
    return resolve_goal_routing(goal_brief=goal_brief)


def _build_profile(
    *,
    primary_context: str,
    main_contexts: list[str],
    context_scores: dict[str, int],
    decision_source: str,
) -> GoalRoutingProfile:
    if primary_context not in _SUPPORTED_PRIMARY:
        primary_context = (
            normalize_goal_brief_context(primary_context) or _DEFAULT_PRIMARY_CONTEXT
        )
        main_contexts = [primary_context]

    normalized_contexts = tuple(normalize_goal_brief_contexts(main_contexts) or [primary_context])
    if normalized_contexts[0] != primary_context:
        # Always put the resolved primary first.
        remainder = tuple(c for c in normalized_contexts if c != primary_context)
        normalized_contexts = (primary_context, *remainder)

    return GoalRoutingProfile(
        primary_context=primary_context,
        main_contexts=normalized_contexts,
        recommended_track_id=_PRIMARY_TO_TRACK.get(primary_context, _DEFAULT_TRACK_ID),
        first_mission_task_type=_PRIMARY_TO_FIRST_MISSION.get(
            primary_context, _DEFAULT_FIRST_MISSION
        ),
        context_scores=dict(context_scores),
        decision_source=decision_source,
    )
