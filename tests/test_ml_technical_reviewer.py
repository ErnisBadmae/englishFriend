"""Tests for `ml_technical_reviewer.py` rubric partition enforcement.

Covers: valid partition + deterministic score, incomplete / overlapping /
unknown / low-confidence / malformed results fail-closed, and incorrect-
claims capping below the pass threshold.
"""

import pytest

from app.services.ml_technical_reviewer import (
    _parse_review_payload,
    review_technical_answer,
)

# A minimal 3-point rubric question fixture.
_SAMPLE_QUESTION = {
    "id": "mltech_sample",
    "topic_id": "dl_training",
    "question_ru": "Test question",
    "rubric_points": [
        {"id": "p1", "point_ru": "Point one"},
        {"id": "p2", "point_ru": "Point two"},
        {"id": "p3", "point_ru": "Point three"},
    ],
    "reference_explanation_ru": "Ref explanation",
    "follow_ups": ["?", "??"],
    "rubric_version": "ml-technical-v1",
    "provenance_id": "prov:sample",
    "track_id": "ml_technical",
    "difficulty": "easy",
    "tags": ["test"],
}


@pytest.mark.asyncio
async def test_provider_creation_failure_returns_needs_review(monkeypatch):
    def fail_provider_creation():
        raise RuntimeError("provider configuration failed")

    monkeypatch.setattr(
        "app.services.ml_technical_reviewer.get_llm_provider",
        fail_provider_creation,
    )

    outcome = await review_technical_answer(
        question=_SAMPLE_QUESTION,
        answer_text="some answer",
    )

    assert outcome.status == "needs_review"
    assert outcome.failure_reason == "provider_error"


# ---------------------------------------------------------------------------
# _parse_review_payload — valid partition
# ---------------------------------------------------------------------------


def test_valid_partition_yields_deterministic_score():
    """All 3 points covered → deterministic score = 3/3 * 100 = 100."""
    outcome = _parse_review_payload(
        {
            "score_percent": 80,
            "covered_points": ["p1", "p2", "p3"],
            "missing_points": [],
            "incorrect_claims": [],
            "feedback": "Great job",
            "follow_up_question": "Tell me more",
            "confidence": 0.9,
        },
        question=_SAMPLE_QUESTION,
        model_id="test-model",
        rubric_version="v1",
    )
    assert outcome.status == "graded"
    assert outcome.score_percent == 100.0
    assert outcome.covered_points == ["p1", "p2", "p3"]
    assert outcome.missing_points == []


def test_valid_partition_partial_coverage():
    """2 of 3 covered → deterministic score = 2/3 * 100 = 66.7."""
    outcome = _parse_review_payload(
        {
            "score_percent": 90,
            "covered_points": ["p1", "p2"],
            "missing_points": ["p3"],
            "incorrect_claims": [],
            "feedback": "Good but missed p3",
            "follow_up_question": "What about p3?",
            "confidence": 0.9,
        },
        question=_SAMPLE_QUESTION,
        model_id="test-model",
        rubric_version="v1",
    )
    assert outcome.status == "graded"
    assert outcome.score_percent == 66.7


def test_valid_partition_all_missing():
    """All 3 missing → deterministic score = 0."""
    outcome = _parse_review_payload(
        {
            "score_percent": 10,
            "covered_points": [],
            "missing_points": ["p1", "p2", "p3"],
            "incorrect_claims": [],
            "feedback": "No points covered",
            "follow_up_question": "Please study more",
            "confidence": 0.8,
        },
        question=_SAMPLE_QUESTION,
        model_id="test-model",
        rubric_version="v1",
    )
    assert outcome.status == "graded"
    assert outcome.score_percent == 0.0


# ---------------------------------------------------------------------------
# Incomplete partition (missing point IDs from union)
# ---------------------------------------------------------------------------


def test_incomplete_partition_missing_from_union_fails():
    """Only p1 covered, p2 missing, p3 absent → invalid_schema."""
    with pytest.raises(ValueError, match="rubric partition incomplete"):
        _parse_review_payload(
            {
                "score_percent": 33.3,
                "covered_points": ["p1"],
                "missing_points": ["p2"],
                "incorrect_claims": [],
                "feedback": "ok",
                "follow_up_question": "ok",
                "confidence": 0.9,
            },
            question=_SAMPLE_QUESTION,
            model_id="test-model",
            rubric_version="v1",
        )


# ---------------------------------------------------------------------------
# Overlapping partition
# ---------------------------------------------------------------------------


def test_overlapping_partition_fails():
    """p1 appears in both covered and missing → invalid_schema."""
    with pytest.raises(ValueError, match="share IDs"):
        _parse_review_payload(
            {
                "score_percent": 50,
                "covered_points": ["p1", "p2"],
                "missing_points": ["p1", "p3"],
                "incorrect_claims": [],
                "feedback": "overlap",
                "follow_up_question": "overlap",
                "confidence": 0.9,
            },
            question=_SAMPLE_QUESTION,
            model_id="test-model",
            rubric_version="v1",
        )


# ---------------------------------------------------------------------------
# Unknown point IDs
# ---------------------------------------------------------------------------


def test_unknown_covered_point_id_fails():
    with pytest.raises(ValueError, match="unknown covered_point id"):
        _parse_review_payload(
            {
                "score_percent": 50,
                "covered_points": ["p1", "pFake"],
                "missing_points": ["p2", "p3"],
                "incorrect_claims": [],
                "feedback": "ok",
                "follow_up_question": "ok",
                "confidence": 0.9,
            },
            question=_SAMPLE_QUESTION,
            model_id="test-model",
            rubric_version="v1",
        )


def test_unknown_missing_point_id_fails():
    with pytest.raises(ValueError, match="unknown missing_point id"):
        _parse_review_payload(
            {
                "score_percent": 50,
                "covered_points": ["p1", "p2"],
                "missing_points": ["pFake"],
                "incorrect_claims": [],
                "feedback": "ok",
                "follow_up_question": "ok",
                "confidence": 0.9,
            },
            question=_SAMPLE_QUESTION,
            model_id="test-model",
            rubric_version="v1",
        )


# ---------------------------------------------------------------------------
# Low confidence gate
# ---------------------------------------------------------------------------


def test_low_confidence_returns_needs_review():
    """Confidence below 0.6 → needs_review with low_confidence."""
    outcome = _parse_review_payload(
        {
            "score_percent": 100,
            "covered_points": ["p1", "p2", "p3"],
            "missing_points": [],
            "incorrect_claims": [],
            "feedback": "ok",
            "follow_up_question": "ok",
            "confidence": 0.45,
        },
        question=_SAMPLE_QUESTION,
        model_id="test-model",
        rubric_version="v1",
    )
    assert outcome.status == "needs_review"
    assert outcome.failure_reason == "low_confidence"


def test_confidence_at_threshold_passes():
    """Confidence exactly 0.6 should pass (>= 0.6)."""
    outcome = _parse_review_payload(
        {
            "score_percent": 100,
            "covered_points": ["p1", "p2", "p3"],
            "missing_points": [],
            "incorrect_claims": [],
            "feedback": "ok",
            "follow_up_question": "ok",
            "confidence": 0.6,
        },
        question=_SAMPLE_QUESTION,
        model_id="test-model",
        rubric_version="v1",
    )
    assert outcome.status == "graded"


# ---------------------------------------------------------------------------
# Incorrect claims cap
# ---------------------------------------------------------------------------


def test_incorrect_claims_cap_score_below_threshold():
    """100% coverage with incorrect_claims → score capped below 60.0."""
    outcome = _parse_review_payload(
        {
            "score_percent": 100,
            "covered_points": ["p1", "p2", "p3"],
            "missing_points": [],
            "incorrect_claims": ["Wrong fact about backpropagation"],
            "feedback": "Good but has errors",
            "follow_up_question": "What about backprop?",
            "confidence": 0.9,
        },
        question=_SAMPLE_QUESTION,
        model_id="test-model",
        rubric_version="v1",
    )
    assert outcome.status == "graded"
    assert outcome.score_percent < 60.0
    assert outcome.score_percent == 59.9


def test_incorrect_claims_with_low_base_score_stays_low():
    """2/3 covered (66.7) with incorrect claims → min(66.7, 59.9) = 59.9."""
    outcome = _parse_review_payload(
        {
            "score_percent": 70,
            "covered_points": ["p1", "p2"],
            "missing_points": ["p3"],
            "incorrect_claims": ["small error"],
            "feedback": "ok",
            "follow_up_question": "ok",
            "confidence": 0.9,
        },
        question=_SAMPLE_QUESTION,
        model_id="test-model",
        rubric_version="v1",
    )
    assert outcome.status == "graded"
    assert outcome.score_percent == 59.9


# ---------------------------------------------------------------------------
# Malformed payloads fail closed
# ---------------------------------------------------------------------------


def test_missing_required_keys_raises():
    with pytest.raises(ValueError, match="missing required keys"):
        _parse_review_payload(
            {
                "score_percent": 50,
                "covered_points": ["p1", "p2", "p3"],
                "missing_points": [],
            },
            question=_SAMPLE_QUESTION,
            model_id="test-model",
            rubric_version="v1",
        )


def test_empty_feedback_raises():
    with pytest.raises(ValueError, match="feedback is empty"):
        _parse_review_payload(
            {
                "score_percent": 100,
                "covered_points": ["p1", "p2", "p3"],
                "missing_points": [],
                "incorrect_claims": [],
                "feedback": "",
                "follow_up_question": "ok",
                "confidence": 0.9,
            },
            question=_SAMPLE_QUESTION,
            model_id="test-model",
            rubric_version="v1",
        )


def test_empty_follow_up_raises():
    with pytest.raises(ValueError, match="follow_up_question is empty"):
        _parse_review_payload(
            {
                "score_percent": 100,
                "covered_points": ["p1", "p2", "p3"],
                "missing_points": [],
                "incorrect_claims": [],
                "feedback": "ok",
                "follow_up_question": "",
                "confidence": 0.9,
            },
            question=_SAMPLE_QUESTION,
            model_id="test-model",
            rubric_version="v1",
        )


def test_invalid_score_raises():
    with pytest.raises(ValueError, match="score_percent is not a valid number"):
        _parse_review_payload(
            {
                "score_percent": "not_a_number",
                "covered_points": ["p1", "p2", "p3"],
                "missing_points": [],
                "incorrect_claims": [],
                "feedback": "ok",
                "follow_up_question": "ok",
                "confidence": 0.9,
            },
            question=_SAMPLE_QUESTION,
            model_id="test-model",
            rubric_version="v1",
        )


# ---------------------------------------------------------------------------
# Model ID, prompt version, rubric version are preserved
# ---------------------------------------------------------------------------


def test_outcome_preserves_metadata():
    outcome = _parse_review_payload(
        {
            "score_percent": 100,
            "covered_points": ["p1", "p2", "p3"],
            "missing_points": [],
            "incorrect_claims": [],
            "feedback": "ok",
            "follow_up_question": "ok",
            "confidence": 0.9,
        },
        question=_SAMPLE_QUESTION,
        model_id="gpt-4-turbo",
        rubric_version="ml-technical-v2",
    )
    assert outcome.model_id == "gpt-4-turbo"
    assert outcome.prompt_version == "ml-technical-review-v1"
    assert outcome.rubric_version == "ml-technical-v2"


# ---------------------------------------------------------------------------
# review_technical_answer — empty answer fails closed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_answer_returns_needs_review():
    """An empty answer string should not call the provider."""
    outcome = await review_technical_answer(
        question=_SAMPLE_QUESTION,
        answer_text="",
    )
    assert outcome.status == "needs_review"
    assert outcome.failure_reason == "empty_answer"


@pytest.mark.asyncio
async def test_empty_answer_text_strips_and_fails():
    """Whitespace-only answer should also fail closed."""
    outcome = await review_technical_answer(
        question=_SAMPLE_QUESTION,
        answer_text="   \n\t  ",
    )
    assert outcome.status == "needs_review"
    assert outcome.failure_reason == "empty_answer"


# ---------------------------------------------------------------------------
# Duplicate rubric IDs fail closed
# ---------------------------------------------------------------------------


def test_duplicate_covered_point_id_fails():
    """Duplicate ID inside covered_points → invalid_schema."""
    with pytest.raises(ValueError, match="duplicate covered_point id"):
        _parse_review_payload(
            {
                "score_percent": 50,
                "covered_points": ["p1", "p1", "p2"],
                "missing_points": ["p3"],
                "incorrect_claims": [],
                "feedback": "ok",
                "follow_up_question": "ok",
                "confidence": 0.9,
            },
            question=_SAMPLE_QUESTION,
            model_id="test-model",
            rubric_version="v1",
        )


def test_duplicate_missing_point_id_fails():
    """Duplicate ID inside missing_points → invalid_schema."""
    with pytest.raises(ValueError, match="duplicate missing_point id"):
        _parse_review_payload(
            {
                "score_percent": 50,
                "covered_points": ["p1", "p2"],
                "missing_points": ["p3", "p3"],
                "incorrect_claims": [],
                "feedback": "ok",
                "follow_up_question": "ok",
                "confidence": 0.9,
            },
            question=_SAMPLE_QUESTION,
            model_id="test-model",
            rubric_version="v1",
        )


# ---------------------------------------------------------------------------
# Invalid confidence fails as schema error
# ---------------------------------------------------------------------------


def test_non_numeric_confidence_raises():
    """Non-numeric confidence → schema error via needs_review."""
    with pytest.raises(ValueError, match="confidence is not a valid number"):
        _parse_review_payload(
            {
                "score_percent": 100,
                "covered_points": ["p1", "p2", "p3"],
                "missing_points": [],
                "incorrect_claims": [],
                "feedback": "ok",
                "follow_up_question": "ok",
                "confidence": "not_a_number",
            },
            question=_SAMPLE_QUESTION,
            model_id="test-model",
            rubric_version="v1",
        )


def test_confidence_out_of_range_raises():
    """Confidence > 1.0 → schema error via needs_review."""
    with pytest.raises(ValueError, match="confidence out of range"):
        _parse_review_payload(
            {
                "score_percent": 100,
                "covered_points": ["p1", "p2", "p3"],
                "missing_points": [],
                "incorrect_claims": [],
                "feedback": "ok",
                "follow_up_question": "ok",
                "confidence": 1.5,
            },
            question=_SAMPLE_QUESTION,
            model_id="test-model",
            rubric_version="v1",
        )


def test_covered_points_not_array_raises():
    """covered_points as a string instead of array → invalid_schema."""
    with pytest.raises(ValueError, match="covered_points must be a JSON array"):
        _parse_review_payload(
            {
                "score_percent": 100,
                "covered_points": "p1",
                "missing_points": ["p2", "p3"],
                "incorrect_claims": [],
                "feedback": "ok",
                "follow_up_question": "ok",
                "confidence": 0.9,
            },
            question=_SAMPLE_QUESTION,
            model_id="test-model",
            rubric_version="v1",
        )


def test_missing_points_not_array_raises():
    """missing_points as a number instead of array → invalid_schema."""
    with pytest.raises(ValueError, match="missing_points must be a JSON array"):
        _parse_review_payload(
            {
                "score_percent": 100,
                "covered_points": ["p1", "p2", "p3"],
                "missing_points": 0,
                "incorrect_claims": [],
                "feedback": "ok",
                "follow_up_question": "ok",
                "confidence": 0.9,
            },
            question=_SAMPLE_QUESTION,
            model_id="test-model",
            rubric_version="v1",
        )
