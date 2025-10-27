from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator

# Импортируем enum из моделей
from app.models.enums_and_dimensions import CEFRLevel

class UserCreate(BaseModel):
    """Схема для создания пользователя"""
    telegram_id: int = Field(..., description="Telegram ID пользователя")
    username: Optional[str] = Field(None, max_length=255, description="Имя пользователя")
    language_level: Optional[CEFRLevel] = Field(None, description="Уровень английского")
    
    @validator('telegram_id')
    def validate_telegram_id(cls, v):
        """Валидация Telegram ID"""
        if v <= 0:
            raise ValueError('Telegram ID должен быть положительным числом')
        return v

class UserUpdate(BaseModel):
    """Схема для обновления пользователя"""
    username: Optional[str] = Field(None, max_length=255)
    language_level: Optional[CEFRLevel] = None

class UserResponse(BaseModel):
    """Схема ответа с данными пользователя"""
    id: int
    telegram_id: int
    username: Optional[str]
    language_level: Optional[CEFRLevel]
    created_at: datetime
    
    class Config:
        # datetime объекты
        from_attributes = True

class UserListResponse(BaseModel):
    """Схема ответа со списком пользователей"""
    users: List[UserResponse]
    total: int
