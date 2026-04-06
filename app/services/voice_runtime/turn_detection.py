"""Turn detection strategies for the modular voice runtime."""

from __future__ import annotations

from app.services.voice_runtime.base import TurnDetection, TurnDetector


class ExplicitMessageTurnDetector(TurnDetector):
    """Commit turns from explicit transport messages.

    This is the minimal detector for the current Vosk/text protocol:
    - `{"type": "text"}` commits a user turn
    - `{"type": "end"}` ends the session
    - everything else is ignored
    """

    def detect(self, message: dict[str, object]) -> TurnDetection:
        message_type = str(message.get("type", "")).strip().lower()
        if message_type == "end":
            return TurnDetection(disposition="end", reason="explicit_end")

        if message_type != "text":
            return TurnDetection(disposition="ignore", reason="unsupported_message")

        text = str(message.get("text", "")).strip()
        if not text:
            return TurnDetection(disposition="ignore", reason="empty_text")

        return TurnDetection(
            disposition="commit",
            text=text,
            reason="explicit_text",
        )
