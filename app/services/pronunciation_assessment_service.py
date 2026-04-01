from __future__ import annotations

from datetime import datetime
from statistics import mean
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.ai.pronunciation_provider import get_pronunciation_provider


def build_pronunciation_summary(assessments: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(
        [item for item in assessments if isinstance(item, dict) and item.get("overall_score") is not None],
        key=lambda item: item.get("recorded_at") or "",
        reverse=True,
    )

    if not ordered:
        return {
            "latest_score": None,
            "accuracy_score": None,
            "fluency_score": None,
            "prosody_score": None,
            "focus": [],
            "word_feedback": [],
            "source": None,
            "assessment_mode": None,
            "confidence": None,
            "last_assessed_at": None,
            "trend": "building",
            "history_count": 0,
        }

    latest = ordered[0]
    latest_score = float(latest["overall_score"])
    previous_scores = [float(item["overall_score"]) for item in ordered[1:4]]
    if previous_scores:
        delta = latest_score - mean(previous_scores)
        if delta >= 0.5:
            trend = "rising"
        elif delta <= -0.5:
            trend = "needs_stability"
        else:
            trend = "steady"
    else:
        trend = "building"

    return {
        "latest_score": latest_score,
        "accuracy_score": latest.get("accuracy_score"),
        "fluency_score": latest.get("fluency_score"),
        "prosody_score": latest.get("prosody_score"),
        "focus": latest.get("recommended_focus") or [],
        "word_feedback": latest.get("word_feedback") or [],
        "source": latest.get("source") or latest.get("provider"),
        "assessment_mode": latest.get("assessment_mode"),
        "confidence": latest.get("confidence"),
        "last_assessed_at": latest.get("recorded_at"),
        "trend": trend,
        "history_count": len(ordered),
    }


class PronunciationAssessmentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.provider = get_pronunciation_provider()

    async def assess_conversation(
        self,
        *,
        session_id: str,
        conversation_history: list[dict[str, str]],
        track_id: Optional[str] = None,
        reference_text: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        user_messages = [
            message.get("content", "").strip()
            for message in conversation_history
            if message.get("role") == "user" and message.get("content")
        ]
        transcript = " ".join(item for item in user_messages if item).strip()
        if len(transcript.split()) < 4:
            return None

        result = await self.provider.assess(
            transcript=transcript,
            locale=settings.pronunciation_locale,
            scenario=track_id,
            reference_text=reference_text,
        )
        recorded_at = datetime.utcnow().isoformat()

        return {
            "session_id": session_id,
            "track_id": track_id,
            "recorded_at": recorded_at,
            "source": result.provider,
            **result.to_dict(),
        }
