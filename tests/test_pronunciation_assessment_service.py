from unittest.mock import AsyncMock

import pytest

from app.services.pronunciation_assessment_service import (
    PronunciationAssessmentService,
    build_pronunciation_summary,
)


def test_build_pronunciation_summary_returns_latest_signal_and_trend():
    summary = build_pronunciation_summary(
        [
            {
                "recorded_at": "2026-04-01T12:00:00",
                "overall_score": 7.8,
                "accuracy_score": 7.5,
                "fluency_score": 8.2,
                "prosody_score": None,
                "recommended_focus": ["Practice TH words"],
                "word_feedback": [{"word": "three", "issue": "TH articulation", "severity": "medium", "tip": "Tongue between teeth"}],
                "source": "heuristic_text",
                "assessment_mode": "text_heuristic",
                "confidence": 0.52,
            },
            {
                "recorded_at": "2026-03-30T12:00:00",
                "overall_score": 6.9,
                "accuracy_score": 6.8,
                "fluency_score": 7.1,
                "recommended_focus": ["Slow down on key terms"],
                "word_feedback": [],
                "source": "heuristic_text",
                "assessment_mode": "text_heuristic",
                "confidence": 0.44,
            },
        ]
    )

    assert summary["latest_score"] == 7.8
    assert summary["trend"] == "rising"
    assert summary["focus"] == ["Practice TH words"]
    assert summary["history_count"] == 2


@pytest.mark.asyncio
async def test_assess_conversation_returns_none_for_short_transcript():
    service = PronunciationAssessmentService(AsyncMock())

    result = await service.assess_conversation(
        session_id="s1",
        conversation_history=[
            {"role": "assistant", "content": "Tell me about yourself."},
            {"role": "user", "content": "Sure"},
        ],
        track_id="hr_intro",
    )

    assert result is None


@pytest.mark.asyncio
async def test_assess_conversation_builds_pronunciation_payload():
    service = PronunciationAssessmentService(AsyncMock())

    result = await service.assess_conversation(
        session_id="s2",
        conversation_history=[
            {"role": "assistant", "content": "Tell me about yourself."},
            {
                "role": "user",
                "content": "I worked on a weather platform where the main thing was improving throughput and reliability.",
            },
            {"role": "assistant", "content": "What was hard about it?"},
            {
                "role": "user",
                "content": "The trade-off was latency versus accuracy, and we had to think about the whole workflow.",
            },
        ],
        track_id="project_walkthrough",
    )

    assert result is not None
    assert result["provider"] == "heuristic_text"
    assert result["assessment_mode"] == "text_heuristic"
    assert result["overall_score"] >= 1.0
    assert isinstance(result["recommended_focus"], list)
