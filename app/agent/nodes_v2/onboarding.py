"""Onboarding Node - Unified LLM-driven onboarding flow.

Handles:
- Goal discovery and confirmation
- Interest extraction
- Quick assessment

The product uses a hard guided onboarding flow:
- noisy speech should still produce a draft career goal
- a routing-ready draft is enough to move to baseline assessment
- onboarding prompt is code-owned to avoid drift from stale DB templates
"""

import logging
import re
import time
from typing import Any, Optional

from app.agent.guardrails import (
    CONFIDENCE_THRESHOLDS,
    validate_and_sanitize,
    validate_confidence,
)
from app.agent.response_parser import (
    extract_assessment_from_action,
    extract_goal_brief_from_action,
    extract_goal_from_action,
    extract_interests_from_action,
    parse_llm_response,
)
from app.agent.state import AgentPhase, AgentState, add_decision_log
from app.core.metrics import (
    agent_guardrail_fallbacks,
    agent_v2_goal_detection,
    agent_v2_llm_latency,
    agent_v2_parse_success,
)
from app.services.ai.llm_provider import get_llm_provider
from app.services.pedagogy_logger import get_pedagogy_logger
from app.services.prompt_service import get_prompt_service

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
_INTERVIEW_SIGNAL_PATTERNS = (
    "interview",
    "interviews",
    "mock interview",
    "hr interview",
)
_PROJECT_SIGNAL_PATTERNS = (
    "project",
    "projects",
    "architecture",
    "system design",
    "tradeoff",
    "trade off",
    "explain",
)
_WORKPLACE_SIGNAL_PATTERNS = (
    "team",
    "meeting",
    "standup",
    "manager",
    "stakeholder",
    "workplace",
)
_VOCAB_SIGNAL_PATTERNS = (
    "vocabulary",
    "words",
    "terminology",
)


async def onboarding_node(state: AgentState) -> AgentState:
    """Unified onboarding: goal discovery + interests + assessment."""
    pedagogy = get_pedagogy_logger(state["user_id"])
    prompt_service = get_prompt_service()
    llm = get_llm_provider()

    user_message = state.get("last_user_message", "") or ""
    user_id = state["user_id"]
    session_id = state.get("session_id", "")

    # Pre-seed state with a draft goal from noisy speech before the LLM sees it.
    inferred_goal_brief = _infer_goal_brief_from_message(user_message, state.get("goal_brief") or {})
    if inferred_goal_brief:
        normalized_goal_brief = _merge_goal_brief(state.get("goal_brief") or {}, inferred_goal_brief)
        state["goal_brief"] = normalized_goal_brief
        state["goal_setup_complete"] = _is_goal_brief_routing_ready(normalized_goal_brief)
        if not state.get("detected_goal"):
            state["detected_goal"] = normalized_goal_brief.get("primary_goal")

    rendered_prompt = _get_fallback_prompt(state)
    template = None

    start_time = time.time()
    try:
        response = await llm.generate(
            user_message=user_message,
            system_prompt=rendered_prompt,
            max_tokens=500,
        )
        latency_ms = int((time.time() - start_time) * 1000)
        agent_v2_llm_latency.labels(node="onboarding").observe(latency_ms / 1000)
    except Exception as exc:
        logger.error("[Onboarding] LLM error: %s", exc)
        state["pending_response"] = "I'm having trouble right now. Could you repeat that?"
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
    return state


async def _apply_onboarding_action(
    state: AgentState,
    action: dict,
    pedagogy,
) -> AgentState:
    action_type = action.get("action", "")
    response_text = action.get("response_text", "")
    goal_brief = extract_goal_brief_from_action(action)
    goal_value = extract_goal_from_action(action)
    inferred_goal_brief = _infer_goal_brief_from_message(
        state.get("last_user_message", ""),
        state.get("goal_brief") or {},
    )
    merged_goal_brief = _merge_goal_brief(state.get("goal_brief") or {}, goal_brief, inferred_goal_brief)
    if not goal_value:
        goal_value = merged_goal_brief.get("primary_goal")

    state["pending_response"] = response_text
    state["needs_user_input"] = True
    state["current_phase"] = AgentPhase.ONBOARDING

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
            return state
        if not state.get("assessed_level") and not state.get("_skip_assessment", False):
            state["pending_response"] = _build_assessment_followup_question(state)
            return state
        state["current_phase"] = AgentPhase.LEARNING_SESSION
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
            if not state.get("assessed_level") and not state.get("_skip_assessment", False):
                state["pending_response"] = _build_assessment_followup_question(state)
            else:
                state["pending_response"] = "I have enough to keep building your program. Let's continue."
        else:
            state["pending_response"] = _build_goal_followup_question(
                state.get("goal_brief") or {},
                state.get("confirmed_goal") or state.get("detected_goal") or goal_value,
            )

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
            "I can move to your baseline now unless you want to correct the draft."
        )

    first_missing = missing[0]
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
    goal_brief = state.get("goal_brief") or {}
    target_role = goal_brief.get("target_role") or "your target role"
    contexts = ", ".join(item.replace("_", " ") for item in (goal_brief.get("main_contexts") or [])[:2])
    if goal_brief.get("status") == "draft":
        return (
            f"I have a draft target for {target_role}"
            f"{f' focused on {contexts}' if contexts else ''}. "
            "I will use that draft unless you correct it later. One quick baseline first: "
            "answer in English - what do you do now, what role are you aiming for, and why?"
        )
    return (
        f"Before I build the program for {target_role}, I need a quick speaking baseline. "
        "Answer in English: what do you do now, what kind of role are you aiming for, and why?"
    )


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
Treat a routing-ready draft goal_brief as enough to move toward baseline assessment.
Use "goal_confirmed" only when the user clearly confirms the draft or clearly restates it.

Respond with JSON:
{{"action": "ask_goal" or "confirm_goal" or "goal_confirmed", "response_text": "your response", "confidence": 0.0, "extracted_data": {{"goal": "detected goal or null", "goal_brief": {{"primary_goal": "...", "target_role": "...", "domain": "...", "target_market": "...", "deadline_type": "...", "main_contexts": ["..."], "current_blockers": ["..."], "motivation": "...", "status": "incomplete or draft or confirmed"}}}}}}"""

    if not skip_assessment and not state.get("assessed_level"):
        return f"""You are English Friend.
Student: {username}, Goal: {state.get('confirmed_goal') or (goal_brief.get('primary_goal') if goal_brief else None)}, Level: {state.get('language_level', 'B1')}

Ask 2-3 questions to assess their English level for the target job context. Start simple, then increase difficulty.
Return both the CEFR level and numeric scores for fluency, grammar, vocabulary, and comprehension.

Respond with JSON:
{{"action": "ask_assessment" or "assessment_complete", "response_text": "your response", "extracted_data": {{"assessed_level": "A1-C2", "assessment_scores": {{"fluency": 0.0, "grammar": 0.0, "vocabulary": 0.0, "comprehension": 0.0}}}}}}"""

    return f"""You are English Friend.
Student: {username}, Goal: {state.get('confirmed_goal') or (goal_brief.get('primary_goal') if goal_brief else None)}, Level: {state.get('assessed_level') or state.get('language_level', 'B1')}

Onboarding is complete. Give one short response that transitions into guided practice.

Respond with JSON:
{{"action": "transition_to_learning", "response_text": "your response"}}"""


def route_after_onboarding(state: AgentState) -> str:
    if state.get("should_end_session"):
        return "session_end"
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


def _has_any_signal(message: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in message for pattern in patterns)


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
) -> Optional[dict[str, Any]]:
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
        inferred["main_contexts"] = _dedupe_text(contexts)
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
) -> dict[str, Any]:
    merged = dict(existing_goal_brief or {})
    for update in updates:
        if not update:
            continue
        for key, value in update.items():
            if value in (None, "", []):
                continue
            merged[key] = value
    if confirmed or merged.get("status") == "confirmed" or merged.get("confirmed_by_user"):
        merged["confirmed_by_user"] = True
    return _coerce_goal_brief_state(merged)


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
