from __future__ import annotations

from typing import Any


INTERVIEW_TRACKS: list[dict[str, Any]] = [
    {
        "id": "hr_intro",
        "title": "HR Interview",
        "subtitle": "Tell your story with confidence",
        "description": "Practice introductions, motivation, strengths, and behavioral answers.",
        "prompt_focus": "behavioral answers with STAR structure and concise motivation",
        "starter_question": "Tell me about yourself and why this role is the right next step for you.",
        "rubric_focus": ["clarity", "structure", "confidence"],
        "goal_keywords": ["interview", "job", "career", "recruiter", "hr"],
    },
    {
        "id": "project_walkthrough",
        "title": "Project Walkthrough",
        "subtitle": "Explain real technical work clearly",
        "description": "Practice describing your stack, trade-offs, impact, and technical decisions.",
        "prompt_focus": "clear technical explanation, architecture trade-offs, and business impact",
        "starter_question": "Walk me through one project you are proud of and explain your role in it.",
        "rubric_focus": ["clarity", "vocabulary", "technical_depth"],
        "goal_keywords": [
            "ml",
            "machine learning",
            "data",
            "software",
            "developer",
            "engineer",
            "technical",
            "system design",
        ],
    },
    {
        "id": "workplace_communication",
        "title": "Workplace Communication",
        "subtitle": "Handle standups, reviews, and stakeholder talk",
        "description": "Practice standups, code reviews, blockers, updates, and collaboration language.",
        "prompt_focus": "short workplace updates, ownership language, and collaborative problem solving",
        "starter_question": "Imagine you are giving a standup update. What did you finish, what is next, and what is blocked?",
        "rubric_focus": ["accuracy", "clarity", "professional_tone"],
        "goal_keywords": ["work", "team", "meeting", "standup", "office", "communication"],
    },
]


def list_interview_tracks() -> list[dict[str, Any]]:
    return [dict(track) for track in INTERVIEW_TRACKS]


def get_interview_track(track_id: str | None) -> dict[str, Any] | None:
    if not track_id:
        return None

    normalized = track_id.strip().lower()
    for track in INTERVIEW_TRACKS:
        if track["id"] == normalized:
            return dict(track)
    return None


def recommend_interview_track(goal: str | None, recent_runs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    goal_lower = (goal or "").lower()

    if any(keyword in goal_lower for keyword in ("ml", "machine learning", "data", "software", "engineer", "developer")):
        recommended_id = "project_walkthrough"
    elif any(keyword in goal_lower for keyword in ("team", "manager", "meeting", "standup", "workplace")):
        recommended_id = "workplace_communication"
    else:
        recommended_id = "hr_intro"

    return get_interview_track(recommended_id) or dict(INTERVIEW_TRACKS[0])
