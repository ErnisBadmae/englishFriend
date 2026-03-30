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


class GoalSummary(BaseModel):
    text: Optional[str] = None
    preferred_mode: str
    target_level: Optional[str] = None
    focus_areas: list[str]


class AssessmentSummary(BaseModel):
    date: Optional[str] = None
    level: str
    scores: dict[str, Any]
    notes: Optional[str] = None


class MissionSummary(BaseModel):
    mode: str
    title: str
    reason: str


class XPInfo(BaseModel):
    total_xp: int
    level: int
    current_level_xp: int
    next_level_xp: int
    progress: float


class StreakInfo(BaseModel):
    current: int
    max: int
    at_risk: bool
    last_activity: Optional[str] = None


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


class ProgramSnapshotResponse(BaseModel):
    user: UserIdentity
    goal: GoalSummary
    assessment: Optional[AssessmentSummary] = None
    mission: MissionSummary
    gamification: dict[str, Any]
    vocabulary: VocabularySnapshot
    progress: ProgressSnapshot


@router.get("/{user_id}/snapshot", response_model=ProgramSnapshotResponse)
async def get_program_snapshot(
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> ProgramSnapshotResponse:
    snapshot_service = ProgramSnapshotService(db)
    snapshot = await snapshot_service.get_snapshot(user_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="User not found")
    return ProgramSnapshotResponse.model_validate(snapshot)
