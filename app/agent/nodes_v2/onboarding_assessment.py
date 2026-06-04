"""Baseline (CEFR) assessment subsystem for the onboarding node.

A short, deterministic speaking baseline: asks up to three baseline prompts,
scores answer signal quality, infers a provisional CEFR level, and hands back
to the program. All functions operate on AgentState and depend only on the
onboarding patterns/text leaves — they never call the goal-brief logic or the
node, so this stays a leaf of the onboarding package.
"""

from typing import Optional

from app.agent.state import AgentPhase, AgentState, LearningModeEnum
from app.agent.nodes_v2.onboarding_patterns import (
    _ASSESSMENT_FILLER_TOKENS,
    _ASSESSMENT_NUMBER_WORDS,
    _BASELINE_PROMPTS,
    _CURRENT_ROLE_PATTERNS,
    _FUTURE_ROLE_PATTERNS,
    _LOW_SIGNAL_PATTERNS,
    _ML_SIGNAL_PATTERNS,
    _NO_CURRENT_ROLE_PATTERNS,
    _PROCEED_PATTERNS,
    _PROJECT_TASK_PATTERNS,
    _TARGET_ROLE_PATTERNS,
)
from app.agent.nodes_v2.onboarding_text import (
    _has_any_signal,
    _normalize_assessment_answer,
    _normalize_user_message,
)


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
