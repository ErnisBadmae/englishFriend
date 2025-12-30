from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse

from app.schemas.additional_schemas import (
    UserInterestCreate, UserInterestResponse, UserInterestListResponse, UserInterestUpdate,
    MemoryCreate, MemoryResponse, MemoryListResponse, MemoryUpdate,
    LearningPlanCreate, LearningPlanResponse, LearningPlanListResponse, LearningPlanUpdate,
    XPEventCreate, XPEventResponse, XPEventListResponse
)
from app.services.memory_and_interests import (
    UserInterestService, MemoryService, LearningPlanService, 
    XPEventService
)
from app.core.database import get_db
from app.models.enums_and_dimensions import MemoryKind

router = APIRouter(prefix="/api/v1", tags=["interests", "memory", "learning", "xp"])

# Endpoints для интересов пользователя
@router.post("/users/{user_id}/interests", response_model=UserInterestResponse, status_code=201)
async def create_user_interest(
    user_id: int, 
    interest_data: UserInterestCreate, 
    db: AsyncSession = Depends(get_db)
):
    """
    Создать интерес пользователя.
    
    Добавляет новый интерес пользователя к определенной теме.
    """
    try:
        interest_service = UserInterestService(db)
        interest = await interest_service.create_interest(interest_data)
        return UserInterestResponse(
            user_id=interest.user_id,
            topic_id=interest.topic_id,
            weight=interest.weight,
            last_mentioned=interest.last_mentioned
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка создания интереса: {str(e)}")

@router.get("/users/{user_id}/interests", response_model=UserInterestListResponse)
async def get_user_interests(
    user_id: int,
    skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество записей"),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить интересы пользователя.
    
    Возвращает список интересов пользователя, отсортированных по весу.
    """
    interest_service = UserInterestService(db)
    interests = await interest_service.get_user_interests(user_id, skip=skip, limit=limit)
    return UserInterestListResponse(
        interests=[
            UserInterestResponse(
                user_id=interest.user_id,
                topic_id=interest.topic_id,
                weight=interest.weight,
                last_mentioned=interest.last_mentioned
            ) for interest in interests
        ],
        total=len(interests)
    )

@router.get("/users/{user_id}/interests/top", response_model=UserInterestListResponse)
async def get_top_user_interests(
    user_id: int,
    limit: int = Query(10, ge=1, le=50, description="Количество топ интересов"),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить топ интересы пользователя.
    
    Возвращает самые важные интересы пользователя.
    """
    interest_service = UserInterestService(db)
    interests = await interest_service.get_top_interests(user_id, limit=limit)
    return UserInterestListResponse(
        interests=[
            UserInterestResponse(
                user_id=interest.user_id,
                topic_id=interest.topic_id,
                weight=interest.weight,
                last_mentioned=interest.last_mentioned
            ) for interest in interests
        ],
        total=len(interests)
    )

@router.put("/users/{user_id}/interests/{topic_id}", response_model=UserInterestResponse)
async def update_interest_weight(
    user_id: int,
    topic_id: str,
    weight: float = Query(..., ge=0, le=1, description="Новый вес интереса (0-1)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Обновить вес интереса пользователя.
    
    Обновляет важность интереса пользователя к теме.
    """
    interest_service = UserInterestService(db)
    updated_interest = await interest_service.update_interest_weight(user_id, topic_id, weight)
    if not updated_interest:
        raise HTTPException(status_code=404, detail="Интерес не найден")
    
    return UserInterestResponse(
        user_id=updated_interest.user_id,
        topic_id=updated_interest.topic_id,
        weight=updated_interest.weight,
        last_mentioned=updated_interest.last_mentioned
    )

# Endpoints для памяти
@router.post("/memories/", response_model=MemoryResponse, status_code=201)
async def create_memory(memory_data: MemoryCreate, db: AsyncSession = Depends(get_db)):
    """
    Создать запись памяти.
    
    Добавляет новую запись в память пользователя (эпизодическую, семантическую и т.д.).
    """
    try:
        memory_service = MemoryService(db)
        memory = await memory_service.create_memory(memory_data)
        return MemoryResponse(
            id=memory.id,
            user_id=memory.user_id,
            kind=memory.kind,
            content=memory.content,
            meta=memory.meta,
            salience=memory.salience,
            created_at=memory.created_at,
            last_refreshed=memory.last_refreshed
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка создания памяти: {str(e)}")

@router.get("/memories/{memory_id}", response_model=MemoryResponse)
async def get_memory(memory_id: str, db: AsyncSession = Depends(get_db)):
    """
    Получить запись памяти по ID.
    
    Возвращает запись памяти и обновляет время последнего доступа.
    """
    memory_service = MemoryService(db)
    memory = await memory_service.get_memory(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Запись памяти не найдена")
    
    # Обновляем время доступа (triggers in DB will handle last_refreshed)
    await memory_service.update_memory_access(memory_id)
    
    return MemoryResponse(
        id=memory.id,
        user_id=memory.user_id,
        kind=memory.kind,
        content=memory.content,
        meta=memory.meta,
        salience=memory.salience,
        created_at=memory.created_at,
        last_refreshed=memory.last_refreshed
    )

@router.get("/users/{user_id}/memories", response_model=MemoryListResponse)
async def get_user_memories(
    user_id: int,
    kind: Optional[MemoryKind] = Query(None, description="Тип памяти для фильтрации"),
    skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество записей"),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить записи памяти пользователя.
    
    Возвращает список записей памяти пользователя, опционально фильтрованных по типу.
    """
    memory_service = MemoryService(db)
    memories = await memory_service.get_user_memories(user_id, kind=kind, skip=skip, limit=limit)
    return MemoryListResponse(
        memories=[
            MemoryResponse(
                id=memory.id,
                user_id=memory.user_id,
                kind=memory.kind,
                content=memory.content,
                meta=memory.meta,
                salience=memory.salience,
                created_at=memory.created_at,
                last_refreshed=memory.last_refreshed
            ) for memory in memories
        ],
        total=len(memories)
    )

@router.get("/users/{user_id}/memories/search", response_model=MemoryListResponse)
async def search_user_memories(
    user_id: int,
    query: str = Query(..., min_length=2, description="Текст для поиска"),
    limit: int = Query(20, ge=1, le=100, description="Максимальное количество результатов"),
    db: AsyncSession = Depends(get_db)
):
    """
    Поиск по памяти пользователя.
    
    Выполняет текстовый поиск по содержимому записей памяти пользователя.
    """
    memory_service = MemoryService(db)
    memories = await memory_service.search_memories(user_id, query, limit=limit)
    return MemoryListResponse(
        memories=[
            MemoryResponse(
                id=memory.id,
                user_id=memory.user_id,
                kind=memory.kind,
                content=memory.content,
                meta=memory.meta,
                salience=memory.salience,
                created_at=memory.created_at,
                last_refreshed=memory.last_refreshed
            ) for memory in memories
        ],
        total=len(memories)
    )

# Endpoints для планов обучения
@router.post("/learning-plans/", response_model=LearningPlanResponse, status_code=201)
async def create_learning_plan(plan_data: LearningPlanCreate, db: AsyncSession = Depends(get_db)):
    """
    Создать план обучения.
    
    Создает новый план обучения для пользователя с целями и этапами.
    """
    try:
        plan_service = LearningPlanService(db)
        plan = await plan_service.create_plan(plan_data)
        return LearningPlanResponse(
            id=plan.id,
            user_id=plan.user_id,
            level_target=plan.level_target,
            next_review_at=plan.next_review_at,
            roadmap=plan.roadmap,
            updated_at=plan.updated_at
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка создания плана обучения: {str(e)}")

@router.get("/learning-plans/{plan_id}", response_model=LearningPlanResponse)
async def get_learning_plan(plan_id: str, db: AsyncSession = Depends(get_db)):
    """
    Получить план обучения по ID.
    
    Возвращает план обучения с указанным ID.
    """
    plan_service = LearningPlanService(db)
    plan = await plan_service.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="План обучения не найден")
    
    return LearningPlanResponse(
        id=plan.id,
        user_id=plan.user_id,
        level_target=plan.level_target,
        next_review_at=plan.next_review_at,
        roadmap=plan.roadmap,
        updated_at=plan.updated_at
    )

@router.get("/users/{user_id}/learning-plan", response_model=LearningPlanResponse)
async def get_user_active_plan(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Получить активный план обучения пользователя.
    
    Возвращает текущий активный план обучения пользователя.
    """
    plan_service = LearningPlanService(db)
    plan = await plan_service.get_user_active_plan(user_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Активный план обучения не найден")
    
    return LearningPlanResponse(
        id=plan.id,
        user_id=plan.user_id,
        level_target=plan.level_target,
        next_review_at=plan.next_review_at,
        roadmap=plan.roadmap,
        updated_at=plan.updated_at
    )

# Endpoints для событий XP
@router.post("/xp-events/", response_model=XPEventResponse, status_code=201)
async def create_xp_event(event_data: XPEventCreate, db: AsyncSession = Depends(get_db)):
    """
    Создать событие XP.
    
    Добавляет новое событие с изменением очков опыта пользователя.
    """
    try:
        xp_service = XPEventService(db)
        event = await xp_service.create_xp_event(event_data)
        return XPEventResponse(
            id=event.id,
            user_id=event.user_id,
            session_id=event.session_id,
            kind=event.kind,
            points=event.points,
            happened_at=event.happened_at
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка создания события XP: {str(e)}")

@router.get("/users/{user_id}/xp-events", response_model=XPEventListResponse)
async def get_user_xp_events(
    user_id: int,
    skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество записей"),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить события XP пользователя.
    
    Возвращает список событий XP пользователя.
    """
    xp_service = XPEventService(db)
    events = await xp_service.get_user_xp_events(user_id, skip=skip, limit=limit)
    return XPEventListResponse(
        events=[
            XPEventResponse(
                id=event.id,
                user_id=event.user_id,
                session_id=event.session_id,
                kind=event.kind,
                points=event.points,
                happened_at=event.happened_at
            ) for event in events
        ],
        total=len(events)
    )

@router.get("/users/{user_id}/xp-total", response_model=dict)
async def get_user_total_xp(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Получить общий XP пользователя.
    
    Возвращает суммарное количество очков опыта пользователя.
    """
    xp_service = XPEventService(db)
    total_xp = await xp_service.get_user_total_xp(user_id)
    return {"user_id": user_id, "total_xp": total_xp}
