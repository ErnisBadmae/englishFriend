import pytest

from app.agent.intent_policy import build_intent_context_from_state, classify_intent
from app.agent.intent_policy.taxonomy import INTENT_TAXONOMY_V1
from app.agent.intent_policy.types import IntentContext, IntentType
from app.agent.state import AgentPhase, LearningModeEnum, create_initial_state


def test_intent_taxonomy_v1_stays_bounded_to_eight_classes():
    assert len(INTENT_TAXONOMY_V1) == 8
    assert {spec.type for spec in INTENT_TAXONOMY_V1} == {
        IntentType.DIRECT_ANSWER,
        IntentType.LOW_SIGNAL_NOISE,
        IntentType.SUPPORT_REQUEST,
        IntentType.LEXICAL_CONFUSION,
        IntentType.ANSWER_SHIFT_NEXT_ANCHOR,
        IntentType.META_PROGRESS,
        IntentType.OFF_TOPIC,
        IntentType.END_REQUEST,
    }


def test_build_intent_context_from_state_extracts_bounded_fields():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["current_phase"] = AgentPhase.ASSESSMENT
    state["current_mode"] = LearningModeEnum.ASSESSMENT
    state["mission_task_type"] = "foundation_speaking_drill"
    state["anchor_question_id"] = 1
    state["anchor_follow_up_pending"] = True
    state["goal_setup_complete"] = True
    state["assessment_step_index"] = 2
    state["low_signal_turn_streak"] = 1
    state["last_question_type"] = "project_task"

    context = build_intent_context_from_state(state)

    assert context.phase == "assessment"
    assert context.current_mode == "assessment"
    assert context.mission_task_type == "foundation_speaking_drill"
    assert context.anchor_question_id == 1
    assert context.anchor_follow_up_pending is True
    assert context.goal_setup_complete is True
    assert context.assessment_step_index == 2
    assert context.low_signal_turn_streak == 1
    assert context.last_question_type == "project_task"


def test_support_request_is_classified_by_fast_path():
    result = classify_intent(
        "sorry my english is very bad could you teach me",
        IntentContext(mission_task_type="foundation_speaking_drill"),
    )

    assert result.type == IntentType.SUPPORT_REQUEST
    assert result.classifier_source == "fast_rule"
    assert "support_request_pattern" in result.reason_codes


def test_lexical_confusion_is_classified_by_fast_path():
    result = classify_intent(
        "what does elaborate mean",
        IntentContext(mission_task_type="foundation_speaking_drill"),
    )

    assert result.type == IntentType.LEXICAL_CONFUSION
    assert result.classifier_source == "fast_rule"


def test_low_signal_noise_sets_composer_hint_on_repeat_context():
    result = classify_intent(
        "now sorry one two three four five test",
        IntentContext(mission_task_type="foundation_speaking_drill", low_signal_turn_streak=1),
    )

    assert result.type == IntentType.LOW_SIGNAL_NOISE
    assert result.needs_composer_hint is True
    assert result.classifier_source == "fast_rule"


def test_meta_progress_is_classified_by_fast_path():
    result = classify_intent(
        "continue",
        IntentContext(phase="assessment"),
    )

    assert result.type == IntentType.META_PROGRESS
    assert result.classifier_source == "fast_rule"


def test_end_request_is_classified_by_fast_path():
    result = classify_intent(
        "stop here",
        IntentContext(phase="learning_session"),
    )

    assert result.type == IntentType.END_REQUEST
    assert result.classifier_source == "fast_rule"


def test_unclassified_turn_falls_back_to_direct_answer():
    result = classify_intent(
        "I work as a data scientist and build recommendation models.",
        IntentContext(mission_task_type="foundation_speaking_drill"),
    )

    assert result.type == IntentType.DIRECT_ANSWER
    assert result.classifier_source == "fallback"
    assert result.confidence == pytest.approx(0.6)
