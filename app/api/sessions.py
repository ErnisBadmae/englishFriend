from typing import List
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.session import SessionCreate, SessionUpdate, SessionResponse
from app.services.database import SessionService
from app.core.deps import get_db

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

@router.post("/", response_model=SessionResponse, status_code=201)
async def create_session(session_data: SessionCreate, db: AsyncSession = Depends(get_db)):
    """
    Создать новую сессию.
    
    Создает новую сессию для указанного пользователя.
    """
    session_service = SessionService(db)
    session = await session_service.create_session(session_data)
    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        audio_url=session.audio_url,
        lang_code=session.lang_code,
        call_quality=session.call_quality
    )

@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Получить сессию по ID.
    
    Возвращает данные сессии с указанным ID.
    """
    session_service = SessionService(db)
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    
    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        audio_url=session.audio_url,
        lang_code=session.lang_code,
        call_quality=session.call_quality
    )

@router.get("/user/{user_id}", response_model=List[SessionResponse])
async def get_user_sessions(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Получить все сессии пользователя.
    
    Возвращает список всех сессий для указанного пользователя.
    """
    session_service = SessionService(db)
    sessions = await session_service.get_user_sessions(user_id)
    
    return [
        SessionResponse(
            id=session.id,
            user_id=session.user_id,
            started_at=session.started_at,
            ended_at=session.ended_at,
            audio_url=session.audio_url,
            lang_code=session.lang_code,
            call_quality=session.call_quality
        )
        for session in sessions
    ]

@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(session_id: str, session_data: SessionUpdate, db: AsyncSession = Depends(get_db)):
    """
    Обновить данные сессии.
    
    Обновляет время завершения, URL аудио или статус сессии.
    """
    session_service = SessionService(db)
    session = await session_service.update_session(session_id, session_data)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    
    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        audio_url=session.audio_url,
        lang_code=session.lang_code,
        call_quality=session.call_quality
    )

@router.post("/{session_id}/complete", response_model=SessionResponse)
async def complete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Завершить сессию.
    
    Помечает сессию как завершенную и устанавливает время окончания.
    """
    session_service = SessionService(db)
    session = await session_service.complete_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    
    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        audio_url=session.audio_url,
        lang_code=session.lang_code,
        call_quality=session.call_quality
    )
