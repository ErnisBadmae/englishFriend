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
    assert isinstance(result.get("rubric_notes"), list)


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


def _make_run(run_id: str, session_id: str, track_id: str, overall: float) -> dict:
    return {
        "id": run_id,
        "session_id": session_id,
        "track_id": track_id,
        "track_title": "Test Track",
        "track_subtitle": "subtitle",
        "recorded_at": "2026-03-31T10:00:00",
        "scores": {
            "overall": overall,
            "clarity": overall,
            "structure": overall,
            "accuracy": overall,
            "vocabulary": overall,
            "confidence": overall,
        },
        "strengths": [],
        "next_focus": [],
        "summary": "test",
        "meta": {
            "user_turns": 3,
            "avg_words_per_turn": 15.0,
            "corrections_count": 1,
            "weakest_area": "clarity",
            "strongest_area": "vocabulary",
        },
        "delta_vs_previous": None,
    }


def test_score_interview_run_delta_none_when_no_previous_same_track():
    """score_interview_run itself doesn't compute delta - record_run does.
    Verify the score function still returns expected structure."""
    from app.services.interview_service import score_interview_run
    track = {"id": "hr_intro", "title": "HR Interview", "subtitle": "sub"}
    history = [
        {"role": "assistant", "content": "Tell me about yourself."},
        {"role": "user", "content": "I am a software engineer with 5 years experience. My situation was I needed to lead a project, my task was designing the architecture, I took action by creating specs, and the result was on-time delivery."},
        {"role": "assistant", "content": "What are your strengths?"},
        {"role": "user", "content": "I am good at problem solving. The outcome was always positive."},
    ]
    result = score_interview_run(track=track, conversation_history=history, corrections_count=1)
    assert "scores" in result
    assert result["scores"]["overall"] >= 1.0
    # STAR markers should boost structure
    assert result["scores"]["structure"] >= 5.0


def test_score_interview_run_workplace_update_hits_boost():
    """workplace_communication track: update markers boost clarity and structure."""
    from app.services.interview_service import score_interview_run
    track = {"id": "workplace_communication", "title": "Workplace", "subtitle": "sub"}
    history_with_updates = [
        {"role": "assistant", "content": "Give your standup."},
        {"role": "user", "content": "Yesterday I finished the auth module. Today I am working on the API. I am blocked by the database migration waiting for approval. Next step is to test the endpoints."},
        {"role": "assistant", "content": "Good. What else?"},
        {"role": "user", "content": "This week I completed the review. Tomorrow I will deploy."},
    ]
    history_no_updates = [
        {"role": "assistant", "content": "Give your standup."},
        {"role": "user", "content": "I did some stuff. There are some problems. I need help."},
        {"role": "assistant", "content": "Good. What else?"},
        {"role": "user", "content": "I will continue doing things."},
    ]
    result_with = score_interview_run(track=track, conversation_history=history_with_updates, corrections_count=0)
    result_without = score_interview_run(track=track, conversation_history=history_no_updates, corrections_count=0)
    assert result_with["scores"]["clarity"] >= result_without["scores"]["clarity"]


def test_score_interview_run_hr_intro_produces_rubric_notes():
    """hr_intro run should produce rubric_notes list."""
    from app.services.interview_service import score_interview_run
    track = {"id": "hr_intro", "title": "HR Interview", "subtitle": "sub"}
    history = [
        {"role": "assistant", "content": "Tell me about yourself."},
        {
            "role": "user",
            "content": (
                "The situation was that my team had no CI pipeline. "
                "My task was to build one from scratch. "
                "I took action by setting up GitHub Actions, and the result was 40% faster releases."
            ),
        },
        {"role": "assistant", "content": "What is your main strength?"},
        {"role": "user", "content": "I am good at problem solving. My goal is to keep improving."},
    ]
    result = score_interview_run(track=track, conversation_history=history, corrections_count=0)
    assert isinstance(result["rubric_notes"], list)
    assert len(result["rubric_notes"]) >= 1
    assert len(result["rubric_notes"]) <= 3


def test_score_interview_run_project_walkthrough_tradeoff_bonus_raises_vocabulary():
    """Mentioning trade-off in project_walkthrough should boost vocabulary score."""
    from app.services.interview_service import score_interview_run
    track = {"id": "project_walkthrough", "title": "Project Walkthrough", "subtitle": "sub"}
    history_with = [
        {"role": "assistant", "content": "Walk me through a project."},
        {"role": "user", "content": "I designed an API. The key trade-off was latency versus accuracy. The impact was 20% improvement."},
        {"role": "assistant", "content": "What was the hardest part?"},
        {"role": "user", "content": "Balancing the architecture with the deployment pipeline."},
    ]
    history_without = [
        {"role": "assistant", "content": "Walk me through a project."},
        {"role": "user", "content": "I designed an API. It was hard to build. We finished it on time."},
        {"role": "assistant", "content": "What was the hardest part?"},
        {"role": "user", "content": "Writing the code and testing it properly."},
    ]
    result_with = score_interview_run(track=track, conversation_history=history_with, corrections_count=0)
    result_without = score_interview_run(track=track, conversation_history=history_without, corrections_count=0)
    assert result_with["scores"]["vocabulary"] >= result_without["scores"]["vocabulary"]


def test_score_interview_run_workplace_verbose_penalty_lowers_clarity():
    """Very verbose answers in workplace_communication should lower clarity."""
    from app.services.interview_service import score_interview_run
    track = {"id": "workplace_communication", "title": "Workplace", "subtitle": "sub"}
    # Verbose answers: ~70+ words per turn
    verbose_turn = " ".join(["word"] * 75)
    history_verbose = [
        {"role": "assistant", "content": "Give a standup."},
        {"role": "user", "content": verbose_turn},
        {"role": "assistant", "content": "What else?"},
        {"role": "user", "content": verbose_turn},
    ]
    history_concise = [
        {"role": "assistant", "content": "Give a standup."},
        {"role": "user", "content": "Yesterday I finished the auth module. Today I am working on the API. I am blocked by the migration."},
        {"role": "assistant", "content": "What else?"},
        {"role": "user", "content": "Next step is testing. Tomorrow I will deploy."},
    ]
    result_verbose = score_interview_run(track=track, conversation_history=history_verbose, corrections_count=0)
    result_concise = score_interview_run(track=track, conversation_history=history_concise, corrections_count=0)
    assert result_concise["scores"]["clarity"] >= result_verbose["scores"]["clarity"]


import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_record_run_dedup_same_session_id():
    """record_run returns existing run without DB write for duplicate session_id."""
    existing_run = _make_run("existing-run", "session-abc", "hr_intro", 7.5)

    db = AsyncMock()
    mock_plan = MagicMock()
    mock_plan.roadmap = {"interview_runs": [existing_run]}

    mock_lps = AsyncMock()
    mock_lps.get_or_create_plan = AsyncMock(return_value=mock_plan)

    with patch(
        "app.services.interview_service.LearningPlanService",
        return_value=mock_lps,
    ):
        from app.services.interview_service import InterviewService
        service = InterviewService(db)

        result = await service.record_run(
            user_id=1,
            session_id="session-abc",  # same session_id as existing_run
            conversation_history=[
                {"role": "user", "content": "Hello"},
                {"role": "user", "content": "Let me try again"},
            ],
            corrections_count=0,
        )

    # Should return existing run, not create new one
    assert result["id"] == "existing-run"
    # DB commit should NOT have been called (dedup = no write)
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_record_run_delta_computed_vs_previous_same_track():
    """record_run computes delta_vs_previous when a run for same track exists."""
    prev_run = _make_run("prev-run", "session-prev", "hr_intro", 6.0)

    db = AsyncMock()
    mock_plan = MagicMock()
    mock_plan.roadmap = {"interview_runs": [prev_run]}
    mock_plan.updated_at = None

    mock_lps = AsyncMock()
    mock_lps.get_or_create_plan = AsyncMock(return_value=mock_plan)
    mock_lps.get_goal = MagicMock(return_value="Get a job")
    mock_lps._update_milestone = MagicMock()

    with patch(
        "app.services.interview_service.LearningPlanService",
        return_value=mock_lps,
    ):
        from app.services.interview_service import InterviewService
        service = InterviewService(db)

        result = await service.record_run(
            user_id=1,
            session_id="session-new",
            conversation_history=[
                {"role": "assistant", "content": "Tell me about yourself."},
                {
                    "role": "user",
                    "content": (
                        "I am an engineer. The situation was I needed to lead a project. "
                        "My task was to design the architecture and the result was success."
                    ),
                },
                {"role": "assistant", "content": "What is your strength?"},
                {"role": "user", "content": "I am good at problem solving and my outcome is always positive."},
            ],
            corrections_count=1,
            track_id="hr_intro",
        )

    assert "delta_vs_previous" in result
    # prev overall was 6.0; new score should differ — delta is computed
    assert result["delta_vs_previous"] is not None


@pytest.mark.asyncio
async def test_record_run_delta_none_when_no_previous_same_track():
    """record_run sets delta_vs_previous=None when no prior run for same track."""
    prev_run_other_track = _make_run("prev-other", "session-prev", "project_walkthrough", 7.0)

    db = AsyncMock()
    mock_plan = MagicMock()
    mock_plan.roadmap = {"interview_runs": [prev_run_other_track]}
    mock_plan.updated_at = None

    mock_lps = AsyncMock()
    mock_lps.get_or_create_plan = AsyncMock(return_value=mock_plan)
    mock_lps.get_goal = MagicMock(return_value=None)
    mock_lps._update_milestone = MagicMock()

    with patch(
        "app.services.interview_service.LearningPlanService",
        return_value=mock_lps,
    ):
        from app.services.interview_service import InterviewService
        service = InterviewService(db)

        result = await service.record_run(
            user_id=1,
            session_id="session-new",
            conversation_history=[
                {"role": "assistant", "content": "Tell me about yourself."},
                {"role": "user", "content": "I am a software engineer."},
                {"role": "assistant", "content": "Why this role?"},
                {"role": "user", "content": "I love solving hard problems."},
            ],
            corrections_count=0,
            track_id="hr_intro",  # different track from prev_run_other_track
        )

    assert result["delta_vs_previous"] is None


@pytest.mark.asyncio
async def test_record_run_updates_adaptation_fields():
    """record_run writes weakest_interview_area, last_interview_track, interview_focus, track_stats to roadmap."""
    db = AsyncMock()
    mock_plan = MagicMock()
    mock_plan.roadmap = {"interview_runs": [], "milestones": []}
    mock_plan.updated_at = None

    mock_lps = AsyncMock()
    mock_lps.get_or_create_plan = AsyncMock(return_value=mock_plan)
    mock_lps.get_goal = MagicMock(return_value="Job interview prep")
    mock_lps._update_milestone = MagicMock()

    with patch(
        "app.services.interview_service.LearningPlanService",
        return_value=mock_lps,
    ):
        from app.services.interview_service import InterviewService
        service = InterviewService(db)

        result = await service.record_run(
            user_id=1,
            session_id="s-adapt",
            conversation_history=[
                {"role": "assistant", "content": "Tell me about yourself."},
                {"role": "user", "content": "I am a software engineer with years of experience working on web platforms."},
                {"role": "assistant", "content": "What is your main strength?"},
                {"role": "user", "content": "I am good at solving hard problems quickly and improving workflow reliability."},
            ],
            corrections_count=3,
            track_id="hr_intro",
        )

    roadmap = mock_plan.roadmap
    assert result["pronunciation"] is not None
    assert result["pronunciation"]["provider"] == "heuristic_text"
    assert roadmap["weakest_interview_area"] in ("clarity", "structure", "accuracy", "vocabulary", "confidence")
    assert roadmap["last_interview_track"] == "hr_intro"
    assert isinstance(roadmap["interview_focus"], list)
    assert len(roadmap["interview_focus"]) <= 2
    assert roadmap["interview_track_stats"]["hr_intro"] == 1
    assert roadmap["pronunciation_summary"]["latest_score"] is not None
    assert isinstance(roadmap["pronunciation_focus"], list)


@pytest.mark.asyncio
async def test_record_run_increments_mock_interview_milestone():
    """record_run calls _update_milestone with mock_interview increment=1."""
    db = AsyncMock()
    mock_plan = MagicMock()
    mock_plan.roadmap = {
        "interview_runs": [],
        "milestones": [
            {"name": "Complete 5 mock interviews", "type": "mock_interview", "target": 5, "count": 2}
        ],
    }
    mock_plan.updated_at = None

    mock_lps = AsyncMock()
    mock_lps.get_or_create_plan = AsyncMock(return_value=mock_plan)
    mock_lps.get_goal = MagicMock(return_value=None)
    mock_lps._update_milestone = MagicMock()

    with patch(
        "app.services.interview_service.LearningPlanService",
        return_value=mock_lps,
    ):
        from app.services.interview_service import InterviewService
        service = InterviewService(db)

        await service.record_run(
            user_id=1,
            session_id="s-milestone",
            conversation_history=[
                {"role": "assistant", "content": "Tell me about yourself."},
                {"role": "user", "content": "I am a software engineer."},
                {"role": "assistant", "content": "What is your strength?"},
                {"role": "user", "content": "Problem solving and delivery."},
            ],
            corrections_count=0,
        )

    mock_lps._update_milestone.assert_called_once()
    call_args = mock_lps._update_milestone.call_args
    assert call_args[0][1] == "mock_interview"
    assert call_args[1].get("increment") == 1
