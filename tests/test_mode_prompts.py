"""Tests for md-backed mode prompts with safe fallback behavior."""

from unittest.mock import patch

from app.services.ai.mode_prompts import (
    ASSESSMENT_PROMPT,
    LearningMode,
    build_mode_prompt,
    get_session_greeting,
)


def test_build_mode_prompt_uses_markdown_skill_instructions():
    prompt = build_mode_prompt(
        mode=LearningMode.ASSESSMENT,
        username="Dana",
        goal="Prepare for an ML interview",
        level="B1",
    )

    assert "Dana" in prompt
    assert "one short question at a time" in prompt
    assert "Prepare for an ML interview" in prompt


def test_build_mode_prompt_falls_back_when_skill_missing():
    with patch("app.services.ai.mode_prompts.get_skill_registry") as mocked_registry:
        mocked_registry.return_value.get.return_value = None
        mocked_registry.return_value.get_for_mode.return_value = None

        prompt = build_mode_prompt(
            mode=LearningMode.ASSESSMENT,
            username="Dana",
            goal="Prepare for an ML interview",
            level="B1",
        )

    assert prompt == ASSESSMENT_PROMPT.format(
        username="Dana",
        goal="Prepare for an ML interview",
        goal_field="machine learning and data science",
    )


def test_get_session_greeting_uses_skill_template():
    greeting = get_session_greeting(LearningMode.VOCABULARY_DRILL, username="Dana")

    assert "Dana" in greeting
    assert "review" in greeting.lower()
