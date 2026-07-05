from typing import List
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse

from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserListResponse
from app.services.database import UserService
from app.core.deps import get_db

router = APIRouter(prefix="/api/v1/users", tags=["users"])

@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Создать нового пользователя.
    
    Создает пользователя с указанным Telegram ID, именем и уровнем английского.
    Telegram ID должен быть уникальным.
    """
    try:
        user_service = UserService(db)
        user = await user_service.create_user(user_data)
        return UserResponse(
            id=user.id,
            telegram_id=user.telegram_id,
            username=user.username,
            language_level=user.language_level,
            created_at=user.created_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Получить пользователя по ID.
    
    Возвращает данные пользователя с указанным ID.
    """
    user_service = UserService(db)
    user = await user_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    return UserResponse(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        language_level=user.language_level,
        created_at=user.created_at
    )

@router.get("/", response_model=UserListResponse)
async def get_users(
    skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество записей"),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить список пользователей.
    
    Возвращает список пользователей с пагинацией.
    """
    user_service = UserService(db)
    users = await user_service.get_users(skip=skip, limit=limit)
    total = await user_service.get_total_count()
    
    user_responses = [
        UserResponse(
            id=user.id,
            telegram_id=user.telegram_id,
            username=user.username,
            language_level=user.language_level,
            created_at=user.created_at
        )
        for user in users
    ]
    
    return UserListResponse(users=user_responses, total=total)

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user_data: UserUpdate, db: AsyncSession = Depends(get_db)):
    """
    Обновить данные пользователя.
    
    Обновляет имя пользователя и/или уровень английского языка.
    """
    user_service = UserService(db)
    user = await user_service.update_user(user_id, user_data)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    return UserResponse(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        language_level=user.language_level,
        created_at=user.created_at
    )

@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Удалить пользователя.
    
    Удаляет пользователя и все связанные с ним данные.
    """
    user_service = UserService(db)
    success = await user_service.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    return JSONResponse(content=None, status_code=204)

@router.get("/telegram/{telegram_id}", response_model=UserResponse)
async def get_user_by_telegram_id(telegram_id: int, db: AsyncSession = Depends(get_db)):
    """
    Получить пользователя по Telegram ID.
    
    Возвращает данные пользователя с указанным Telegram ID.
    """
    user_service = UserService(db)
    user = await user_service.get_user_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    return UserResponse(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        language_level=user.language_level,
        created_at=user.created_at
    )
