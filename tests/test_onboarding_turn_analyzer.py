from unittest.mock import AsyncMock

import pytest

from app.services.onboarding.turn_analyzer import analyze_onboarding_turn


class FakeLLM:
    def __init__(self, response: str):
        self.generate = AsyncMock(return_value=response)


@pytest.mark.asyncio
async def test_turn_analyzer_parses_hr_interview_as_partial_interview_intent():
    llm = FakeLLM(
        """
        {
          "scope_status": "in_scope",
          "main_contexts": ["interviews"],
          "target_role": null,
          "domain": null,
          "target_market": null,
          "next_action": "ask_target_role",
          "confidence": 0.88,
          "rationale": "The learner wants HR interview preparation but did not name a role."
        }
        """
    )

    analysis = await analyze_onboarding_turn(
        user_message="hi, wanna try to prepare to hr interview",
        conversation_history=[],
        existing_goal_brief={},
        llm=llm,
    )

    assert analysis is not None
    assert analysis.scope_status == "in_scope"
    assert analysis.main_contexts == ("interviews",)
    assert analysis.target_role is None
    assert analysis.next_action == "ask_target_role"
    assert analysis.confidence == 0.88
    assert analysis.to_goal_brief_update()["main_contexts"] == ["interviews"]


@pytest.mark.asyncio
async def test_turn_analyzer_rejects_invalid_or_low_value_payload():
    llm = FakeLLM("{}")

    analysis = await analyze_onboarding_turn(
        user_message="zxc",
        conversation_history=[],
        existing_goal_brief={},
        llm=llm,
    )

    assert analysis is not None
    assert analysis.scope_status == "needs_narrowing"
    assert analysis.main_contexts == ()
    assert analysis.confidence == 0.0

