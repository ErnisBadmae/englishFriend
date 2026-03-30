from app.services.program_snapshot_service import (
    build_latest_assessment,
    extract_focus_areas,
    recommend_next_mission,
)


def test_build_latest_assessment_from_history():
    roadmap = {
        "assessment_history": [
            {"date": "2026-03-01T10:00:00", "level": "A2", "scores": {"fluency": 0.4}},
            {"date": "2026-03-10T10:00:00", "level": "B1", "scores": {"fluency": 0.7}},
        ]
    }

    latest = build_latest_assessment(roadmap)

    assert latest is not None
    assert latest["level"] == "B1"
    assert latest["scores"]["fluency"] == 0.7


def test_extract_focus_areas_prefers_descriptions():
    roadmap = {
        "focus_areas": [
            {"area": "behavioral_questions", "description": "STAR answers"},
            {"area": "technical_vocabulary"},
        ]
    }

    assert extract_focus_areas(roadmap) == ["STAR answers", "technical_vocabulary"]


def test_recommend_next_mission_prioritizes_due_vocab():
    mission = recommend_next_mission(
        goal="ML interview preparation",
        preferred_mode="mock_interview",
        due_count=7,
        error_patterns=[],
        has_assessment=True,
    )

    assert mission["mode"] == "vocabulary_drill"
    assert "7" in mission["reason"]
