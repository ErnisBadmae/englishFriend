"""Pedagogy logger for tracking educational decisions.

This module provides structured logging for pedagogical decisions
made by the LangGraph agent. It helps developers understand:
- Why certain goals were detected/confirmed
- How interests were identified
- What triggered mode selections
- When and why corrections were made
- Memory retrieval and storage events

All logs use the standard Python logging module and are formatted
for easy parsing and analysis.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Any


logger = logging.getLogger("pedagogy")

_CATEGORY_MARKERS = {
    "GOAL": "GOAL",
    "INTEREST": "INTEREST",
    "ASSESS": "ASSESS",
    "MODE": "MODE",
    "ERROR": "ERROR",
    "CORRECT": "CORRECT",
    "MEMORY": "MEMORY",
    "SESSION": "SESSION",
    "PHASE": "PHASE",
}


def _ascii_safe(value: Optional[Any], limit: Optional[int] = None) -> str:
    """Return a stable ASCII-only representation safe for Windows consoles."""
    text = "" if value is None else str(value)
    if limit is not None and len(text) > limit:
        text = f"{text[:limit]}..."
    return text.encode("ascii", errors="backslashreplace").decode("ascii")


def _preview_text(value: Optional[Any], limit: int) -> str:
    """Render a safe short preview for logs."""
    if value is None:
        return "'<none>'"
    return f"'{_ascii_safe(value, limit)}'"


class PedagogyLogger:
    """Logger for pedagogical decisions and events.

    Provides structured logging methods for key educational moments
    in the conversation. Each method logs at the appropriate level
    and includes relevant context.
    """

    def __init__(self, user_id: Optional[int] = None):
        """Initialize the pedagogy logger.

        Args:
            user_id: Optional user ID to include in all log messages
        """
        self.user_id = user_id

    def _log(
        self,
        level: int,
        emoji: str,
        category: str,
        message: str,
        **kwargs: Any,
    ) -> None:
        """Internal logging method with consistent formatting.

        Args:
            level: Logging level (INFO, DEBUG, etc.)
            emoji: Emoji prefix for visual identification
            category: Category of the log (e.g., "GOAL", "MODE")
            message: Main log message
            **kwargs: Additional context to include
        """
        del emoji
        user_prefix = f"[user:{self.user_id}] " if self.user_id else ""
        context = " ".join(
            f"{_ascii_safe(k)}={_ascii_safe(v, 120)}" for k, v in kwargs.items()
        ) if kwargs else ""

        log_message = (
            f"[PEDAGOGY] {_CATEGORY_MARKERS.get(category, category)} "
            f"[{_ascii_safe(category)}] {user_prefix}{_ascii_safe(message, 240)}"
        )
        if context:
            log_message += f" | {context}"

        logger.log(level, log_message)

    # === Goal Detection & Confirmation ===

    def log_goal_detected(
        self,
        user_id: int,
        message: Optional[str],
        goal: str,
        confidence: float = 1.0,
    ) -> None:
        """Log when a goal is detected from user message.

        Args:
            user_id: User ID
            message: User message that triggered detection
            goal: Detected goal
            confidence: Confidence score (0.0 - 1.0)
        """
        self.user_id = user_id
        self._log(
            logging.INFO,
            "\U0001F3AF",  # Target emoji
            "GOAL",
            f"Detected: {goal}",
            confidence=f"{confidence:.2f}",
            from_message=_preview_text(message, 50),
        )

    def log_goal_confirmation_requested(
        self,
        user_id: int,
        goal: str,
        confirmation_prompt: str,
    ) -> None:
        """Log when asking user to confirm detected goal.

        Args:
            user_id: User ID
            goal: Goal being confirmed
            confirmation_prompt: The prompt sent to user
        """
        self.user_id = user_id
        self._log(
            logging.INFO,
            "\u2753",  # Question mark
            "GOAL",
            f"Requesting confirmation: {goal}",
            prompt=_preview_text(confirmation_prompt, 50),
        )

    def log_goal_confirmed(
        self,
        user_id: int,
        goal: str,
        user_response: str,
    ) -> None:
        """Log when user confirms their goal.

        Args:
            user_id: User ID
            goal: Confirmed goal
            user_response: User's confirmation response
        """
        self.user_id = user_id
        self._log(
            logging.INFO,
            "\u2705",  # Checkmark
            "GOAL",
            f"CONFIRMED by user: {goal}",
            response=_preview_text(user_response, 30),
        )

    def log_goal_rejected(
        self,
        user_id: int,
        goal: str,
        user_response: str,
    ) -> None:
        """Log when user rejects detected goal.

        Args:
            user_id: User ID
            goal: Rejected goal
            user_response: User's rejection response
        """
        self.user_id = user_id
        self._log(
            logging.INFO,
            "\u274C",  # Cross mark
            "GOAL",
            f"REJECTED by user: {goal}",
            response=_preview_text(user_response, 30),
        )

    def log_goal_defaulted(
        self,
        user_id: int,
        default_goal: str,
        reason: str,
    ) -> None:
        """Log when falling back to default goal.

        Args:
            user_id: User ID
            default_goal: Default goal being used
            reason: Why default was used
        """
        self.user_id = user_id
        self._log(
            logging.INFO,
            "\U0001F504",  # Arrows (cycle)
            "GOAL",
            f"Defaulted to: {default_goal}",
            reason=reason,
        )

    # === Interest Detection ===

    def log_interests_detected(
        self,
        user_id: int,
        interests: list[str],
        source: str = "conversation",
    ) -> None:
        """Log when interests are detected.

        Args:
            user_id: User ID
            interests: List of detected interests
            source: Where interests were detected from
        """
        self.user_id = user_id
        self._log(
            logging.INFO,
            "\U0001F4A1",  # Light bulb
            "INTEREST",
            f"Detected: {interests}",
            source=source,
        )

    def log_interests_confirmed(
        self,
        user_id: int,
        interests: list[str],
    ) -> None:
        """Log when interests are confirmed.

        Args:
            user_id: User ID
            interests: Confirmed interests
        """
        self.user_id = user_id
        self._log(
            logging.INFO,
            "\u2705",  # Checkmark
            "INTEREST",
            f"Confirmed: {interests}",
        )

    # === Assessment ===

    def log_assessment_started(
        self,
        user_id: int,
        current_level: Optional[str] = None,
    ) -> None:
        """Log when assessment begins.

        Args:
            user_id: User ID
            current_level: User's current level if known
        """
        self.user_id = user_id
        self._log(
            logging.INFO,
            "\U0001F4DD",  # Memo
            "ASSESS",
            "Assessment started",
            current_level=current_level or "unknown",
        )

    def log_assessment_question(
        self,
        user_id: int,
        question_number: int,
        target_level: str,
        question: str,
    ) -> None:
        """Log assessment question asked.

        Args:
            user_id: User ID
            question_number: Question number in sequence
            target_level: CEFR level this question targets
            question: The question asked
        """
        self.user_id = user_id
        self._log(
            logging.DEBUG,
            "\u2753",  # Question mark
            "ASSESS",
            f"Q{question_number} ({target_level}): {question[:50]}...",
        )

    def log_level_assessed(
        self,
        user_id: int,
        level: str,
        scores: dict[str, float],
        confidence: float = 1.0,
    ) -> None:
        """Log final assessment result.

        Args:
            user_id: User ID
            level: Assessed CEFR level
            scores: Detailed scores by category
            confidence: Confidence in assessment
        """
        self.user_id = user_id
        self._log(
            logging.INFO,
            "\U0001F4CA",  # Bar chart
            "ASSESS",
            f"Level assessed: {level}",
            confidence=f"{confidence:.2f}",
            scores=str(scores),
        )

    # === Mode Selection ===

    def log_mode_selected(
        self,
        user_id: int,
        mode: str,
        reason: str,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log learning mode selection.

        Args:
            user_id: User ID
            mode: Selected learning mode
            reason: Why this mode was selected
            context: Additional context (due_vocab, goal, etc.)
        """
        self.user_id = user_id
        extra_kwargs = {}
        if context:
            extra_kwargs = {k: str(v)[:20] for k, v in context.items()}

        self._log(
            logging.INFO,
            "\U0001F500",  # Shuffle
            "MODE",
            f"Selected: {mode}",
            reason=reason,
            **extra_kwargs,
        )

    def log_mode_changed(
        self,
        user_id: int,
        from_mode: str,
        to_mode: str,
        trigger: str,
    ) -> None:
        """Log mode change during session.

        Args:
            user_id: User ID
            from_mode: Previous mode
            to_mode: New mode
            trigger: What triggered the change
        """
        self.user_id = user_id
        self._log(
            logging.INFO,
            "\u27A1\uFE0F",  # Right arrow
            "MODE",
            f"Changed: {from_mode} -> {to_mode}",
            trigger=trigger,
        )

    # === Error Correction ===

    def log_error_detected(
        self,
        user_id: int,
        error_type: str,
        original: str,
        severity: str = "minor",
    ) -> None:
        """Log when a language error is detected.

        Args:
            user_id: User ID
            error_type: Type of error (grammar, vocabulary, pronunciation)
            original: Original text with error
            severity: Error severity (minor, moderate, major)
        """
        self.user_id = user_id
        self._log(
            logging.DEBUG,
            "\U0001F50D",  # Magnifying glass
            "ERROR",
            f"Detected ({error_type}): '{original[:40]}...'",
            severity=severity,
        )

    def log_error_corrected(
        self,
        user_id: int,
        error_type: str,
        original: str,
        corrected: str,
        method: str = "socratic_recast",
    ) -> None:
        """Log when an error is corrected.

        Args:
            user_id: User ID
            error_type: Type of error
            original: Original text
            corrected: Corrected text
            method: Correction method used
        """
        self.user_id = user_id
        self._log(
            logging.INFO,
            "\u270F\uFE0F",  # Pencil
            "CORRECT",
            f"Corrected ({error_type}): '{original[:20]}...' -> '{corrected[:20]}...'",
            method=method,
        )

    # === Memory (RAG) ===

    def log_memory_retrieved(
        self,
        user_id: int,
        count: int,
        query: Optional[str] = None,
    ) -> None:
        """Log memory retrieval from Qdrant.

        Args:
            user_id: User ID
            count: Number of memories retrieved
            query: Search query used
        """
        self.user_id = user_id
        self._log(
            logging.INFO,
            "\U0001F9E0",  # Brain
            "MEMORY",
            f"Retrieved {count} memories",
            query=_preview_text(query, 30) if query else "context",
        )

    def log_memory_saved(
        self,
        user_id: int,
        memory_type: str,
        content_preview: str,
    ) -> None:
        """Log memory saved to Qdrant.

        Args:
            user_id: User ID
            memory_type: Type of memory (fact, preference, skill, etc.)
            content_preview: Preview of saved content
        """
        self.user_id = user_id
        self._log(
            logging.INFO,
            "\U0001F4BE",  # Floppy disk
            "MEMORY",
            f"Saved ({memory_type}): '{content_preview[:40]}...'",
        )

    # === Session Events ===

    def log_session_started(
        self,
        user_id: int,
        session_id: str,
        is_new_user: bool,
    ) -> None:
        """Log session start.

        Args:
            user_id: User ID
            session_id: Session identifier
            is_new_user: Whether this is a new user
        """
        self.user_id = user_id
        user_type = "NEW" if is_new_user else "RETURNING"
        self._log(
            logging.INFO,
            "\U0001F3AC",  # Clapper board
            "SESSION",
            f"Started ({user_type})",
            session_id=session_id[:8],
        )

    def log_session_ended(
        self,
        user_id: int,
        session_id: str,
        turn_count: int,
        duration_minutes: int,
        mode: str,
    ) -> None:
        """Log session end.

        Args:
            user_id: User ID
            session_id: Session identifier
            turn_count: Number of conversation turns
            duration_minutes: Session duration
            mode: Final learning mode
        """
        self.user_id = user_id
        self._log(
            logging.INFO,
            "\U0001F3C1",  # Checkered flag
            "SESSION",
            f"Ended",
            session_id=session_id[:8],
            turns=turn_count,
            duration=f"{duration_minutes}min",
            mode=mode,
        )

    # === Phase Transitions ===

    def log_phase_transition(
        self,
        user_id: int,
        from_phase: str,
        to_phase: str,
        reason: str,
    ) -> None:
        """Log agent phase transition.

        Args:
            user_id: User ID
            from_phase: Previous phase
            to_phase: New phase
            reason: Why transition occurred
        """
        self.user_id = user_id
        self._log(
            logging.INFO,
            "\U0001F504",  # Arrows (cycle)
            "PHASE",
            f"{from_phase} -> {to_phase}",
            reason=reason,
        )


# Global instance for convenience
pedagogy_logger = PedagogyLogger()


def get_pedagogy_logger(user_id: Optional[int] = None) -> PedagogyLogger:
    """Get a pedagogy logger instance.

    Args:
        user_id: Optional user ID to attach to logs

    Returns:
        PedagogyLogger instance
    """
    if user_id:
        return PedagogyLogger(user_id)
    return pedagogy_logger
