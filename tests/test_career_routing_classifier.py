from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.nodes_v2.onboarding import onboarding_node
from app.agent.state import AgentPhase, create_initial_state
from app.core.config import settings
from app.services.routing.career_classifier import (
    LLMCareerRoutingClassifier,
    CareerRoutingClassifierResult,
    arbitrate_career_routing,
)


@pytest.mark.asyncio
async def test_llm_career_routing_classifier_parses_valid_json():
    fake_llm = MagicMock(
        generate=AsyncMock(
            return_value="""
            {
              "primary_context": "project_walkthrough",
              "secondary_contexts": ["interviews"],
              "confidence": 0.91,
              "requires_confirmation": true,
              "explicit_correction_detected": false,
              "negated_contexts": [],
              "target_role": "ML Engineer",
              "domain": "machine_learning",
              "target_market": "international_company",
              "reason_codes": ["technical_project_signal"],
              "evidence_spans": ["architecture tradeoff", "latency"]
            }
            """
        )
    )

    with patch(
        "app.services.routing.career_classifier.get_llm_provider",
        return_value=fake_llm,
    ):
        classifier = LLMCareerRoutingClassifier(model_version="test-model")
        result = await classifier.classify(
            transcript_text="I need to explain one architecture tradeoff in my project.",
            latest_user_message="I need to explain one architecture tradeoff in my project.",
            existing_goal_brief={},
        )

    assert result.primary_context == "project_walkthrough"
    assert result.secondary_contexts == ("interviews",)
    assert result.confidence == pytest.approx(0.91)
    assert result.target_role == "ML Engineer"
    assert result.domain == "machine_learning"
    assert result.target_market == "international_company"
    assert result.model_version == "test-model"


def test_shadow_mode_keeps_legacy_even_when_classifier_disagrees():
    lexical_goal_brief = {"main_contexts": ["interviews"], "target_role": "ML Engineer"}
    classifier_result = CareerRoutingClassifierResult(
        primary_context="workplace_communication",
        secondary_contexts=("project_walkthrough",),
        confidence=0.94,
        target_role="ML Engineer",
        domain="machine_learning",
        target_market="international_company",
        reason_codes=("stakeholder_signal",),
        classifier_source="llm",
        model_version="test-model",
    )

    decision = arbitrate_career_routing(
        existing_goal_brief={},
        lexical_goal_brief=lexical_goal_brief,
        classifier_result=classifier_result,
        transcript_text="I need interview English for recruiter calls.",
        mode="shadow",
        min_confidence=0.72,
    )

    assert decision.applied_source == "legacy"
    assert decision.applied_classifier is False
    assert decision.goal_brief_update == lexical_goal_brief
    assert decision.disagreement is True


def test_gate_mode_applies_classifier_when_legacy_is_ambiguous():
    classifier_result = CareerRoutingClassifierResult(
        primary_context="project_walkthrough",
        secondary_contexts=("interviews",),
        confidence=0.88,
        target_role="ML Engineer",
        domain="machine_learning",
        target_market="international_company",
        reason_codes=("project_story",),
        classifier_source="llm",
        model_version="test-model",
    )

    decision = arbitrate_career_routing(
        existing_goal_brief={},
        lexical_goal_brief=None,
        classifier_result=classifier_result,
        transcript_text="I need to explain what I built and why the tradeoff mattered.",
        mode="gate",
        min_confidence=0.72,
    )

    assert decision.applied_source == "classifier"
    assert decision.applied_classifier is True
    assert decision.goal_brief_update is not None
    assert decision.goal_brief_update["main_contexts"][0] == "project_walkthrough"
    assert decision.goal_brief_update["routing_decision_source"] == "classifier_inferred"


def test_mainline_mode_falls_back_to_legacy_on_low_confidence():
    lexical_goal_brief = {"main_contexts": ["interviews"], "target_role": "ML Engineer"}
    classifier_result = CareerRoutingClassifierResult(
        primary_context="workplace_communication",
        confidence=0.51,
        target_role="ML Engineer",
        domain="machine_learning",
        target_market="international_company",
        classifier_source="llm",
        model_version="test-model",
    )

    decision = arbitrate_career_routing(
        existing_goal_brief={},
        lexical_goal_brief=lexical_goal_brief,
        classifier_result=classifier_result,
        transcript_text="I need interview help.",
        mode="mainline",
        min_confidence=0.72,
    )

    assert decision.applied_source == "legacy"
    assert decision.applied_classifier is False
    assert decision.goal_brief_update == lexical_goal_brief


@pytest.mark.asyncio
async def test_onboarding_node_uses_classifier_mainline_for_weak_lexical_case():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["last_question_type"] = "goal_setup"
    state["last_user_message"] = "I need help for hiring soon."

    classifier_result = CareerRoutingClassifierResult(
        primary_context="interviews",
        secondary_contexts=("project_walkthrough",),
        confidence=0.93,
        target_role="ML Engineer",
        domain="machine_learning",
        target_market="international_company",
        reason_codes=("hiring_context",),
        classifier_source="llm",
        model_version="test-model",
    )

    previous_mode = settings.career_routing_classifier_mode
    try:
        settings.career_routing_classifier_mode = "mainline"
        with patch(
            "app.agent.nodes_v2.onboarding.classify_career_routing",
            AsyncMock(return_value=classifier_result),
        ), patch(
            "app.agent.nodes_v2.onboarding.get_prompt_service",
            return_value=MagicMock(log_usage=AsyncMock()),
        ), patch(
            "app.agent.nodes_v2.onboarding.get_pedagogy_logger",
            return_value=MagicMock(),
        ), patch(
            "app.agent.nodes_v2.onboarding.get_llm_provider",
            return_value=MagicMock(generate=AsyncMock(return_value="{}")),
        ):
            updated = await onboarding_node(state)
    finally:
        settings.career_routing_classifier_mode = previous_mode

    assert updated["goal_setup_complete"] is True
    assert updated["current_phase"] == AgentPhase.LEARNING_SESSION
    assert updated["mission_task_type"] == "foundation_speaking_drill"
    assert updated["goal_brief"]["main_contexts"][0] == "interviews"
    assert updated["goal_brief"]["routing_decision_source"] == "classifier_inferred"
    assert "real mission" in updated["pending_response"].lower()
