from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.program_snapshot_service import ProgramSnapshotService

router = APIRouter(prefix="/api/v1/programs", tags=["programs"])


class UserIdentity(BaseModel):
    id: int
    telegram_id: Optional[int] = None
    username: Optional[str] = None
    language_level: Optional[str] = None


class GoalBriefSummary(BaseModel):
    primary_goal: Optional[str] = None
    target_role: Optional[str] = None
    domain: Optional[str] = None
    target_market: Optional[str] = None
    deadline_type: Optional[str] = None
    main_contexts: list[str] = []
    current_blockers: list[str] = []
    motivation: Optional[str] = None
    confidence: Optional[float] = None
    status: Optional[str] = None
    summary: Optional[str] = None


class GoalSummary(BaseModel):
    text: Optional[str] = None
    preferred_mode: str
    target_level: Optional[str] = None
    focus_areas: list[str]
    brief: Optional[GoalBriefSummary] = None
    missing_fields: list[str] = []


class AssessmentSummary(BaseModel):
    date: Optional[str] = None
    level: str
    scores: dict[str, Any]
    notes: Optional[str] = None
    confidence: Optional[float] = None
    goal_readiness: Optional[float] = None
    critical_gaps: list[str] = []
    skill_axes: dict[str, Any] = {}


class MissionSummary(BaseModel):
    mode: str
    launch_mode: Optional[str] = None
    title: str
    reason: str
    why_now: Optional[str] = None
    linked_goal_context: Optional[str] = None
    linked_skill_gap: Optional[str] = None
    from_interview: bool = False


class ProgramStage(BaseModel):
    id: str
    label: str
    status: str


class ProgramSummary(BaseModel):
    title: str
    time_horizon_days: int
    current_stage: str
    stage_label: str
    weekly_focus: list[str]
    success_metric: str
    next_milestone: str
    stages: list[ProgramStage]
    preferred_mode: str
    focus_areas: list[str] = []


class InterviewRecommendedTrack(BaseModel):
    id: str
    title: str
    subtitle: str


class InterviewScores(BaseModel):
    overall: float
    clarity: float
    structure: float
    accuracy: float
    vocabulary: float
    confidence: float


class InterviewRunMeta(BaseModel):
    user_turns: int
    avg_words_per_turn: float
    corrections_count: int
    weakest_area: str
    strongest_area: str


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


class InterviewSnapshot(BaseModel):
    completed_runs: int
    readiness_score: Optional[float] = None
    trend: str
    recommended_track: InterviewRecommendedTrack
    latest_run: Optional[InterviewRun] = None
    recent_runs: list[InterviewRun]
    weakest_area: Optional[str] = None
    interview_focus: list[str] = []
    last_track: Optional[str] = None


class VocabularyCardPreview(BaseModel):
    id: str
    word: str
    translation: Optional[str] = None
    example_sentence: Optional[str] = None
    due_at: Optional[datetime] = None
    state: int


class VocabularySnapshot(BaseModel):
    stats: dict[str, int]
    due_preview: list[VocabularyCardPreview]


class ErrorPattern(BaseModel):
    label: str
    count: int


class RecentSession(BaseModel):
    id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    corrections_count: int
    summary: Optional[str] = None


class ProgressSnapshot(BaseModel):
    sessions_completed: int
    milestones: list[dict[str, Any]]
    recommended_vocabulary: list[str]
    top_error_patterns: list[ErrorPattern]
    recent_sessions: list[RecentSession]


class SetupSnapshot(BaseModel):
    goal_complete: bool
    assessment_complete: bool
    needs_attention: bool


class ProgramSnapshotResponse(BaseModel):
    user: UserIdentity
    goal: GoalSummary
    assessment: Optional[AssessmentSummary] = None
    program: ProgramSummary
    mission: MissionSummary
    gamification: dict[str, Any]
    interview: InterviewSnapshot
    vocabulary: VocabularySnapshot
    progress: ProgressSnapshot
    setup: SetupSnapshot


@router.get("/{user_id}/snapshot", response_model=ProgramSnapshotResponse)
async def get_program_snapshot(
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> ProgramSnapshotResponse:
    snapshot = await ProgramSnapshotService(db).get_snapshot(user_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="User not found")
    return ProgramSnapshotResponse.model_validate(snapshot)
