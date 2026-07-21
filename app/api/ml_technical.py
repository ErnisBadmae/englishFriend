from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.data.ml_technical_questions import list_ml_technical_topics
from app.services.ml_technical_service import (
    ANSWER_KIND_NORMAL,
    ANSWER_LANGUAGE_DEFAULT,
    SOURCE_CHANNEL_DEFAULT,
    MlTechnicalConflictError,
    MlTechnicalService,
)

router = APIRouter(prefix="/api/v1/ml-technical", tags=["ml_technical"])


class MlTechnicalTopic(BaseModel):
    id: str
    title_ru: str
    description_ru: str


class MlTechnicalQuestionProgress(BaseModel):
    question_id: str
    topic_id: str
    unseen: bool
    attempted: bool
    attempt_count: int
    latest_pass: bool
    needs_review: bool
    due_for_repetition: bool
    best_score_percent: Optional[float] = None
    latest_score_percent: Optional[float] = None
    last_attempted_at: Optional[str] = None


class MlTechnicalTopicProgress(BaseModel):
    topic_id: str
    total_questions: int
    unseen: int
    attempted: int
    passed: int
    needs_review: int
    due_for_repetition: int
    average_latest_score_percent: Optional[float] = None
    questions: list[MlTechnicalQuestionProgress]


class MlTechnicalTrackProgress(BaseModel):
    track_id: str
    pass_threshold_percent: float
    repetition_due_days: int
    total_questions: int
    unseen: int
    attempted: int
    passed: int
    needs_review: int
    due_for_repetition: int
    readiness_percent: float
    topics: list[MlTechnicalTopicProgress]


class MlTechnicalTopicsResponse(BaseModel):
    topics: list[MlTechnicalTopic]
    progress: MlTechnicalTrackProgress


class StartSessionRequest(BaseModel):
    topic_id: str
    session_seed: Optional[str] = None


class SessionQuestion(BaseModel):
    id: str
    topic_id: str
    question_ru: str
    difficulty: str
    tags: list[str]


class StartSessionResponse(BaseModel):
    session_id: str
    topic_id: str
    questions: list[SessionQuestion]


class SubmitAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer_text: str = ""
    answer_language: str = ANSWER_LANGUAGE_DEFAULT
    answer_kind: str = ANSWER_KIND_NORMAL
    source_channel: str = SOURCE_CHANNEL_DEFAULT
    source_event_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_answer_text(self) -> "SubmitAnswerRequest":
        if self.answer_kind == ANSWER_KIND_NORMAL and not self.answer_text.strip():
            raise ValueError("answer_text must not be empty for a normal answer")
        return self


class TechnicalReview(BaseModel):
    status: str
    model_id: str
    prompt_version: str
    rubric_version: Optional[str] = None
    score_percent: Optional[float] = None
    covered_points: list[str] = []
    missing_points: list[str] = []
    covered_points_text: list[str] = []
    missing_points_text: list[str] = []
    incorrect_claims: list[str] = []
    feedback: Optional[str] = None
    follow_up_question: Optional[str] = None
    confidence: Optional[float] = None
    failure_reason: Optional[str] = None


class SubmitAnswerResponse(BaseModel):
    attempt_id: str
    review: TechnicalReview
    reference_explanation_ru: str
    next_question: Optional[SessionQuestion] = None
    question_progress: MlTechnicalQuestionProgress
    topic_progress: MlTechnicalTopicProgress


@router.get("/{user_id}/topics", response_model=MlTechnicalTopicsResponse)
async def get_ml_technical_topics(
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> MlTechnicalTopicsResponse:
    service = MlTechnicalService(db)
    progress = await service.get_progress(user_id)
    return MlTechnicalTopicsResponse.model_validate(
        {"topics": list_ml_technical_topics(), "progress": progress}
    )


@router.post("/{user_id}/sessions", response_model=StartSessionResponse)
async def start_ml_technical_session(
    user_id: int,
    payload: StartSessionRequest,
    db: AsyncSession = Depends(get_db),
) -> StartSessionResponse:
    service = MlTechnicalService(db)
    try:
        result = await service.start_topic_session(
            user_id,
            payload.topic_id,
            session_seed=payload.session_seed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return StartSessionResponse.model_validate(result)


@router.post("/{user_id}/answers", response_model=SubmitAnswerResponse)
async def submit_ml_technical_answer(
    user_id: int,
    payload: SubmitAnswerRequest,
    db: AsyncSession = Depends(get_db),
) -> SubmitAnswerResponse:
    service = MlTechnicalService(db)
    try:
        result = await service.submit_answer(
            user_id,
            session_id=payload.session_id,
            question_id=payload.question_id,
            answer_text=payload.answer_text,
            answer_language=payload.answer_language,
            answer_kind=payload.answer_kind,
            source_channel=payload.source_channel,
            source_event_id=payload.source_event_id,
        )
    except MlTechnicalConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SubmitAnswerResponse.model_validate(result)


@router.get("/{user_id}/attempts", response_model=list[dict])
async def get_ml_technical_attempts(
    user_id: int,
    status: Optional[str] = Query(default=None, pattern="^(graded|needs_review)$"),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    service = MlTechnicalService(db)
    return await service.get_recent_attempts(user_id, status=status, limit=limit)
