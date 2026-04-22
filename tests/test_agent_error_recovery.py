"""Tests for mission-safe runtime recovery.

Covers:
- ``build_mission_safe_recovery`` returns the pinned template per task type.
- Stage-level fallback kicks in when mission_task_type is empty.
- Generic fallback is only returned when both mission and stage are unknown.
- None of the recovery strings regress to the legacy "I'm having trouble"
  phrasing that synthetic eval treats as a runtime leak.
"""

from __future__ import annotations

import pytest

from app.agent.recovery import build_mission_safe_recovery


_LEAK_PHRASES = ("i'm having trouble", "server error. please refresh")


def _assert_no_legacy_leak(text: str) -> None:
    lowered = text.lower()
    for phrase in _LEAK_PHRASES:
        assert phrase not in lowered, f"recovery text leaked legacy phrase: {phrase}"


@pytest.mark.parametrize(
    "mission_task_type, expected_fragment",
    [
        ("foundation_speaking_drill", "current role"),
        ("stakeholder_explanation_drill", "non-technical"),
        ("technical_project_walkthrough", "problem"),
    ],
)
def test_mission_specific_template(
    mission_task_type: str, expected_fragment: str
) -> None:
    text = build_mission_safe_recovery(mission_task_type=mission_task_type)
    assert expected_fragment.lower() in text.lower()
    _assert_no_legacy_leak(text)


def test_unknown_mission_falls_back_to_stage_template() -> None:
    onboarding = build_mission_safe_recovery(
        mission_task_type=None, stage="onboarding"
    )
    assert "interviews" in onboarding.lower()
    _assert_no_legacy_leak(onboarding)

    learning = build_mission_safe_recovery(mission_task_type="", stage="learning")
    assert "focused" in learning.lower() or "continue" in learning.lower()
    _assert_no_legacy_leak(learning)


def test_generic_fallback_when_everything_unknown() -> None:
    text = build_mission_safe_recovery(mission_task_type=None, stage=None)
    assert text.strip()
    _assert_no_legacy_leak(text)


def test_mission_takes_precedence_over_stage() -> None:
    # Mission-specific template must win even if stage is also set.
    text = build_mission_safe_recovery(
        mission_task_type="foundation_speaking_drill",
        stage="learning",
    )
    assert "current role" in text.lower()
    _assert_no_legacy_leak(text)


def test_case_insensitive_mission_lookup() -> None:
    text = build_mission_safe_recovery(
        mission_task_type="  Foundation_Speaking_Drill  "
    )
    assert "current role" in text.lower()
