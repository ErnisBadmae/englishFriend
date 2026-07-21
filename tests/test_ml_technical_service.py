"""Tests for `ml_technical` selection and progress aggregation.

These exercise the pure, DB-free functions in `app.services.ml_technical_service`
directly with constructed attempt fixtures — the same style already used for
`app.services.interview_service` (no DB fixtures needed to test selection and
aggregation logic).
"""

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api import ml_technical as ml_technical_api
from app.services.ml_technical_service import (
    ANSWER_KIND_DONT_KNOW,
    MlTechnicalConflictError,
    PASS_THRESHOLD_PERCENT,
    REPETITION_DUE_DAYS,
    _attempt_dict,
    compute_question_progress,
    compute_topic_progress,
    compute_track_progress,
    deterministic_dont_know_review,
    question_state,
    select_topic_queue,
)
from app.data.ml_technical_questions import get_ml_technical_question
from app.models.ml_technical import MlTechnicalAttempt
from app.api.ml_technical import SubmitAnswerRequest, SubmitAnswerResponse

# dl_training topic questions, in checked-in pack order.
DL_TRAINING_IDS = ["mltech_001", "mltech_002", "mltech_009", "mltech_010", "mltech_012"]
# transformers_llm topic questions, in checked-in pack order.
TRANSFORMERS_IDS = [
    "mltech_004",
    "mltech_005",
    "mltech_006",
    "mltech_008",
    "mltech_011",
]


def _iso(days_ago: float) -> str:
    return (datetime.utcnow() - timedelta(days=days_ago)).isoformat()


def _attempt(
    question_id: str,
    *,
    days_ago: float,
    status: str,
    score_percent: float | None = None,
) -> dict:
    review: dict = {"status": status}
    if score_percent is not None:
        review["score_percent"] = score_percent
    return {
        "question_id": question_id,
        "topic_id": "dl_training",
        "answered_at": _iso(days_ago),
        "review": review,
    }


# ---------------------------------------------------------------------------
# question_state
# ---------------------------------------------------------------------------


def test_question_state_unseen_when_no_attempts():
    state = question_state("mltech_001", attempts=[])
    assert state["attempted"] is False
    assert state["attempt_count"] == 0
    assert state["passed"] is False
    assert state["failed"] is False
    assert state["due_for_repetition"] is False


def test_question_state_failed_below_threshold():
    attempts = [
        _attempt(
            "mltech_002",
            days_ago=1,
            status="graded",
            score_percent=PASS_THRESHOLD_PERCENT - 10,
        )
    ]
    state = question_state("mltech_002", attempts)
    assert state["attempted"] is True
    assert state["failed"] is True
    assert state["passed"] is False


def test_question_state_passed_and_not_yet_due():
    attempts = [
        _attempt(
            "mltech_010",
            days_ago=0,
            status="graded",
            score_percent=PASS_THRESHOLD_PERCENT + 10,
        )
    ]
    state = question_state("mltech_010", attempts)
    assert state["passed"] is True
    assert state["due_for_repetition"] is False


def test_question_state_passed_and_due_for_repetition():
    attempts = [
        _attempt(
            "mltech_009",
            days_ago=REPETITION_DUE_DAYS + 1,
            status="graded",
            score_percent=PASS_THRESHOLD_PERCENT + 5,
        )
    ]
    state = question_state("mltech_009", attempts)
    assert state["passed"] is True
    assert state["due_for_repetition"] is True


def test_question_state_uses_latest_graded_attempt_not_best():
    attempts = [
        _attempt("mltech_001", days_ago=5, status="graded", score_percent=95.0),
        _attempt("mltech_001", days_ago=1, status="graded", score_percent=40.0),
    ]
    state = question_state("mltech_001", attempts)
    assert state["latest_score"] == 40.0
    assert state["best_score"] == 95.0
    assert state["failed"] is True


def test_question_state_needs_review_does_not_count_as_passed_or_failed():
    attempts = [_attempt("mltech_012", days_ago=20, status="needs_review")]
    state = question_state("mltech_012", attempts)
    assert state["attempted"] is True
    assert state["passed"] is False
    assert state["failed"] is False
    assert state["latest_status"] == "needs_review"


# ---------------------------------------------------------------------------
# select_topic_queue: priority order, no duplicates, determinism.
# ---------------------------------------------------------------------------


def test_select_topic_queue_priority_order_unseen_failed_due_stale():
    attempts = [
        # mltech_001 stays unseen (no attempts).
        _attempt(
            "mltech_002", days_ago=1, status="graded", score_percent=30.0
        ),  # failed
        _attempt(
            "mltech_009",
            days_ago=REPETITION_DUE_DAYS + 5,
            status="graded",
            score_percent=85.0,
        ),  # passed, due
        _attempt(
            "mltech_010", days_ago=0, status="graded", score_percent=90.0
        ),  # passed, not due -> stale bucket
        _attempt(
            "mltech_012", days_ago=20, status="needs_review"
        ),  # needs_review -> stale bucket, oldest
    ]

    ordered = select_topic_queue("dl_training", attempts)

    assert ordered == [
        "mltech_001",
        "mltech_002",
        "mltech_009",
        "mltech_012",
        "mltech_010",
    ]


def test_select_topic_queue_no_duplicates():
    attempts = [
        _attempt("mltech_002", days_ago=1, status="graded", score_percent=30.0),
        _attempt("mltech_002", days_ago=0.5, status="graded", score_percent=25.0),
        _attempt("mltech_009", days_ago=1, status="needs_review"),
    ]
    ordered = select_topic_queue("dl_training", attempts)
    assert sorted(ordered) == sorted(DL_TRAINING_IDS)
    assert len(ordered) == len(set(ordered))


def test_select_topic_queue_deterministic_with_same_seed():
    a = select_topic_queue("transformers_llm", attempts=[], session_seed="seed-abc")
    b = select_topic_queue("transformers_llm", attempts=[], session_seed="seed-abc")
    assert a == b
    assert sorted(a) == sorted(TRANSFORMERS_IDS)


def test_select_topic_queue_varies_with_different_seed():
    orderings = [
        tuple(
            select_topic_queue(
                "transformers_llm", attempts=[], session_seed=f"session-{i}"
            )
        )
        for i in range(20)
    ]
    assert len(set(orderings)) > 1


def test_select_topic_queue_stable_pack_order_without_seed():
    ordered = select_topic_queue("transformers_llm", attempts=[], session_seed=None)
    assert ordered == TRANSFORMERS_IDS


def test_select_topic_queue_unknown_topic_returns_empty():
    assert select_topic_queue("unknown_topic", attempts=[]) == []


# ---------------------------------------------------------------------------
# Progress aggregation: question, topic, track.
# ---------------------------------------------------------------------------


def test_compute_question_progress_reports_required_fields():
    attempts = [_attempt("mltech_002", days_ago=1, status="graded", score_percent=55.0)]
    progress = compute_question_progress("mltech_002", attempts)

    assert progress["question_id"] == "mltech_002"
    assert progress["topic_id"] == "dl_training"
    assert progress["unseen"] is False
    assert progress["attempted"] is True
    assert progress["attempt_count"] == 1
    assert progress["latest_pass"] is False
    assert progress["needs_review"] is False
    assert progress["due_for_repetition"] is False
    assert progress["best_score_percent"] == 55.0
    assert progress["latest_score_percent"] == 55.0
    assert progress["last_attempted_at"] is not None


def test_compute_question_progress_unknown_question_raises():
    try:
        compute_question_progress("mltech_does_not_exist", attempts=[])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown question_id")


def test_compute_topic_progress_aggregates_all_questions_in_topic():
    attempts = [
        _attempt(
            "mltech_002", days_ago=1, status="graded", score_percent=30.0
        ),  # failed
        _attempt(
            "mltech_009", days_ago=1, status="graded", score_percent=85.0
        ),  # passed
        _attempt("mltech_012", days_ago=1, status="needs_review"),  # needs_review
        # mltech_001, mltech_010 stay unseen
    ]
    progress = compute_topic_progress("dl_training", attempts)

    assert progress["topic_id"] == "dl_training"
    assert progress["total_questions"] == 5
    assert progress["unseen"] == 2
    assert progress["attempted"] == 3
    assert progress["passed"] == 1
    assert progress["needs_review"] == 1
    assert len(progress["questions"]) == 5
    assert progress["average_latest_score_percent"] == 57.5  # mean of 30.0 and 85.0


def test_compute_topic_progress_with_no_attempts_is_all_unseen():
    progress = compute_topic_progress("finetuning_peft", attempts=[])
    assert progress["total_questions"] == 2
    assert progress["unseen"] == 2
    assert progress["attempted"] == 0
    assert progress["average_latest_score_percent"] is None


def test_compute_track_progress_sums_across_all_topics():
    attempts = [
        _attempt("mltech_002", days_ago=1, status="graded", score_percent=30.0),
        _attempt("mltech_009", days_ago=1, status="graded", score_percent=85.0),
    ]
    progress = compute_track_progress(attempts)

    assert progress["track_id"] == "ml_technical"
    assert progress["pass_threshold_percent"] == PASS_THRESHOLD_PERCENT
    assert progress["repetition_due_days"] == REPETITION_DUE_DAYS
    assert progress["total_questions"] == 15
    assert progress["passed"] == 1
    assert progress["attempted"] == 2
    assert progress["unseen"] == 13
    assert len(progress["topics"]) == 7
    assert progress["readiness_percent"] == round(1 / 15 * 100, 1)


def test_compute_track_progress_with_no_attempts_has_zero_readiness():
    progress = compute_track_progress(attempts=[])
    assert progress["passed"] == 0
    assert progress["readiness_percent"] == 0.0
    assert progress["unseen"] == 15


# ---------------------------------------------------------------------------
# Append-only: more than former caps preserved
# ---------------------------------------------------------------------------


def test_more_than_max_attempts_preserved():
    """501 attempts for one question should all be kept (former cap was 500)."""
    attempts = [
        _attempt("mltech_001", days_ago=i, status="graded", score_percent=50.0)
        for i in range(501)
    ]
    state = question_state("mltech_001", attempts)
    assert state["attempt_count"] == 501


def test_more_than_max_sessions_preserved():
    """101 session records should all be kept (former cap was 100)."""
    from app.services.ml_technical_service import _empty_ml_technical_roadmap

    roadmap = _empty_ml_technical_roadmap()
    for i in range(101):
        roadmap["sessions"].insert(
            0,
            {
                "session_id": f"sess-{i}",
                "topic_id": "dl_training",
                "question_ids": ["mltech_001"],
                "created_at": _iso(i),
            },
        )
    assert len(roadmap["sessions"]) == 101


def test_more_than_max_external_reviews_preserved():
    """201 external reviews should all be kept (former cap was 200)."""
    from app.services.ml_technical_service import _empty_ml_technical_roadmap

    roadmap = _empty_ml_technical_roadmap()
    for i in range(201):
        roadmap["external_reviews"].insert(
            0,
            {
                "review_id": f"rev-{i}",
                "attempt_id": "att-0",
                "reviewer": f"reviewer-{i}",
                "verdict": "pass",
                "created_at": _iso(i),
            },
        )
    assert len(roadmap["external_reviews"]) == 201


def test_dont_know_review_is_deterministic_and_marks_all_points_missing():
    question = get_ml_technical_question("mltech_001")
    review = deterministic_dont_know_review(question)

    assert review.status == "graded"
    assert review.model_id == "deterministic:dont_know"
    assert review.score_percent == 0.0
    assert review.covered_points == []
    assert review.missing_points == [point["id"] for point in question["rubric_points"]]
    assert review.confidence == 1.0


def test_conflict_error_is_typed_value_error_for_api_mapping():
    assert issubclass(MlTechnicalConflictError, ValueError)


def test_orm_attempt_row_converts_to_original_attempt_dictionary_shape():
    attempt = MlTechnicalAttempt(
        id="00000000-0000-0000-0000-000000000001",
        user_id=11,
        session_id="00000000-0000-0000-0000-000000000002",
        question_id="mltech_001",
        topic_id="dl_training",
        answer_kind=ANSWER_KIND_DONT_KNOW,
        answer_language="ru_knowledge",
        raw_answer="[dont_know]",
        source_channel="web",
        source_event_id=None,
        answered_at=datetime(2026, 7, 21, 12, 0, 0),
        provenance_id="source-q1",
        review={"status": "graded", "score_percent": 0.0},
    )

    converted = _attempt_dict(attempt)

    assert converted == {
        "attempt_id": "00000000-0000-0000-0000-000000000001",
        "session_id": "00000000-0000-0000-0000-000000000002",
        "question_id": "mltech_001",
        "topic_id": "dl_training",
        "answer_kind": "dont_know",
        "answer_language": "ru_knowledge",
        "raw_answer": "[dont_know]",
        "source_channel": "web",
        "source_event_id": None,
        "answered_at": "2026-07-21T12:00:00+00:00",
        "provenance_id": "source-q1",
        "review": {"status": "graded", "score_percent": 0.0},
    }


def test_relational_attempt_dicts_preserve_progress_functions():
    attempts = [
        {
            "attempt_id": "att-1",
            "session_id": "sess-1",
            "question_id": "mltech_001",
            "topic_id": "dl_training",
            "answer_kind": "dont_know",
            "answer_language": "ru_knowledge",
            "raw_answer": "[dont_know]",
            "source_channel": "web",
            "source_event_id": None,
            "answered_at": _iso(0),
            "review": {"status": "graded", "score_percent": 0.0},
        }
    ]

    progress = compute_question_progress("mltech_001", attempts)

    assert progress["attempted"] is True
    assert progress["latest_pass"] is False
    assert progress["latest_score_percent"] == 0.0


def test_submit_answer_request_keeps_backward_compatible_defaults():
    payload = SubmitAnswerRequest(
        session_id="00000000-0000-0000-0000-000000000002",
        question_id="mltech_001",
        answer_text="normal answer",
    )

    assert payload.answer_language == "ru_knowledge"
    assert payload.answer_kind == "normal"
    assert payload.source_channel == "web"
    assert payload.source_event_id is None


def test_submit_answer_request_accepts_empty_text_for_dont_know():
    payload = SubmitAnswerRequest(
        session_id="00000000-0000-0000-0000-000000000002",
        question_id="mltech_001",
        answer_text="",
        answer_kind=ANSWER_KIND_DONT_KNOW,
    )

    assert payload.answer_text == ""
    assert payload.answer_kind == ANSWER_KIND_DONT_KNOW


def test_submit_answer_request_rejects_blank_normal_answer():
    with pytest.raises(ValidationError):
        SubmitAnswerRequest(
            session_id="00000000-0000-0000-0000-000000000002",
            question_id="mltech_001",
            answer_text="   ",
        )


@pytest.mark.asyncio
async def test_submit_answer_endpoint_maps_service_conflict_to_409(monkeypatch):
    class ConflictService:
        def __init__(self, _db):
            pass

        async def submit_answer(self, *_args, **_kwargs):
            raise MlTechnicalConflictError("duplicate ml_technical attempt")

    monkeypatch.setattr(ml_technical_api, "MlTechnicalService", ConflictService)
    payload = SubmitAnswerRequest(
        session_id="00000000-0000-0000-0000-000000000002",
        question_id="mltech_001",
        answer_text="normal answer",
    )

    with pytest.raises(HTTPException) as exc_info:
        await ml_technical_api.submit_ml_technical_answer(11, payload, db=object())

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "duplicate ml_technical attempt"


def test_submit_answer_response_accepts_original_public_shape():
    response = SubmitAnswerResponse.model_validate(
        {
            "attempt_id": "00000000-0000-0000-0000-000000000001",
            "review": {
                "status": "graded",
                "model_id": "deterministic:dont_know",
                "prompt_version": "ml-technical-review-v1",
                "rubric_version": "ml-technical-v1",
                "score_percent": 0.0,
                "covered_points": [],
                "missing_points": ["lr_definition"],
                "covered_points_text": [],
                "missing_points_text": ["LR point"],
                "incorrect_claims": [],
                "feedback": "Ответ не дан.",
                "follow_up_question": None,
                "confidence": 1.0,
                "failure_reason": None,
            },
            "reference_explanation_ru": "reference",
            "next_question": None,
            "question_progress": {
                "question_id": "mltech_001",
                "topic_id": "dl_training",
                "unseen": False,
                "attempted": True,
                "attempt_count": 1,
                "latest_pass": False,
                "needs_review": False,
                "due_for_repetition": False,
                "best_score_percent": 0.0,
                "latest_score_percent": 0.0,
                "last_attempted_at": "2026-07-21T12:00:00+00:00",
            },
            "topic_progress": {
                "topic_id": "dl_training",
                "total_questions": 5,
                "unseen": 4,
                "attempted": 1,
                "passed": 0,
                "needs_review": 0,
                "due_for_repetition": 0,
                "average_latest_score_percent": 0.0,
                "questions": [],
            },
        }
    )

    assert response.attempt_id == "00000000-0000-0000-0000-000000000001"
