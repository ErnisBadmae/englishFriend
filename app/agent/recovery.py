"""Mission-safe recovery prompts for runtime failures.

When an LLM call fails mid-turn, we should not drop the user into a generic
"I'm having trouble" apology. Instead, we keep the session productive by
pinning the next utterance to the current mission's task type so the user
can simply continue speaking on the same drill.

Recovery templates are short, unambiguous, and self-contained — safe to emit
without any LLM round-trip.
"""

from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# Mission-specific recovery templates
# ---------------------------------------------------------------------------

_MISSION_RECOVERY_TEMPLATES: dict[str, str] = {
    "foundation_speaking_drill": (
        "Let's keep it simple. In one sentence — what's your current role, "
        "and where do you feel your English blocks you most?"
    ),
    "stakeholder_explanation_drill": (
        "Let's try once more. Explain your work to a non-technical colleague "
        "in 1-2 simple sentences."
    ),
    "technical_project_walkthrough": (
        "Let's walk through one project using this pattern: "
        "problem → approach → metric → impact. Start with the problem."
    ),
}

# ---------------------------------------------------------------------------
# Stage-specific fallbacks when mission_task_type is unknown
# ---------------------------------------------------------------------------

_STAGE_RECOVERY_TEMPLATES: dict[str, str] = {
    "onboarding": (
        "Let's keep going. Tell me in one sentence what you want to practice "
        "in English — interviews, team meetings, or project walkthroughs?"
    ),
    "assessment": (
        "Let's take it once more. In one sentence, tell me about your current "
        "role and what kind of English tasks you do every week."
    ),
    "learning": (
        "Let's keep it focused. In one or two sentences, continue where we "
        "left off — what were you about to say?"
    ),
}

_GENERIC_RECOVERY = (
    "Let's keep going. In one sentence, tell me what you'd like to focus on "
    "next in English."
)


def build_mission_safe_recovery(
    mission_task_type: Optional[str] = None,
    stage: Optional[str] = None,
) -> str:
    """Return a mission-safe recovery prompt for a failed turn.

    Preference order:
    1. Mission-specific template matching ``mission_task_type``.
    2. Stage-specific template matching ``stage`` (onboarding | assessment | learning).
    3. Generic focus question — only when nothing more specific is known.
    """
    if mission_task_type:
        template = _MISSION_RECOVERY_TEMPLATES.get(str(mission_task_type).strip().lower())
        if template:
            return template

    if stage:
        template = _STAGE_RECOVERY_TEMPLATES.get(str(stage).strip().lower())
        if template:
            return template

    return _GENERIC_RECOVERY


__all__ = ["build_mission_safe_recovery"]
