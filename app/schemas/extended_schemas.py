from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID

from app.models.enums_and_dimensions import CEFRLevel, MemoryKind

# Схемы для User
class UserBase(BaseModel):
    """Базовая схема пользователя"""
    telegram_id: int = Field(..., description="Telegram ID пользователя")
    username: Optional[str] = Field(None, max_length=255, description="Имя пользователя")
    language_level: Optional[CEFRLevel] = Field(None, description="Уровень английского языка")
    accent_pref: Optional[str] = Field(None, max_length=20, description="Предпочитаемый акцент")

class UserCreate(UserBase):
    """Схема для создания пользователя"""
    pass

class UserUpdate(BaseModel):
    """Схема для обновления пользователя"""
    username: Optional[str] = Field(None, max_length=255)
    language_level: Optional[CEFRLevel] = None
    accent_pref: Optional[str] = Field(None, max_length=20)

class UserResponse(UserBase):
    """Схема ответа для пользователя"""
    id: int = Field(..., description="ID пользователя")
    created_at: datetime = Field(..., description="Дата создания")
    deleted_at: Optional[datetime] = Field(None, description="Дата удаления")
    
    class Config:
        from_attributes = True

class UserListResponse(BaseModel):
    """Схема ответа для списка пользователей"""
    users: List[UserResponse] = Field(..., description="Список пользователей")
    total: int = Field(..., description="Общее количество пользователей")

# Схемы для Session
class SessionBase(BaseModel):
    """Базовая схема сессии"""
    user_id: int = Field(..., description="ID пользователя")
    started_at: Optional[datetime] = Field(None, description="Время начала сессии")
    audio_url: Optional[str] = Field(None, description="URL аудиозаписи")
    lang_code: str = Field("en", max_length=10, description="Код языка")
    call_quality: Optional[Dict[str, Any]] = Field(None, description="Качество связи")
    transcript_text: Optional[str] = Field(None, description="Текст транскрипции")
    topics_detected: Optional[Dict[str, Any]] = Field(None, description="Обнаруженные темы")
    emotion_detected: Optional[str] = Field(None, max_length=50, description="Обнаруженная эмоция")
    grammar_score: Optional[float] = Field(None, ge=0, le=10, description="Оценка грамматики")
    pronunciation_score: Optional[float] = Field(None, ge=0, le=10, description="Оценка произношения")

class SessionCreate(SessionBase):
    """Схема для создания сессии"""
    started_at: datetime = Field(default_factory=datetime.utcnow, description="Время начала сессии")

class SessionUpdate(BaseModel):
    """Схема для обновления сессии"""
    ended_at: Optional[datetime] = Field(None, description="Время окончания сессии")
    audio_url: Optional[str] = Field(None, description="URL аудиозаписи")
    lang_code: Optional[str] = Field(None, max_length=10, description="Код языка")
    call_quality: Optional[Dict[str, Any]] = Field(None, description="Качество связи")
    transcript_text: Optional[str] = Field(None, description="Текст транскрипции")
    topics_detected: Optional[Dict[str, Any]] = Field(None, description="Обнаруженные темы")
    emotion_detected: Optional[str] = Field(None, max_length=50, description="Обнаруженная эмоция")
    grammar_score: Optional[float] = Field(None, ge=0, le=10, description="Оценка грамматики")
    pronunciation_score: Optional[float] = Field(None, ge=0, le=10, description="Оценка произношения")

class SessionResponse(SessionBase):
    """Схема ответа для сессии"""
    id: str = Field(..., description="UUID сессии")
    ended_at: Optional[datetime] = Field(None, description="Время окончания сессии")
    
    class Config:
        from_attributes = True

class SessionListResponse(BaseModel):
    """Схема ответа для списка сессий"""
    sessions: List[SessionResponse] = Field(..., description="Список сессий")
    total: int = Field(..., description="Общее количество сессий")

# Схемы для Utterance
class UtteranceBase(BaseModel):
    """Базовая схема реплики"""
    session_id: str = Field(..., description="ID сессии")
    speaker: str = Field(..., max_length=20, description="Говорящий (user/assistant)")
    t_start_ms: int = Field(..., ge=0, description="Время начала в миллисекундах")
    t_end_ms: int = Field(..., ge=0, description="Время окончания в миллисекундах")
    text: str = Field(..., description="Текст реплики")
    phonemes: Optional[Dict[str, Any]] = Field(None, description="Фонемы")
    topics: Optional[Dict[str, Any]] = Field(None, description="Темы")
    emotion_code: Optional[str] = Field(None, max_length=50, description="Код эмоции")
    emotion_score: Optional[float] = Field(None, ge=0, le=1, description="Оценка эмоции")
    grammar_score: Optional[float] = Field(None, ge=0, le=10, description="Оценка грамматики")
    pronunciation_score: Optional[float] = Field(None, ge=0, le=10, description="Оценка произношения")

class UtteranceCreate(UtteranceBase):
    """Схема для создания реплики"""
    pass

class UtteranceResponse(UtteranceBase):
    """Схема ответа для реплики"""
    id: str = Field(..., description="UUID реплики")
    
    class Config:
        from_attributes = True

class UtteranceListResponse(BaseModel):
    """Схема ответа для списка реплик"""
    utterances: List[UtteranceResponse] = Field(..., description="Список реплик")
    total: int = Field(..., description="Общее количество реплик")
