"""Onboarding Node - Unified LLM-driven onboarding flow.

Handles:
- Goal discovery and confirmation
- Interest extraction
- Quick assessment

The product uses a hard guided onboarding flow:
- noisy speech should still produce a draft career goal
- a routing-ready draft is enough to move to the first useful mission
- onboarding prompt is code-owned to avoid drift from stale DB templates
"""

import logging
import time
from typing import Any, Optional

from app.agent.recovery import build_mission_safe_recovery
from app.agent.guardrails import (
    CONFIDENCE_THRESHOLDS,
    validate_and_sanitize,
    validate_confidence,
)
from app.agent.intent_policy import build_intent_context_from_state, classify_intent
from app.agent.pedagogy_policy import shadow_policy_action_for_intent
from app.agent.response_parser import (
    extract_assessment_from_action,
    extract_goal_brief_from_action,
    extract_goal_from_action,
    extract_interests_from_action,
    parse_llm_response,
)
from app.agent.state import AgentPhase, AgentState, LearningModeEnum, add_decision_log
from app.core.config import settings
from app.core.metrics import (
    agent_guardrail_fallbacks,
    agent_v2_goal_detection,
    agent_v2_llm_latency,
    agent_v2_parse_success,
)
from app.services.goal_brief_contract import (
    goal_brief_missing_keys,
    goal_brief_missing_labels,
    is_goal_brief_routing_ready,
    normalize_goal_brief,
)
from app.services.ai.llm_provider import LLMEmptyContentError, get_llm_provider
from app.services.onboarding.turn_analyzer import (
    OnboardingTurnAnalysis,
    analyze_onboarding_turn,
)
from app.services.pedagogy_logger import get_pedagogy_logger
from app.services.prompt_service import get_prompt_service
from app.services.program_snapshot_service import recommend_next_mission
from app.services.routing.career_classifier import (
    CareerRoutingArbiterDecision,
    arbitrate_career_routing,
    classify_career_routing,
)
from app.services.routing.goal_routing import (
    resolve_goal_routing,
    resolve_scope_status,
    score_context_signals,
)
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
    _normalize_assessment_answer,
    _normalize_user_message,
    _order_main_contexts,
)
from app.agent.nodes_v2.onboarding_assessment import (
    _build_assessment_followup_question,
    _enter_assessment_phase,
    _get_active_assessment_key,
    _handle_assessment_turn,
    _should_run_explicit_assessment,
)

logger = logging.getLogger(__name__)


def _is_transient_llm_connection_error(exc: Exception) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True
    message = f"{type(exc).__name__}: {exc}".lower()
    needles = (
        "connection error",
        "connect error",
        "connection aborted",
        "connection reset",
        "server disconnected",
        "timed out",
        "timeout",
        "temporarily unavailable",
        "remote protocol error",
    )
    return any(needle in message for needle in needles)


def _should_retry_first_turn_llm(state: AgentState) -> bool:
    return (
        int(state.get("turn_count", 0) or 0) == 1
        and state.get("last_question_type") == "goal_setup"
        and not state.get("goal_setup_complete")
    )


async def _generate_onboarding_llm_response(
    *,
    llm,
    user_message: str,
    system_prompt: str,
    state: AgentState,
    max_tokens: int,
) -> str:
    retry_allowed = _should_retry_first_turn_llm(state)
    attempt = 0
    while True:
        attempt += 1
        try:
            return await llm.generate(
                user_message=user_message,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            if retry_allowed and attempt == 1 and _is_transient_llm_connection_error(exc):
                logger.warning(
                    "[Onboarding] First-turn LLM connection glitch, retrying once: %s",
                    exc,
                )
                continue
            raise


async def onboarding_node(state: AgentState) -> AgentState:
    """Unified onboarding: goal discovery + interests + assessment."""
    pedagogy = get_pedagogy_logger(state["user_id"])
    prompt_service = get_prompt_service()
    llm = get_llm_provider()

    user_message = state.get("last_user_message", "") or ""
    user_id = state["user_id"]
    session_id = state.get("session_id", "")

    _record_onboarding_user_turn(state, user_message)
    _update_shadow_intent(state, user_message)

    if not user_message.strip():
        if state.get("goal_setup_complete") and not state.get("assessed_level"):
            if _should_run_explicit_assessment(state):
                state["pending_response"] = _build_assessment_followup_question(state)
                state["needs_user_input"] = True
                state["current_phase"] = AgentPhase.ASSESSMENT
                state["current_mode"] = LearningModeEnum.ASSESSMENT
            else:
                _enter_first_useful_mission(state)
            _record_onboarding_assistant_turn(state)
            return state

        if not state.get("goal_setup_complete"):
            state["pending_response"] = _build_goal_followup_question(
                state.get("goal_brief") or {},
                state.get("confirmed_goal") or state.get("detected_goal"),
            )
            state["needs_user_input"] = True
            state["current_phase"] = AgentPhase.ONBOARDING
            state["setup_step"] = "goal_setup"
            state["last_question_type"] = "goal_setup"
            _record_onboarding_assistant_turn(state)
            return state

        state["pending_response"] = "I have enough to keep building your program. Let's continue."
        state["needs_user_input"] = True
        _record_onboarding_assistant_turn(state)
        return state

    explicit_correction = _infer_goal_brief_correction_from_message(
        state,
        user_message,
    )
    if explicit_correction:
        corrected_goal_brief = _apply_explicit_goal_correction(
            state,
            explicit_correction,
        )
        state["pending_response"] = _build_goal_followup_question(
            corrected_goal_brief,
            corrected_goal_brief.get("primary_goal"),
        )
        state["needs_user_input"] = True
        _record_onboarding_assistant_turn(state)
        return state

    # Pre-routing scope gate: keep out-of-scope and vague users out of the
    # 3-bucket routing taxonomy. Only in_scope moves into goal-brief inference.
    scope_status = resolve_scope_status(
        goal_brief=state.get("goal_brief"),
        conversation_history=state.get("conversation_history"),
        last_user_message=user_message,
    )
    state["scope_status"] = scope_status
    if (
        scope_status != "in_scope"
        and not state.get("goal_setup_complete")
        and not _is_goal_brief_routing_ready(state.get("goal_brief") or {})
    ):
        _apply_scope_gate_response(state, scope_status)
        add_decision_log(
            state,
            node="onboarding",
            action="scope_gate",
            reason=f"scope_status={scope_status}",
            data={"scope_status": scope_status},
        )
        _record_onboarding_assistant_turn(state)
        return state

    if not state.get("goal_setup_complete"):
        turn_analysis = await analyze_onboarding_turn(
            user_message=user_message,
            conversation_history=state.get("conversation_history") or [],
            existing_goal_brief=state.get("goal_brief") or {},
            llm=llm,
        )
        if turn_analysis:
            state["last_onboarding_turn_analysis"] = turn_analysis.to_observability_payload()
        if _apply_turn_analysis_followup_if_needed(state, turn_analysis):
            add_decision_log(
                state,
                node="onboarding",
                action="turn_analyzer_followup",
                reason=f"next_action={turn_analysis.next_action if turn_analysis else None}",
                data=turn_analysis.to_observability_payload() if turn_analysis else None,
            )
            _record_onboarding_assistant_turn(state)
            return state

    # Pre-seed state with a draft goal from noisy speech before the LLM sees it.
    goal_became_routing_ready_this_turn = False
    cumulative_transcript = _collect_user_transcript(state, current_message=user_message)
    routing_turn_decision = await _prepare_goal_brief_turn_update(
        state,
        user_message=user_message,
        cumulative_text=cumulative_transcript,
    )
    inferred_goal_brief = routing_turn_decision.goal_brief_update
    if settings.career_routing_classifier_mode != "off" and (
        routing_turn_decision.classifier_result is not None
        or routing_turn_decision.mode != "off"
    ):
        add_decision_log(
            state,
            node="onboarding",
            action="career_routing_arbiter",
            reason=(
                f"mode={routing_turn_decision.mode}, "
                f"applied={routing_turn_decision.applied_source}"
            ),
            data=routing_turn_decision.to_observability_payload(),
        )
    if inferred_goal_brief:
        normalized_goal_brief = _finalize_goal_brief_after_merge(
            _merge_goal_brief(state.get("goal_brief") or {}, inferred_goal_brief)
        )
        state["goal_brief"] = normalized_goal_brief
        state["goal_setup_complete"] = _is_goal_brief_routing_ready(normalized_goal_brief)
        state["setup_step"] = "first_useful_mission" if state["goal_setup_complete"] else "goal_setup"
        if not state.get("detected_goal"):
            state["detected_goal"] = normalized_goal_brief.get("primary_goal")
        goal_became_routing_ready_this_turn = bool(
            state.get("goal_setup_complete") and state.get("last_question_type") == "goal_setup"
        )
        if goal_became_routing_ready_this_turn:
            state["_skip_assessment"] = True

    if goal_became_routing_ready_this_turn and not state.get("assessed_level"):
        if _should_run_explicit_assessment(state):
            _enter_assessment_phase(state)
            state["pending_response"] = _build_assessment_followup_question(state)
        else:
            _enter_first_useful_mission(state)
        state["needs_user_input"] = True
        _record_onboarding_assistant_turn(state)
        return state

    if state.get("goal_setup_complete") and not state.get("assessed_level") and _should_run_explicit_assessment(state):
        state = await _handle_assessment_turn(state, pedagogy)
        add_decision_log(
            state,
            node="onboarding",
            action="assessment_complete" if state.get("assessed_level") else "ask_assessment",
            reason="Deterministic first-run baseline flow",
            data={
                "assessment_step_index": state.get("assessment_step_index", 0),
                "baseline_provisional": state.get("baseline_provisional", False),
            },
        )
        _record_onboarding_assistant_turn(state)
        return state

    if state.get("goal_setup_complete") and not state.get("assessed_level") and state.get("_skip_assessment", False):
        _enter_first_useful_mission(state)
        _record_onboarding_assistant_turn(state)
        return state

    rendered_prompt = _get_fallback_prompt(state)
    template = None

    start_time = time.time()
    try:
        response = await _generate_onboarding_llm_response(
            llm=llm,
            user_message=user_message,
            system_prompt=rendered_prompt,
            state=state,
            max_tokens=500,
        )
        latency_ms = int((time.time() - start_time) * 1000)
        agent_v2_llm_latency.labels(node="onboarding").observe(latency_ms / 1000)
    except LLMEmptyContentError as exc:
        logger.warning("[Onboarding] Empty final content: %s", exc)
        state["pending_response"] = _build_goal_followup_question(
            state.get("goal_brief") or {},
            state.get("last_user_message"),
        )
        state["needs_user_input"] = True
        return state
    except Exception as exc:
        logger.error("[Onboarding] LLM error: %s", exc)
        if inferred_goal_brief or (
            _should_retry_first_turn_llm(state) and _is_transient_llm_connection_error(exc)
        ):
            normalized_goal_brief = _finalize_goal_brief_after_merge(
                _merge_goal_brief(state.get("goal_brief") or {}, inferred_goal_brief)
            )
            state["goal_brief"] = normalized_goal_brief
            state["goal_setup_complete"] = _is_goal_brief_routing_ready(normalized_goal_brief)
            if state["goal_setup_complete"] and not state.get("assessed_level"):
                if _should_run_explicit_assessment(state):
                    _enter_assessment_phase(state)
                    state["pending_response"] = _build_assessment_followup_question(state)
                else:
                    _enter_first_useful_mission(state)
            else:
                state["pending_response"] = _build_goal_followup_question(
                    normalized_goal_brief,
                    normalized_goal_brief.get("primary_goal") or state.get("last_user_message"),
                )
        else:
            state["pending_response"] = build_mission_safe_recovery(
                mission_task_type=state.get("mission_task_type"),
                stage="onboarding",
            )
            state["fallback_reason"] = type(exc).__name__
            state["fallback_stage"] = "onboarding"
            state["retry_attempted"] = bool(_should_retry_first_turn_llm(state))
        state["needs_user_input"] = True
        return state

    parse_result = parse_llm_response(response, default_action="ask_goal")
    action = parse_result.action

    action, was_modified = validate_and_sanitize(
        response=response,
        node_type="onboarding",
        parsed_action=action,
        state=state,
    )
    if was_modified:
        agent_guardrail_fallbacks.labels(node="onboarding").inc()

    agent_v2_parse_success.labels(
        node="onboarding",
        success=str(parse_result.success).lower(),
    ).inc()

    await prompt_service.log_usage(
        session_id=session_id,
        user_id=user_id,
        node_type="onboarding",
        template=template,
        variant="fallback_hard_guided",
        turn_number=state.get("turn_count", 0),
        llm_response=response,
        parsed_action=action,
        parse_success=parse_result.success,
        latency_ms=latency_ms,
    )

    state = await _apply_onboarding_action(
        state,
        action,
        pedagogy,
        preseed_goal_brief=inferred_goal_brief,
    )

    add_decision_log(
        state,
        node="onboarding",
        action=action.get("action", "unknown"),
        reason=f"LLM decision (strategy={parse_result.strategy})",
        data={
            "parse_success": parse_result.success,
            "confidence": action.get("confidence"),
            "goal_status": (state.get("goal_brief") or {}).get("status"),
        },
    )

    logger.info(
        "[Onboarding] User %s: action=%s, parse_strategy=%s, goal_status=%s",
        user_id,
        action.get("action"),
        parse_result.strategy,
        (state.get("goal_brief") or {}).get("status"),
    )
    _record_onboarding_assistant_turn(state)
    return state


async def _apply_onboarding_action(
    state: AgentState,
    action: dict,
    pedagogy,
    *,
    preseed_goal_brief: Optional[dict[str, Any]] = None,
) -> AgentState:
    action_type = action.get("action", "")
    response_text = action.get("response_text", "")
    goal_brief = _filter_llm_goal_brief_extraction(state, extract_goal_brief_from_action(action))
    goal_value = extract_goal_from_action(action)
    inferred_goal_brief = preseed_goal_brief
    if inferred_goal_brief is None:
        routing_decision = await _prepare_goal_brief_turn_update(
            state,
            user_message=state.get("last_user_message", "") or "",
            cumulative_text=_collect_user_transcript(state),
        )
        inferred_goal_brief = routing_decision.goal_brief_update
    merged_goal_brief = _finalize_goal_brief_after_merge(
        _merge_goal_brief(state.get("goal_brief") or {}, goal_brief, inferred_goal_brief)
    )
    if not goal_value:
        goal_value = merged_goal_brief.get("primary_goal")

    state["pending_response"] = response_text
    state["needs_user_input"] = True
    state["current_phase"] = AgentPhase.ONBOARDING
    state["setup_step"] = "goal_setup"

    if action_type == "goal_confirmed":
        normalized_goal_brief = _apply_goal_brief_to_state(
            state,
            merged_goal_brief,
            goal_text=goal_value,
            confirmed=True,
        )
        state["goal_needs_confirmation"] = False
        agent_v2_goal_detection.labels(detected="true").inc()
        if pedagogy is not None:
            pedagogy.log_goal_confirmed(
                user_id=state["user_id"],
                goal=goal_value or normalized_goal_brief.get("primary_goal"),
                user_response=state.get("last_user_message", ""),
            )

    elif action_type == "confirm_goal":
        if goal_value or merged_goal_brief:
            if validate_confidence(action, "goal_detection"):
                normalized_goal_brief = _apply_goal_brief_to_state(
                    state,
                    merged_goal_brief,
                    goal_text=goal_value,
                    confirmed=False,
                )
                state["goal_needs_confirmation"] = not state["goal_setup_complete"]
                agent_v2_goal_detection.labels(detected="true").inc()
                if pedagogy is not None:
                    pedagogy.log_goal_detected(
                        user_id=state["user_id"],
                        message=state.get("last_user_message", ""),
                        goal=goal_value or normalized_goal_brief.get("primary_goal"),
                        confidence=action.get("confidence", 0.8),
                    )
            else:
                logger.info(
                    "[Onboarding] Goal confidence too low (%s), threshold is %s",
                    action.get("confidence", 0.5),
                    CONFIDENCE_THRESHOLDS["goal_detection"],
                )
                agent_v2_goal_detection.labels(detected="false").inc()

    elif action_type == "goal_skipped":
        normalized_goal_brief = _finalize_goal_brief_after_merge(
            _merge_goal_brief(state.get("goal_brief") or {}, inferred_goal_brief)
        )
        state["goal_brief"] = normalized_goal_brief
        state["goal_setup_complete"] = _is_goal_brief_routing_ready(normalized_goal_brief)
        state["goal_needs_confirmation"] = False
        if not state.get("detected_goal") and normalized_goal_brief.get("primary_goal"):
            state["detected_goal"] = normalized_goal_brief.get("primary_goal")
        if pedagogy is not None:
            pedagogy.log_goal_defaulted(
                user_id=state["user_id"],
                default_goal="goal_setup_retry",
                reason="User stayed vague, so onboarding kept a draft goal and asked for one concrete clarification",
            )

    elif action_type == "interests_confirmed":
        interests = extract_interests_from_action(action)
        if interests:
            state["confirmed_interests"] = interests
            if pedagogy is not None:
                pedagogy.log_interests_detected(
                    user_id=state["user_id"],
                    interests=interests,
                    source="llm_extraction",
                )

    elif action_type == "assessment_complete":
        level, scores = extract_assessment_from_action(action)
        if level:
            state["assessed_level"] = level
        if scores:
            state["assessment_scores"] = scores
        state["assessment_source"] = "explicit_assessment"
        if pedagogy is not None:
            pedagogy.log_level_assessed(
                user_id=state["user_id"],
                level=level or "B1",
                scores=scores or {},
                confidence=1.0,
            )

    elif action_type == "transition_to_learning":
        goal_setup_ready = state.get("goal_setup_complete") or _is_goal_brief_routing_ready(state.get("goal_brief") or {})
        state["goal_setup_complete"] = goal_setup_ready
        if not goal_setup_ready:
            state["pending_response"] = _build_goal_followup_question(
                state.get("goal_brief") or {},
                state.get("confirmed_goal") or state.get("detected_goal"),
            )
            state["last_question_type"] = "goal_setup"
            return state
        if not state.get("assessed_level"):
            if _should_run_explicit_assessment(state):
                _enter_assessment_phase(state)
                state["pending_response"] = _build_assessment_followup_question(state)
            else:
                _enter_first_useful_mission(state)
            return state
        state["current_phase"] = AgentPhase.LEARNING_SESSION
        state["setup_step"] = "ready_for_program"
        if pedagogy is not None:
            pedagogy.log_phase_transition(
                user_id=state["user_id"],
                from_phase="onboarding",
                to_phase="learning_session",
                reason="onboarding_complete",
            )
        return state

    if action_type in {"ask_goal", "confirm_goal", "goal_confirmed", "goal_skipped"}:
        if state.get("goal_setup_complete"):
            if not state.get("assessed_level"):
                if _should_run_explicit_assessment(state):
                    _enter_assessment_phase(state)
                    state["pending_response"] = _build_assessment_followup_question(state)
                else:
                    _enter_first_useful_mission(state)
            else:
                state["pending_response"] = "I have enough to keep building your program. Let's continue."
                state["setup_step"] = "ready_for_program"
        else:
            state["pending_response"] = _build_goal_followup_question(
                state.get("goal_brief") or {},
                state.get("confirmed_goal") or state.get("detected_goal") or goal_value,
            )
            state["last_question_type"] = "goal_setup"

    return state


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


def _build_template_context(state: AgentState) -> dict[str, Any]:
    return {
        "username": state.get("username", "Student"),
        "user_id": state.get("user_id"),
        "language_level": state.get("language_level", "B1"),
        "turn_count": state.get("turn_count", 0),
        "session_id": state.get("session_id", ""),
        "last_user_message": state.get("last_user_message", ""),
        "confirmed_goal": state.get("confirmed_goal"),
        "goal_brief": state.get("goal_brief") or {},
        "goal_setup_complete": state.get("goal_setup_complete", False),
        "detected_goal": state.get("detected_goal"),
        "goal_needs_confirmation": state.get("goal_needs_confirmation", False),
        "confirmed_interests": state.get("confirmed_interests", []),
        "assessed_level": state.get("assessed_level"),
        "assessment_scores": state.get("assessment_scores", {}),
        "conversation_history": state.get("conversation_history", []),
        "is_new_user": state.get("is_new_user", True),
    }


def _get_fallback_prompt(state: AgentState) -> str:
    username = state.get("username", "Student")
    goal_brief = state.get("goal_brief") or {}
    goal_setup_complete = state.get("goal_setup_complete", False)
    skip_goal = state.get("_skip_goal", False)
    skip_assessment = state.get("_skip_assessment", False)
    missing_goal_fields = goal_brief_missing_keys(goal_brief, mode="full")

    if not skip_goal and not goal_setup_complete:
        next_hint = {
            "primary_goal": "Synthesize a draft ML/AI career goal from noisy speech. If you hear job, abroad, ML, interview, project, or vocabulary signals, form a draft instead of asking a generic goal question again.",
            "target_role": "Ask what role they are aiming for, for example ML engineer, data scientist, or applied scientist.",
            "domain": "Ask which domain matters most for the program: machine learning, data science, or software engineering.",
            "main_contexts": "Ask which situations matter most right now: interviews, project walkthroughs, or workplace communication.",
            "target_market": "Ask what company context they target: western company, international startup, or global remote team.",
            "deadline_type": "Ask for the timeline: 1-3 months, 3-6 months, or open-ended.",
        }.get(missing_goal_fields[0] if missing_goal_fields else "primary_goal")
        return f"""You are English Friend, a proactive career-English coach for Russian-speaking ML/AI professionals.
Student: {username}

You are building a precise career-English goal brief.
{next_hint}
Never ask a broad question like "what is your goal?" if a plausible draft already exists.
If the student is passive, offer short forced-choice options.
Treat a routing-ready draft goal_brief as enough to move toward the first useful mission.
Use "goal_confirmed" only when the user clearly confirms the draft or clearly restates it.

Respond with JSON:
{{"action": "ask_goal" or "confirm_goal" or "goal_confirmed", "response_text": "your response", "confidence": 0.0, "extracted_data": {{"goal": "detected goal or null", "goal_brief": {{"primary_goal": "...", "target_role": "...", "domain": "...", "target_market": "...", "deadline_type": "...", "main_contexts": ["..."], "current_blockers": ["..."], "motivation": "...", "status": "incomplete or draft or confirmed"}}}}}}"""

    if not skip_assessment and not state.get("assessed_level"):
        return f"""You are English Friend.
Student: {username}, Goal: {state.get('confirmed_goal') or (goal_brief.get('primary_goal') if goal_brief else None)}, Level: {state.get('language_level', 'B1')}

Run a short baseline for a weak-to-mid English learner.
Ask exactly ONE short question per turn.
Use simple wording and allow short answers.
Prefer this sequence:
1. what do you do now
2. what role do you want
3. describe one ML or work project in simple words
If the learner already answered one of these, ask the next missing one.
Do not ask 2-3 questions in one message.
Do not sound like an exam.
After 2-3 useful answers, return assessment_complete with CEFR level and numeric scores for fluency, grammar, vocabulary, and comprehension.

Respond with JSON:
{{"action": "ask_assessment" or "assessment_complete", "response_text": "your response", "extracted_data": {{"assessed_level": "A1-C2", "assessment_scores": {{"fluency": 0.0, "grammar": 0.0, "vocabulary": 0.0, "comprehension": 0.0}}}}}}"""

    return f"""You are English Friend.
Student: {username}, Goal: {state.get('confirmed_goal') or (goal_brief.get('primary_goal') if goal_brief else None)}, Level: {state.get('assessed_level') or state.get('language_level', 'B1')}

Onboarding is complete. Give one short response that transitions into guided practice.

Respond with JSON:
{{"action": "transition_to_learning", "response_text": "your response"}}"""


def _record_onboarding_user_turn(state: AgentState, user_message: str) -> None:
    normalized_message = (user_message or "").strip()
    if not normalized_message:
        return
    state["turn_count"] = state.get("turn_count", 0) + 1
    history = list(state.get("conversation_history") or [])
    history.append({"role": "user", "content": normalized_message})
    state["conversation_history"] = history[-20:]


def _collect_user_transcript(
    state: AgentState,
    *,
    current_message: Optional[str] = None,
) -> str:
    """Concatenate user turns for cumulative context scoring."""
    parts: list[str] = []
    for entry in state.get("conversation_history") or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("role") or "").lower() != "user":
            continue
        content = str(entry.get("content") or "").strip()
        if content:
            parts.append(content)
    last_message = (current_message or state.get("last_user_message") or "").strip()
    if last_message and (not parts or parts[-1] != last_message):
        parts.append(last_message)
    return " \n ".join(parts)


def _record_onboarding_assistant_turn(state: AgentState) -> None:
    response_text = str(state.get("pending_response") or "").strip()
    if not response_text:
        return
    history = list(state.get("conversation_history") or [])
    if history and history[-1].get("role") == "assistant" and history[-1].get("content") == response_text:
        return
    history.append({"role": "assistant", "content": response_text})
    state["conversation_history"] = history[-20:]


def _mode_to_learning_mode(mode: Optional[str]) -> LearningModeEnum:
    if mode == "assessment":
        return LearningModeEnum.ASSESSMENT
    if mode == "mock_interview":
        return LearningModeEnum.MOCK_INTERVIEW
    if mode == "vocabulary_drill":
        return LearningModeEnum.VOCABULARY_DRILL
    if mode == "grammar_focus":
        return LearningModeEnum.GRAMMAR_FOCUS
    return LearningModeEnum.FREE_CONVERSATION


def _build_first_useful_mission_intro(mission: dict[str, Any]) -> str:
    task_type = str(mission.get("task_type") or "")
    if task_type == "technical_project_walkthrough":
        return (
            "Let's start with a real mission, not a separate baseline. "
            "Walk through one recent technical project: problem, approach, metric, and impact."
        )
    if task_type == "stakeholder_explanation_drill":
        return (
            "Let's start with a real mission, not a separate baseline. "
            "Explain your project to a non-technical stakeholder in simple English."
        )
    if task_type == "foundation_speaking_drill":
        return (
            "Let's start with a real mission. "
            "Tell me in simple English what you do now and what speaking skill feels weakest."
        )
    fallback_title = mission.get("title") or "today's drill"
    fallback_signal = mission.get("success_signal") or "Give me one short answer in English to begin."
    return (
        f"Let's start with a real mission: {fallback_title}. "
        f"{fallback_signal}"
    )


def _enter_first_useful_mission(state: AgentState) -> None:
    roadmap = state.get("roadmap") or {}
    goal_brief = _coerce_goal_brief_state(state.get("goal_brief") or {})
    state["goal_brief"] = goal_brief
    mission = recommend_next_mission(
        goal_brief=goal_brief,
        program_plan=(roadmap or {}).get("program_plan"),
        due_count=int(state.get("due_vocabulary_count", 0) or 0),
        error_patterns=list((roadmap or {}).get("error_patterns") or []),
        has_assessment=False,
        interview_pack=(roadmap or {}).get("interview_pack"),
        session_evidence=list((roadmap or {}).get("session_evidence") or []),
        interview_runs_count=len((roadmap or {}).get("interview_runs") or []),
    )

    launch_mode = mission.get("launch_mode") or mission.get("mode")
    state["mission_task_type"] = mission.get("task_type")
    state["mission_title"] = mission.get("title")
    state["mission_reason"] = mission.get("reason")
    state["mission_success_signal"] = mission.get("success_signal")
    state["mission_linked_goal_context"] = mission.get("linked_goal_context")
    state["interview_track_id"] = mission.get("interview_track_id")
    state["current_mode"] = _mode_to_learning_mode(str(launch_mode or "free_conversation"))
    state["current_phase"] = AgentPhase.LEARNING_SESSION
    state["setup_step"] = "first_useful_mission"
    state["last_question_type"] = "first_mission_handoff"
    state["_skip_assessment"] = True
    state["anchor_question_id"] = 0
    state["anchor_follow_up_pending"] = False
    state["pending_response"] = _build_first_useful_mission_intro(mission)
    state["needs_user_input"] = True


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


def route_after_onboarding(state: AgentState) -> str:
    if state.get("should_end_session"):
        return "session_end"
    if state.get("last_question_type") == "first_mission_handoff":
        return "wait_for_input"
    if state.get("current_phase", AgentPhase.ONBOARDING) == AgentPhase.LEARNING_SESSION:
        return "learning"
    if state.get("needs_user_input", True):
        return "wait_for_input"
    return "wait_for_input"


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


def _update_shadow_intent(state: AgentState, user_message: str) -> None:
    if not (user_message or "").strip():
        state["last_intent"] = None
        return
    result = classify_intent(user_message, build_intent_context_from_state(state))
    state["last_intent"] = result.to_payload(
        policy_action=shadow_policy_action_for_intent(result.type),
        shadow_mode=True,
    )


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
