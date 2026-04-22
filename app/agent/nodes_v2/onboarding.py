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
import re
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
from app.core.metrics import (
    agent_guardrail_fallbacks,
    agent_v2_goal_detection,
    agent_v2_llm_latency,
    agent_v2_parse_success,
)
from app.services.ai.llm_provider import LLMEmptyContentError, get_llm_provider
from app.services.pedagogy_logger import get_pedagogy_logger
from app.services.prompt_service import get_prompt_service
from app.services.program_snapshot_service import recommend_next_mission
from app.services.routing.goal_routing import (
    INTERVIEW_SIGNAL_PATTERNS as _ROUTING_INTERVIEW_PATTERNS,
    PROJECT_SIGNAL_PATTERNS as _ROUTING_PROJECT_PATTERNS,
    WORKPLACE_SIGNAL_PATTERNS as _ROUTING_WORKPLACE_PATTERNS,
    score_context_signals,
)

logger = logging.getLogger(__name__)

_ML_SIGNAL_PATTERNS = (
    "machine learning",
    "ml",
    "artificial intelligence",
    " ai ",
    "model",
    "models",
    "dataset",
    "feature engineering",
    "neural",
)
_JOB_SIGNAL_PATTERNS = (
    "job",
    "work",
    "career",
    "abroad",
    "international",
    "western",
    "remote",
    "company",
)
# Canonical signal patterns live in app.services.routing.goal_routing so the
# onboarding layer and the snapshot/mission layer agree on primary context.
_INTERVIEW_SIGNAL_PATTERNS = _ROUTING_INTERVIEW_PATTERNS
_PROJECT_SIGNAL_PATTERNS = _ROUTING_PROJECT_PATTERNS
_WORKPLACE_SIGNAL_PATTERNS = _ROUTING_WORKPLACE_PATTERNS
_VOCAB_SIGNAL_PATTERNS = (
    "vocabulary",
    "words",
    "terminology",
)
_FLEXIBLE_COMPANY_CONTEXT_PATTERNS = (
    "doesnt matter",
    "does not matter",
    "dont care",
    "do not care",
    "whatever",
    "any company",
    "no matter",
)
_CORRECTION_CUE_PATTERNS = (
    "actually",
    "instead",
    "change it",
    "change the draft",
    "change my goal",
    "not interviews",
    "not interview",
    "not project",
    "not project walkthrough",
    "not workplace",
    "not workplace communication",
    "rather than",
    "instead of",
)
_CONTEXT_NEGATION_PATTERNS: dict[str, tuple[str, ...]] = {
    "interviews": (
        "not interview",
        "not interviews",
        "instead of interview",
        "instead of interviews",
    ),
    "project_walkthrough": (
        "not project",
        "not projects",
        "not project walkthrough",
        "instead of project",
        "instead of projects",
    ),
    "workplace_communication": (
        "not workplace",
        "not workplace communication",
        "not team meetings",
        "instead of workplace",
        "instead of team meetings",
    ),
}
_ROLE_DOMAIN_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("applied scientist", "Applied Scientist", "machine_learning"),
    ("research scientist", "Research Scientist", "machine_learning"),
    ("data scientist", "Data Scientist", "data_science"),
    ("data science", "Data Scientist", "data_science"),
    ("backend engineer", "Backend Engineer", "software_engineering"),
    ("frontend engineer", "Frontend Engineer", "software_engineering"),
    ("software engineer", "Software Engineer", "software_engineering"),
    ("machine learning engineer", "ML Engineer", "machine_learning"),
    ("ml engineer", "ML Engineer", "machine_learning"),
    ("ai engineer", "ML Engineer", "machine_learning"),
)
_PROCEED_PATTERNS = (
    "let's go",
    "lets go",
    "go on",
    "continue",
    "prepare my program",
    "build my program",
    "waiting that you",
    "just tell",
    "start now",
)
_LOW_SIGNAL_PATTERNS = (
    "i don't know",
    "i dont know",
    "my english is weak",
    "my english is bad",
    "hard for me",
    "i cannot say",
)
_BASELINE_PROMPTS: list[tuple[str, str]] = [
    ("current_role", "What do you do now? You can answer in simple English or mixed Russian and English."),
    ("target_role", "What role do you want next: ML engineer, data scientist, or software engineer?"),
    ("project_task", "Tell me about one ML or work task in simple words."),
]
_ASSESSMENT_FILLER_TOKENS = {
    "a",
    "ah",
    "an",
    "and",
    "as",
    "at",
    "eh",
    "erm",
    "hmm",
    "i",
    "im",
    "is",
    "just",
    "let",
    "lets",
    "like",
    "mean",
    "mm",
    "my",
    "no",
    "now",
    "of",
    "ok",
    "okay",
    "please",
    "say",
    "sorry",
    "test",
    "the",
    "to",
    "uh",
    "um",
    "well",
    "yeah",
    "yes",
    "you",
    "your",
}
_ASSESSMENT_NUMBER_WORDS = {
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
}
_CURRENT_ROLE_PATTERNS = (
    "i work",
    "i am",
    "my role",
    "data analyst",
    "data scientist",
    "ml engineer",
    "engineer",
    "scientist",
    "analyst",
    "developer",
    "researcher",
    "manager",
    "intern",
    "build",
    "built",
    "working on",
)
_NO_CURRENT_ROLE_PATTERNS = (
    "dont work now",
    "don't work now",
    "don t work now",
    "not working now",
    "i am not working",
    "im not working",
    "between jobs",
    "looking for my first role",
    "student now",
)
_TARGET_ROLE_PATTERNS = (
    "ml engineer",
    "machine learning engineer",
    "data scientist",
    "software engineer",
    "backend engineer",
    "frontend engineer",
    "developer",
    "scientist",
    "engineer",
    "analyst",
)
_PROJECT_TASK_PATTERNS = (
    "project",
    "task",
    "model",
    "models",
    "prediction",
    "recommendation",
    "recommender",
    "churn",
    "fraud",
    "pipeline",
    "dataset",
    "feature",
    "classification",
    "training",
    "recall",
    "precision",
    "e commerce",
    "ecommerce",
)
_FUTURE_ROLE_PATTERNS = (
    "want",
    "want to",
    "want next",
    "next role",
    "become",
    "looking for",
    "job abroad",
    "role abroad",
)
_ASSESSMENT_AFFIRMATION_PREFIX_RE = re.compile(r"^(yes|yeah|yep|ok|okay|sure)\b[\s,:.-]*")


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

    # Pre-seed state with a draft goal from noisy speech before the LLM sees it.
    goal_became_routing_ready_this_turn = False
    inferred_goal_brief = _filter_goal_brief_update_for_turn(
        state,
        _infer_goal_brief_from_message(
            user_message,
            state.get("goal_brief") or {},
            cumulative_text=_collect_user_transcript(state, current_message=user_message),
        ),
    )
    if inferred_goal_brief:
        normalized_goal_brief = _merge_goal_brief(state.get("goal_brief") or {}, inferred_goal_brief)
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
            normalized_goal_brief = _merge_goal_brief(state.get("goal_brief") or {}, inferred_goal_brief)
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

    state = await _apply_onboarding_action(state, action, pedagogy)

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
) -> AgentState:
    action_type = action.get("action", "")
    response_text = action.get("response_text", "")
    goal_brief = _filter_llm_goal_brief_extraction(state, extract_goal_brief_from_action(action))
    goal_value = extract_goal_from_action(action)
    inferred_goal_brief = _filter_goal_brief_update_for_turn(
        state,
        _infer_goal_brief_from_message(
            state.get("last_user_message", ""),
            state.get("goal_brief") or {},
            cumulative_text=_collect_user_transcript(state),
        ),
    )
    merged_goal_brief = _merge_goal_brief(state.get("goal_brief") or {}, goal_brief, inferred_goal_brief)
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
        normalized_goal_brief = _merge_goal_brief(state.get("goal_brief") or {}, inferred_goal_brief)
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
    required = {
        "primary_goal": "goal",
        "target_role": "target role",
        "domain": "domain",
        "target_market": "company context",
        "deadline_type": "timeline",
        "main_contexts": "practice context",
    }
    missing: list[str] = []
    for key, label in required.items():
        if not goal_brief.get(key):
            missing.append(label)
    return missing


def _is_goal_brief_routing_ready(goal_brief: dict[str, Any]) -> bool:
    contexts = goal_brief.get("main_contexts") or []
    return bool(
        goal_brief.get("primary_goal")
        and goal_brief.get("target_role")
        and goal_brief.get("domain")
        and goal_brief.get("target_market")
        and contexts
        and "general_fluency" not in contexts
    )


def _coerce_goal_brief_state(goal_brief: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(goal_brief)
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


def _build_assessment_followup_question(state: AgentState) -> str:
    question_key, question_text = _get_current_baseline_prompt(state)
    goal_brief = state.get("goal_brief") or {}
    target_role = goal_brief.get("target_role") or "your target role"
    contexts = ", ".join(item.replace("_", " ") for item in (goal_brief.get("main_contexts") or [])[:2])
    state["last_question_type"] = question_key
    state["setup_step"] = "baseline_assessment"
    state["current_mode"] = LearningModeEnum.ASSESSMENT
    state["current_phase"] = AgentPhase.ASSESSMENT
    if state.get("assessment_step_index", 0) <= 0:
        if goal_brief.get("status") == "draft":
            return (
                f"I have a draft target for {target_role}"
                f"{f' focused on {contexts}' if contexts else ''}. "
                "I will use that draft unless you correct it later. One quick baseline first. "
                f"{question_text}"
            )
        return (
            f"Before I build the program for {target_role}, I need one short speaking baseline. "
            f"{question_text}"
        )
    return question_text


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
    missing_goal_fields = [
        name
        for name in ["primary_goal", "target_role", "domain", "target_market", "deadline_type", "main_contexts"]
        if not goal_brief.get(name)
    ]

    if not skip_goal and not goal_setup_complete:
        next_hint = {
            "primary_goal": "Synthesize a draft ML/AI career goal from noisy speech. If you hear job, abroad, ML, interview, project, or vocabulary signals, form a draft instead of asking a generic goal question again.",
            "target_role": "Ask what role they are aiming for, for example ML engineer, data scientist, or applied scientist.",
            "domain": "Ask which domain matters most for the program: machine learning, data science, or software engineering.",
            "target_market": "Ask what company context they target: western company, international startup, or global remote team.",
            "deadline_type": "Ask for the timeline: 1-3 months, 3-6 months, or open-ended.",
            "main_contexts": "Ask which situations matter most right now: interviews, project walkthroughs, or workplace communication.",
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


def _should_run_explicit_assessment(state: AgentState) -> bool:
    if state.get("mission_task_type") == "baseline_assessment":
        return True
    if state.get("setup_step") == "baseline_assessment" and not state.get("_skip_assessment", False):
        return True
    if state.get("current_phase") == AgentPhase.ASSESSMENT and not state.get("_skip_assessment", False):
        return True
    return state.get("current_mode") == LearningModeEnum.ASSESSMENT and not state.get("_skip_assessment", False)


def _enter_assessment_phase(state: AgentState) -> None:
    state["setup_step"] = "baseline_assessment"
    state["current_mode"] = LearningModeEnum.ASSESSMENT
    state["current_phase"] = AgentPhase.ASSESSMENT


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


def _get_active_assessment_key(state: AgentState) -> Optional[str]:
    if not state.get("goal_setup_complete"):
        return None
    if state.get("assessed_level") or state.get("_skip_assessment", False):
        return None
    current_phase = state.get("current_phase")
    current_mode = state.get("current_mode")
    if current_phase not in {None, AgentPhase.ASSESSMENT, AgentPhase.ONBOARDING}:
        return None
    if current_mode not in {None, LearningModeEnum.ASSESSMENT}:
        return None
    return _get_current_baseline_prompt(state)[0]


def _get_current_baseline_prompt(state: AgentState) -> tuple[str, str]:
    index = min(state.get("assessment_step_index", 0), len(_BASELINE_PROMPTS) - 1)
    return _BASELINE_PROMPTS[index]


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


def _is_meta_progress_message(message: str) -> bool:
    normalized = _normalize_user_message(message)
    return _has_any_signal(normalized, _PROCEED_PATTERNS) or _has_any_signal(normalized, _LOW_SIGNAL_PATTERNS)


def _extract_assessment_content_tokens(message: str) -> list[str]:
    normalized = _normalize_assessment_answer(message).strip()
    if not normalized:
        return []
    tokens = [word for word in normalized.split() if word]
    return [
        token
        for token in tokens
        if token not in _ASSESSMENT_FILLER_TOKENS
        and token not in _ASSESSMENT_NUMBER_WORDS
        and not token.isdigit()
    ]


def _is_low_signal_assessment_answer(
    message: str,
    question_key: str,
    state: AgentState,
) -> bool:
    normalized = _normalize_assessment_answer(message).strip()
    if not normalized:
        return True

    content_tokens = _extract_assessment_content_tokens(normalized)
    if len(content_tokens) < 2:
        return True

    goal_role = str((state.get("goal_brief") or {}).get("target_role") or "").lower()

    if question_key == "target_role":
        role_patterns = list(_TARGET_ROLE_PATTERNS)
        if goal_role:
            role_patterns.append(goal_role)
        return not any(pattern in normalized for pattern in role_patterns)

    if question_key == "current_role":
        no_current_role_signal = any(pattern in normalized for pattern in _NO_CURRENT_ROLE_PATTERNS)
        current_role_signal = any(pattern in normalized for pattern in _CURRENT_ROLE_PATTERNS)
        future_role_signal = any(pattern in normalized for pattern in _FUTURE_ROLE_PATTERNS)
        content_tokens = _extract_assessment_content_tokens(normalized)
        compact_role_label = len(content_tokens) <= 2
        if no_current_role_signal:
            return False
        if current_role_signal and not future_role_signal and not compact_role_label:
            return False
        return True

    words = [word for word in normalized.split() if word]
    filler_ratio = 1.0 - (len(content_tokens) / max(len(words), 1))
    if filler_ratio > 0.55 and len(content_tokens) < 4:
        return True

    if question_key == "project_task":
        return not (
            any(pattern in normalized for pattern in _PROJECT_TASK_PATTERNS)
            or _has_any_signal(normalized, _ML_SIGNAL_PATTERNS)
        )

    return len(content_tokens) < 3


def _is_usable_baseline_answer(
    message: str,
    question_key: str,
    state: AgentState,
) -> bool:
    normalized = _normalize_assessment_answer(message).strip()
    if not normalized:
        return False
    if _is_meta_progress_message(normalized):
        return False
    return not _is_low_signal_assessment_answer(normalized, question_key, state)


def _build_low_signal_assessment_response(
    state: AgentState,
    question_key: str,
) -> str:
    streak = int(state.get("low_signal_turn_streak", 0) or 0)
    if question_key == "target_role":
        base = "I did not catch the target role. Choose one short answer: ML engineer, data scientist, or software engineer."
    elif question_key == "project_task":
        base = (
            "I did not catch the project answer clearly. Say one short example, for example: "
            "churn prediction for e-commerce."
        )
    else:
        base = (
            "I did not catch your current work clearly. Say one short sentence, for example: "
            "I work as a data analyst."
        )

    if streak >= 3:
        return f"{base} Speech recognition is still noisy, so type the key words in the composer and send them."
    if streak >= 2:
        return f"{base} If speech recognition is weak, type the key words in the composer."
    return base


def _store_baseline_answer(state: AgentState, key: str, value: str) -> None:
    answers = dict(state.get("assessment_answers") or {})
    answers[key] = value.strip()
    state["assessment_answers"] = answers


def _usable_baseline_answer_count(state: AgentState) -> int:
    return len(
        [
            value
            for value in (state.get("assessment_answers") or {}).values()
            if isinstance(value, str) and value.strip()
        ]
    )


def _infer_level_from_baseline(state: AgentState) -> tuple[str, dict[str, float], bool, float]:
    answers = state.get("assessment_answers") or {}
    combined = " ".join(value for value in answers.values() if isinstance(value, str))
    token_count = len(combined.split())
    has_ml_signal = _has_any_signal(_normalize_user_message(combined), _ML_SIGNAL_PATTERNS)
    answer_count = _usable_baseline_answer_count(state)

    if token_count < 10:
        level = "A2"
        fluency = 3.8
        grammar = 3.9
        vocabulary = 4.1
        comprehension = 4.4
    elif token_count < 28:
        level = "B1"
        fluency = 4.8
        grammar = 4.6
        vocabulary = 5.0
        comprehension = 5.1
    else:
        level = "B1"
        fluency = 5.5
        grammar = 5.1
        vocabulary = 5.6
        comprehension = 5.6

    if has_ml_signal:
        vocabulary += 0.4
    provisional = answer_count < 3 or token_count < 18
    confidence = 0.42 if provisional else 0.68
    scores = {
        "fluency": round(min(fluency, 9.5), 1),
        "grammar": round(min(grammar, 9.5), 1),
        "vocabulary": round(min(vocabulary, 9.5), 1),
        "comprehension": round(min(comprehension, 9.5), 1),
    }
    return level, scores, provisional, confidence


def _complete_baseline_assessment(state: AgentState) -> None:
    level, scores, provisional, confidence = _infer_level_from_baseline(state)
    goal_brief = state.get("goal_brief") or {}
    role = goal_brief.get("target_role") or "your target role"
    qualifier = "provisional" if provisional else "first"
    state["assessed_level"] = level
    state["assessment_scores"] = scores
    state["assessment_status"] = "provisional" if provisional else "confirmed"
    state["baseline_provisional"] = provisional
    state["baseline_confidence"] = confidence
    state["level_confidence"] = confidence
    state["assessment_source"] = "explicit_assessment"
    state["setup_step"] = "ready_for_program"
    state["last_question_type"] = "baseline_complete"
    state["session_complete_reason"] = "baseline_complete"
    state["session_complete_return_screen"] = "home"
    state["pending_response"] = (
        f"I have enough for a {qualifier} baseline for {role}. "
        f"Current level looks around {level}. Your first mission is ready on the dashboard."
    )


def _advance_baseline_prompt(state: AgentState) -> str:
    state["assessment_step_index"] = min(state.get("assessment_step_index", 0) + 1, len(_BASELINE_PROMPTS) - 1)
    next_key, next_prompt = _get_current_baseline_prompt(state)
    state["last_question_type"] = next_key
    return next_prompt


async def _handle_assessment_turn(state: AgentState, pedagogy) -> AgentState:
    _enter_assessment_phase(state)
    user_message = str(state.get("last_user_message") or "").strip()
    current_key, current_prompt = _get_current_baseline_prompt(state)

    if not user_message:
        state["pending_response"] = _build_assessment_followup_question(state)
        state["needs_user_input"] = True
        return state

    meta_progress = _is_meta_progress_message(user_message)

    if _is_usable_baseline_answer(user_message, current_key, state):
        _store_baseline_answer(state, current_key, user_message)
        state["low_signal_turn_streak"] = 0
    elif current_key == "target_role":
        role = (state.get("goal_brief") or {}).get("target_role")
        if role:
            _store_baseline_answer(state, current_key, role)
            state["low_signal_turn_streak"] = 0
    elif not meta_progress and _is_low_signal_assessment_answer(user_message, current_key, state):
        state["low_signal_turn_streak"] = int(state.get("low_signal_turn_streak", 0) or 0) + 1
        state["pending_response"] = _build_low_signal_assessment_response(state, current_key)
        state["last_question_type"] = current_key
        state["needs_user_input"] = True
        return state
    else:
        state["low_signal_turn_streak"] = 0

    usable_answers = _usable_baseline_answer_count(state)
    reached_last_question = state.get("assessment_step_index", 0) >= len(_BASELINE_PROMPTS) - 1

    if usable_answers >= 3:
        _complete_baseline_assessment(state)
    elif usable_answers >= 2 and (meta_progress or reached_last_question):
        _complete_baseline_assessment(state)
    elif meta_progress and usable_answers >= 1:
        bridge = "OK, I am already building the program. One more short answer for the baseline."
        state["pending_response"] = f"{bridge} {_advance_baseline_prompt(state)}"
        state["needs_user_input"] = True
        return state
    else:
        if _is_usable_baseline_answer(user_message, current_key, state) or meta_progress:
            next_prompt = _advance_baseline_prompt(state)
            state["pending_response"] = next_prompt
            state["needs_user_input"] = True
            return state
        else:
            state["pending_response"] = (
                "It is OK to answer in simple English or mixed Russian and English. "
                f"{current_prompt}"
            )
            state["last_question_type"] = current_key
            state["needs_user_input"] = True
            return state

    if pedagogy is not None and state.get("assessed_level"):
        pedagogy.log_level_assessed(
            user_id=state["user_id"],
            level=state.get("assessed_level") or "B1",
            scores=state.get("assessment_scores") or {},
            confidence=state.get("baseline_confidence") or 0.5,
        )
    state["needs_user_input"] = True
    return state


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


def _normalize_user_message(message: Optional[str]) -> str:
    source = (message or "").lower().replace("-", " ")
    normalized = f" {source} "
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
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


def _has_explicit_goal_correction_signal(message: str) -> bool:
    return _has_any_signal(message, _CORRECTION_CUE_PATTERNS)


def _negated_contexts_from_message(normalized_message: str) -> set[str]:
    negated: set[str] = set()
    for context, patterns in _CONTEXT_NEGATION_PATTERNS.items():
        if _has_any_signal(normalized_message, patterns):
            negated.add(context)
    return negated


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
    context_scores = score_context_signals(normalized_message)
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


def _has_any_signal(message: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in message for pattern in patterns)


def _count_signal_hits(message: str, patterns: tuple[str, ...]) -> int:
    return sum(1 for pattern in patterns if pattern in message)


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

    existing = dict(existing_goal_brief or {})
    inferred = dict(existing)
    signal_count = 0

    if _has_any_signal(normalized_message, _ML_SIGNAL_PATTERNS):
        signal_count += 1
        inferred.setdefault("target_role", "ML Engineer")
        inferred.setdefault("domain", "machine_learning")

    if _has_any_signal(normalized_message, _JOB_SIGNAL_PATTERNS):
        signal_count += 1
        inferred.setdefault("target_market", "international_company")
    elif _has_any_signal(normalized_message, _FLEXIBLE_COMPANY_CONTEXT_PATTERNS):
        signal_count += 1
        inferred.setdefault("target_market", "international_company")

    contexts = list(inferred.get("main_contexts") or [])
    if _has_any_signal(normalized_message, _INTERVIEW_SIGNAL_PATTERNS):
        signal_count += 1
        contexts.append("interviews")
    if _has_any_signal(normalized_message, _PROJECT_SIGNAL_PATTERNS):
        signal_count += 1
        contexts.append("project_walkthrough")
    if _has_any_signal(normalized_message, _WORKPLACE_SIGNAL_PATTERNS):
        signal_count += 1
        contexts.append("workplace_communication")
    if _has_any_signal(normalized_message, _VOCAB_SIGNAL_PATTERNS):
        signal_count += 1
        blockers = list(inferred.get("current_blockers") or [])
        blockers.append("Need stronger ML and interview vocabulary")
        inferred["current_blockers"] = blockers

    if signal_count < 2 and not _is_goal_brief_routing_ready(existing):
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
        if _has_any_signal(normalized_message, _INTERVIEW_SIGNAL_PATTERNS):
            blockers.append("Need structured interview answers under pressure")
        if _has_any_signal(normalized_message, _JOB_SIGNAL_PATTERNS):
            blockers.append("Need confident English for international job opportunities")
        inferred["current_blockers"] = blockers

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
    normalized_goal_brief = _merge_goal_brief(
        state.get("goal_brief") or {},
        goal_brief,
        confirmed=confirmed,
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
