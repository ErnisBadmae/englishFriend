from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID

# Импортируем enum из моделей
from app.models.enums_and_dimensions import SessionStatus

class SessionCreate(BaseModel):
    """Схема для создания сессии"""
    user_id: int = Field(..., description="ID пользователя")
    lang_code: str = Field(default="en", description="Код языка")

class SessionUpdate(BaseModel):
    """Схема для обновления сессии"""
    ended_at: Optional[datetime] = None
    audio_url: Optional[str] = None
    status: Optional[SessionStatus] = None

class SessionResponse(BaseModel):
    """Схема ответа с данными сессии"""
    id: str
    user_id: int
    started_at: datetime
    ended_at: Optional[datetime]
    audio_url: Optional[str]
    lang_code: str
    status: SessionStatus
    
    class Config:
        from_attributes = True
