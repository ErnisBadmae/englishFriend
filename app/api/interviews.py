from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.interview_service import InterviewService


router = APIRouter(prefix="/api/v1/interviews", tags=["interviews"])


class RecommendedTrack(BaseModel):
    id: str
    title: str
    subtitle: str


class InterviewRunMeta(BaseModel):
    user_turns: int
    avg_words_per_turn: float
    corrections_count: int
    weakest_area: str
    strongest_area: str


class InterviewScores(BaseModel):
    overall: float
    clarity: float
    structure: float
    accuracy: float
    vocabulary: float
    confidence: float


class InterviewRun(BaseModel):
    id: str
    session_id: str
    track_id: str
    track_title: str
    track_subtitle: str
    recorded_at: str
    scores: InterviewScores
    strengths: list[str]
    next_focus: list[str]
    rubric_notes: list[str] = []
    summary: str
    meta: InterviewRunMeta
    delta_vs_previous: Optional[float] = None


class InterviewSummary(BaseModel):
    completed_runs: int
    readiness_score: Optional[float] = None
    trend: str
    recommended_track: RecommendedTrack
    latest_run: Optional[InterviewRun] = None
    recent_runs: list[InterviewRun]


class InterviewTrack(BaseModel):
    id: str
    title: str
    subtitle: str
    description: str
    prompt_focus: str
    starter_question: str
    rubric_focus: list[str]
    recommended: bool
    completed_runs: int


class InterviewTracksResponse(BaseModel):
    summary: InterviewSummary
    tracks: list[InterviewTrack]


class InterviewTranscriptMessage(BaseModel):
    role: str
    content: str


class CreateInterviewRunRequest(BaseModel):
    session_id: str
    track_id: Optional[str] = None
    corrections_count: int = 0
    reviewed_words: list[dict] = Field(default_factory=list)
    conversation_history: list[InterviewTranscriptMessage]


@router.get("/{user_id}/tracks", response_model=InterviewTracksResponse)
async def get_interview_tracks(
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> InterviewTracksResponse:
    service = InterviewService(db)
    payload = await service.get_tracks(user_id)
    return InterviewTracksResponse.model_validate(payload)


@router.get("/{user_id}/runs", response_model=list[InterviewRun])
async def get_interview_runs(
    user_id: int,
    limit: int = Query(10, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
) -> list[InterviewRun]:
    service = InterviewService(db)
    runs = await service.get_runs(user_id, limit=limit)
    return [InterviewRun.model_validate(run) for run in runs]


@router.post("/{user_id}/runs", response_model=InterviewRun)
async def create_interview_run(
    user_id: int,
    payload: CreateInterviewRunRequest,
    db: AsyncSession = Depends(get_db),
) -> InterviewRun:
    service = InterviewService(db)
    run = await service.record_run(
        user_id=user_id,
        session_id=payload.session_id,
        conversation_history=[
            {"role": item.role, "content": item.content}
            for item in payload.conversation_history
        ],
        corrections_count=payload.corrections_count,
        reviewed_words=payload.reviewed_words,
        track_id=payload.track_id,
    )
    return InterviewRun.model_validate(run)
