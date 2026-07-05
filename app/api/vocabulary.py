from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.core_tables import User
from app.models.extended_tables import VocabularyCard
from app.services.ai.vocabulary_service import ReviewRating, VocabularyService


router = APIRouter(prefix="/api/v1/vocabulary", tags=["vocabulary"])


class VocabularyCardResponse(BaseModel):
    id: str
    word: str
    translation: Optional[str] = None
    example_sentence: Optional[str] = None
    phonetic: Optional[str] = None
    due_at: datetime
    fsrs_state: int
    review_count: int
    correct_count: int


class VocabularyStatsResponse(BaseModel):
    total: int
    new: int
    learning: int
    review: int
    relearning: int
    due_now: int


class ReviewCardRequest(BaseModel):
    card_id: str
    rating: int = Field(..., ge=1, le=4)
    session_id: Optional[str] = None
    duration_ms: Optional[int] = Field(default=None, ge=0)


async def _ensure_user_exists(db: AsyncSession, user_id: int) -> None:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")


@router.get("/{user_id}/stats", response_model=VocabularyStatsResponse)
async def get_vocabulary_stats(
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> VocabularyStatsResponse:
    await _ensure_user_exists(db, user_id)
    vocabulary_service = VocabularyService(db)
    stats = await vocabulary_service.get_vocabulary_stats(user_id)
    return VocabularyStatsResponse(**stats)


@router.get("/{user_id}/due", response_model=list[VocabularyCardResponse])
async def get_due_cards(
    user_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[VocabularyCardResponse]:
    await _ensure_user_exists(db, user_id)
    vocabulary_service = VocabularyService(db)
    cards = await vocabulary_service.get_due_cards(user_id, limit=limit)
    return [
        VocabularyCardResponse(
            id=card.id,
            word=card.word,
            translation=card.translation,
            example_sentence=card.example_sentence,
            phonetic=card.phonetic,
            due_at=card.due_at,
            fsrs_state=card.fsrs_state,
            review_count=card.review_count,
            correct_count=card.correct_count,
        )
        for card in cards
    ]


@router.post("/{user_id}/review", response_model=VocabularyCardResponse)
async def review_card(
    user_id: int,
    payload: ReviewCardRequest,
    db: AsyncSession = Depends(get_db),
) -> VocabularyCardResponse:
    await _ensure_user_exists(db, user_id)
    vocabulary_service = VocabularyService(db)
    card = await db.get(VocabularyCard, payload.card_id)
    if card is None or card.user_id != user_id:
        raise HTTPException(status_code=404, detail="Vocabulary card not found")

    updated = await vocabulary_service.review_card(
        card=card,
        rating=ReviewRating(payload.rating),
        session_id=payload.session_id,
        duration_ms=payload.duration_ms,
    )
    return VocabularyCardResponse(
        id=updated.id,
        word=updated.word,
        translation=updated.translation,
        example_sentence=updated.example_sentence,
        phonetic=updated.phonetic,
        due_at=updated.due_at,
        fsrs_state=updated.fsrs_state,
        review_count=updated.review_count,
        correct_count=updated.correct_count,
    )
