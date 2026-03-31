"""Learning Node - LLM-driven conversation with pedagogical features.

Handles:
- Mode-aware conversation (free_conversation, mock_interview, etc.)
- Error correction (Socratic recast)
- Vocabulary tracking
- Memory extraction
"""

import logging
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
    agent_guardrail_violations,
    agent_guardrail_fallbacks,
)
from app.agent.guardrails import (
    validate_and_sanitize,
    check_rate_limit,
    MAX_TURNS_PER_SESSION,
)

logger = logging.getLogger(__name__)


async def learning_node(state: AgentState) -> AgentState:
    """Process learning session turns with LLM-driven decisions.

    Uses structured JSON output for:
    - Conversation responses
    - Error corrections
    - Vocabulary emphasis
    - Mode change detection
    - Session end detection

    Args:
        state: Current agent state

    Returns:
        Updated state
    """
    pedagogy = get_pedagogy_logger(state["user_id"])
    prompt_service = get_prompt_service()
    llm = get_llm_provider()

    user_message = state.get("last_user_message", "")
    user_id = state["user_id"]
    session_id = state.get("session_id", "")

    # Increment turn count
    turn_count = state.get("turn_count", 0) + 1
    state["turn_count"] = turn_count

    # Rate limiting check
    is_allowed, rate_limit_message = check_rate_limit(turn_count)
    if not is_allowed:
        state["pending_response"] = rate_limit_message
        state["should_end_session"] = True
        state["needs_user_input"] = False
        logger.info(f"[Learning] Rate limit reached for user {user_id} at turn {turn_count}")
        return state

    # Build template context
    template_context = _build_template_context(state)

    # Get and render prompt template
    rendered_prompt, template = await prompt_service.get_and_render(
        node_type="learning_session",
        user_id=user_id,
        state=template_context,
    )

    if not rendered_prompt:
        logger.warning("[Learning] No template found, using fallback")
        rendered_prompt = _get_fallback_prompt(state)

    # Build conversation context
    conversation_history = state.get("conversation_history", [])[-18:]

    # Call LLM
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

    except Exception as e:
        logger.error(f"[Learning] LLM error: {e}")
        state["pending_response"] = "Sorry, I didn't catch that. Could you say it again?"
        state["needs_user_input"] = True
        return state

    # Parse structured response
    parse_result = parse_llm_response(response, default_action="continue")
    action = parse_result.action

    # Apply guardrails
    action, was_modified = validate_and_sanitize(
        response=response,
        node_type="learning",
        parsed_action=action,
        state=state,
    )

    if was_modified:
        agent_guardrail_fallbacks.labels(node="learning").inc()

    # Log metrics
    agent_v2_parse_success.labels(
        node="learning",
        success=str(parse_result.success).lower()
    ).inc()

    # Log usage for A/B analytics
    await prompt_service.log_usage(
        session_id=session_id,
        user_id=user_id,
        node_type="learning_session",
        template=template,
        variant=template.variant if template else "fallback",
        turn_number=turn_count,
        llm_response=response,
        parsed_action=action,
        parse_success=parse_result.success,
        latency_ms=latency_ms,
    )

    # Apply action to state
    state = _apply_learning_action(state, action, pedagogy)

    # Update conversation history
    if user_message:
        state["conversation_history"] = conversation_history + [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": action.get("response_text", "")},
        ]

    # Log decision
    add_decision_log(
        state,
        node="learning",
        action=action.get("action", "continue"),
        reason=f"Turn {turn_count} (strategy={parse_result.strategy})",
        data={
            "corrections": len(action.get("corrections", [])),
            "vocabulary": len(action.get("vocabulary_emphasized", [])),
        },
    )

    logger.info(
        f"[Learning] User {user_id}: turn={turn_count}, action={action.get('action')}"
    )

    return state


def _apply_learning_action(
    state: AgentState,
    action: dict,
    pedagogy,
) -> AgentState:
    """Apply parsed LLM action to state.

    Args:
        state: Current state
        action: Parsed action dict
        pedagogy: Pedagogy logger

    Returns:
        Updated state
    """
    action_type = action.get("action", "continue")
    response_text = action.get("response_text", "")

    # Always set response
    state["pending_response"] = response_text
    state["needs_user_input"] = True

    # Track corrections
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

    # Track vocabulary
    vocabulary = action.get("vocabulary_emphasized", [])
    if vocabulary:
        existing_vocab = state.get("vocabulary_reviewed", [])
        state["vocabulary_reviewed"] = existing_vocab + [
            {"word": word, "turn": state.get("turn_count", 0)}
            for word in vocabulary
        ]

    # Handle mode change request
    mode_request = action.get("detected_mode_request")
    if mode_request:
        try:
            # Get old mode before changing
            old_mode = state.get("current_mode", "free_conversation")
            from_mode_str = old_mode.value if hasattr(old_mode, "value") else str(old_mode)

            new_mode = LearningMode(mode_request)
            state["current_mode"] = new_mode
            state["system_prompt"] = None  # Force rebuild

            pedagogy.log_mode_changed(
                user_id=state["user_id"],
                from_mode=from_mode_str,
                to_mode=mode_request,
                trigger="user_request",
            )
        except ValueError:
            logger.warning(f"Invalid mode request: {mode_request}")

    # Handle session end
    if action.get("should_end"):
        state["should_end_session"] = True

    # Save memory if extracted
    memory = action.get("memory_to_save")
    if memory:
        existing_memories = state.get("new_memories_to_save", [])
        state["new_memories_to_save"] = existing_memories + [
            {"content": memory, "turn": state.get("turn_count", 0)}
        ]

    return state


def _build_template_context(state: AgentState) -> dict:
    """Build context dict for template rendering.

    Args:
        state: Agent state

    Returns:
        Context dict for Jinja2
    """
    # Get current mode
    current_mode = state.get("current_mode")
    if hasattr(current_mode, "value"):
        current_mode = current_mode.value

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
        "vocabulary_list": _format_vocabulary_list(state),
        "memory_section": state.get("memory_section", ""),
        "corrections_made": state.get("corrections_made", []),
        "vocabulary_reviewed": state.get("vocabulary_reviewed", []),
    }


def _format_vocabulary_list(state: AgentState) -> str:
    """Format vocabulary list for prompt."""
    words = state.get("due_vocabulary_words", [])
    if not words:
        return ""
    return ", ".join(words[:10])


def _get_fallback_prompt(state: AgentState) -> str:
    """Get fallback prompt when template not available."""
    username = state.get("username", "Student")
    level = state.get("language_level", "B1")
    goal = state.get("confirmed_goal", "General Fluency")
    current_mode = state.get("current_mode")
    if hasattr(current_mode, "value"):
        current_mode = current_mode.value

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
        style_hint = track_styles.get(track.get("id", "hr_intro"), "Focus on clear, structured professional communication.")

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


def route_after_learning(state: AgentState) -> str:
    """Conditional edge function after learning.

    Routes to:
    - "wait_for_input": Pause graph, wait for user response (routes to END)
    - "session_end": End session

    Args:
        state: Current agent state

    Returns:
        Next node name or "wait_for_input" to pause
    """
    # Check if we should end
    if state.get("should_end_session"):
        return "session_end"

    # Pause for user input (route to END)
    # Learning node always sets needs_user_input=True
    return "wait_for_input"
