"""Turn Processor Node - handles individual conversation turns.

This node processes each user message:
1. Check for mode change requests
2. Check for session end requests
3. Generate LLM response with current mode prompt
4. Extract vocabulary from response
5. Detect and log errors
6. Trigger memory extraction periodically
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from app.agent.state import AgentState, AgentPhase, LearningModeEnum, add_decision_log
from app.services.pedagogy_logger import get_pedagogy_logger
from app.services.ai.llm_provider import get_llm_provider
from app.services.ai.mode_prompts import LearningMode, get_session_greeting

logger = logging.getLogger(__name__)


async def turn_processor_node(state: AgentState) -> AgentState:
    """Node that processes a single conversation turn.

    Handles:
    - User message processing
    - LLM response generation
    - Error detection (for Socratic recast)
    - Vocabulary extraction
    - Conversation history management

    Args:
        state: Current agent state

    Returns:
        Updated agent state with response
    """
    pedagogy = get_pedagogy_logger(state["user_id"])
    llm = get_llm_provider()

    user_message = state.get("last_user_message", "")

    # Check for session end request
    if _is_end_request(user_message):
        state["should_end_session"] = True
        state["current_phase"] = AgentPhase.SESSION_END
        state["needs_user_input"] = False

        add_decision_log(
            state,
            node="turn_processor",
            action="session_end_requested",
            reason="User requested to end session",
        )

        return state

    # Check for mode change request
    requested_mode = _parse_mode_change(user_message)
    if requested_mode and requested_mode != state.get("current_mode"):
        old_mode = state.get("current_mode", LearningModeEnum.FREE_CONVERSATION)
        state["current_mode"] = requested_mode

        # Rebuild system prompt for new mode
        from app.agent.nodes.mode_router import _build_system_prompt
        state["system_prompt"] = _build_system_prompt(state, requested_mode)

        # Send mode change acknowledgment
        greeting = get_session_greeting(
            LearningMode(requested_mode.value),
            state.get("username", "there"),
        )

        state["pending_response"] = f"Sure! Switching to {requested_mode.value.replace('_', ' ')} mode. {greeting}"
        state["needs_user_input"] = True

        pedagogy.log_mode_changed(
            user_id=state["user_id"],
            from_mode=old_mode.value,
            to_mode=requested_mode.value,
            trigger="user_request",
        )

        add_decision_log(
            state,
            node="turn_processor",
            action="mode_changed",
            reason=f"User requested mode change to {requested_mode.value}",
            data={"old_mode": old_mode.value, "new_mode": requested_mode.value},
        )

        return state

    # Normal turn processing
    if user_message:
        # Increment turn count
        turn_count = state.get("turn_count", 0) + 1
        state["turn_count"] = turn_count

        # Add user message to history
        conversation_history = state.get("conversation_history", [])
        conversation_history.append({"role": "user", "content": user_message})

        # Generate LLM response
        try:
            system_prompt = state.get("system_prompt", "")
            if not system_prompt:
                from app.agent.nodes.mode_router import _build_system_prompt
                system_prompt = _build_system_prompt(
                    state,
                    state.get("current_mode", LearningModeEnum.FREE_CONVERSATION),
                )
                state["system_prompt"] = system_prompt

            response_text = await llm.generate(
                user_message=user_message,
                system_prompt=system_prompt,
                conversation_history=conversation_history[-18:],  # Keep last 18 for context
                max_tokens=250,  # Enough for detailed explanations
            )

            # Add response to history
            conversation_history.append({"role": "assistant", "content": response_text})

            # Limit history length
            if len(conversation_history) > 20:
                conversation_history = conversation_history[-20:]

            state["conversation_history"] = conversation_history
            state["pending_response"] = response_text
            state["needs_user_input"] = True

            # Extract vocabulary from response (words in CAPS are emphasized)
            _extract_vocabulary(state, response_text)

            # Detect errors for future reference
            _detect_errors(state, user_message)

            # Trigger memory extraction periodically (every 5 turns)
            if turn_count % 5 == 0:
                state["new_memories_to_save"].append({
                    "trigger": "periodic",
                    "turn": turn_count,
                    "recent_messages": conversation_history[-10:],
                })

            add_decision_log(
                state,
                node="turn_processor",
                action="turn_processed",
                reason=f"Turn {turn_count} completed",
                data={
                    "mode": state.get("current_mode", LearningModeEnum.FREE_CONVERSATION).value,
                    "user_msg_len": len(user_message),
                    "response_len": len(response_text),
                },
            )

            logger.info(f"[TurnProcessor] Turn {turn_count} processed, "
                       f"mode={state.get('current_mode', LearningModeEnum.FREE_CONVERSATION).value}")

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            state["pending_response"] = (
                "I'm having a bit of trouble right now. "
                "Could you repeat what you said?"
            )
            state["needs_user_input"] = True

            add_decision_log(
                state,
                node="turn_processor",
                action="llm_error",
                reason=str(e),
            )

    return state


def _is_end_request(message: str) -> bool:
    """Check if user wants to end the session.

    Args:
        message: User's message

    Returns:
        True if end request detected
    """
    if not message:
        return False

    message_lower = message.lower().strip()

    end_keywords = [
        "bye", "goodbye", "see you", "gotta go",
        "end session", "stop", "quit", "exit",
        "пока", "до свидания", "всё", "хватит",
        "that's all", "i'm done", "let's stop",
    ]

    return any(kw in message_lower for kw in end_keywords)


def _parse_mode_change(message: str) -> Optional[LearningModeEnum]:
    """Parse user message for mode change request.

    Args:
        message: User's message

    Returns:
        Requested mode or None
    """
    if not message:
        return None

    message_lower = message.lower()

    # Check for explicit mode requests
    mode_patterns = {
        LearningModeEnum.MOCK_INTERVIEW: [
            "let's do interview", "practice interview",
            "mock interview", "interview mode",
            "давай интервью", "собеседование",
        ],
        LearningModeEnum.VOCABULARY_DRILL: [
            "practice vocabulary", "review words", "vocab drill",
            "повторить слова", "слова",
        ],
        LearningModeEnum.FREE_CONVERSATION: [
            "just chat", "free talk", "just conversation",
            "просто поговорить",
        ],
        LearningModeEnum.GRAMMAR_FOCUS: [
            "practice grammar", "grammar mode",
            "грамматика",
        ],
        LearningModeEnum.ASSESSMENT: [
            "check my level", "assess me",
            "проверить уровень",
        ],
    }

    for mode, patterns in mode_patterns.items():
        if any(p in message_lower for p in patterns):
            return mode

    return None


def _extract_vocabulary(state: AgentState, response: str) -> None:
    """Extract vocabulary words from assistant response.

    Looks for words in CAPS (mentor emphasis) and adds them
    to the vocabulary tracking list.

    Args:
        state: Agent state to update
        response: Assistant's response text
    """
    try:
        # Find words in CAPS (2+ chars to avoid "I", "A")
        caps_words = re.findall(r'\b([A-Z]{2,})\b', response)

        for word in caps_words[:3]:  # Max 3 per turn
            word_lower = word.lower()
            vocabulary_reviewed = state.get("vocabulary_reviewed", [])
            vocabulary_reviewed.append({
                "word": word_lower,
                "context": response[:100],
                "turn": state.get("turn_count", 0),
            })
            state["vocabulary_reviewed"] = vocabulary_reviewed

    except Exception as e:
        logger.debug(f"Error extracting vocabulary: {e}")


def _detect_errors(state: AgentState, user_message: str) -> None:
    """Detect potential grammar/vocabulary errors in user message.

    This is a simple heuristic-based detection. The actual correction
    is done by the LLM via Socratic recast in the prompt.

    Args:
        state: Agent state to update
        user_message: User's message
    """
    try:
        errors_detected = state.get("errors_detected", [])
        message_lower = user_message.lower()

        # Common error patterns for Russian speakers
        error_patterns = [
            # Missing articles
            (r'\b(go to|went to|at) (?!(the|a|an)\b)\w+', "missing_article"),
            # Wrong verb form
            (r"\bhe|she\b.+\b(don't|don't)\b", "verb_agreement"),
            (r'\bi am\s+(agree|think|want)\b', "verb_form"),
            # Preposition errors
            (r'\bdepend from\b', "preposition"),
            (r'\bexplain me\b', "preposition"),
        ]

        for pattern, error_type in error_patterns:
            if re.search(pattern, message_lower):
                errors_detected.append({
                    "type": "grammar",
                    "subtype": error_type,
                    "message": user_message[:50],
                    "turn": state.get("turn_count", 0),
                })
                break  # One error per message is enough

        state["errors_detected"] = errors_detected

    except Exception as e:
        logger.debug(f"Error detecting errors: {e}")


def route_after_turn(state: AgentState) -> str:
    """Conditional edge function to route after turn processing.

    Args:
        state: Current agent state

    Returns:
        Name of the next node
    """
    if state.get("should_end_session"):
        return "session_end"

    # Stay in turn processor for next turn
    return "turn_processor"
