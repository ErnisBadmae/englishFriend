"""Tests for the scope-dependent classifier gate predicate.

Plan contract (scalable-booping-quilt.md, "Classifier stays inside in-scope ambiguity only"):
  Gate fires only when ALL hold:
    - scope_status == "in_scope"
    - ambiguous_legacy
    - classifier_eligible (semantic_safe + min_confidence + classifier_primary)
    - lexical_primary is not None
    - semantic_slot_validity is True
"""

from app.services.routing.career_classifier import (
    CareerRoutingClassifierResult,
    arbitrate_career_routing,
)


def _classifier_result(
    *,
    primary_context: str = "project_walkthrough",
    confidence: float = 0.88,
) -> CareerRoutingClassifierResult:
    return CareerRoutingClassifierResult(
        primary_context=primary_context,
        secondary_contexts=("interviews",),
        confidence=confidence,
        target_role="ML Engineer",
        domain="machine_learning",
        target_market="international_company",
        intent_action=primary_context,
        audience="technical_audience",
        artifact_focus="project_architecture_tradeoff_impact",
        job_process_stage="project_story_preparation",
        reason_codes=(primary_context,),
        classifier_source="llm",
        model_version="test-model",
    )


_AMBIGUOUS_LEXICAL = {
    "primary_goal": "Explain my ML projects during interviews",
    "target_role": "ML Engineer",
    "domain": "machine_learning",
    "main_contexts": ["interviews"],
}
_AMBIGUOUS_TRANSCRIPT = "I need to explain my project during interviews."


def test_gate_skipped_when_scope_status_is_needs_narrowing():
    decision = arbitrate_career_routing(
        existing_goal_brief={},
        lexical_goal_brief=_AMBIGUOUS_LEXICAL,
        classifier_result=_classifier_result(),
        transcript_text=_AMBIGUOUS_TRANSCRIPT,
        mode="gate",
        min_confidence=0.72,
        scope_status="needs_narrowing",
    )
    assert decision.applied_source == "legacy"
    assert decision.applied_classifier is False
    assert decision.scoped_gate_applied is False
    assert decision.scope_status == "needs_narrowing"


def test_gate_skipped_when_scope_status_is_generic_english_only():
    decision = arbitrate_career_routing(
        existing_goal_brief={},
        lexical_goal_brief=_AMBIGUOUS_LEXICAL,
        classifier_result=_classifier_result(),
        transcript_text=_AMBIGUOUS_TRANSCRIPT,
        mode="gate",
        min_confidence=0.72,
        scope_status="generic_english_only",
    )
    assert decision.applied_source == "legacy"
    assert decision.applied_classifier is False
    assert decision.scoped_gate_applied is False
    assert decision.scope_status == "generic_english_only"


def test_gate_skipped_when_lexical_primary_is_missing():
    decision = arbitrate_career_routing(
        existing_goal_brief={},
        lexical_goal_brief=None,
        classifier_result=_classifier_result(),
        transcript_text=_AMBIGUOUS_TRANSCRIPT,
        mode="gate",
        min_confidence=0.72,
        scope_status="in_scope",
    )
    assert decision.applied_source == "fallback"
    assert decision.applied_classifier is False
    assert decision.scoped_gate_applied is False


def test_gate_skipped_when_classifier_below_min_confidence():
    decision = arbitrate_career_routing(
        existing_goal_brief={},
        lexical_goal_brief=_AMBIGUOUS_LEXICAL,
        classifier_result=_classifier_result(confidence=0.50),
        transcript_text=_AMBIGUOUS_TRANSCRIPT,
        mode="gate",
        min_confidence=0.72,
        scope_status="in_scope",
    )
    assert decision.applied_source == "legacy"
    assert decision.applied_classifier is False
    assert decision.scoped_gate_applied is False


def test_gate_applies_classifier_when_all_predicates_hold():
    decision = arbitrate_career_routing(
        existing_goal_brief={},
        lexical_goal_brief=_AMBIGUOUS_LEXICAL,
        classifier_result=_classifier_result(),
        transcript_text=_AMBIGUOUS_TRANSCRIPT,
        mode="gate",
        min_confidence=0.72,
        scope_status="in_scope",
    )
    assert decision.applied_source == "classifier"
    assert decision.applied_classifier is True
    assert decision.scoped_gate_applied is True
    assert decision.scope_status == "in_scope"


def test_mainline_mode_also_respects_scope_status():
    """Even in mainline, classifier must not override out-of-scope cases."""
    decision = arbitrate_career_routing(
        existing_goal_brief={},
        lexical_goal_brief=_AMBIGUOUS_LEXICAL,
        classifier_result=_classifier_result(),
        transcript_text=_AMBIGUOUS_TRANSCRIPT,
        mode="mainline",
        min_confidence=0.72,
        scope_status="generic_english_only",
    )
    assert decision.applied_source == "legacy"
    assert decision.applied_classifier is False


def test_shadow_mode_records_scope_status_without_overriding():
    decision = arbitrate_career_routing(
        existing_goal_brief={},
        lexical_goal_brief=_AMBIGUOUS_LEXICAL,
        classifier_result=_classifier_result(),
        transcript_text=_AMBIGUOUS_TRANSCRIPT,
        mode="shadow",
        min_confidence=0.72,
        scope_status="in_scope",
    )
    assert decision.applied_source == "legacy"
    assert decision.applied_classifier is False
    assert decision.scope_status == "in_scope"
    assert decision.scoped_gate_applied is False
