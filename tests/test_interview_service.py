from app.data.interview_tracks import get_interview_track
from app.services.interview_service import build_interview_summary, score_interview_run


def test_score_interview_run_returns_weighted_scores():
    track = get_interview_track("project_walkthrough")
    assert track is not None

    result = score_interview_run(
        track=track,
        conversation_history=[
            {"role": "assistant", "content": "Walk me through a project you built."},
            {
                "role": "user",
                "content": (
                    "First I designed the data pipeline, then I handled deployment. "
                    "The main trade-off was latency versus model accuracy."
                ),
            },
            {
                "role": "assistant",
                "content": "Good. What impact did that decision have on the product?",
            },
            {
                "role": "user",
                "content": (
                    "It reduced response time for inference and made the architecture more scalable "
                    "for our production traffic."
                ),
            },
        ],
        corrections_count=2,
        reviewed_words=[{"word": "deployment"}, {"word": "scalable"}],
    )

    assert 1 <= result["scores"]["overall"] <= 10
    assert result["scores"]["vocabulary"] >= 6
    assert result["meta"]["user_turns"] == 2
    assert result["strengths"]
    assert result["next_focus"]


def test_build_interview_summary_marks_rising_trend():
    runs = [
        {
            "id": "run-4",
            "recorded_at": "2026-03-30T12:00:00",
            "track_id": "project_walkthrough",
            "track_title": "Project Walkthrough",
            "track_subtitle": "Explain technical work",
            "session_id": "s4",
            "scores": {"overall": 8.2, "clarity": 8.0, "structure": 8.0, "accuracy": 8.0, "vocabulary": 8.5, "confidence": 8.2},
            "strengths": [],
            "next_focus": [],
            "summary": "Latest",
            "meta": {"user_turns": 5, "avg_words_per_turn": 20.0, "corrections_count": 2, "weakest_area": "structure", "strongest_area": "vocabulary"},
        },
        {
            "id": "run-3",
            "recorded_at": "2026-03-29T12:00:00",
            "track_id": "project_walkthrough",
            "track_title": "Project Walkthrough",
            "track_subtitle": "Explain technical work",
            "session_id": "s3",
            "scores": {"overall": 7.8, "clarity": 7.5, "structure": 7.6, "accuracy": 7.7, "vocabulary": 8.1, "confidence": 7.8},
            "strengths": [],
            "next_focus": [],
            "summary": "Previous",
            "meta": {"user_turns": 5, "avg_words_per_turn": 18.0, "corrections_count": 3, "weakest_area": "clarity", "strongest_area": "vocabulary"},
        },
        {
            "id": "run-2",
            "recorded_at": "2026-03-20T12:00:00",
            "track_id": "hr_intro",
            "track_title": "HR Interview",
            "track_subtitle": "Tell your story",
            "session_id": "s2",
            "scores": {"overall": 6.4, "clarity": 6.3, "structure": 6.0, "accuracy": 6.5, "vocabulary": 6.2, "confidence": 6.7},
            "strengths": [],
            "next_focus": [],
            "summary": "Earlier",
            "meta": {"user_turns": 4, "avg_words_per_turn": 14.0, "corrections_count": 5, "weakest_area": "structure", "strongest_area": "confidence"},
        },
        {
            "id": "run-1",
            "recorded_at": "2026-03-18T12:00:00",
            "track_id": "hr_intro",
            "track_title": "HR Interview",
            "track_subtitle": "Tell your story",
            "session_id": "s1",
            "scores": {"overall": 6.0, "clarity": 5.9, "structure": 5.8, "accuracy": 6.2, "vocabulary": 6.0, "confidence": 6.1},
            "strengths": [],
            "next_focus": [],
            "summary": "Oldest",
            "meta": {"user_turns": 4, "avg_words_per_turn": 12.0, "corrections_count": 6, "weakest_area": "structure", "strongest_area": "accuracy"},
        },
    ]

    summary = build_interview_summary(runs, goal="ML interview preparation")

    assert summary["completed_runs"] == 4
    assert summary["trend"] == "rising"
    assert summary["recommended_track"]["id"] == "project_walkthrough"
    assert summary["readiness_score"] == 7.5
