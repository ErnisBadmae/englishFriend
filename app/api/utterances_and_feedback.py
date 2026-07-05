from typing import List
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse

from app.schemas.extended_schemas import (
    UtteranceCreate, UtteranceResponse, UtteranceListResponse
)
from app.schemas.additional_schemas import (
    CorrectionCreate, CorrectionResponse, CorrectionListResponse,
    FeedbackCreate, FeedbackResponse, FeedbackUpdate
)
from app.services.utterances_and_feedback import UtteranceService, FeedbackService, CorrectionService
from app.core.deps import get_db

router = APIRouter(prefix="/api/v1", tags=["utterances", "feedback", "corrections"])

# Endpoints для реплик
@router.post("/utterances/", response_model=UtteranceResponse, status_code=201)
async def create_utterance(utterance_data: UtteranceCreate, db: AsyncSession = Depends(get_db)):
    """
    Создать новую реплику в диалоге.
    
    Добавляет реплику пользователя или ассистента с временными метками и анализом.
    """
    try:
        utterance_service = UtteranceService(db)
        utterance = await utterance_service.create_utterance(utterance_data)
        return UtteranceResponse(
            id=utterance.id,
            session_id=utterance.session_id,
            speaker=utterance.speaker,
            t_start_ms=utterance.t_start_ms,
            t_end_ms=utterance.t_end_ms,
            text=utterance.text,
            phonemes=utterance.phonemes,
            topics=utterance.topics,
            emotion_code=utterance.emotion_code,
            emotion_score=utterance.emotion_score,
            grammar_score=utterance.grammar_score,
            pronunciation_score=utterance.pronunciation_score
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка создания реплики: {str(e)}")

@router.get("/utterances/{utterance_id}", response_model=UtteranceResponse)
async def get_utterance(utterance_id: str, db: AsyncSession = Depends(get_db)):
    """
    Получить реплику по ID.
    
    Возвращает данные реплики с указанным ID.
    """
    utterance_service = UtteranceService(db)
    utterance = await utterance_service.get_utterance(utterance_id)
    if not utterance:
        raise HTTPException(status_code=404, detail="Реплика не найдена")
    
    return UtteranceResponse(
        id=utterance.id,
        session_id=utterance.session_id,
        speaker=utterance.speaker,
        t_start_ms=utterance.t_start_ms,
        t_end_ms=utterance.t_end_ms,
        text=utterance.text,
        phonemes=utterance.phonemes,
        topics=utterance.topics,
        emotion_code=utterance.emotion_code,
        emotion_score=utterance.emotion_score,
        grammar_score=utterance.grammar_score,
        pronunciation_score=utterance.pronunciation_score
    )

@router.get("/sessions/{session_id}/utterances", response_model=UtteranceListResponse)
async def get_session_utterances(
    session_id: str,
    skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество записей"),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить реплики сессии.
    
    Возвращает список реплик для указанной сессии, отсортированных по времени.
    """
    utterance_service = UtteranceService(db)
    utterances = await utterance_service.get_session_utterances(session_id, skip=skip, limit=limit)
    return UtteranceListResponse(
        utterances=[
            UtteranceResponse(
                id=utterance.id,
                session_id=utterance.session_id,
                speaker=utterance.speaker,
                t_start_ms=utterance.t_start_ms,
                t_end_ms=utterance.t_end_ms,
                text=utterance.text,
                phonemes=utterance.phonemes,
                topics=utterance.topics,
                emotion_code=utterance.emotion_code,
                emotion_score=utterance.emotion_score,
                grammar_score=utterance.grammar_score,
                pronunciation_score=utterance.pronunciation_score
            ) for utterance in utterances
        ],
        total=len(utterances)
    )

@router.get("/users/{user_id}/utterances", response_model=UtteranceListResponse)
async def get_user_utterances(
    user_id: int,
    skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество записей"),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить реплики пользователя.
    
    Возвращает список реплик пользователя из всех его сессий.
    """
    utterance_service = UtteranceService(db)
    utterances = await utterance_service.get_user_utterances(user_id, skip=skip, limit=limit)
    return UtteranceListResponse(
        utterances=[
            UtteranceResponse(
                id=utterance.id,
                session_id=utterance.session_id,
                speaker=utterance.speaker,
                t_start_ms=utterance.t_start_ms,
                t_end_ms=utterance.t_end_ms,
                text=utterance.text,
                phonemes=utterance.phonemes,
                topics=utterance.topics,
                emotion_code=utterance.emotion_code,
                emotion_score=utterance.emotion_score,
                grammar_score=utterance.grammar_score,
                pronunciation_score=utterance.pronunciation_score
            ) for utterance in utterances
        ],
        total=len(utterances)
    )

# Endpoints для обратной связи
@router.post("/feedback/", response_model=FeedbackResponse, status_code=201)
async def create_feedback(feedback_data: FeedbackCreate, db: AsyncSession = Depends(get_db)):
    """
    Создать обратную связь по сессии.
    
    Добавляет детальную обратную связь с оценками грамматики и произношения.
    """
    try:
        feedback_service = FeedbackService(db)
        feedback = await feedback_service.create_feedback(feedback_data)
        return FeedbackResponse(
            session_id=feedback.session_id,
            overall_grammar=feedback.overall_grammar,
            overall_pronunciation=feedback.overall_pronunciation,
            summary_md=feedback.summary_md,
            tips_md=feedback.tips_md,
            corrected_phrases=feedback.corrected_phrases,
            grammar_tips=feedback.grammar_tips,
            pronunciation_tips=feedback.pronunciation_tips,
            vocabulary_suggestions=feedback.vocabulary_suggestions
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка создания обратной связи: {str(e)}")

@router.get("/sessions/{session_id}/feedback", response_model=FeedbackResponse)
async def get_session_feedback(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Получить обратную связь по сессии.
    
    Возвращает обратную связь для указанной сессии.
    """
    feedback_service = FeedbackService(db)
    feedback = await feedback_service.get_feedback(session_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="Обратная связь не найдена")
    
    return FeedbackResponse(
        session_id=feedback.session_id,
        overall_grammar=feedback.overall_grammar,
        overall_pronunciation=feedback.overall_pronunciation,
        summary_md=feedback.summary_md,
        tips_md=feedback.tips_md,
        corrected_phrases=feedback.corrected_phrases,
        grammar_tips=feedback.grammar_tips,
        pronunciation_tips=feedback.pronunciation_tips,
        vocabulary_suggestions=feedback.vocabulary_suggestions
    )

@router.put("/sessions/{session_id}/feedback", response_model=FeedbackResponse)
async def update_session_feedback(
    session_id: str, 
    feedback_data: FeedbackUpdate, 
    db: AsyncSession = Depends(get_db)
):
    """
    Обновить обратную связь по сессии.
    
    Обновляет существующую обратную связь для указанной сессии.
    """
    feedback_service = FeedbackService(db)
    updated_feedback = await feedback_service.update_feedback(session_id, feedback_data)
    if not updated_feedback:
        raise HTTPException(status_code=404, detail="Обратная связь не найдена")
    
    return FeedbackResponse(
        session_id=updated_feedback.session_id,
        overall_grammar=updated_feedback.overall_grammar,
        overall_pronunciation=updated_feedback.overall_pronunciation,
        summary_md=updated_feedback.summary_md,
        tips_md=updated_feedback.tips_md,
        corrected_phrases=updated_feedback.corrected_phrases,
        grammar_tips=updated_feedback.grammar_tips,
        pronunciation_tips=updated_feedback.pronunciation_tips,
        vocabulary_suggestions=updated_feedback.vocabulary_suggestions
    )

# Endpoints для исправлений
@router.post("/corrections/", response_model=CorrectionResponse, status_code=201)
async def create_correction(correction_data: CorrectionCreate, db: AsyncSession = Depends(get_db)):
    """
    Создать исправление ошибки.
    
    Добавляет исправление с объяснением грамматического правила.
    """
    try:
        correction_service = CorrectionService(db)
        correction = await correction_service.create_correction(correction_data)
        return CorrectionResponse(
            id=correction.id,
            session_id=correction.session_id,
            utterance_id=correction.utterance_id,
            user_text=correction.user_text,
            corrected_text=correction.corrected_text,
            rule_tag=correction.rule_tag,
            explanation_md=correction.explanation_md
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка создания исправления: {str(e)}")

@router.get("/corrections/{correction_id}", response_model=CorrectionResponse)
async def get_correction(correction_id: str, db: AsyncSession = Depends(get_db)):
    """
    Получить исправление по ID.
    
    Возвращает данные исправления с указанным ID.
    """
    correction_service = CorrectionService(db)
    correction = await correction_service.get_correction(correction_id)
    if not correction:
        raise HTTPException(status_code=404, detail="Исправление не найдено")
    
    return CorrectionResponse(
        id=correction.id,
        session_id=correction.session_id,
        utterance_id=correction.utterance_id,
        user_text=correction.user_text,
        corrected_text=correction.corrected_text,
        rule_tag=correction.rule_tag,
        explanation_md=correction.explanation_md
    )

@router.get("/sessions/{session_id}/corrections", response_model=CorrectionListResponse)
async def get_session_corrections(
    session_id: str,
    skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество записей"),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить исправления сессии.
    
    Возвращает список исправлений для указанной сессии.
    """
    correction_service = CorrectionService(db)
    corrections = await correction_service.get_session_corrections(session_id, skip=skip, limit=limit)
    return CorrectionListResponse(
        corrections=[
            CorrectionResponse(
                id=correction.id,
                session_id=correction.session_id,
                utterance_id=correction.utterance_id,
                user_text=correction.user_text,
                corrected_text=correction.corrected_text,
                rule_tag=correction.rule_tag,
                explanation_md=correction.explanation_md
            ) for correction in corrections
        ],
        total=len(corrections)
    )

@router.get("/users/{user_id}/corrections", response_model=CorrectionListResponse)
async def get_user_corrections(
    user_id: int,
    skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество записей"),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить исправления пользователя.
    
    Возвращает список исправлений пользователя из всех его сессий.
    """
    correction_service = CorrectionService(db)
    corrections = await correction_service.get_user_corrections(user_id, skip=skip, limit=limit)
    return CorrectionListResponse(
        corrections=[
            CorrectionResponse(
                id=correction.id,
                session_id=correction.session_id,
                utterance_id=correction.utterance_id,
                user_text=correction.user_text,
                corrected_text=correction.corrected_text,
                rule_tag=correction.rule_tag,
                explanation_md=correction.explanation_md
            ) for correction in corrections
        ],
        total=len(corrections)
    )
