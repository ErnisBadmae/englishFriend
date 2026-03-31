from __future__ import annotations

from datetime import datetime
from statistics import mean
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.data.interview_tracks import (
    get_interview_track,
    list_interview_tracks,
    recommend_interview_track,
)
from app.services.learning_plan_service import LearningPlanService


def _clamp_score(value: float) -> float:
    return round(max(1.0, min(10.0, value)), 1)


def _count_keyword_hits(text: str, keywords: list[str]) -> int:
    haystack = text.lower()
    return sum(1 for keyword in keywords if keyword.lower() in haystack)


def _build_strengths(scores: dict[str, float], track: dict[str, Any]) -> list[str]:
    strengths: list[str] = []
    if scores["clarity"] >= 7:
        strengths.append("You explained ideas clearly without drifting too much.")
    if scores["structure"] >= 7:
        strengths.append("Your answer structure felt organized and easy to follow.")
    if scores["accuracy"] >= 7:
        strengths.append("Grammar control was solid enough to keep the answer credible.")
    if scores["vocabulary"] >= 7:
        strengths.append("You used professional English instead of generic wording.")
    if scores["confidence"] >= 7:
        strengths.append("You sounded more confident and decisive than in a typical practice chat.")

    if strengths:
        return strengths[:3]

    return [f"You finished a full {track['title'].lower()} run, which already builds interview stamina."]


def _build_rubric_notes(
    scores: dict[str, float],
    track: dict[str, Any],
    user_text: str,
    avg_words_per_turn: float,
    structure_hits: int,
    technical_hits: int,
    update_hits: int,
) -> list[str]:
    notes: list[str] = []
    track_id = track["id"]
    text = user_text.lower()

    if track_id == "hr_intro":
        if structure_hits >= 3:
            notes.append("Used clear STAR structure — answer was easy to follow.")
        elif structure_hits <= 1:
            notes.append("Missing concrete result or outcome — add one sentence.")
        if any(kw in text for kw in ("because", "reason", "goal", "motivation", "want to")):
            notes.append("Good motivation language woven into the answer.")
        if scores["confidence"] >= 7:
            notes.append("Sounded decisive and confident throughout.")
        elif scores["confidence"] < 5:
            notes.append("Add more decisive language — avoid trailing off mid-answer.")

    elif track_id == "project_walkthrough":
        if any(kw in text for kw in ("trade-off", "tradeoff", "trade off")):
            notes.append("Named the trade-off explicitly — strong technical clarity.")
        else:
            notes.append("Consider naming the key trade-off in your next answer.")
        if any(kw in text for kw in ("impact", "improved", "reduced", "increased", "user", "customer", "revenue")):
            notes.append("Linked technical decision to a concrete outcome or impact.")
        else:
            notes.append("Missing business impact — add a metric or measurable result.")
        if technical_hits >= 3:
            notes.append("Used technical vocabulary with precision.")

    elif track_id == "workplace_communication":
        if update_hits >= 2:
            notes.append("Update was clear: done, next, blocked — great standup structure.")
        else:
            notes.append("Structure the update more clearly: done / next / any blockers.")
        if avg_words_per_turn < 28:
            notes.append("Good brevity — standup-style length.")
        elif avg_words_per_turn > 50:
            notes.append("Answers too verbose — aim for 20–30 words per update.")
        if any(kw in text for kw in ("blocked", "blocker", "waiting for", "depend")):
            notes.append("Good awareness of blockers — named them clearly.")

    return notes[:3]


def _build_next_focus(scores: dict[str, float], track: dict[str, Any]) -> list[str]:
    areas = [
        ("clarity", "Make answers shorter and clearer before adding extra detail."),
        ("structure", "Use a tighter structure so each answer has a beginning, middle, and result."),
        ("accuracy", "Reduce small grammar slips so your answers sound more polished."),
        ("vocabulary", "Use more role-specific vocabulary instead of repeating basic verbs."),
        ("confidence", "Pause less and finish ideas more decisively."),
    ]
    ranked = sorted(areas, key=lambda item: scores[item[0]])
    next_focus = [item[1] for item in ranked[:2]]
    if track["id"] == "hr_intro":
        next_focus.append("Practice one STAR story until it feels automatic.")
    elif track["id"] == "project_walkthrough":
        next_focus.append("Name the trade-off, your decision, and the business impact in one flow.")
    else:
        next_focus.append("Keep workplace updates concise: done, next, blocked.")
    return next_focus[:3]


def score_interview_run(
    *,
    track: dict[str, Any],
    conversation_history: list[dict[str, str]],
    corrections_count: int,
    reviewed_words: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    reviewed_words = reviewed_words or []
    user_messages = [
        message.get("content", "").strip()
        for message in conversation_history
        if message.get("role") == "user" and message.get("content")
    ]
    assistant_messages = [
        message.get("content", "").strip()
        for message in conversation_history
        if message.get("role") == "assistant" and message.get("content")
    ]

    user_turns = len(user_messages)
    total_user_words = sum(len(message.split()) for message in user_messages)
    avg_words_per_turn = total_user_words / max(user_turns, 1)
    combined_user_text = " ".join(user_messages)
    combined_all_text = " ".join(user_messages + assistant_messages)

    filler_hits = _count_keyword_hits(
        combined_user_text,
        [" um ", " uh ", " like ", " you know ", " actually ", " basically "],
    )
    structure_hits = _count_keyword_hits(
        combined_user_text,
        ["first", "then", "because", "result", "impact", "finally", "after that",
         "situation", "task", "action", "outcome"],
    )
    technical_hits = _count_keyword_hits(
        combined_all_text,
        [
            "architecture",
            "trade-off",
            "deployment",
            "scalability",
            "stakeholder",
            "pipeline",
            "blocked",
            "ownership",
            "microservice",
            "api",
            "performance",
            "throughput",
            "optimize",
            "bottleneck",
            "latency",
            "reliability",
            "schema",
            "endpoint",
            "tradeoff",
            "trade off",
        ],
    )
    reviewed_hits = sum(
        1
        for item in reviewed_words
        if isinstance(item, dict) and item.get("word") and item.get("word", "").lower() in combined_all_text.lower()
    )
    update_hits = (
        _count_keyword_hits(
            combined_user_text,
            ["finished", "completed", "working on", "blocked by", "waiting for",
             "next step", "tomorrow", "yesterday", "this week"],
        )
        if track["id"] == "workplace_communication"
        else 0
    )

    # Track-specific rubric bonuses
    track_id = track["id"]
    hr_star_bonus = min(0.8, structure_hits * 0.2) if track_id == "hr_intro" and structure_hits >= 2 else 0.0
    pw_impact_bonus = (
        0.5
        if track_id == "project_walkthrough"
        and any(kw in combined_user_text.lower() for kw in ("impact", "improved", "reduced", "increased", "revenue", "user"))
        else 0.0
    )
    pw_tradeoff_bonus = (
        0.4
        if track_id == "project_walkthrough"
        and any(kw in combined_user_text.lower() for kw in ("trade-off", "tradeoff", "trade off"))
        else 0.0
    )
    wc_concise_bonus = (
        0.5 if track_id == "workplace_communication" and avg_words_per_turn <= 25 else 0.0
    )
    wc_verbose_penalty = (
        -0.6 if track_id == "workplace_communication" and avg_words_per_turn > 50 else 0.0
    )

    clarity = _clamp_score(
        4.8 + min(2.2, avg_words_per_turn / 9) + min(1.2, user_turns * 0.35) - filler_hits * 0.3
        + (min(1.0, update_hits * 0.3) if update_hits else 0.0)
        + wc_concise_bonus + wc_verbose_penalty
    )
    structure = _clamp_score(
        4.5 + min(3.0, structure_hits * 0.7) + (0.6 if track_id == "hr_intro" else 0.0)
        + hr_star_bonus
        + (min(1.0, update_hits * 0.3) if update_hits else 0.0)
    )
    accuracy = _clamp_score(8.8 - min(5.4, corrections_count * 0.7))
    vocabulary = _clamp_score(
        4.7 + min(3.3, technical_hits * 0.45) + min(1.5, reviewed_hits * 0.5)
        + pw_tradeoff_bonus
    )
    confidence = _clamp_score(4.6 + min(2.4, user_turns * 0.45) + min(1.4, avg_words_per_turn / 14) - filler_hits * 0.25)

    overall = _clamp_score(
        clarity * 0.24
        + structure * 0.2
        + accuracy * 0.22
        + vocabulary * 0.18
        + confidence * 0.16
    )

    scores = {
        "overall": overall,
        "clarity": clarity,
        "structure": structure,
        "accuracy": accuracy,
        "vocabulary": vocabulary,
        "confidence": confidence,
    }

    weakest_area = min(("clarity", "structure", "accuracy", "vocabulary", "confidence"), key=lambda key: scores[key])
    strongest_area = max(("clarity", "structure", "accuracy", "vocabulary", "confidence"), key=lambda key: scores[key])

    rubric_notes = _build_rubric_notes(
        scores=scores,
        track=track,
        user_text=combined_user_text,
        avg_words_per_turn=avg_words_per_turn,
        structure_hits=structure_hits,
        technical_hits=technical_hits,
        update_hits=update_hits,
    )

    return {
        "scores": scores,
        "strengths": _build_strengths(scores, track),
        "next_focus": _build_next_focus(scores, track),
        "rubric_notes": rubric_notes,
        "summary": (
            f"{track['title']} score {overall}/10. "
            f"Strongest area: {strongest_area}. "
            f"Main improvement area: {weakest_area}."
        ),
        "meta": {
            "user_turns": user_turns,
            "avg_words_per_turn": round(avg_words_per_turn, 1),
            "corrections_count": corrections_count,
            "weakest_area": weakest_area,
            "strongest_area": strongest_area,
        },
    }


def build_interview_summary(
    runs: list[dict[str, Any]],
    goal: Optional[str] = None,
) -> dict[str, Any]:
    ordered_runs = sorted(
        runs,
        key=lambda item: item.get("recorded_at") or "",
        reverse=True,
    )
    recommended_track = recommend_interview_track(goal, ordered_runs)
    latest_run = ordered_runs[0] if ordered_runs else None
    readiness_score = round(mean(run["scores"]["overall"] for run in ordered_runs[:3]), 1) if ordered_runs else None

    if len(ordered_runs) >= 2:
        latest_window = mean(run["scores"]["overall"] for run in ordered_runs[:2])
        previous_window = mean(
            run["scores"]["overall"]
            for run in ordered_runs[2:4]
        ) if len(ordered_runs) >= 4 else ordered_runs[-1]["scores"]["overall"]
        delta = latest_window - previous_window
        if delta >= 0.6:
            trend = "rising"
        elif delta <= -0.6:
            trend = "needs_stability"
        else:
            trend = "steady"
    else:
        trend = "building"

    return {
        "completed_runs": len(ordered_runs),
        "readiness_score": readiness_score,
        "trend": trend,
        "recommended_track": {
            "id": recommended_track["id"],
            "title": recommended_track["title"],
            "subtitle": recommended_track["subtitle"],
        },
        "latest_run": latest_run,
        "recent_runs": ordered_runs[:5],
    }


class InterviewService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.learning_plan_service = LearningPlanService(db)

    async def get_tracks(self, user_id: int) -> dict[str, Any]:
        plan = await self.learning_plan_service.get_or_create_plan(user_id)
        roadmap = plan.roadmap or {}
        runs = self._normalize_runs(roadmap.get("interview_runs"))
        goal = self.learning_plan_service.get_goal(plan)
        summary = build_interview_summary(runs, goal=goal)
        recommended_id = summary["recommended_track"]["id"]

        tracks = []
        for track in list_interview_tracks():
            completed_runs = sum(1 for run in runs if run.get("track_id") == track["id"])
            tracks.append(
                {
                    **track,
                    "recommended": track["id"] == recommended_id,
                    "completed_runs": completed_runs,
                }
            )

        return {
            "summary": summary,
            "tracks": tracks,
        }

    async def get_runs(self, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
        plan = await self.learning_plan_service.get_or_create_plan(user_id)
        roadmap = plan.roadmap or {}
        return self._normalize_runs(roadmap.get("interview_runs"))[:limit]

    async def record_run(
        self,
        *,
        user_id: int,
        session_id: str,
        conversation_history: list[dict[str, str]],
        corrections_count: int,
        reviewed_words: list[dict[str, Any]] | None = None,
        track_id: str | None = None,
    ) -> dict[str, Any]:
        plan = await self.learning_plan_service.get_or_create_plan(user_id)
        roadmap = dict(plan.roadmap or {})
        existing_runs = self._normalize_runs(roadmap.get("interview_runs"))

        # Deduplication: return existing run if this session was already recorded
        for existing_run in existing_runs:
            if existing_run.get("session_id") == session_id:
                return existing_run

        goal = self.learning_plan_service.get_goal(plan)

        track = get_interview_track(track_id) or recommend_interview_track(goal, existing_runs)
        scored = score_interview_run(
            track=track,
            conversation_history=conversation_history,
            corrections_count=corrections_count,
            reviewed_words=reviewed_words,
        )

        prev_same_track = next(
            (r for r in existing_runs if r.get("track_id") == track["id"]),
            None,
        )
        delta_vs_previous = (
            round(scored["scores"]["overall"] - prev_same_track["scores"]["overall"], 1)
            if prev_same_track
            else None
        )

        run = {
            "id": str(uuid4()),
            "session_id": session_id,
            "track_id": track["id"],
            "track_title": track["title"],
            "track_subtitle": track["subtitle"],
            "recorded_at": datetime.utcnow().isoformat(),
            "scores": scored["scores"],
            "strengths": scored["strengths"],
            "next_focus": scored["next_focus"],
            "rubric_notes": scored["rubric_notes"],
            "summary": scored["summary"],
            "meta": scored["meta"],
            "delta_vs_previous": delta_vs_previous,
        }

        # Update roadmap adaptation fields
        weakest_area = scored["meta"]["weakest_area"]
        roadmap["weakest_interview_area"] = weakest_area
        roadmap["last_interview_track"] = track["id"]
        roadmap["interview_focus"] = scored["next_focus"][:2]
        track_stats: dict[str, int] = dict(roadmap.get("interview_track_stats") or {})
        track_stats[track["id"]] = track_stats.get(track["id"], 0) + 1
        roadmap["interview_track_stats"] = track_stats
        self.learning_plan_service._update_milestone(roadmap, "mock_interview", increment=1)

        runs = [run, *existing_runs][:20]
        summary = build_interview_summary(runs, goal=goal)

        roadmap["interview_runs"] = runs
        roadmap["interview_summary"] = summary

        plan.roadmap = roadmap
        flag_modified(plan, "roadmap")
        plan.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(plan)

        return run

    def _normalize_runs(self, runs: Any) -> list[dict[str, Any]]:
        if not isinstance(runs, list):
            return []

        normalized: list[dict[str, Any]] = []
        for run in runs:
            if not isinstance(run, dict):
                continue
            scores = run.get("scores") or {}
            if "overall" not in scores:
                continue
            normalized.append(dict(run))

        return sorted(
            normalized,
            key=lambda item: item.get("recorded_at") or "",
            reverse=True,
        )
