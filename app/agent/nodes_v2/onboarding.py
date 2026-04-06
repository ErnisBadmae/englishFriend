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
_FLEXIBLE_COMPANY_CONTEXT_PATTERNS = (
    "doesnt matter",
    "does not matter",
    "dont care",
    "do not care",
    "whatever",
    "any company",
    "no matter",
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


async def onboarding_node(state: AgentState) -> AgentState:
    """Unified onboarding: goal discovery + interests + assessment."""
    pedagogy = get_pedagogy_logger(state["user_id"])
    prompt_service = get_prompt_service()
    llm = get_llm_provider()

    user_message = state.get("last_user_message", "") or ""
    user_id = state["user_id"]
    session_id = state.get("session_id", "")

    _record_onboarding_user_turn(state, user_message)

    # Pre-seed state with a draft goal from noisy speech before the LLM sees it.
    inferred_goal_brief = _infer_goal_brief_from_message(user_message, state.get("goal_brief") or {})
    if inferred_goal_brief:
        normalized_goal_brief = _merge_goal_brief(state.get("goal_brief") or {}, inferred_goal_brief)
        state["goal_brief"] = normalized_goal_brief
        state["goal_setup_complete"] = _is_goal_brief_routing_ready(normalized_goal_brief)
        state["setup_step"] = "baseline_assessment" if state["goal_setup_complete"] else "goal_setup"
        if not state.get("detected_goal"):
            state["detected_goal"] = normalized_goal_brief.get("primary_goal")

    if state.get("goal_setup_complete") and not state.get("assessed_level") and not state.get("_skip_assessment", False):
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
    _record_onboarding_assistant_turn(state)
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
        if not state.get("assessed_level") and not state.get("_skip_assessment", False):
            _enter_assessment_phase(state)
            state["pending_response"] = _build_assessment_followup_question(state)
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
            if not state.get("assessed_level") and not state.get("_skip_assessment", False):
                _enter_assessment_phase(state)
                state["pending_response"] = _build_assessment_followup_question(state)
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
            "I can move to your baseline now unless you want to correct the draft."
        )

    first_missing = missing[0]
    if first_missing == "goal":
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
Treat a routing-ready draft goal_brief as enough to move toward baseline assessment.
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


def _record_onboarding_assistant_turn(state: AgentState) -> None:
    response_text = str(state.get("pending_response") or "").strip()
    if not response_text:
        return
    history = list(state.get("conversation_history") or [])
    if history and history[-1].get("role") == "assistant" and history[-1].get("content") == response_text:
        return
    history.append({"role": "assistant", "content": response_text})
    state["conversation_history"] = history[-20:]


def _enter_assessment_phase(state: AgentState) -> None:
    state["setup_step"] = "baseline_assessment"
    state["current_mode"] = LearningModeEnum.ASSESSMENT
    state["current_phase"] = AgentPhase.ASSESSMENT


def _get_current_baseline_prompt(state: AgentState) -> tuple[str, str]:
    index = min(state.get("assessment_step_index", 0), len(_BASELINE_PROMPTS) - 1)
    return _BASELINE_PROMPTS[index]


def _is_meta_progress_message(message: str) -> bool:
    normalized = _normalize_user_message(message)
    return _has_any_signal(normalized, _PROCEED_PATTERNS) or _has_any_signal(normalized, _LOW_SIGNAL_PATTERNS)


def _extract_assessment_content_tokens(message: str) -> list[str]:
    normalized = _normalize_user_message(message).strip()
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
    normalized = _normalize_user_message(message).strip()
    if not normalized:
        return True

    content_tokens = _extract_assessment_content_tokens(normalized)
    if len(content_tokens) < 2:
        return True

    words = [word for word in normalized.split() if word]
    filler_ratio = 1.0 - (len(content_tokens) / max(len(words), 1))
    if filler_ratio > 0.55 and len(content_tokens) < 4:
        return True

    goal_role = str((state.get("goal_brief") or {}).get("target_role") or "").lower()

    if question_key == "target_role":
        role_patterns = list(_TARGET_ROLE_PATTERNS)
        if goal_role:
            role_patterns.append(goal_role)
        return not any(pattern in normalized for pattern in role_patterns)

    if question_key == "current_role":
        return not (
            any(pattern in normalized for pattern in _CURRENT_ROLE_PATTERNS)
            or _has_any_signal(normalized, _ML_SIGNAL_PATTERNS)
        )

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
    normalized = _normalize_user_message(message).strip()
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
            if usable_answers >= 2 and state.get("assessment_step_index", 0) >= 2:
                _complete_baseline_assessment(state)
            else:
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
