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

from app.agent.intent_policy import build_intent_context_from_state, classify_intent
from app.agent.intent_policy.fast_rules import SUPPORT_REQUEST_RU_PATTERNS
from app.agent.intent_policy.language import is_russian
from app.agent.state import AgentState, AgentPhase, add_decision_log
from app.agent.pedagogy_policy import shadow_policy_action_for_intent
from app.data.interview_tracks import get_interview_track
from app.agent.response_parser import parse_llm_response
from app.services.pedagogy_logger import get_pedagogy_logger
from app.services.prompt_service import get_prompt_service
from app.services.ai.llm_provider import LLMEmptyContentError, get_llm_provider
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

MISSION_ANCHORED_TASK_TYPES = {
    "foundation_speaking_drill",
    "grammar_rescue",
    "technical_project_walkthrough",
    "model_choice_drill",
    "metrics_explainer",
    "tradeoff_explanation_drill",
    "stakeholder_explanation_drill",
    "failure_debugging_drill",
}
TECHNICAL_MISSION_SPECS = {
    "technical_project_walkthrough": {
        "label": "one technical project",
        "question": "Explain one recent ML or technical project: problem, approach, metric, and impact.",
        "example": "I worked on a churn model. The goal was to predict which users might leave.",
        "russian_hint": "Коротко объясни по-русски структуру ответа: проблема, решение, метрика, результат. Затем сразу верни ученика к английскому ответу.",
        "english_target": "After any Russian clarification, ask the learner to answer again in English as in a technical interview.",
    },
    "model_choice_drill": {
        "label": "one model choice",
        "question": "Explain why you chose one model instead of another in one project.",
        "example": "We started with logistic regression as a baseline, then moved to gradient boosting for better recall.",
        "russian_hint": "Если ученик застрял, кратко объясни по-русски как сравнить baseline, chosen model и причину выбора. Потом вернись к английскому.",
        "english_target": "Push for a compact interview answer in English with baseline, chosen model, and one clear reason.",
    },
    "metrics_explainer": {
        "label": "one metric explanation",
        "question": "Explain one metric you used and why it mattered for the task.",
        "example": "We focused on recall because missing positive cases was more expensive than extra false alarms.",
        "russian_hint": "Если ученик путается, кратко объясни по-русски: что измеряет метрика и почему именно она важна для задачи. Потом верни его к английскому.",
        "english_target": "Push for simple English: what the metric measures, why it mattered, and what trade-off it implied.",
    },
    "tradeoff_explanation_drill": {
        "label": "one trade-off decision",
        "question": "Explain one trade-off you made between two technical options.",
        "example": "We chose the simpler pipeline because it was easier to maintain and fast enough for the latency target.",
        "russian_hint": "Если ученик не может начать, кратко объясни по-русски схему: option A, option B, criterion, final choice. Затем снова попроси английский ответ.",
        "english_target": "Push for one clear trade-off answer in English with two options and one decisive reason.",
    },
    "stakeholder_explanation_drill": {
        "label": "one stakeholder-friendly explanation",
        "question": "Explain your project to a non-technical stakeholder in simple English.",
        "example": "The model helped the team find risky cases earlier, so the business could react faster.",
        "russian_hint": "Если ученик уходит в jargon, коротко объясни по-русски: бизнес-проблема, что изменилось, почему это важно. Потом снова переведи его на английский.",
        "english_target": "Keep the answer in simple English and reduce jargon after any Russian rescue.",
    },
    "failure_debugging_drill": {
        "label": "one failure and recovery story",
        "question": "Explain one time a model or system did not work as expected. What happened, and what changed after that?",
        "example": "Our first model overfit badly, so we changed the feature set and added stronger validation.",
        "russian_hint": "Если ученик теряет структуру, коротко объясни по-русски: проблема, как заметили, что поменяли, итог. Потом верни к английскому answer.",
        "english_target": "Push for a calm interview answer in English with failure, diagnosis, fix, and outcome.",
    },
}
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
        "label": "the next guided mission",
        "question": "I will choose the next mission focus from your answers. Does that sound right?",
        "follow_up": "Reply with one short confirmation or correction.",
        "example": "Yes, focus on project answers first.",
    },
]
ANCHOR_PARAPHRASES = {
    "current_work": "Tell me briefly about your current role and the ML work you handle.",
    "recent_project": "Walk me through one recent project. What problem were you solving there?",
    "next_step": "I will set the next mission from your answers. Does that focus fit?",
}
ANCHOR_SIGNAL_PATTERNS = {
    "current_work": (
        "current work",
        "i work",
        "my role",
        "data scientist",
        "data analyst",
        "engineer",
        "build recommendation",
        "work now",
    ),
    "recent_project": (
        "recent project",
        "my project",
        "project was",
        "pet project",
        "side project",
        "personal project",
        "creating",
        "building",
        "i built",
        "model i",
        "mentor",
        "app",
        "recommendation model",
        "churn model",
        "fraud model",
        "pipeline",
        "problem",
        "result",
        "metric",
    ),
    "next_step": (
        "next step",
        "my next step",
        "in our program",
        "improve grammar",
        "improve fluency",
        "improve vocabulary",
        "my plan",
        "skill i want",
    ),
}
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
SUPPORT_REQUEST_PATTERNS = (
    "my english is bad",
    "my english is very bad",
    "my english is weak",
    "could you teach me",
    "teach me",
    "i can not describe",
    "i cannot describe",
    "i cant describe",
    "i dont know how to say",
    "i don't know how to say",
    "i dont know how can i say",
    "i don't know how can i say",
    "i cant explain in english",
    "i can't explain in english",
    "i do not know how to say",
)


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

    _update_shadow_intent(state, user_message)

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

    if mission_anchored and _needs_supportive_anchor_recovery(user_message):
        state["low_signal_turn_streak"] = int(state.get("low_signal_turn_streak", 0) or 0) + 1
        action = _build_supportive_anchor_action(state, user_message=user_message)
        return _record_learning_turn(
            state,
            action,
            pedagogy,
            conversation_history,
            user_message,
            reason=f"Supportive recovery {state['low_signal_turn_streak']}",
            strategy="supportive_recovery",
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
        _apply_anchor_shift_if_needed(state, user_message)

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
    except LLMEmptyContentError as exc:
        logger.warning("[Learning] Empty final content from LLM: %s", exc)
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
        _advance_anchor_state(state, user_message=user_message)

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
    _rewrite_legacy_next_step_response_if_needed(state, action)
    _dedupe_anchor_response_if_needed(state, action)
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
        return _get_mission_anchored_prompt(state)

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


def _get_mission_anchored_prompt(state: AgentState) -> str:
    mission_task_type = state.get("mission_task_type") or ""
    if mission_task_type in TECHNICAL_MISSION_SPECS:
        return _get_technical_drill_prompt(state)
    return _get_foundation_prompt(state)


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
    next_mission_focus = _get_next_mission_focus_hint(state)
    anchor_question = _get_anchor_prompt_text(state, follow_up=False)
    anchor_follow_up = _get_anchor_prompt_text(state, follow_up=True)

    next_instruction = (
        f"After a clear follow-up answer, move to the next anchor question: {_get_anchor_prompt_text(state, anchor=next_anchor, follow_up=False)}"
        if next_anchor
        else "After a clear follow-up answer, give one brief confirmation and close the drill."
    )
    next_step_instruction = (
        "For the next_step anchor, recap one concrete detail from the learner's recent answers, "
        f"state that the next mission will focus on {next_mission_focus}, and ask only for a short confirmation or correction. "
        "Do NOT ask the learner to design the program or choose a skill list."
    )
    next_step_follow_up_instruction = (
        "If the learner confirms or lightly corrects the next-step plan, acknowledge it in one short sentence and end the drill."
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
Primary anchor question: {anchor_question}
Follow-up anchor question: {anchor_follow_up}
Suggested next mission focus: {next_mission_focus}
{next_instruction}
{next_step_instruction if anchor['id'] == 'next_step' and stage == 'primary' else ''}
{next_step_follow_up_instruction if anchor['id'] == 'next_step' and stage == 'follow_up' else ''}

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


def _get_technical_drill_prompt(state: AgentState) -> str:
    mission_task_type = state.get("mission_task_type") or ""
    spec = TECHNICAL_MISSION_SPECS[mission_task_type]
    mission_title = state.get("mission_title") or "Technical explanation drill"
    mission_reason = state.get("mission_reason") or "Practice one interview-relevant technical explanation."
    mission_success_signal = state.get("mission_success_signal") or "The learner gives one clearer technical answer."
    linked_context = state.get("mission_linked_goal_context") or "project_walkthrough"
    goal = state.get("confirmed_goal") or "Career English"
    level = state.get("language_level", "B1")
    username = state.get("username", "Student")

    return f"""You are English Friend running a bounded technical mentoring drill for a Russian-speaking learner.

Student: {username}
Level: {level}
Goal: {goal}
Mission title: {mission_title}
Mission reason: {mission_reason}
Mission success signal: {mission_success_signal}
Linked goal context: {linked_context}
Active drill label: {spec['label']}
Primary drill question: {spec['question']}
Suggested example: {spec['example']}

Rules:
1. Stay on this one technical concept or explanation task.
2. Your job is not to teach a full ML course. Keep it interview-relevant and practical.
3. First try to get the learner to answer in English.
4. If the learner is confused, blocked, or asks for help, you may give a very short clarification in Russian.
5. Russian clarification must be brief and only unblock understanding. {spec['russian_hint']}
6. {spec['english_target']}
7. After any Russian clarification, immediately ask the learner to try again in English.
8. Keep answers short and voice-friendly. Prefer 2-4 sentences, then one question.
9. Use at most one gentle recast for grammar.
10. Emphasize strong interview phrasing and reusable vocabulary.
11. If there is no user answer yet, ask the primary drill question directly.

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
    mission_task_type = state.get("mission_task_type") or ""
    if mission_task_type in TECHNICAL_MISSION_SPECS:
        spec = TECHNICAL_MISSION_SPECS[mission_task_type]
        return {
            "action": "continue",
            "response_text": (
                f"Let's do one technical explanation drill. {spec['question']} "
                "Use simple English. If you get stuck, I can briefly help in Russian."
            ),
            "should_end": False,
        }

    anchor = _get_anchor(state)
    if mission_task_type == "foundation_speaking_drill":
        intro = "Let's keep this foundation speaking drill focused."
    elif mission_task_type == "grammar_rescue":
        intro = "Let's keep this grammar rescue session focused."
    else:
        mission_title = state.get("mission_title") or "today's mission"
        intro = f"Let's keep {mission_title.lower()} focused."
    return {
        "action": "continue",
        "response_text": f"{intro} {_get_anchor_prompt_text(state, follow_up=False)}",
        "should_end": False,
    }


def _build_low_signal_action(state: AgentState) -> dict:
    mission_task_type = state.get("mission_task_type") or ""
    if mission_task_type in TECHNICAL_MISSION_SPECS:
        streak = int(state.get("low_signal_turn_streak", 0) or 0)
        spec = TECHNICAL_MISSION_SPECS[mission_task_type]
        if streak <= 1:
            response_text = (
                f"Let's keep it simple and stay with {spec['label']}. "
                f"{spec['question']}"
            )
            should_end = False
        elif streak == 2:
            response_text = (
                f"Type one short answer in the composer if speaking is hard. Example: "
                f"\"{spec['example']}\""
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

    streak = int(state.get("low_signal_turn_streak", 0) or 0)
    anchor = _get_anchor(state)
    if streak <= 1:
        response_text = (
            f"Let's stay with {anchor['label']}. Please answer in one short sentence. "
            f"{_get_anchor_prompt_text(state, follow_up=False)}"
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


ANCHOR_RU_HINTS = {
    "current_work": "Расскажи коротко по-английски, кем работаешь и какие ML-задачи решаешь.",
    "recent_project": "Расскажи по-английски про один недавний проект: какую проблему решал.",
    "next_step": "Подтверди одной фразой по-английски, согласен ли ты с предложенной следующей миссией.",
}


def _build_supportive_anchor_action(state: AgentState, *, user_message: Optional[str] = None) -> dict:
    mission_task_type = state.get("mission_task_type") or ""
    if mission_task_type in TECHNICAL_MISSION_SPECS:
        streak = int(state.get("low_signal_turn_streak", 0) or 0)
        spec = TECHNICAL_MISSION_SPECS[mission_task_type]
        if streak <= 1:
            response_text = (
                f"Все нормально. Very simple English is fine. Example: \"{spec['example']}\" "
                f"{spec['question']}"
            )
        elif streak == 2:
            response_text = (
                f"Все нормально. Type one short answer in the composer if speaking is hard. "
                f"Example: \"{spec['example']}\""
            )
        else:
            response_text = (
                f"Все нормально. Say or type one short interview-style sentence only. "
                f"Example: \"{spec['example']}\""
            )
        return {
            "action": "continue",
            "response_text": response_text,
            "should_end": False,
        }

    streak = int(state.get("low_signal_turn_streak", 0) or 0)
    anchor = _get_anchor(state)
    example = anchor["example"]

    if is_russian(user_message):
        ru_hint = ANCHOR_RU_HINTS.get(anchor["id"], "")
        return {
            "action": "continue",
            "response_text": (
                f"{ru_hint} Example: \"{example}\""
            ),
            "should_end": False,
        }

    if streak <= 1:
        response_text = (
            f"No problem. Use very simple English. Example: \"{example}\" "
            f"{_get_anchor_prompt_text(state, follow_up=False)}"
        )
    elif streak == 2:
        response_text = (
            f"No problem. Type one short answer in the composer if speaking is hard. "
            f"Example: \"{example}\""
        )
    else:
        response_text = (
            f"We can keep it very short. Say or type 3-6 words only. "
            f"Example: \"{example}\""
        )

    return {
        "action": "continue",
        "response_text": response_text,
        "should_end": False,
    }


def _build_mission_error_action(state: AgentState, reason: str) -> dict:
    mission_task_type = state.get("mission_task_type") or ""
    if mission_task_type in TECHNICAL_MISSION_SPECS:
        spec = TECHNICAL_MISSION_SPECS[mission_task_type]
        logger.warning(
            "[Learning] Technical mission fallback for user=%s reason=%s task=%s",
            state.get("user_id"),
            reason,
            mission_task_type,
        )
        return {
            "action": "continue",
            "response_text": (
                f"Let's keep it focused on {spec['label']}. {spec['question']} "
                "Use simple English."
            ),
            "should_end": False,
        }

    anchor = _get_anchor(state)
    logger.warning(
        "[Learning] Mission-anchored fallback for user=%s reason=%s anchor=%s",
        state.get("user_id"),
        reason,
        anchor["id"],
    )
    return {
        "action": "continue",
        "response_text": f"Let's keep it focused on {anchor['label']}. {_get_anchor_prompt_text(state, follow_up=False)}",
        "should_end": False,
    }


_MISSION_KEYWORD_MAP: tuple[tuple[tuple[str, ...], str], ...] = (
    (("mock interview", "mock", "test interview"), "mock_interview"),
    (("intro", "introduction", "about myself", "self introduction"), "interview_intro"),
    (("pronunciation", "accent"), "pronunciation_drill"),
    (("project walk", "project answer", "walkthrough"), "technical_project_walkthrough"),
    (("grammar", "tense", "article"), "grammar_rescue"),
    (("vocab", "vocabulary", "words"), "vocabulary_drill"),
)
_AFFIRM_TOKENS = (" yes ", " ok ", " okay ", " sure ", " right ", " match ", " sounds right ", " да ", " угу ", " подтверждаю ")
_NEGATION_TOKENS = (" no ", " not ", " nope ", " нет ", " не ")


def _parse_anchor_two_choice(
    user_text: Optional[str],
    proposed_mission: Optional[str],
) -> Optional[str]:
    """Извлечь mission preference из ответа на anchor 2 confirm.

    Возвращает имя миссии (`mock_interview`, ...), либо `proposed_mission`
    при простом подтверждении, либо None если сигнал не обнаружен.
    """
    if not (user_text or "").strip():
        return None
    lowered = (user_text or "").lower()
    padded = f" {lowered} "
    is_affirm = any(token in padded for token in _AFFIRM_TOKENS)
    is_negation = any(token in padded for token in _NEGATION_TOKENS)
    for keywords, mission_id in _MISSION_KEYWORD_MAP:
        if any(keyword in lowered for keyword in keywords):
            return mission_id
    if is_affirm and not is_negation:
        return proposed_mission
    return None


def _proposed_mission_from_focus_hint(state: AgentState) -> Optional[str]:
    linked_context = state.get("mission_linked_goal_context") or "foundation"
    mapping = {
        "interviews": "interview_intro",
        "project_walkthrough": "technical_project_walkthrough",
        "workplace_communication": "stakeholder_explanation_drill",
    }
    return mapping.get(linked_context)


def _advance_anchor_state(state: AgentState, user_message: Optional[str] = None) -> None:
    index = int(state.get("anchor_question_id", 0) or 0)
    follow_up_pending = bool(state.get("anchor_follow_up_pending", False))

    if not follow_up_pending:
        state["anchor_follow_up_pending"] = True
        return

    if index < len(ANCHORS) - 1:
        state["anchor_question_id"] = index + 1
        state["anchor_follow_up_pending"] = False
        return

    proposed = _proposed_mission_from_focus_hint(state)
    chosen = _parse_anchor_two_choice(user_message, proposed)
    if chosen:
        state["next_mission_choice"] = chosen
        add_decision_log(
            state,
            node="learning",
            action="anchor_two_choice",
            reason="user confirmed/corrected next mission",
            data={"chosen": chosen, "proposed": proposed},
        )

    state["anchor_question_id"] = len(ANCHORS) - 1
    state["anchor_follow_up_pending"] = False
    state["should_end_session"] = True


def _apply_anchor_shift_if_needed(state: AgentState, user_message: Optional[str]) -> None:
    if not state.get("anchor_follow_up_pending"):
        return
    current_index = int(state.get("anchor_question_id", 0) or 0)
    next_index = min(current_index + 1, len(ANCHORS) - 1)
    if next_index == current_index:
        return
    if _matches_anchor(ANCHORS[next_index]["id"], user_message):
        state["anchor_question_id"] = next_index
        state["anchor_follow_up_pending"] = False


def _matches_anchor(anchor_id: str, text: Optional[str]) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    return any(pattern in normalized for pattern in ANCHOR_SIGNAL_PATTERNS.get(anchor_id, ()))


def _normalize_text(text: Optional[str]) -> str:
    source = (text or "").lower().replace("-", " ")
    normalized = re.sub(r"[^a-z0-9\s]", " ", source)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return f" {normalized} "


def _get_next_mission_focus_hint(state: AgentState) -> str:
    linked_context = state.get("mission_linked_goal_context") or "foundation"
    focus_by_context = {
        "interviews": "a tighter self-introduction for interviews",
        "project_walkthrough": "a clearer project walkthrough with problem, approach, metric, and impact",
        "workplace_communication": "a clearer explanation for a manager or stakeholder",
        "foundation": "one clearer interview-style answer about your current work and project",
    }
    return focus_by_context.get(
        linked_context,
        "one clearer interview-style answer about your current work and project",
    )


def _get_anchor_prompt_text(
    state: AgentState,
    *,
    follow_up: bool,
    anchor: Optional[dict] = None,
) -> str:
    active_anchor = anchor or _get_anchor(state)
    prompt_key = "follow_up" if follow_up else "question"
    if active_anchor["id"] != "next_step":
        return active_anchor[prompt_key]

    next_mission_focus = _get_next_mission_focus_hint(state)
    if follow_up:
        return "Reply with one short confirmation or correction."
    return (
        "From what you said, I can choose the next mission focus. "
        f"Next mission will focus on {next_mission_focus}. Does that match what you want?"
    )


def _iter_anchor_prompt_fragments() -> list[tuple[str, str, str]]:
    fragments: list[tuple[str, str, str]] = []
    for anchor in ANCHORS:
        for prompt_key in ("question", "follow_up"):
            raw_fragment = anchor[prompt_key]
            fragments.append((anchor["id"], _normalize_text(raw_fragment), raw_fragment))
    return fragments


def _match_anchor_prompt_fragment(response_text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    normalized_response = _normalize_text(response_text)
    for anchor_id, normalized_fragment, raw_fragment in _iter_anchor_prompt_fragments():
        if normalized_fragment.strip() and normalized_fragment in normalized_response:
            return anchor_id, normalized_fragment, raw_fragment
    return None, None, None


_RECENT_QUESTIONS_CAP = 4
_DUP_JACCARD_THRESHOLD = 0.7
_QUESTION_SENTENCE_RE = re.compile(r"[^.!?]*\?")


def _extract_last_question(text: str) -> Optional[str]:
    matches = _QUESTION_SENTENCE_RE.findall(text or "")
    if not matches:
        return None
    return matches[-1].strip() or None


def _jaccard(a: str, b: str) -> float:
    set_a = {tok for tok in a.split() if tok}
    set_b = {tok for tok in b.split() if tok}
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


def _push_recent_question(state: AgentState, normalized_question: str) -> None:
    history: list[str] = list(state.get("recent_assistant_questions") or [])
    history.append(normalized_question)
    state["recent_assistant_questions"] = history[-_RECENT_QUESTIONS_CAP:]


def _dedupe_anchor_response_if_needed(state: AgentState, action: dict) -> None:
    if not _is_mission_anchored(state):
        return

    mission_task_type = state.get("mission_task_type") or ""
    if mission_task_type in TECHNICAL_MISSION_SPECS:
        return

    response_text = action.get("response_text", "")
    if not response_text:
        return

    anchor_id, normalized_fragment, raw_fragment = _match_anchor_prompt_fragment(response_text)
    if anchor_id and normalized_fragment:
        if state.get("last_anchor_question_text") == normalized_fragment:
            paraphrase = ANCHOR_PARAPHRASES.get(anchor_id)
            if paraphrase:
                if raw_fragment and raw_fragment in response_text:
                    action["response_text"] = response_text.replace(raw_fragment, paraphrase, 1)
                else:
                    action["response_text"] = paraphrase
        state["last_anchor_question_text"] = normalized_fragment

    response_text = action.get("response_text", "")
    last_question = _extract_last_question(response_text)
    if not last_question:
        return
    normalized_question = _normalize_text(last_question).strip()
    if not normalized_question:
        return

    history = list(state.get("recent_assistant_questions") or [])
    if any(_jaccard(normalized_question, prior) >= _DUP_JACCARD_THRESHOLD for prior in history):
        anchor = _get_anchor(state)
        paraphrase = ANCHOR_PARAPHRASES.get(anchor["id"])
        if paraphrase and last_question in response_text:
            action["response_text"] = response_text.replace(last_question, paraphrase, 1)
        else:
            action["response_text"] = f"Let me put it differently — {response_text}"
        normalized_question = _normalize_text(_extract_last_question(action["response_text"]) or last_question).strip()

    _push_recent_question(state, normalized_question)


def _rewrite_legacy_next_step_response_if_needed(state: AgentState, action: dict) -> None:
    if not _is_mission_anchored(state):
        return

    mission_task_type = state.get("mission_task_type") or ""
    if mission_task_type in TECHNICAL_MISSION_SPECS:
        return

    if int(state.get("anchor_question_id", 0) or 0) != 2:
        return

    normalized_response = _normalize_text(action.get("response_text", ""))
    legacy_patterns = (
        " say it as one short plan ",
        " what is your next step in our program ",
        " which skill do you want to improve first ",
    )
    if not any(pattern in normalized_response for pattern in legacy_patterns):
        return

    action["response_text"] = _get_anchor_prompt_text(state, follow_up=False)


def _update_shadow_intent(state: AgentState, user_message: Optional[str]) -> None:
    if not (user_message or "").strip():
        state["last_intent"] = None
        return
    result = classify_intent(str(user_message), build_intent_context_from_state(state))
    state["last_intent"] = result.to_payload(
        policy_action=shadow_policy_action_for_intent(result.type),
        shadow_mode=True,
    )


def _needs_supportive_anchor_recovery(text: Optional[str]) -> bool:
    if not (text or "").strip():
        return False
    normalized = _normalize_text(text)
    if any(pattern in normalized for pattern in SUPPORT_REQUEST_PATTERNS):
        return True
    lowered = text.lower()
    return any(pattern in lowered for pattern in SUPPORT_REQUEST_RU_PATTERNS)


def route_after_learning(state: AgentState) -> str:
    """Conditional edge function after learning."""
    if state.get("should_end_session"):
        return "session_end"
    return "wait_for_input"
