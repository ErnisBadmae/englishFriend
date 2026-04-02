"""Tests for the internal markdown skill and tool registries."""

from app.services.ai.mode_prompts import LearningMode
from app.services.skills.registry import get_skill_registry, render_skill_instructions
from app.services.skills.tool_registry import get_internal_tool_registry


def test_internal_skill_registry_loads_mode_skills():
    registry = get_skill_registry()

    baseline = registry.get("baseline_assessment")
    assert baseline is not None
    assert baseline.kind == "coach_mode"
    assert "assessment" in baseline.trigger_modes


def test_internal_skill_registry_resolves_mode_skill():
    registry = get_skill_registry()

    skill = registry.get_for_mode(LearningMode.ASSESSMENT.value)
    assert skill is not None
    assert skill.id == "baseline_assessment"


def test_render_skill_instructions_injects_context():
    registry = get_skill_registry()
    skill = registry.get("baseline_assessment")

    rendered = render_skill_instructions(
        skill,
        {
            "username": "Dana",
            "goal": "ML interviews",
            "goal_field": "machine learning",
            "level": "B1",
        },
    )

    assert "Dana" in rendered
    assert "ML interviews" in rendered
    assert "one short question at a time" in rendered


def test_internal_tool_registry_lists_expected_tools():
    registry = get_internal_tool_registry()

    assert registry.get("browser_vosk_stt") is not None
    assert registry.get("learning_plan_state") is not None
    assert len(registry.list()) >= 5
