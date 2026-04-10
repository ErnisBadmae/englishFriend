import json
from pathlib import Path

from app.services.stt_benchmark import (
    BenchmarkExpectations,
    STTBenchmarkCase,
    STTBenchmarkObservation,
    build_report,
    evaluate_observation,
    load_cases_from_json,
    normalize_text,
    observation_from_voice_debug_snapshot,
)


def test_normalize_text_simplifies_punctuation_and_spacing():
    assert normalize_text(" ML-engineer, abroad!  ") == "ml engineer abroad"


def test_evaluate_observation_scores_expected_signals():
    case = STTBenchmarkCase(
        case_id="clean-foundation",
        scenario="clean_foundation",
        expected=BenchmarkExpectations(
            target_role_terms=["data scientist"],
            project_terms=["recommendation model"],
            technical_terms=["recommendation", "model"],
            required_phrases=["improve grammar"],
        ),
        observations=[],
    )
    observation = STTBenchmarkObservation(
        provider="browser_vosk",
        transcript=(
            "I work as a data scientist and build recommendation models. "
            "My recent project was a recommendation model for e-commerce. "
            "My next step is to improve grammar for project answers."
        ),
        source="browser_vosk",
        fallback_used=False,
    )

    result = evaluate_observation(case, observation)

    assert result.score.target_role_captured is True
    assert result.score.project_signal_captured is True
    assert result.score.technical_term_hits == 2
    assert result.score.required_phrase_hits == 1
    assert result.score.fallback_used is False
    assert result.score.overall_score == 100.0


def test_observation_from_voice_debug_snapshot_extracts_sent_text_and_fallback():
    payload = {
        "exportedAt": "2026-04-10T10:00:00Z",
        "session": {
            "sessionId": "session-123",
            "missionTaskType": "foundation_speaking_drill",
            "sttProvider": "browser_vosk",
        },
        "events": [
            {
                "id": 1,
                "timestamp": "2026-04-10T10:00:01Z",
                "source": "websocket",
                "event": "ws_text_sent",
                "data": {
                    "source": "browser_vosk",
                    "text": "I work as a data scientist",
                },
            },
            {
                "id": 2,
                "timestamp": "2026-04-10T10:00:05Z",
                "source": "websocket",
                "event": "ws_text_sent",
                "data": {
                    "source": "composer",
                    "text": "My recent project was a recommendation model",
                },
            },
        ],
    }
    temp_dir = Path.cwd() / "tests" / "__tmp__"
    temp_dir.mkdir(exist_ok=True)
    path = temp_dir / "voice-debug.json"
    try:
        path.write_text(json.dumps(payload), encoding="utf-8")

        observation = observation_from_voice_debug_snapshot(path)

        assert observation.provider == "browser_vosk"
        assert observation.session_id == "session-123"
        assert observation.mission_task_type == "foundation_speaking_drill"
        assert observation.fallback_used is True
        assert observation.source == "mixed"
        assert "data scientist" in observation.transcript
        assert "recommendation model" in observation.transcript
    finally:
        if path.exists():
            path.unlink()


def test_build_report_summarizes_results_and_loads_cases():
    payload = {
        "cases": [
            {
                "case_id": "first-run",
                "scenario": "first_run",
                "expected": {
                    "target_role_terms": ["ml engineer"],
                    "project_terms": ["churn prediction"],
                    "technical_terms": ["churn", "prediction"],
                },
                "observations": [
                    {
                        "provider": "browser_vosk",
                        "transcript": "I want an ML engineer job. My recent project was churn prediction.",
                        "latency_ms": 820,
                        "source": "browser_vosk",
                        "fallback_used": True,
                    },
                    {
                        "provider": "browser_whisper_webgpu",
                        "transcript": "I want an ML engineer job. My recent project was churn prediction.",
                        "latency_ms": 610,
                        "source": "browser_whisper_webgpu",
                        "fallback_used": False,
                    },
                ],
            }
        ]
    }
    temp_dir = Path.cwd() / "tests" / "__tmp__"
    temp_dir.mkdir(exist_ok=True)
    path = temp_dir / "cases.json"
    try:
        path.write_text(json.dumps(payload), encoding="utf-8")

        cases = load_cases_from_json(path)
        report = build_report(cases)

        assert len(report.results) == 2
        assert report.provider_summary[0].provider == "browser_whisper_webgpu"
        assert report.provider_summary[0].avg_latency_ms == 610.0
        assert report.provider_summary[1].provider == "browser_vosk"
    finally:
        if path.exists():
            path.unlink()
