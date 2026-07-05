from typing import List
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse

from app.schemas.dimensions import (
    DimEmotionCreate, DimEmotionResponse, 
    DimTopicCreate, DimTopicResponse,
    DimAccentCreate, DimAccentResponse
)
from app.services.dimensions import DimensionService
from app.core.deps import get_db

router = APIRouter(prefix="/api/v1/dimensions", tags=["dimensions"])

# Endpoints для эмоций
@router.post("/emotions/", response_model=DimEmotionResponse, status_code=201)
async def create_emotion(emotion_data: DimEmotionCreate, db: AsyncSession = Depends(get_db)):
    """
    Создать новую эмоцию в справочнике.
    
    Добавляет новую эмоцию с указанным кодом, названием и параметрами валентности/возбуждения.
    """
    try:
        dimension_service = DimensionService(db)
        emotion = await dimension_service.create_emotion(emotion_data)
        return DimEmotionResponse(
            code=emotion.code,
            name_ru=emotion.name_ru,
            valence=emotion.valence,
            arousal=emotion.arousal
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка создания эмоции: {str(e)}")

@router.get("/emotions/{code}", response_model=DimEmotionResponse)
async def get_emotion(code: str, db: AsyncSession = Depends(get_db)):
    """
    Получить эмоцию по коду.
    
    Возвращает данные эмоции с указанным кодом.
    """
    dimension_service = DimensionService(db)
    emotion = await dimension_service.get_emotion(code)
    if not emotion:
        raise HTTPException(status_code=404, detail="Эмоция не найдена")
    
    return DimEmotionResponse(
        code=emotion.code,
        name_ru=emotion.name_ru,
        valence=emotion.valence,
        arousal=emotion.arousal
    )

@router.get("/emotions/", response_model=List[DimEmotionResponse])
async def get_emotions(
    skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество записей"),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить список всех эмоций.
    
    Возвращает список эмоций с пагинацией.
    """
    dimension_service = DimensionService(db)
    emotions = await dimension_service.get_emotions(skip=skip, limit=limit)
    return [
        DimEmotionResponse(
            code=emotion.code,
            name_ru=emotion.name_ru,
            valence=emotion.valence,
            arousal=emotion.arousal
        ) for emotion in emotions
    ]

# Endpoints для тем
@router.post("/topics/", response_model=DimTopicResponse, status_code=201)
async def create_topic(topic_data: DimTopicCreate, db: AsyncSession = Depends(get_db)):
    """
    Создать новую тему в справочнике.
    
    Добавляет новую тему с указанным слагом и названием.
    """
    try:
        dimension_service = DimensionService(db)
        topic = await dimension_service.create_topic(topic_data)
        return DimTopicResponse(
            id=topic.id,
            slug=topic.slug,
            display_name=topic.display_name,
            parent_id=topic.parent_id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка создания темы: {str(e)}")

@router.get("/topics/{topic_id}", response_model=DimTopicResponse)
async def get_topic(topic_id: str, db: AsyncSession = Depends(get_db)):
    """
    Получить тему по ID.
    
    Возвращает данные темы с указанным ID.
    """
    dimension_service = DimensionService(db)
    topic = await dimension_service.get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Тема не найдена")
    
    return DimTopicResponse(
        id=topic.id,
        slug=topic.slug,
        display_name=topic.display_name,
        parent_id=topic.parent_id
    )

@router.get("/topics/slug/{slug}", response_model=DimTopicResponse)
async def get_topic_by_slug(slug: str, db: AsyncSession = Depends(get_db)):
    """
    Получить тему по слагу.
    
    Возвращает данные темы с указанным слагом.
    """
    dimension_service = DimensionService(db)
    topic = await dimension_service.get_topic_by_slug(slug)
    if not topic:
        raise HTTPException(status_code=404, detail="Тема не найдена")
    
    return DimTopicResponse(
        id=topic.id,
        slug=topic.slug,
        display_name=topic.display_name,
        parent_id=topic.parent_id
    )

@router.get("/topics/", response_model=List[DimTopicResponse])
async def get_topics(
    skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество записей"),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить список всех тем.
    
    Возвращает список тем с пагинацией.
    """
    dimension_service = DimensionService(db)
    topics = await dimension_service.get_topics(skip=skip, limit=limit)
    return [
        DimTopicResponse(
            id=topic.id,
            slug=topic.slug,
            display_name=topic.display_name,
            parent_id=topic.parent_id
        ) for topic in topics
    ]

# Endpoints для акцентов
@router.post("/accents/", response_model=DimAccentResponse, status_code=201)
async def create_accent(accent_data: DimAccentCreate, db: AsyncSession = Depends(get_db)):
    """
    Создать новый акцент в справочнике.
    
    Добавляет новый акцент с указанным кодом и названием.
    """
    try:
        dimension_service = DimensionService(db)
        accent = await dimension_service.create_accent(accent_data)
        return DimAccentResponse(
            code=accent.code,
            display_name=accent.display_name
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка создания акцента: {str(e)}")

@router.get("/accents/{code}", response_model=DimAccentResponse)
async def get_accent(code: str, db: AsyncSession = Depends(get_db)):
    """
    Получить акцент по коду.
    
    Возвращает данные акцента с указанным кодом.
    """
    dimension_service = DimensionService(db)
    accent = await dimension_service.get_accent(code)
    if not accent:
        raise HTTPException(status_code=404, detail="Акцент не найден")
    
    return DimAccentResponse(
        code=accent.code,
        display_name=accent.display_name
    )

@router.get("/accents/", response_model=List[DimAccentResponse])
async def get_accents(
    skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество записей"),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить список всех акцентов.
    
    Возвращает список акцентов с пагинацией.
    """
    dimension_service = DimensionService(db)
    accents = await dimension_service.get_accents(skip=skip, limit=limit)
    return [
        DimAccentResponse(
            code=accent.code,
            display_name=accent.display_name
        ) for accent in accents
    ]
