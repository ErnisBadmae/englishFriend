"""Tests for interview question bank and selection logic."""

from app.data.interview_questions import INTERVIEW_QUESTIONS, select_questions_for_track


def test_question_bank_has_all_tracks():
    track_ids = {q["track_id"] for q in INTERVIEW_QUESTIONS}
    assert "hr_intro" in track_ids
    assert "project_walkthrough" in track_ids
    assert "workplace_communication" in track_ids


def test_each_track_has_minimum_questions():
    for track_id in ("hr_intro", "project_walkthrough", "workplace_communication"):
        count = sum(1 for q in INTERVIEW_QUESTIONS if q["track_id"] == track_id)
        assert count >= 10, f"{track_id} has only {count} questions"


def test_question_structure():
    for q in INTERVIEW_QUESTIONS:
        assert "id" in q
        assert "track_id" in q
        assert "prompt" in q
        assert "follow_up_prompts" in q
        assert isinstance(q["follow_up_prompts"], list)
        assert "difficulty" in q
        assert q["difficulty"] in ("easy", "medium", "hard")
        assert "tags" in q
        assert "evaluation_focus" in q


def test_select_returns_correct_limit():
    result = select_questions_for_track("hr_intro", limit=3)
    assert len(result) == 3


def test_select_starts_with_easy():
    result = select_questions_for_track("hr_intro", limit=3)
    assert result[0]["difficulty"] == "easy"


def test_select_progresses_difficulty():
    result = select_questions_for_track("project_walkthrough", limit=3)
    difficulties = [q["difficulty"] for q in result]
    order = {"easy": 0, "medium": 1, "hard": 2}
    ordered = sorted(difficulties, key=lambda d: order[d])
    assert difficulties == ordered


def test_select_deterministic_with_same_seed():
    a = select_questions_for_track("hr_intro", limit=4, session_seed="abc-123")
    b = select_questions_for_track("hr_intro", limit=4, session_seed="abc-123")
    assert [q["id"] for q in a] == [q["id"] for q in b]


def test_select_varies_with_different_seed():
    # limit=3 from 4 easy questions — different seeds should produce different subsets
    attempts = [
        select_questions_for_track("hr_intro", limit=3, session_seed=f"session-{i}")
        for i in range(20)
    ]
    id_sets = [frozenset(q["id"] for q in a) for a in attempts]
    # Not all sessions should have the same question set
    assert len(set(id_sets)) > 1


def test_select_skips_excluded_ids():
    all_qs = select_questions_for_track("hr_intro", limit=15)
    all_ids = [q["id"] for q in all_qs]
    skip_ids = all_ids[:3]

    result = select_questions_for_track("hr_intro", limit=3, skip_ids=skip_ids)
    result_ids = [q["id"] for q in result]
    assert not any(rid in skip_ids for rid in result_ids)


def test_select_fallback_to_full_set_when_skip_too_many():
    """If too many IDs are skipped, selection falls back to full set."""
    # Skip almost everything — should still return results
    all_qs = INTERVIEW_QUESTIONS
    all_ids = [q["id"] for q in all_qs if q["track_id"] == "workplace_communication"]
    result = select_questions_for_track("workplace_communication", limit=3, skip_ids=all_ids)
    assert len(result) == 3


def test_select_unknown_track_returns_empty():
    result = select_questions_for_track("nonexistent_track", limit=3)
    assert result == []
