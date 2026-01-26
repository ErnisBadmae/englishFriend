"""LLM Response Parser for structured agent outputs.

Extracts JSON actions from LLM responses with multiple fallback strategies.
"""

import json
import logging
import re
from typing import TypedDict, Optional, Any

logger = logging.getLogger(__name__)


class ParsedAction(TypedDict, total=False):
    """Structured action parsed from LLM response."""
    action: str
    response_text: str
    extracted_data: dict
    next_phase: str
    confidence: float
    corrections: list[dict]
    vocabulary_emphasized: list[str]
    detected_mode_request: Optional[str]
    should_end: bool
    memory_to_save: Optional[str]
    session_summary: dict


class ParseResult:
    """Result of parsing attempt."""

    def __init__(
        self,
        action: ParsedAction,
        success: bool = True,
        strategy: str = "direct",
        raw_response: str = "",
    ):
        self.action = action
        self.success = success
        self.strategy = strategy
        self.raw_response = raw_response

    @property
    def response_text(self) -> str:
        """Get response text from parsed action."""
        return self.action.get("response_text", "")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "action": self.action,
            "success": self.success,
            "strategy": self.strategy,
        }


def parse_llm_response(
    response: str,
    expected_schema: Optional[dict] = None,
    default_action: str = "continue",
) -> ParseResult:
    """Parse LLM response into structured action.

    Strategies (tried in order):
    1. Direct JSON parse
    2. Extract from ```json code block
    3. Find JSON object anywhere in response
    4. Regex extraction of key fields
    5. Fallback with raw response as text

    Args:
        response: Raw LLM response string
        expected_schema: Optional JSON schema for validation
        default_action: Default action if parsing fails

    Returns:
        ParseResult with parsed action and metadata
    """
    if not response or not response.strip():
        return ParseResult(
            action=_create_fallback_action("", default_action),
            success=False,
            strategy="empty",
            raw_response="",
        )

    response = response.strip()

    # Strategy 1: Direct JSON parse
    try:
        parsed = json.loads(response)
        if isinstance(parsed, dict) and "response_text" in parsed:
            return ParseResult(
                action=_normalize_action(parsed),
                success=True,
                strategy="direct",
                raw_response=response,
            )
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown code block
    code_block_match = re.search(
        r'```(?:json)?\s*(\{[\s\S]*?\})\s*```',
        response,
        re.DOTALL
    )
    if code_block_match:
        try:
            parsed = json.loads(code_block_match.group(1))
            if isinstance(parsed, dict):
                return ParseResult(
                    action=_normalize_action(parsed),
                    success=True,
                    strategy="code_block",
                    raw_response=response,
                )
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find JSON object anywhere in response
    json_match = re.search(
        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
        response,
        re.DOTALL
    )
    if json_match:
        try:
            parsed = json.loads(json_match.group(0))
            if isinstance(parsed, dict):
                return ParseResult(
                    action=_normalize_action(parsed),
                    success=True,
                    strategy="json_search",
                    raw_response=response,
                )
        except json.JSONDecodeError:
            pass

    # Strategy 4: Try to find nested JSON (handle escaped quotes)
    try:
        # Sometimes LLM returns JSON with extra escaping
        cleaned = response.replace('\\"', '"').replace('\\n', '\n')
        json_match = re.search(r'\{[\s\S]*\}', cleaned)
        if json_match:
            parsed = json.loads(json_match.group(0))
            if isinstance(parsed, dict):
                return ParseResult(
                    action=_normalize_action(parsed),
                    success=True,
                    strategy="cleaned_json",
                    raw_response=response,
                )
    except (json.JSONDecodeError, Exception):
        pass

    # Strategy 5: Regex extraction for key fields
    extracted = _extract_fields_regex(response)
    if extracted.get("response_text"):
        return ParseResult(
            action=_normalize_action(extracted),
            success=True,
            strategy="regex",
            raw_response=response,
        )

    # Strategy 6: Fallback - use response as text
    logger.warning(f"Failed to parse LLM response, using fallback. Response: {response[:200]}...")
    return ParseResult(
        action=_create_fallback_action(response, default_action),
        success=False,
        strategy="fallback",
        raw_response=response,
    )


def _normalize_action(parsed: dict) -> ParsedAction:
    """Normalize parsed dict to ParsedAction format."""
    action: ParsedAction = {
        "action": parsed.get("action", "continue"),
        "response_text": parsed.get("response_text", ""),
    }

    # Copy optional fields if present
    optional_fields = [
        "extracted_data", "next_phase", "confidence", "corrections",
        "vocabulary_emphasized", "detected_mode_request", "should_end",
        "memory_to_save", "session_summary"
    ]

    for field in optional_fields:
        if field in parsed:
            action[field] = parsed[field]

    return action


def _extract_fields_regex(text: str) -> dict:
    """Extract key fields using regex patterns."""
    result = {}

    # Extract action
    action_match = re.search(r'"action"\s*:\s*"([^"]+)"', text)
    if action_match:
        result["action"] = action_match.group(1)

    # Extract response_text (may be multiline)
    response_match = re.search(
        r'"response_text"\s*:\s*"((?:[^"\\]|\\.)*)?"',
        text,
        re.DOTALL
    )
    if response_match:
        # Unescape
        response_text = response_match.group(1)
        response_text = response_text.replace('\\"', '"').replace('\\n', '\n')
        result["response_text"] = response_text

    # Extract confidence
    confidence_match = re.search(r'"confidence"\s*:\s*([0-9.]+)', text)
    if confidence_match:
        try:
            result["confidence"] = float(confidence_match.group(1))
        except ValueError:
            pass

    # Extract should_end
    should_end_match = re.search(r'"should_end"\s*:\s*(true|false)', text, re.IGNORECASE)
    if should_end_match:
        result["should_end"] = should_end_match.group(1).lower() == "true"

    return result


def _create_fallback_action(response: str, default_action: str) -> ParsedAction:
    """Create fallback action from raw response."""
    # Clean response of any JSON artifacts
    cleaned = _clean_response(response)

    return ParsedAction(
        action=default_action,
        response_text=cleaned,
        confidence=0.2,
    )


def _clean_response(text: str) -> str:
    """Remove JSON artifacts from response for fallback."""
    if not text:
        return "I'm sorry, could you repeat that?"

    # Remove JSON-like patterns
    text = re.sub(r'\{[^{}]*\}', '', text)
    text = re.sub(r'```[\s\S]*?```', '', text)

    # Remove common JSON field names
    text = re.sub(r'"(action|response_text|extracted_data|confidence)":\s*', '', text)

    # Clean up whitespace
    text = ' '.join(text.split())

    return text.strip() or "I'm sorry, could you repeat that?"


def validate_action(
    action: ParsedAction,
    node_type: str,
    required_fields: Optional[list[str]] = None,
) -> tuple[bool, list[str]]:
    """Validate parsed action against expected schema.

    Args:
        action: Parsed action to validate
        node_type: Node type for action validation
        required_fields: List of required fields

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check required fields
    required = required_fields or ["response_text"]
    for field in required:
        if not action.get(field):
            errors.append(f"Missing required field: {field}")

    # Validate action by node type
    valid_actions_by_node = {
        "onboarding": {
            "ask_goal", "confirm_goal", "goal_confirmed", "goal_skipped",
            "ask_interests", "interests_confirmed",
            "ask_assessment", "assessment_complete",
            "transition_to_learning"
        },
        "learning_session": {
            "continue", "mode_change", "error_correction",
            "vocabulary_emphasis", "end_session"
        },
        "session_end": {
            "farewell"
        },
    }

    if node_type in valid_actions_by_node:
        valid_actions = valid_actions_by_node[node_type]
        if action.get("action") not in valid_actions:
            errors.append(f"Invalid action '{action.get('action')}' for node_type '{node_type}'")

    # Validate confidence range
    confidence = action.get("confidence")
    if confidence is not None and (confidence < 0 or confidence > 1):
        errors.append(f"Confidence {confidence} out of range [0, 1]")

    return len(errors) == 0, errors


def extract_goal_from_action(action: ParsedAction) -> Optional[str]:
    """Extract detected goal from parsed action.

    Args:
        action: Parsed action

    Returns:
        Goal slug or None
    """
    extracted_data = action.get("extracted_data", {})
    if isinstance(extracted_data, dict):
        return extracted_data.get("goal")
    return None


def extract_interests_from_action(action: ParsedAction) -> list[str]:
    """Extract interests from parsed action.

    Args:
        action: Parsed action

    Returns:
        List of interests
    """
    extracted_data = action.get("extracted_data", {})
    if isinstance(extracted_data, dict):
        interests = extracted_data.get("interests", [])
        if isinstance(interests, list):
            return interests
    return []


def extract_assessment_from_action(action: ParsedAction) -> tuple[Optional[str], Optional[dict]]:
    """Extract assessment data from parsed action.

    Args:
        action: Parsed action

    Returns:
        Tuple of (assessed_level, assessment_scores)
    """
    extracted_data = action.get("extracted_data", {})
    if isinstance(extracted_data, dict):
        level = extracted_data.get("assessed_level")
        scores = extracted_data.get("assessment_scores")
        return level, scores
    return None, None
