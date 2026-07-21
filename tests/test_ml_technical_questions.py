"""Tests for the `ml_technical` track registration and question pack.

Covers: backward compatibility of existing tracks, the 15-question pack
validation (unique ids, valid rubrics, no private Telegram URLs), and the
pre-submission public view that must hide the rubric/reference explanation.
"""

from app.data.interview_tracks import get_interview_track, list_interview_tracks
from app.data.ml_technical_questions import (
    ML_TECHNICAL_QUESTIONS,
    ML_TECHNICAL_TOPICS,
    get_ml_technical_question,
    get_ml_technical_topic,
    list_ml_technical_questions,
    list_ml_technical_topics,
    public_question_view,
)

EXPECTED_TOPIC_IDS = {
    "ml_fundamentals",
    "dl_training",
    "transformers_llm",
    "finetuning_peft",
    "inference_mlops",
    "rag_agents_evaluation",
    "recsys_ranking",
}


# ---------------------------------------------------------------------------
# Backward compatibility of existing tracks.
# ---------------------------------------------------------------------------


def test_existing_three_tracks_remain_present_and_unchanged():
    hr_intro = get_interview_track("hr_intro")
    project_walkthrough = get_interview_track("project_walkthrough")
    workplace_communication = get_interview_track("workplace_communication")

    assert hr_intro is not None
    assert project_walkthrough is not None
    assert workplace_communication is not None

    assert hr_intro["title"] == "HR Interview"
    assert hr_intro["rubric_focus"] == ["clarity", "structure", "confidence"]

    assert project_walkthrough["title"] == "Project Walkthrough"
    assert project_walkthrough["rubric_focus"] == ["clarity", "vocabulary", "technical_depth"]

    assert workplace_communication["title"] == "Workplace Communication"
    assert workplace_communication["rubric_focus"] == ["accuracy", "clarity", "professional_tone"]


def test_ml_technical_track_registered_with_stable_id():
    track = get_interview_track("ml_technical")
    assert track is not None
    assert track["id"] == "ml_technical"
    assert track["title"]
    # Russian-first UI copy for the technical track.
    assert any(ch.isalpha() and ord(ch) > 127 for ch in track["subtitle"])


def test_track_registry_has_exactly_four_tracks():
    ids = {track["id"] for track in list_interview_tracks()}
    assert ids == {"hr_intro", "project_walkthrough", "workplace_communication", "ml_technical"}


# ---------------------------------------------------------------------------
# 15-question pack validation.
# ---------------------------------------------------------------------------


def test_exactly_15_questions_with_unique_ids():
    assert len(ML_TECHNICAL_QUESTIONS) == 15
    ids = [q["id"] for q in ML_TECHNICAL_QUESTIONS]
    assert len(set(ids)) == 15


def test_all_initial_topics_present():
    topic_ids = {topic["id"] for topic in ML_TECHNICAL_TOPICS}
    assert topic_ids == EXPECTED_TOPIC_IDS


def test_every_question_has_a_valid_structure():
    for question in ML_TECHNICAL_QUESTIONS:
        assert question["track_id"] == "ml_technical"
        assert question["topic_id"] in EXPECTED_TOPIC_IDS
        assert question["question_ru"]
        assert question["difficulty"] in ("easy", "medium", "hard")
        assert isinstance(question["tags"], list) and question["tags"]
        assert len(question["rubric_points"]) >= 3
        for point in question["rubric_points"]:
            assert point["id"]
            assert point["point_ru"]
        assert question["reference_explanation_ru"]
        assert len(question["follow_ups"]) == 2
        assert question["rubric_version"] == "ml-technical-v1"
        assert question["provenance_id"]


def test_question_pack_has_no_private_telegram_urls():
    forbidden_markers = ("t.me/", "telegram.me/", "https://t.me", "tg://")
    for question in ML_TECHNICAL_QUESTIONS:
        haystack = " ".join(
            [
                question["question_ru"],
                question["reference_explanation_ru"],
                question["provenance_id"],
                *[p["point_ru"] for p in question["rubric_points"]],
                *question["follow_ups"],
            ]
        ).lower()
        for marker in forbidden_markers:
            assert marker not in haystack


def test_list_and_get_helpers_are_consistent_with_the_pack():
    assert len(list_ml_technical_questions()) == 15
    for question in ML_TECHNICAL_QUESTIONS:
        fetched = get_ml_technical_question(question["id"])
        assert fetched is not None
        assert fetched["id"] == question["id"]

    assert get_ml_technical_question("mltech_999") is None


def test_topic_filtering_only_returns_that_topics_questions():
    for topic in ML_TECHNICAL_TOPICS:
        filtered = list_ml_technical_questions(topic["id"])
        assert all(q["topic_id"] == topic["id"] for q in filtered)

    assert get_ml_technical_topic("dl_training") is not None
    assert get_ml_technical_topic("unknown_topic") is None
    assert list_ml_technical_topics()[0]["id"] == ML_TECHNICAL_TOPICS[0]["id"]


def test_public_question_view_hides_rubric_and_reference():
    for question in ML_TECHNICAL_QUESTIONS:
        view = public_question_view(question)
        assert "rubric_points" not in view
        assert "reference_explanation_ru" not in view
        assert "follow_ups" not in view
        assert view["id"] == question["id"]
        assert view["topic_id"] == question["topic_id"]
        assert view["question_ru"] == question["question_ru"]
