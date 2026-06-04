"""Career goal-brief inference and routing for the onboarding node.

Owns the goal-brief: lexical inference from (noisy) user text, the 3-bucket
scope gate, slot merge/normalization, the career-routing arbiter, and
explicit-correction handling. Functions read and mutate AgentState but never
call the onboarding node or the LLM directly — that orchestration stays in
onboarding.py. Depends on the patterns/text/assessment leaves of the package.
"""

from typing import Any, Optional

from app.core.config import settings
from app.agent.state import AgentPhase, AgentState
from app.services.goal_brief_contract import (
    goal_brief_missing_labels,
    is_goal_brief_routing_ready,
    normalize_goal_brief,
)
from app.services.routing.career_classifier import (
    CareerRoutingArbiterDecision,
    arbitrate_career_routing,
    classify_career_routing,
)
from app.services.routing.goal_routing import (
    resolve_goal_routing,
    score_context_signals,
)
from app.services.onboarding.turn_analyzer import OnboardingTurnAnalysis
from app.agent.nodes_v2.onboarding_patterns import (
    _CONTEXT_NEGATION_PATTERNS,
    _CORRECTION_CUE_PATTERNS,
    _FLEXIBLE_COMPANY_CONTEXT_PATTERNS,
    _FORCE_ROUTE_AFTER_GOAL_TURNS,
    _JOB_SIGNAL_PATTERNS,
    _ML_SIGNAL_PATTERNS,
    _TURN_ANALYZER_MIN_CONFIDENCE,
    _VOCAB_SIGNAL_PATTERNS,
)
from app.agent.nodes_v2.onboarding_text import (
    _build_primary_goal_from_brief,
    _dedupe_text,
    _has_any_signal,
    _infer_role_domain_from_message,
    _normalize_user_message,
    _order_main_contexts,
)
from app.agent.nodes_v2.onboarding_assessment import (
    _get_active_assessment_key,
    _should_run_explicit_assessment,
)


def _goal_brief_missing_fields(goal_brief: dict[str, Any]) -> list[str]:
    return goal_brief_missing_labels(goal_brief, mode="routing")


def _is_goal_brief_routing_ready(goal_brief: dict[str, Any]) -> bool:
    return is_goal_brief_routing_ready(goal_brief)


def _coerce_goal_brief_state(goal_brief: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_goal_brief(goal_brief)
    if normalized.get("status") == "confirmed":
        normalized["confirmed_by_user"] = True
    if _is_goal_brief_routing_ready(normalized) and not normalized.get("deadline_type"):
        normalized["deadline_type"] = "open_ended"

    missing = _goal_brief_missing_fields(normalized)
    if not missing and normalized.get("confirmed_by_user"):
        normalized["status"] = "confirmed"
    elif _is_goal_brief_routing_ready(normalized):
        normalized["status"] = "draft"
    else:
        normalized["status"] = "incomplete"
    return normalized


_SCOPE_NARROWING_QUESTION = (
    "What is closest right now: passing an interview in English, "
    "explaining your projects clearly, or speaking with confidence at work? "
    "Pick the one that feels most urgent."
)

_OUT_OF_SCOPE_MESSAGE = (
    "EnglishFriend is a career-English coach — it works best for interview prep, "
    "project walkthroughs, and international workplace communication. "
    "If one of those matches your goal, tell me more about the role or situation you are preparing for."
)


def _build_scope_narrowing_question() -> str:
    return _SCOPE_NARROWING_QUESTION


def _build_out_of_scope_response() -> str:
    return _OUT_OF_SCOPE_MESSAGE


def _apply_scope_gate_response(state: AgentState, scope_status: str) -> None:
    """Populate state with the scope-gate response so onboarding can exit early."""
    if scope_status == "generic_english_only":
        state["pending_response"] = _build_out_of_scope_response()
    else:
        state["pending_response"] = _build_scope_narrowing_question()
    state["needs_user_input"] = True
    state["current_phase"] = AgentPhase.ONBOARDING
    state["setup_step"] = "goal_setup"
    state["last_question_type"] = "scope_gate"


def _build_goal_followup_question(goal_brief: dict[str, Any], goal_text: Optional[str]) -> str:
    normalized = _coerce_goal_brief_state(goal_brief)
    missing = _goal_brief_missing_fields(normalized)
    if not missing:
        role = normalized.get("target_role") or "your target role"
        contexts = ", ".join(item.replace("_", " ") for item in (normalized.get("main_contexts") or [])[:2])
        return (
            f"I already have a draft target for {role}"
            f"{f' focused on {contexts}' if contexts else ''}. "
            "I can move to your first useful mission now unless you want to correct the draft."
        )

    first_missing = missing[0]
    if first_missing == "goal":
        contexts = ", ".join(item.replace("_", " ") for item in (normalized.get("main_contexts") or [])[:2])
        if contexts:
            return (
                f"I already heard a direction around {contexts}. "
                "Which role is closest right now: ML engineer, data scientist, or applied scientist?"
            )
        return (
            "What is closest right now: getting an ML job abroad, speaking better in an international team, "
            "or passing interviews in English?"
        )
    if first_missing == "target role":
        return (
            f'I understand the direction: "{goal_text or normalized.get("primary_goal") or "career English"}". '
            "Which role is closest right now: ML engineer, data scientist, or applied scientist?"
        )
    if first_missing == "domain":
        return "Which domain should the program optimize for: machine learning, data science, or software engineering?"
    if first_missing == "company context":
        return "What company context matters most: western company, global remote team, or international startup?"
    if first_missing == "timeline":
        return "What is your timeline: 1-3 months, 3-6 months, or open-ended?"
    if first_missing == "practice context":
        return "Which situations matter most first: interviews, project walkthroughs, or workplace communication?"
    return "Before I build your program, I need a more concrete job target. Tell me the role, company context, and main speaking situations."


def _filter_goal_brief_update_for_turn(
    state: AgentState,
    inferred_goal_brief: Optional[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    if not inferred_goal_brief:
        return None

    assessment_key = _get_active_assessment_key(state)
    if not assessment_key:
        return inferred_goal_brief

    if assessment_key != "target_role":
        return None

    target_role = str(inferred_goal_brief.get("target_role") or "").strip()
    if not target_role:
        return None

    existing_target_role = str((state.get("goal_brief") or {}).get("target_role") or "").strip()
    if existing_target_role and existing_target_role.lower() == target_role.lower():
        return None

    return {"target_role": target_role}


def _should_run_goal_routing_classifier(state: AgentState) -> bool:
    if settings.career_routing_classifier_mode == "off":
        return False
    if state.get("goal_setup_complete"):
        return False
    if _should_run_explicit_assessment(state):
        return False
    current_phase = state.get("current_phase")
    if current_phase not in {None, AgentPhase.START, AgentPhase.ONBOARDING}:
        return False
    # Plan contract: classifier is only consulted for in-scope inputs. Out-of-scope
    # and needs_narrowing turns must never reach the classifier.
    scope_status = state.get("scope_status")
    if scope_status not in (None, "in_scope"):
        return False
    return bool(str(state.get("last_user_message") or "").strip())


def _finalize_goal_brief_after_merge(goal_brief: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(goal_brief or {})
    if (
        normalized.get("target_role")
        and normalized.get("main_contexts")
        and not normalized.get("primary_goal")
    ):
        normalized["primary_goal"] = _build_primary_goal_from_brief(normalized)
    if normalized.get("main_contexts") and not normalized.get("deadline_type"):
        normalized["deadline_type"] = "open_ended"
    if normalized.get("main_contexts") and not normalized.get("motivation"):
        normalized["motivation"] = "Use English to move closer to an international role."
    return _coerce_goal_brief_state(normalized)


def _build_forced_goal_brief_if_ready(
    state: AgentState,
    *,
    cumulative_text: str,
) -> Optional[dict[str, Any]]:
    """After repeated low-signal turns, choose a safe bounded first mission.

    This keeps anxious or one-word users out of an infinite "tell me more"
    loop while still using the canonical routing policy.
    """
    if state.get("goal_setup_complete"):
        return None
    if int(state.get("turn_count", 0) or 0) < _FORCE_ROUTE_AFTER_GOAL_TURNS:
        return None

    normalized_text = _normalize_user_message(cumulative_text)
    target_role, domain = _infer_role_domain_from_message(normalized_text)
    profile = resolve_goal_routing(
        goal_brief=state.get("goal_brief") or {},
        conversation_history=state.get("conversation_history") or [],
        last_user_message=state.get("last_user_message") or "",
    )
    goal_brief = {
        "primary_goal": "",
        "target_role": target_role or "IT Specialist",
        "domain": domain or "professional_communication",
        "main_contexts": list(profile.main_contexts),
        "deadline_type": "open_ended",
        "motivation": "Use English to move closer to an international role.",
        "routing_decision_source": (
            "cumulative_signals" if profile.decision_source != "default" else "safe_default"
        ),
    }
    goal_brief["primary_goal"] = _build_primary_goal_from_brief(goal_brief)
    return _coerce_goal_brief_state(goal_brief)


def _apply_turn_analysis_followup_if_needed(
    state: AgentState,
    analysis: Optional[OnboardingTurnAnalysis],
) -> bool:
    """Apply a high-confidence analyzer result only when it asks for a missing slot."""
    if not analysis:
        return False
    if analysis.confidence < _TURN_ANALYZER_MIN_CONFIDENCE:
        return False
    if analysis.scope_status != "in_scope":
        return False
    if state.get("goal_setup_complete"):
        return False
    if _is_goal_brief_routing_ready(state.get("goal_brief") or {}):
        return False

    update = analysis.to_goal_brief_update()
    if not update:
        return False

    normalized_goal_brief = _finalize_goal_brief_after_merge(
        _merge_goal_brief(state.get("goal_brief") or {}, update)
    )
    if _is_goal_brief_routing_ready(normalized_goal_brief):
        return False

    if analysis.next_action not in {
        "ask_goal",
        "ask_target_role",
        "ask_company_context",
        "ask_practice_context",
    }:
        return False

    state["goal_brief"] = normalized_goal_brief
    state["goal_setup_complete"] = False
    state["setup_step"] = "goal_setup"
    state["current_phase"] = AgentPhase.ONBOARDING
    state["needs_user_input"] = True
    state["pending_response"] = _build_goal_followup_question(
        normalized_goal_brief,
        normalized_goal_brief.get("primary_goal"),
    )
    state["last_question_type"] = "goal_setup"
    return True


async def _prepare_goal_brief_turn_update(
    state: AgentState,
    *,
    user_message: str,
    cumulative_text: str,
) -> CareerRoutingArbiterDecision:
    lexical_goal_brief = _filter_goal_brief_update_for_turn(
        state,
        _infer_goal_brief_from_message(
            user_message,
            state.get("goal_brief") or {},
            cumulative_text=cumulative_text,
        ),
    )
    if lexical_goal_brief is None or not _is_goal_brief_routing_ready(lexical_goal_brief):
        forced_goal_brief = _build_forced_goal_brief_if_ready(
            state,
            cumulative_text=cumulative_text,
        )
        if forced_goal_brief:
            lexical_goal_brief = forced_goal_brief
    classifier_result = None
    if _should_run_goal_routing_classifier(state):
        classifier_result = await classify_career_routing(
            transcript_text=cumulative_text,
            latest_user_message=user_message,
            existing_goal_brief=state.get("goal_brief") or {},
        )
    return arbitrate_career_routing(
        existing_goal_brief=state.get("goal_brief") or {},
        lexical_goal_brief=lexical_goal_brief,
        classifier_result=classifier_result,
        transcript_text=cumulative_text,
        mode=settings.career_routing_classifier_mode,
        min_confidence=float(settings.career_routing_classifier_min_confidence),
        scope_status=state.get("scope_status"),
    )


def _has_explicit_goal_correction_signal(message: str) -> bool:
    return _has_any_signal(message, _CORRECTION_CUE_PATTERNS)


def _negated_contexts_from_message(normalized_message: str) -> set[str]:
    negated: set[str] = set()
    for context, patterns in _CONTEXT_NEGATION_PATTERNS.items():
        if _has_any_signal(normalized_message, patterns):
            negated.add(context)
    return negated


def _infer_goal_brief_correction_from_message(
    state: AgentState,
    message: str,
) -> Optional[dict[str, Any]]:
    goal_brief = state.get("goal_brief") or {}
    if not state.get("goal_setup_complete"):
        return None
    if state.get("current_phase") not in {None, AgentPhase.ONBOARDING}:
        return None

    normalized_message = _normalize_user_message(message)
    if not normalized_message.strip() or not _has_explicit_goal_correction_signal(normalized_message):
        return None

    corrected: dict[str, Any] = {}
    existing_contexts = list(goal_brief.get("main_contexts") or [])
    context_scores = score_context_signals(message)
    negated_contexts = _negated_contexts_from_message(normalized_message)
    positive_contexts = [
        context
        for context in ("interviews", "workplace_communication", "project_walkthrough")
        if context_scores.get(context, 0) > 0 and context not in negated_contexts
    ]

    if positive_contexts:
        corrected["main_contexts"] = _order_main_contexts(
            positive_contexts,
            normalized_message=normalized_message,
            cumulative_text=normalized_message,
        )
    elif negated_contexts and existing_contexts:
        remaining_contexts = [
            context for context in existing_contexts
            if str(context).strip().lower() not in negated_contexts
        ]
        remaining_contexts = _dedupe_text(remaining_contexts)
        if remaining_contexts and remaining_contexts != _dedupe_text(existing_contexts):
            corrected["main_contexts"] = remaining_contexts

    target_role, domain = _infer_role_domain_from_message(normalized_message)
    if target_role:
        corrected["target_role"] = target_role
    if domain:
        corrected["domain"] = domain
    if (
        _has_any_signal(normalized_message, _JOB_SIGNAL_PATTERNS)
        or _has_any_signal(normalized_message, _FLEXIBLE_COMPANY_CONTEXT_PATTERNS)
    ):
        corrected["target_market"] = "international_company"

    if not corrected:
        return None
    return corrected


def _infer_goal_brief_from_message(
    message: str,
    existing_goal_brief: Optional[dict[str, Any]] = None,
    *,
    cumulative_text: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Infer goal-brief fields from a single user turn.

    ``cumulative_text`` — optional concatenated onboarding transcript so
    ``main_contexts`` ordering reflects the whole goal-setup conversation,
    not just the latest reply.
    """
    normalized_message = _normalize_user_message(message)
    if not normalized_message.strip():
        return None
    normalized_scoring_text = _normalize_user_message(cumulative_text or message)

    existing = dict(existing_goal_brief or {})
    inferred = dict(existing)
    signal_count = 0

    target_role, domain = _infer_role_domain_from_message(normalized_scoring_text)
    if target_role:
        signal_count += 1
        inferred.setdefault("target_role", target_role)
        if domain:
            inferred.setdefault("domain", domain)
    elif _has_any_signal(normalized_scoring_text, _ML_SIGNAL_PATTERNS):
        signal_count += 1
        inferred.setdefault("target_role", "ML Engineer")
        inferred.setdefault("domain", "machine_learning")

    if _has_any_signal(normalized_scoring_text, _JOB_SIGNAL_PATTERNS):
        signal_count += 1
        inferred.setdefault("target_market", "international_company")
    elif _has_any_signal(normalized_scoring_text, _FLEXIBLE_COMPANY_CONTEXT_PATTERNS):
        signal_count += 1
        inferred.setdefault("target_market", "international_company")

    contexts = list(inferred.get("main_contexts") or [])
    context_scores = score_context_signals(cumulative_text or message)
    positive_contexts = [
        context
        for context in ("interviews", "workplace_communication", "project_walkthrough")
        if context_scores.get(context, 0) > 0
    ]
    if positive_contexts:
        signal_count += 1
        contexts.extend(positive_contexts)
    if _has_any_signal(normalized_scoring_text, _VOCAB_SIGNAL_PATTERNS):
        signal_count += 1
        blockers = list(inferred.get("current_blockers") or [])
        blockers.append("Need stronger ML and interview vocabulary")
        inferred["current_blockers"] = blockers

    existing_has_context = bool(existing.get("main_contexts"))
    if (
        signal_count < 2
        and not _is_goal_brief_routing_ready(existing)
        and not (existing_has_context and signal_count >= 1)
    ):
        return None

    if contexts:
        inferred["main_contexts"] = _order_main_contexts(
            contexts,
            normalized_message=normalized_message,
            cumulative_text=cumulative_text,
        )
    elif inferred.get("domain") == "machine_learning":
        inferred["main_contexts"] = ["interviews", "project_walkthrough", "workplace_communication"]

    if inferred.get("domain") == "machine_learning":
        inferred.setdefault(
            "primary_goal",
            "Build English for an international ML/AI role with stronger interview and project communication.",
        )
        blockers = list(inferred.get("current_blockers") or [])
        if context_scores.get("interviews", 0) > 0:
            blockers.append("Need structured interview answers under pressure")
        if _has_any_signal(normalized_scoring_text, _JOB_SIGNAL_PATTERNS):
            blockers.append("Need confident English for international job opportunities")
        inferred["current_blockers"] = blockers

    if (
        inferred.get("target_role")
        and inferred.get("main_contexts")
        and not inferred.get("primary_goal")
    ):
        inferred["primary_goal"] = _build_primary_goal_from_brief(inferred)

    inferred.setdefault("deadline_type", "open_ended")
    inferred.setdefault("motivation", "Use English to move closer to an international ML/AI role.")
    inferred["confidence"] = round(min(0.95, 0.55 + signal_count * 0.08), 2)
    inferred["main_contexts"] = _dedupe_text(inferred.get("main_contexts") or [])
    inferred["current_blockers"] = _dedupe_text(inferred.get("current_blockers") or [])

    return _coerce_goal_brief_state(inferred)


def _merge_goal_brief(
    existing_goal_brief: dict[str, Any],
    *updates: Optional[dict[str, Any]],
    confirmed: bool = False,
    reset_confirmation: bool = False,
) -> dict[str, Any]:
    """Merge goal-brief updates, keeping ``main_contexts`` sticky.

    Once the existing brief is routing-ready (``status`` in ``draft`` /
    ``confirmed``), ``main_contexts`` is not overwritten. New contexts from
    updates are appended to preserve the primary that onboarding already
    locked in. Other fields keep the existing last-write-wins behavior.
    """
    merged = dict(existing_goal_brief or {})
    if reset_confirmation:
        merged["confirmed_by_user"] = False
        if str(merged.get("status") or "").lower() == "confirmed":
            merged["status"] = "draft"
    existing_is_sticky = _is_goal_brief_routing_ready(merged)
    existing_contexts = list(merged.get("main_contexts") or [])

    for update in updates:
        if not update:
            continue
        for key, value in update.items():
            if value in (None, "", []):
                continue
            if (
                key == "main_contexts"
                and existing_is_sticky
                and existing_contexts
                and not reset_confirmation
            ):
                # Keep the locked-in primary context first; append any new
                # secondary contexts from the update without reordering.
                combined = list(existing_contexts)
                for ctx in value:
                    if ctx and ctx not in combined:
                        combined.append(ctx)
                merged[key] = combined
                continue
            merged[key] = value

    if not reset_confirmation and (
        confirmed or merged.get("status") == "confirmed" or merged.get("confirmed_by_user")
    ):
        merged["confirmed_by_user"] = True
    return _coerce_goal_brief_state(merged)


def _apply_explicit_goal_correction(
    state: AgentState,
    correction: dict[str, Any],
) -> dict[str, Any]:
    normalized_goal_brief = _merge_goal_brief(
        state.get("goal_brief") or {},
        {
            **correction,
            "confirmed_by_user": False,
            "routing_decision_source": "explicit_user_correction",
        },
        reset_confirmation=True,
    )
    if any(key in correction for key in ("main_contexts", "target_role", "domain")):
        normalized_goal_brief["primary_goal"] = _build_primary_goal_from_brief(
            normalized_goal_brief
        )

    state["goal_brief"] = _coerce_goal_brief_state(normalized_goal_brief)
    state["goal_setup_complete"] = _is_goal_brief_routing_ready(state["goal_brief"])
    state["goal_needs_confirmation"] = True
    state["confirmed_goal"] = None
    state["detected_goal"] = state["goal_brief"].get("primary_goal")
    state["current_phase"] = AgentPhase.ONBOARDING
    state["setup_step"] = "goal_setup"
    state["last_question_type"] = "goal_setup"
    state["_skip_assessment"] = False
    return state["goal_brief"]


def _filter_llm_goal_brief_extraction(
    state: AgentState,
    extracted: Optional[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Drop fields that must not change after the goal is routing-ready.

    Protects ``main_contexts``, ``domain``, ``target_role``, and
    ``target_market`` from second-turn LLM drift. Softer fields (blockers,
    motivation, deadline) remain editable.
    """
    if not extracted:
        return extracted
    if not state.get("goal_setup_complete"):
        return extracted

    protected = {"main_contexts", "domain", "target_role", "target_market"}
    filtered = {k: v for k, v in extracted.items() if k not in protected}
    return filtered if filtered else None


def _apply_goal_brief_to_state(
    state: AgentState,
    goal_brief: Optional[dict[str, Any]],
    *,
    goal_text: Optional[str],
    confirmed: bool,
) -> dict[str, Any]:
    normalized_goal_brief = _finalize_goal_brief_after_merge(
        _merge_goal_brief(
            state.get("goal_brief") or {},
            goal_brief,
            confirmed=confirmed,
        )
    )
    if goal_text:
        if confirmed:
            state["confirmed_goal"] = goal_text
        else:
            state["detected_goal"] = goal_text
    elif normalized_goal_brief.get("primary_goal"):
        if confirmed:
            state["confirmed_goal"] = normalized_goal_brief["primary_goal"]
        elif not state.get("detected_goal"):
            state["detected_goal"] = normalized_goal_brief["primary_goal"]

    state["goal_brief"] = normalized_goal_brief
    state["goal_setup_complete"] = _is_goal_brief_routing_ready(normalized_goal_brief)
    return normalized_goal_brief
