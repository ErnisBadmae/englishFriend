"""Guardrails for LLM agent control.

Provides validation and safety mechanisms for LLM responses:
- Response length limits
- Forbidden content patterns
- Required field validation
- Action whitelist per node
- Confidence thresholds
- Rate limiting support
- Safe fallback responses
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ============ CONFIGURATION ============

# Maximum response length (characters)
MAX_RESPONSE_LENGTH = 500

# Maximum turns per session (rate limiting)
MAX_TURNS_PER_SESSION = 100

# Maximum turns per minute (abuse prevention)
MAX_TURNS_PER_MINUTE = 10

# Confidence thresholds for LLM decisions
CONFIDENCE_THRESHOLDS = {
    "goal_detection": 0.7,      # Require 70% confidence to detect goal
    "assessment_level": 0.6,    # 60% for level assessment
    "interest_extraction": 0.5, # 50% for interest detection
}

# Forbidden patterns (safety - sensitive data, harmful content)
FORBIDDEN_PATTERNS = [
    r"(?i)(password|credit.?card|ssn|social.?security)",
    r"(?i)(kill|harm|attack|hack)\s+(yourself|someone|people)",
    r"(?i)(api.?key|secret.?key|private.?key)",
    r"(?i)(bank.?account|routing.?number)",
]

FOUNDATION_FALLBACK_QUESTIONS = (
    "What do you do now, and what kind of ML work do you touch?",
    "Tell me about one recent ML project. What problem were you solving?",
    "What is your next step in our program, and which skill do you want to improve first?",
)

# Required JSON fields by node type
REQUIRED_FIELDS = {
    "onboarding": ["action", "response_text"],
    "learning": ["action", "response_text"],
    "session_end": ["action", "response_text"],
    "router": [],  # Router doesn't generate response_text
}

# Valid actions per node type (whitelist)
VALID_ACTIONS = {
    "router": {"route_onboarding", "route_learning", "route_session_end"},
    "onboarding": {
        "ask_goal",
        "confirm_goal",
        "goal_confirmed",
        "goal_skipped",
        "ask_interests",
        "interests_confirmed",
        "ask_assessment",
        "assessment_complete",
        "transition_to_learning",
    },
    "learning": {
        "continue",
        "mode_change",
        "error_correction",
        "vocabulary_emphasis",
        "end_session",
    },
    "session_end": {"farewell"},
}


# ============ VALIDATION FUNCTIONS ============

def validate_response(
    response: str,
    node_type: str,
    parsed_action: dict,
) -> tuple[bool, list[str]]:
    """Validate LLM response against guardrails.

    Args:
        response: Raw LLM response text
        node_type: Type of node (onboarding, learning, session_end, router)
        parsed_action: Parsed action dict from response

    Returns:
        Tuple of (is_valid, list_of_violations)
    """
    violations = []

    # 1. Length check
    response_text = parsed_action.get("response_text", "")
    if response_text and len(response_text) > MAX_RESPONSE_LENGTH:
        violations.append(
            f"Response too long: {len(response_text)} > {MAX_RESPONSE_LENGTH} chars"
        )

    # 2. Forbidden content check
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, response_text):
            violations.append(f"Forbidden pattern detected")
            logger.warning(f"[Guardrails] Forbidden pattern in response: {pattern}")
            break  # Don't expose which pattern matched

    # 3. Required fields check
    required = REQUIRED_FIELDS.get(node_type, [])
    for field in required:
        if not parsed_action.get(field):
            violations.append(f"Missing required field: {field}")

    # 4. Action validity check (whitelist)
    valid_actions = VALID_ACTIONS.get(node_type, set())
    if valid_actions:
        action = parsed_action.get("action", "")
        if action and action not in valid_actions:
            violations.append(f"Invalid action '{action}' for node '{node_type}'")
            logger.warning(f"[Guardrails] Invalid action: {action} not in {valid_actions}")

    # Log validation result
    if violations:
        logger.warning(
            f"[Guardrails] Validation failed for {node_type}: {violations}"
        )
    else:
        logger.debug(f"[Guardrails] Validation passed for {node_type}")

    return len(violations) == 0, violations


def validate_confidence(
    action: dict,
    threshold_key: str,
) -> bool:
    """Check if confidence exceeds threshold for a decision.

    Args:
        action: Parsed action dict with optional 'confidence' field
        threshold_key: Key in CONFIDENCE_THRESHOLDS (e.g., 'goal_detection')

    Returns:
        True if confidence >= threshold, False otherwise
    """
    confidence = action.get("confidence", 0.5)
    threshold = CONFIDENCE_THRESHOLDS.get(threshold_key, 0.5)

    meets_threshold = confidence >= threshold

    if not meets_threshold:
        logger.debug(
            f"[Guardrails] Confidence {confidence:.2f} below threshold "
            f"{threshold:.2f} for {threshold_key}"
        )

    return meets_threshold


def check_rate_limit(
    turn_count: int,
    max_turns: int = MAX_TURNS_PER_SESSION,
) -> tuple[bool, Optional[str]]:
    """Check if session has exceeded turn limit.

    Args:
        turn_count: Current turn count
        max_turns: Maximum allowed turns

    Returns:
        Tuple of (is_allowed, message_if_blocked)
    """
    if turn_count >= max_turns:
        logger.info(f"[Guardrails] Rate limit reached: {turn_count} >= {max_turns}")
        return False, "We've had a great long session! Let's take a break and continue later."

    return True, None


# ============ FALLBACK RESPONSES ============

def apply_fallback(
    node_type: str,
    state: dict,
    violations: Optional[list[str]] = None,
) -> dict:
    """Generate safe fallback response when validation fails.

    Args:
        node_type: Type of node that failed validation
        state: Current agent state
        violations: List of validation violations (for logging)

    Returns:
        Safe fallback action dict
    """
    username = state.get("username", "there")

    if violations:
        logger.warning(
            f"[Guardrails] Applying fallback for {node_type} due to: {violations}"
        )

    learning_fallback = "Could you tell me more about that?"
    mission_task_type = state.get("mission_task_type")
    if mission_task_type in {"foundation_speaking_drill", "grammar_rescue"}:
        anchor_index = int(state.get("anchor_question_id", 0) or 0)
        anchor_index = max(0, min(anchor_index, len(FOUNDATION_FALLBACK_QUESTIONS) - 1))
        learning_fallback = (
            "Let's stay with today's drill. "
            f"{FOUNDATION_FALLBACK_QUESTIONS[anchor_index]}"
        )

    fallbacks = {
        "onboarding": {
            "action": "ask_goal",
            "response_text": (
                f"I'd love to help you learn English, {username}! "
                f"What's your main goal - is it for work, travel, or something else?"
            ),
        },
        "learning": {
            "action": "continue",
            "response_text": learning_fallback,
        },
        "session_end": {
            "action": "farewell",
            "response_text": (
                f"Thanks for practicing today, {username}! "
                f"You're making great progress. See you next time!"
            ),
        },
        "router": {
            "action": "route_onboarding",
            "next_node": "onboarding",
        },
    }

    fallback = fallbacks.get(node_type, {
        "action": "continue",
        "response_text": "I didn't quite catch that. Could you say it again?",
    })

    logger.info(f"[Guardrails] Fallback applied: {fallback.get('action')}")
    return fallback


# ============ CONTENT SANITIZATION ============

def sanitize_response(response_text: str) -> str:
    """Sanitize response text for safety.

    Removes or masks potentially harmful content while
    preserving the overall message.

    Args:
        response_text: Original response text

    Returns:
        Sanitized response text
    """
    sanitized = response_text

    # Truncate if too long
    if len(sanitized) > MAX_RESPONSE_LENGTH:
        # Find a good breaking point
        truncated = sanitized[:MAX_RESPONSE_LENGTH]
        last_sentence = truncated.rfind('.')
        if last_sentence > MAX_RESPONSE_LENGTH * 0.7:
            sanitized = truncated[:last_sentence + 1]
        else:
            sanitized = truncated.rstrip() + "..."

    # Remove any forbidden patterns (replace with generic text)
    for pattern in FORBIDDEN_PATTERNS:
        sanitized = re.sub(pattern, "[removed]", sanitized, flags=re.IGNORECASE)

    return sanitized


# ============ COMPREHENSIVE VALIDATION ============

def validate_and_sanitize(
    response: str,
    node_type: str,
    parsed_action: dict,
    state: dict,
) -> tuple[dict, bool]:
    """Validate response and apply fixes or fallback if needed.

    This is the main entry point for guardrails - it validates
    the response and either returns a sanitized version or
    a safe fallback.

    Args:
        response: Raw LLM response
        node_type: Type of node
        parsed_action: Parsed action dict
        state: Current agent state

    Returns:
        Tuple of (final_action_dict, was_modified)
    """
    is_valid, violations = validate_response(response, node_type, parsed_action)

    if is_valid:
        # Response is valid, just sanitize the text
        if "response_text" in parsed_action:
            parsed_action["response_text"] = sanitize_response(
                parsed_action["response_text"]
            )
        return parsed_action, False

    # Response failed validation - try to fix or fallback

    # Check if we can fix by sanitization
    if "response_text" in parsed_action:
        sanitized_text = sanitize_response(parsed_action["response_text"])
        parsed_action["response_text"] = sanitized_text

        # Re-validate after sanitization
        is_valid_after, _ = validate_response(response, node_type, parsed_action)
        if is_valid_after:
            return parsed_action, True

    # Can't fix - apply fallback
    fallback = apply_fallback(node_type, state, violations)
    return fallback, True


__all__ = [
    "validate_response",
    "validate_confidence",
    "check_rate_limit",
    "apply_fallback",
    "sanitize_response",
    "validate_and_sanitize",
    "MAX_RESPONSE_LENGTH",
    "MAX_TURNS_PER_SESSION",
    "CONFIDENCE_THRESHOLDS",
]
