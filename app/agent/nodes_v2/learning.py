"""Learning Node - LLM-driven conversation with pedagogical features.

Handles:
- Mode-aware conversation (free_conversation, mock_interview, etc.)
- Error correction (Socratic recast)
- Vocabulary tracking
- Memory extraction
"""

import logging
import re
import time
from typing import Optional

from app.agent.state import AgentState, AgentPhase, add_decision_log
from app.data.interview_tracks import get_interview_track
from app.agent.response_parser import parse_llm_response
from app.services.pedagogy_logger import get_pedagogy_logger
from app.services.prompt_service import get_prompt_service
from app.services.ai.llm_provider import get_llm_provider
from app.services.ai.mode_prompts import LearningMode
from app.core.metrics import (
    agent_v2_llm_latency,
    agent_v2_parse_success,
    agent_v2_corrections,
    agent_guardrail_fallbacks,
)
from app.agent.guardrails import (
    validate_and_sanitize,
    check_rate_limit,
)

logger = logging.getLogger(__name__)

MISSION_ANCHORED_TASK_TYPES = {"foundation_speaking_drill", "grammar_rescue"}
TOKEN_RE = re.compile(r"[a-zA-Z']+|\d+")
NUMBER_WORDS = {
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
FILLER_TOKENS = {
    "a",
    "ah",
    "an",
    "and",
    "as",
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
}
ANCHORS = [
    {
        "id": "current_work",
        "label": "your current work",
        "question": "What do you do now, and what kind of ML work do you touch?",
        "follow_up": "Tell me about one recent task from that work.",
        "example": "I work as a data scientist and I build recommendation models.",
    },
    {
        "id": "recent_project",
        "label": "one recent ML project",
        "question": "Tell me about one recent ML project. What problem were you solving?",
        "follow_up": "What was your contribution, and what was the result?",
        "example": "I built a churn model for an e-commerce product.",
    },
    {
        "id": "next_step",
        "label": "your next step in the program",
        "question": "What is your next step in our program, and which skill do you want to improve first?",
        "follow_up": "Say it as one short plan: next step, skill, and why it matters.",
        "example": "My next step is to improve grammar for project answers.",
    },
]
STATIC_CAREER_KEYWORDS = {
    "career",
    "data",
    "deployment",
    "engineer",
    "engineering",
    "english",
    "feature",
    "goal",
    "grammar",
    "improve",
    "inference",
    "interview",
    "job",
    "machine",
    "metrics",
    "mission",
    "ml",
    "model",
    "pipeline",
    "plan",
    "prepare",
    "presentation",
    "process",
    "product",
    "program",
    "project",
    "role",
    "skill",
    "step",
    "train",
    "vocabulary",
    "work",
}


async def learning_node(state: AgentState) -> AgentState:
    """Process learning session turns with LLM-driven decisions."""
    pedagogy = get_pedagogy_logger(state["user_id"])
    prompt_service = get_prompt_service()
    llm = get_llm_provider()

    user_message = state.get("last_user_message", "")
    user_id = state["user_id"]
    session_id = state.get("session_id", "")
    conversation_history = state.get("conversation_history", [])[-18:]
    mission_anchored = _is_mission_anchored(state)

    turn_count = state.get("turn_count", 0) + 1
    state["turn_count"] = turn_count

    is_allowed, rate_limit_message = check_rate_limit(turn_count)
    if not is_allowed:
        state["pending_response"] = rate_limit_message
        state["should_end_session"] = True
        state["needs_user_input"] = False
        logger.info(f"[Learning] Rate limit reached for user {user_id} at turn {turn_count}")
        return state

    if mission_anchored and not user_message:
        action = _build_mission_opener_action(state)
        return _record_learning_turn(
            state,
            action,
            pedagogy,
            conversation_history,
            user_message,
            reason="Mission-anchored opener",
            strategy="mission_opener",
        )

    if mission_anchored and _is_low_signal_text(user_message, state):
        state["low_signal_turn_streak"] = int(state.get("low_signal_turn_streak", 0) or 0) + 1
        action = _build_low_signal_action(state)
        return _record_learning_turn(
            state,
            action,
            pedagogy,
            conversation_history,
            user_message,
            reason=f"Low-signal turn {state['low_signal_turn_streak']}",
            strategy="low_signal",
        )

    if mission_anchored:
        state["low_signal_turn_streak"] = 0

    template = None
    template_variant = "fallback"
    if mission_anchored:
        rendered_prompt = _get_foundation_prompt(state)
        template_variant = "mission_fallback"
    else:
        template_context = _build_template_context(state)
        rendered_prompt, template = await prompt_service.get_and_render(
            node_type="learning_session",
            user_id=user_id,
            state=template_context,
        )
        if not rendered_prompt:
            logger.warning("[Learning] No template found, using fallback")
            rendered_prompt = _get_fallback_prompt(state)

    start_time = time.time()
    try:
        response = await llm.generate(
            user_message=user_message or "",
            system_prompt=rendered_prompt,
            conversation_history=conversation_history,
            max_tokens=300,
        )
        latency_ms = int((time.time() - start_time) * 1000)
        agent_v2_llm_latency.labels(node="learning").observe(latency_ms / 1000)
    except Exception as exc:
        logger.error(f"[Learning] LLM error: {exc}")
        action = _build_mission_error_action(state, "llm_error") if mission_anchored else {
            "action": "continue",
            "response_text": "Sorry, I didn't catch that. Could you say it again?",
        }
        return _record_learning_turn(
            state,
            action,
            pedagogy,
            conversation_history,
            user_message,
            reason="LLM error fallback",
            strategy="llm_error",
        )

    if not (response or "").strip():
        logger.warning(
            "[Learning] Empty final content from LLM for user=%s session=%s",
            user_id,
            session_id,
        )
        action = _build_mission_error_action(state, "empty_final_content") if mission_anchored else {
            "action": "continue",
            "response_text": "Sorry, I didn't catch that. Could you say it again?",
        }
        return _record_learning_turn(
            state,
            action,
            pedagogy,
            conversation_history,
            user_message,
            reason="Empty final content fallback",
            strategy="empty_final_content",
        )

    parse_result = parse_llm_response(response, default_action="continue")
    action = parse_result.action

    if mission_anchored and not parse_result.success:
        action = _build_mission_error_action(state, "parse_failure")
        was_modified = True
    else:
        action, was_modified = validate_and_sanitize(
            response=response,
            node_type="learning",
            parsed_action=action,
            state=state,
        )

    if not action.get("response_text", "").strip():
        action = _build_mission_error_action(state, "empty_response_text") if mission_anchored else {
            "action": "continue",
            "response_text": "Sorry, I didn't catch that. Could you say it again?",
        }
        was_modified = True

    if was_modified:
        agent_guardrail_fallbacks.labels(node="learning").inc()

    agent_v2_parse_success.labels(
        node="learning",
        success=str(parse_result.success).lower()
    ).inc()

    await prompt_service.log_usage(
        session_id=session_id,
        user_id=user_id,
        node_type="learning_session",
        template=template,
        variant=template.variant if template else template_variant,
        turn_number=turn_count,
        llm_response=response,
        parsed_action=action,
        parse_success=parse_result.success,
        latency_ms=latency_ms,
    )

    if mission_anchored:
        _advance_anchor_state(state)

    return _record_learning_turn(
        state,
        action,
        pedagogy,
        conversation_history,
        user_message,
        reason=f"Turn {turn_count} (strategy={parse_result.strategy})",
        strategy=parse_result.strategy,
    )


def _record_learning_turn(
    state: AgentState,
    action: dict,
    pedagogy,
    conversation_history: list[dict],
    user_message: Optional[str],
    *,
    reason: str,
    strategy: str,
) -> AgentState:
    state = _apply_learning_action(state, action, pedagogy)

    if user_message:
        state["conversation_history"] = conversation_history + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": action.get("response_text", "")},
        ]

    add_decision_log(
        state,
        node="learning",
        action=action.get("action", "continue"),
        reason=reason,
        data={
            "strategy": strategy,
            "corrections": len(action.get("corrections", [])),
            "vocabulary": len(action.get("vocabulary_emphasized", [])),
            "mission_task_type": state.get("mission_task_type"),
            "low_signal_turn_streak": state.get("low_signal_turn_streak", 0),
        },
    )

    logger.info(
        "[Learning] User %s: turn=%s, action=%s, strategy=%s",
        state.get("user_id"),
        state.get("turn_count"),
        action.get("action"),
        strategy,
    )
    return state


def _apply_learning_action(
    state: AgentState,
    action: dict,
    pedagogy,
) -> AgentState:
    """Apply parsed LLM action to state."""
    response_text = action.get("response_text", "")

    state["pending_response"] = response_text
    state["needs_user_input"] = True

    corrections = action.get("corrections", [])
    if corrections:
        existing_corrections = state.get("corrections_made", [])
        state["corrections_made"] = existing_corrections + corrections

        agent_v2_corrections.labels(type="total").inc(len(corrections))

        for correction in corrections:
            pedagogy.log_error_corrected(
                user_id=state["user_id"],
                error_type=correction.get("type", "unknown"),
                original=correction.get("original", ""),
                corrected=correction.get("corrected", ""),
                method="socratic_recast",
            )

    vocabulary = action.get("vocabulary_emphasized", [])
    if vocabulary:
        existing_vocab = state.get("vocabulary_reviewed", [])
        state["vocabulary_reviewed"] = existing_vocab + [
            {"word": word, "turn": state.get("turn_count", 0)}
            for word in vocabulary
        ]

    mode_request = action.get("detected_mode_request")
    if mode_request:
        try:
            old_mode = state.get("current_mode", "free_conversation")
            from_mode_str = old_mode.value if hasattr(old_mode, "value") else str(old_mode)

            new_mode = LearningMode(mode_request)
            state["current_mode"] = new_mode
            state["system_prompt"] = None

            pedagogy.log_mode_changed(
                user_id=state["user_id"],
                from_mode=from_mode_str,
                to_mode=mode_request,
                trigger="user_request",
            )
        except ValueError:
            logger.warning(f"Invalid mode request: {mode_request}")

    if action.get("should_end"):
        state["should_end_session"] = True

    memory = action.get("memory_to_save")
    if memory:
        existing_memories = state.get("new_memories_to_save", [])
        state["new_memories_to_save"] = existing_memories + [
            {"content": memory, "turn": state.get("turn_count", 0)}
        ]

    return state


def _build_template_context(state: AgentState) -> dict:
    """Build context dict for template rendering."""
    current_mode = state.get("current_mode")
    if hasattr(current_mode, "value"):
        current_mode = current_mode.value

    anchor = _get_anchor(state)

    return {
        "username": state.get("username", "Student"),
        "user_id": state.get("user_id"),
        "language_level": state.get("language_level", "B1"),
        "confirmed_goal": state.get("confirmed_goal", "General Fluency"),
        "confirmed_interests": state.get("confirmed_interests", []),
        "current_mode": current_mode or "free_conversation",
        "turn_count": state.get("turn_count", 0),
        "session_id": state.get("session_id", ""),
        "last_user_message": state.get("last_user_message", ""),
        "conversation_history": state.get("conversation_history", []),
        "focus_areas": state.get("focus_areas", []),
        "session_focus": state.get("session_focus"),
        "interview_track_id": state.get("interview_track_id"),
        "interview_track_title": state.get("interview_track_title"),
        "interview_question_prompts": state.get("interview_question_prompts", []),
        "mission_task_type": state.get("mission_task_type"),
        "mission_title": state.get("mission_title"),
        "mission_reason": state.get("mission_reason"),
        "mission_success_signal": state.get("mission_success_signal"),
        "mission_linked_goal_context": state.get("mission_linked_goal_context"),
        "low_signal_turn_streak": state.get("low_signal_turn_streak", 0),
        "anchor_question_id": state.get("anchor_question_id", 0),
        "anchor_follow_up_pending": state.get("anchor_follow_up_pending", False),
        "anchor_question": anchor["question"],
        "anchor_follow_up": anchor["follow_up"],
        "vocabulary_list": _format_vocabulary_list(state),
        "memory_section": state.get("memory_section", ""),
        "corrections_made": state.get("corrections_made", []),
        "vocabulary_reviewed": state.get("vocabulary_reviewed", []),
    }


def _format_vocabulary_list(state: AgentState) -> str:
    words = state.get("due_vocabulary_words", [])
    if not words:
        return ""
    return ", ".join(words[:10])


def _get_fallback_prompt(state: AgentState) -> str:
    username = state.get("username", "Student")
    level = state.get("language_level", "B1")
    goal = state.get("confirmed_goal", "General Fluency")
    current_mode = state.get("current_mode")
    if hasattr(current_mode, "value"):
        current_mode = current_mode.value

    if _is_mission_anchored(state):
        return _get_foundation_prompt(state)

    if current_mode == "mock_interview":
        track = get_interview_track(state.get("interview_track_id")) or {
            "id": "hr_intro",
            "title": state.get("interview_track_title") or "Interview Mission",
            "prompt_focus": state.get("session_focus") or "clear professional communication",
            "starter_question": "Tell me about yourself and your recent work.",
        }
        track_styles = {
            "hr_intro": (
                "Focus on STAR structure (Situation, Task, Action, Result). "
                "Expect concise motivation answers. Push for specific outcomes."
            ),
            "project_walkthrough": (
                "Probe for architecture decisions, trade-offs, and business impact. "
                "Ask for metrics and specific technical choices."
            ),
            "workplace_communication": (
                "Expect standup-style brevity: done / next / blocked. "
                "Ask about collaboration, blockers, and stakeholder communication."
            ),
        }
        style_hint = track_styles.get(
            track.get("id", "hr_intro"),
            "Focus on clear, structured professional communication.",
        )

        question_prompts = state.get("interview_question_prompts", [])
        if question_prompts:
            numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(question_prompts))
            questions_block = (
                f"\nPrepared questions for this session (use in order, one at a time):\n{numbered}\n"
                "After each answer, ask one follow-up to probe deeper before moving to the next question."
            )
        else:
            questions_block = f"\nStarter question: {track['starter_question']}"

        return f"""You are English Friend acting as a friendly but demanding interviewer.

Student: {username}
Level: {level}
Goal: {goal}
Interview track: {track['title']}
Track focus: {track['prompt_focus']}
Interviewing style: {style_hint}
{questions_block}

Rules:
1. Keep the interview realistic and concise.
2. Ask one question at a time, wait for the answer, then ask a focused follow-up.
3. Give brief micro-feedback naturally woven into the transition.
4. Use Socratic recasts for grammar mistakes.
5. If there is no user message yet, open with the first prepared question.

Respond with JSON:
{{"action": "continue", "response_text": "your response", "corrections": [{{"original": "...", "corrected": "...", "type": "grammar"}}], "vocabulary_emphasized": ["word"], "should_end": false}}"""

    return f"""You are English Friend - a patient, encouraging AI English tutor.

Student: {username}
Level: {level}
Goal: {goal}

Teaching principles:
1. Student talks 70%, you 30%
2. Error correction: Use Socratic recast (repeat correctly, don't say "wrong")
3. Keep responses SHORT (2-3 sentences + 1 question)

Example correction:
- Student: "I went to store"
- You: "Oh, you went to THE store! What did you buy?"

Respond with JSON:
{{"action": "continue", "response_text": "your response", "corrections": [{{"original": "...", "corrected": "...", "type": "grammar"}}], "should_end": false}}"""


def _get_foundation_prompt(state: AgentState) -> str:
    anchor = _get_anchor(state)
    next_anchor = _get_anchor(state, offset=1)
    stage = "follow_up" if state.get("anchor_follow_up_pending") else "primary"
    mission_title = state.get("mission_title") or "Foundation speaking drill"
    mission_reason = state.get("mission_reason") or "Stabilize grammar and fluency before higher-pressure scenarios."
    mission_success_signal = state.get("mission_success_signal") or "The student gives one cleaner career-related answer."
    linked_context = state.get("mission_linked_goal_context") or "foundation"
    goal = state.get("confirmed_goal") or "Career English"
    level = state.get("language_level", "B1")
    username = state.get("username", "Student")

    next_instruction = (
        f"After a clear follow-up answer, move to the next anchor question: {next_anchor['question']}"
        if next_anchor
        else "After a clear follow-up answer, ask the learner to restate the plan in one clean sentence and offer to stop."
    )

    return f"""You are English Friend running a strict career-English foundation drill.

Student: {username}
Level: {level}
Goal: {goal}
Mission title: {mission_title}
Mission reason: {mission_reason}
Mission success signal: {mission_success_signal}
Linked goal context: {linked_context}
Active anchor label: {anchor['label']}
Active anchor stage: {stage}
Primary anchor question: {anchor['question']}
Follow-up anchor question: {anchor['follow_up']}
{next_instruction}

Rules:
1. Stay on the active anchor only.
2. Never invent a new topic from a noisy or unclear transcript.
3. If the user answer is vague, noisy, or off-topic, ask for one shorter answer about the same anchor.
4. Keep the reply to at most 2 short sentences.
5. Use at most one gentle recast.
6. End with exactly one question.
7. If active anchor stage is primary and the answer is clear, ask the follow-up anchor question.
8. If active anchor stage is follow_up and another anchor exists, ask the next anchor question.
9. Do not turn this into generic free conversation, vocabulary chat, or a new topic.
10. If the user has not answered yet, ask the active primary anchor question directly.

Respond with JSON:
{{"action": "continue", "response_text": "your response", "corrections": [{{"original": "...", "corrected": "...", "type": "grammar"}}], "vocabulary_emphasized": ["word"], "should_end": false}}"""


def _is_mission_anchored(state: AgentState) -> bool:
    return (state.get("mission_task_type") or "") in MISSION_ANCHORED_TASK_TYPES


def _tokenize_text(text: Optional[str]) -> list[str]:
    if not text:
        return []
    return [token.lower() for token in TOKEN_RE.findall(text)]


def _mission_keywords(state: AgentState) -> set[str]:
    dynamic = set(STATIC_CAREER_KEYWORDS)
    for key in (
        "confirmed_goal",
        "mission_title",
        "mission_reason",
        "mission_success_signal",
        "mission_linked_goal_context",
    ):
        dynamic.update(_tokenize_text(str(state.get(key) or "")))
    dynamic.discard("")
    return dynamic


def _is_low_signal_text(text: Optional[str], state: AgentState) -> bool:
    tokens = _tokenize_text(text)
    if not tokens:
        return True

    filler_or_number_hits = sum(
        1
        for token in tokens
        if token in FILLER_TOKENS or token in NUMBER_WORDS or token.isdigit()
    )
    content_tokens = [
        token
        for token in tokens
        if token not in FILLER_TOKENS and token not in NUMBER_WORDS and not token.isdigit()
    ]

    if len(content_tokens) < 4:
        return True

    if filler_or_number_hits / max(len(tokens), 1) > 0.4:
        return True

    if len(set(content_tokens)) <= 2 and len(content_tokens) >= 4:
        return True

    if _is_mission_anchored(state):
        keywords = _mission_keywords(state)
        has_anchor = any(token in keywords for token in content_tokens)
        if not has_anchor:
            return True

    return False


def _get_anchor(state: AgentState, offset: int = 0) -> dict:
    index = int(state.get("anchor_question_id", 0) or 0) + offset
    index = max(0, min(index, len(ANCHORS) - 1))
    return ANCHORS[index]


def _build_mission_opener_action(state: AgentState) -> dict:
    anchor = _get_anchor(state)
    mission_title = state.get("mission_title") or "today's foundation drill"
    return {
        "action": "continue",
        "response_text": f"Let's keep {mission_title.lower()} focused. {anchor['question']}",
        "should_end": False,
    }


def _build_low_signal_action(state: AgentState) -> dict:
    streak = int(state.get("low_signal_turn_streak", 0) or 0)
    anchor = _get_anchor(state)
    if streak <= 1:
        response_text = (
            f"Let's stay with {anchor['label']}. Please answer in one short sentence. "
            f"{anchor['question']}"
        )
        should_end = False
    elif streak == 2:
        response_text = (
            f"Let's make it simpler. Type one short answer in the composer, for example: "
            f"\"{anchor['example']}\""
        )
        should_end = False
    else:
        response_text = (
            "The audio is too noisy for this drill. Let's stop this run here. "
            "Restart the mission and answer with one short sentence."
        )
        should_end = True

    return {
        "action": "continue",
        "response_text": response_text,
        "should_end": should_end,
    }


def _build_mission_error_action(state: AgentState, reason: str) -> dict:
    anchor = _get_anchor(state)
    logger.warning(
        "[Learning] Mission-anchored fallback for user=%s reason=%s anchor=%s",
        state.get("user_id"),
        reason,
        anchor["id"],
    )
    return {
        "action": "continue",
        "response_text": f"Let's keep it focused on {anchor['label']}. {anchor['question']}",
        "should_end": False,
    }


def _advance_anchor_state(state: AgentState) -> None:
    index = int(state.get("anchor_question_id", 0) or 0)
    follow_up_pending = bool(state.get("anchor_follow_up_pending", False))

    if not follow_up_pending:
        state["anchor_follow_up_pending"] = True
        return

    if index < len(ANCHORS) - 1:
        state["anchor_question_id"] = index + 1
        state["anchor_follow_up_pending"] = False
        return

    state["anchor_question_id"] = len(ANCHORS) - 1
    state["anchor_follow_up_pending"] = False


def route_after_learning(state: AgentState) -> str:
    """Conditional edge function after learning."""
    if state.get("should_end_session"):
        return "session_end"
    return "wait_for_input"
