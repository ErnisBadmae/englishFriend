"""Minimal internal tool registry for the career coach architecture."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


@dataclass(frozen=True)
class InternalToolDescriptor:
    """Named internal tool boundary."""

    id: str
    title: str
    description: str
    category: str


class InternalToolRegistry:
    """Static registry of internal tools used by the career loop."""

    def __init__(self) -> None:
        self._tools = {
            tool.id: tool
            for tool in (
                InternalToolDescriptor(
                    id="browser_vosk_stt",
                    title="Browser Vosk STT",
                    description="Default low-cost browser-side speech recognition path.",
                    category="speech",
                ),
                InternalToolDescriptor(
                    id="personaplex_realtime",
                    title="PersonaPlex Realtime",
                    description="Experimental realtime speech path for premium voice sessions.",
                    category="speech",
                ),
                InternalToolDescriptor(
                    id="modular_voice_runtime",
                    title="Modular Voice Runtime",
                    description="Feature-flagged voice session controller with pluggable transport, STT, turn detection, and TTS boundaries.",
                    category="speech",
                ),
                InternalToolDescriptor(
                    id="fsrs_scheduler",
                    title="FSRS Scheduler",
                    description="Vocabulary review scheduling and spaced repetition logic.",
                    category="learning",
                ),
                InternalToolDescriptor(
                    id="interview_scoring",
                    title="Interview Scoring",
                    description="Deterministic scoring and feedback for career interview runs.",
                    category="evaluation",
                ),
                InternalToolDescriptor(
                    id="pronunciation_assessment",
                    title="Pronunciation Assessment",
                    description="Speech evidence provider boundary for pronunciation and fluency signals.",
                    category="evaluation",
                ),
                InternalToolDescriptor(
                    id="learning_plan_state",
                    title="Learning Plan State",
                    description="Product state engine for goal, baseline, program, mission, and evidence.",
                    category="state",
                ),
            )
        }

    def list(self) -> tuple[InternalToolDescriptor, ...]:
        return tuple(self._tools.values())

    def get(self, tool_id: str) -> Optional[InternalToolDescriptor]:
        return self._tools.get(tool_id)


@lru_cache(maxsize=1)
def get_internal_tool_registry() -> InternalToolRegistry:
    return InternalToolRegistry()
