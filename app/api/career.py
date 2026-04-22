from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.learning_plan_service import LearningPlanService

router = APIRouter(prefix="/api/v1/career", tags=["career"])


class VacancyInput(BaseModel):
    vacancy_text: str = Field(..., min_length=20)
    interview_date: Optional[str] = None


class VacancyUpdateResponse(BaseModel):
    accepted: bool
    target_role: Optional[str] = None
    vacancy_present: bool = False
    vacancy_summary: Optional[str] = None
    recommended_track: Optional[str] = None
    key_terms: list[str] = []
    top_blockers: list[str] = []


class PaidIntentInput(BaseModel):
    source: str = Field(default="home_cta", min_length=2)
    note: Optional[str] = None


class ProjectNotesInput(BaseModel):
    project_notes: str = Field(..., min_length=20)


class ProjectNotesResponse(BaseModel):
    accepted: bool
    target_role: Optional[str] = None
    problem_statement: Optional[str] = None
    approach_summary: Optional[str] = None
    metrics_and_impact: Optional[str] = None
    english_example_answer: Optional[str] = None
    weak_spots: list[str] = []


class PaidIntentResponse(BaseModel):
    accepted: bool
    submitted_at: str
    source: str
    note: Optional[str] = None
    readiness_score: Optional[float] = None
    sessions_completed: int = 0
    interview_runs_completed: int = 0


@router.post("/{user_id}/vacancy", response_model=VacancyUpdateResponse)
async def submit_vacancy(
    user_id: int,
    payload: VacancyInput,
    db: AsyncSession = Depends(get_db),
) -> VacancyUpdateResponse:
    service = LearningPlanService(db)
    plan = await service.set_vacancy_context(
        user_id,
        payload.vacancy_text,
        interview_date=payload.interview_date,
    )
    career_context = service.get_career_context(plan)
    interview_pack = service.get_interview_pack(plan) or {}
    return VacancyUpdateResponse(
        accepted=True,
        target_role=career_context.get("target_role"),
        vacancy_present=bool(career_context.get("vacancy_present")),
        vacancy_summary=career_context.get("vacancy_summary"),
        recommended_track=interview_pack.get("recommended_track"),
        key_terms=list(interview_pack.get("key_terms") or []),
        top_blockers=list(interview_pack.get("top_blockers") or []),
    )


@router.post("/{user_id}/project-notes", response_model=ProjectNotesResponse)
async def submit_project_notes(
    user_id: int,
    payload: ProjectNotesInput,
    db: AsyncSession = Depends(get_db),
) -> ProjectNotesResponse:
    service = LearningPlanService(db)
    plan = await service.set_project_notes(user_id, payload.project_notes)
    project_story_pack = service.get_project_story_pack(plan) or {}
    return ProjectNotesResponse(
        accepted=True,
        target_role=project_story_pack.get("target_role"),
        problem_statement=project_story_pack.get("problem_statement"),
        approach_summary=project_story_pack.get("approach_summary"),
        metrics_and_impact=project_story_pack.get("metrics_and_impact"),
        english_example_answer=project_story_pack.get("english_example_answer"),
        weak_spots=list(project_story_pack.get("weak_spots") or []),
    )


@router.post("/{user_id}/paid-intent", response_model=PaidIntentResponse)
async def submit_paid_intent(
    user_id: int,
    payload: PaidIntentInput,
    db: AsyncSession = Depends(get_db),
) -> PaidIntentResponse:
    signal = await LearningPlanService(db).record_paid_intent(
        user_id=user_id,
        source=payload.source,
        note=payload.note,
    )
    return PaidIntentResponse(accepted=True, **signal)
