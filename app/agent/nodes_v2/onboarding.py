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
from app.services.goal_brief_contract import goal_brief_missing_keys
from app.services.ai.llm_provider import LLMEmptyContentError, get_llm_provider
from app.services.onboarding.turn_analyzer import analyze_onboarding_turn
from app.services.pedagogy_logger import get_pedagogy_logger
from app.services.prompt_service import get_prompt_service
from app.services.program_snapshot_service import recommend_next_mission
from app.services.routing.goal_routing import resolve_scope_status
from app.agent.nodes_v2.onboarding_assessment import (
    _build_assessment_followup_question,
    _enter_assessment_phase,
    _handle_assessment_turn,
    _should_run_explicit_assessment,
)
from app.agent.nodes_v2.onboarding_goal_brief import (
    _apply_explicit_goal_correction,
    _apply_goal_brief_to_state,
    _apply_scope_gate_response,
    _apply_turn_analysis_followup_if_needed,
    _build_goal_followup_question,
    _coerce_goal_brief_state,
    _filter_llm_goal_brief_extraction,
    _finalize_goal_brief_after_merge,
    _infer_goal_brief_correction_from_message,
    _infer_goal_brief_from_message,
    _is_goal_brief_routing_ready,
    _merge_goal_brief,
    _prepare_goal_brief_turn_update,
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


def _update_shadow_intent(state: AgentState, user_message: str) -> None:
    if not (user_message or "").strip():
        state["last_intent"] = None
        return
    result = classify_intent(user_message, build_intent_context_from_state(state))
    state["last_intent"] = result.to_payload(
        policy_action=shadow_policy_action_for_intent(result.type),
        shadow_mode=True,
    )
