from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID
from enum import Enum


class SessionStatus(str, Enum):
    """Status of a learning session"""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class SessionCreate(BaseModel):
    """Схема для создания сессии"""
    user_id: int = Field(..., description="ID пользователя")
    lang_code: str = Field(default="en", description="Код языка")

class SessionUpdate(BaseModel):
    """Схема для обновления сессии"""
    ended_at: Optional[datetime] = None
    audio_url: Optional[str] = None
    lang_code: Optional[str] = None
    call_quality: Optional[Dict[str, Any]] = None
    status: Optional[SessionStatus] = None

class SessionResponse(BaseModel):
    """Схема ответа с данными сессии"""
    id: str
    user_id: int
    started_at: datetime
    ended_at: Optional[datetime]
    audio_url: Optional[str]
    lang_code: str
    call_quality: Optional[Dict[str, Any]] = None
    status: Optional[SessionStatus] = SessionStatus.ACTIVE

    class Config:
        from_attributes = True
