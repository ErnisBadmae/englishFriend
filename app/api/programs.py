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
    draft_available: bool = False


class AssessmentSummary(BaseModel):
    date: Optional[str] = None
    level: str
    scores: dict[str, Any]
    notes: Optional[str] = None
    confidence: Optional[float] = None
    status: Optional[str] = None
    provisional: bool = False
    source: Optional[str] = None
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
    interview_track_id: Optional[str] = None
    task_type: str
    expected_outcome: str
    estimated_minutes: int
    success_signal: str
    adaptation_reason: Optional[str] = None
    evidence_source: str = "stage_default"
    repeat_vs_advance: str = "new"


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


class CareerContextSummary(BaseModel):
    target_role: Optional[str] = None
    company_type: Optional[str] = None
    interview_date: Optional[str] = None
    target_market: Optional[str] = None
    vacancy_present: bool = False
    vacancy_summary: Optional[str] = None


class InterviewPackSummary(BaseModel):
    target_role: Optional[str] = None
    must_answer_questions: list[str] = []
    project_story_prompts: list[str] = []
    key_terms: list[str] = []
    top_blockers: list[str] = []
    recommended_track: Optional[str] = None
    recommended_track_title: Optional[str] = None
    summary: Optional[str] = None


class ProjectStoryPackSummary(BaseModel):
    target_role: Optional[str] = None
    problem_statement: Optional[str] = None
    approach_summary: Optional[str] = None
    metrics_and_impact: Optional[str] = None
    english_example_answer: Optional[str] = None
    weak_spots: list[str] = []
    updated_at: Optional[str] = None


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


class PronunciationWordFeedback(BaseModel):
    word: str
    issue: str
    severity: str
    tip: str


class PronunciationSummary(BaseModel):
    latest_score: Optional[float] = None
    accuracy_score: Optional[float] = None
    fluency_score: Optional[float] = None
    prosody_score: Optional[float] = None
    focus: list[str] = []
    word_feedback: list[PronunciationWordFeedback] = []
    source: Optional[str] = None
    assessment_mode: Optional[str] = None
    confidence: Optional[float] = None
    last_assessed_at: Optional[str] = None
    trend: str = "building"
    history_count: int = 0


class InterviewPronunciationResult(BaseModel):
    session_id: str
    track_id: Optional[str] = None
    recorded_at: str
    provider: str
    assessment_mode: str
    overall_score: float
    accuracy_score: float
    fluency_score: float
    prosody_score: Optional[float] = None
    confidence: float
    notes: str
    recommended_focus: list[str] = []
    word_feedback: list[PronunciationWordFeedback] = []


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
    pronunciation: Optional[InterviewPronunciationResult] = None


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
    improvement_signals: list[str] = []
    recurring_issue: Optional[str] = None
    what_improved: list[str] = []
    western_readiness: Optional[dict[str, Any]] = None
    reusable_answers: list[dict[str, Any]] = []


class SessionEvidence(BaseModel):
    id: str
    session_id: str
    mission_type: str
    mode: Optional[str] = None
    task_type: Optional[str] = None
    linked_goal_context: Optional[str] = None
    mission_title: str
    summary: str
    what_was_trained: str
    what_went_well: list[str] = []
    main_issue: Optional[str] = None
    next_focus: list[str] = []
    evidence_signals: list[str] = []
    outcome_score: Optional[float] = None
    weakness_tags: list[str] = []
    improvement_tags: list[str] = []
    adaptation_hint: Optional[str] = None
    mission_reason: Optional[str] = None
    recorded_at: str
    duration_minutes: int = 0


class SessionEvidenceSnapshot(BaseModel):
    latest: Optional[SessionEvidence] = None
    recent: list[SessionEvidence] = []


class SetupSnapshot(BaseModel):
    goal_complete: bool
    assessment_complete: bool
    needs_attention: bool
    state: str
    scope_status: Optional[str] = None
    next_question_type: Optional[str] = None
    progress: int = 0


class MonetizationSnapshot(BaseModel):
    show_paid_cta: bool = False
    paid_intent_submitted: bool = False
    latest_paid_intent_at: Optional[str] = None
    latest_paid_intent_context: Optional[str] = None


class ProgramSnapshotResponse(BaseModel):
    user: UserIdentity
    goal: GoalSummary
    assessment: Optional[AssessmentSummary] = None
    program: ProgramSummary
    career_context: CareerContextSummary
    interview_pack: Optional[InterviewPackSummary] = None
    project_story_pack: Optional[ProjectStoryPackSummary] = None
    mission: MissionSummary
    gamification: dict[str, Any]
    interview: InterviewSnapshot
    pronunciation: PronunciationSummary
    vocabulary: VocabularySnapshot
    progress: ProgressSnapshot
    session_evidence: SessionEvidenceSnapshot
    setup: SetupSnapshot
    monetization: MonetizationSnapshot


@router.get("/{user_id}/snapshot", response_model=ProgramSnapshotResponse)
async def get_program_snapshot(
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> ProgramSnapshotResponse:
    snapshot = await ProgramSnapshotService(db).get_snapshot(user_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="User not found")
    return ProgramSnapshotResponse.model_validate(snapshot)
