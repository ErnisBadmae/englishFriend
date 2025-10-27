from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID

from app.models.enums_and_dimensions import MemoryKind

# Схемы для Feedback (соответствует db/migrations/postgres/003_sessions_utterances.sql)
class FeedbackBase(BaseModel):
    """Базовая схема обратной связи"""
    overall_grammar: Optional[float] = Field(None, description="Общая оценка грамматики")
    overall_pronunciation: Optional[float] = Field(None, description="Общая оценка произношения")
    summary_md: Optional[str] = Field(None, description="Сводка в Markdown")
    tips_md: Optional[str] = Field(None, description="Советы в Markdown")

class FeedbackCreate(FeedbackBase):
    """Схема для создания обратной связи"""
    session_id: str = Field(..., description="ID сессии")

class FeedbackUpdate(BaseModel):
    """Схема для обновления обратной связи"""
    overall_grammar: Optional[float] = None
    overall_pronunciation: Optional[float] = None
    summary_md: Optional[str] = None
    tips_md: Optional[str] = None

class FeedbackResponse(FeedbackBase):
    """Схема ответа для обратной связи"""
    session_id: str = Field(..., description="ID сессии")
    
    class Config:
        from_attributes = True

# Схемы для Correction
class CorrectionBase(BaseModel):
    """Базовая схема исправления"""
    session_id: str = Field(..., description="ID сессии")
    utterance_id: Optional[str] = Field(None, description="ID реплики")
    user_text: str = Field(..., description="Текст пользователя")
    corrected_text: str = Field(..., description="Исправленный текст")
    rule_tag: Optional[str] = Field(None, max_length=100, description="Тег правила")
    explanation_md: Optional[str] = Field(None, description="Объяснение в Markdown")

class CorrectionCreate(CorrectionBase):
    """Схема для создания исправления"""
    pass

class CorrectionResponse(CorrectionBase):
    """Схема ответа для исправления"""
    id: str = Field(..., description="UUID исправления")
    
    class Config:
        from_attributes = True

class CorrectionListResponse(BaseModel):
    """Схема ответа для списка исправлений"""
    corrections: List[CorrectionResponse] = Field(..., description="Список исправлений")
    total: int = Field(..., description="Общее количество исправлений")

# Схемы для UserInterest
class UserInterestBase(BaseModel):
    """Базовая схема интереса пользователя"""
    user_id: int = Field(..., description="ID пользователя")
    topic_id: str = Field(..., description="ID темы")
    weight: float = Field(1.0, ge=0, le=10, description="Вес интереса")
    last_mentioned: Optional[datetime] = Field(None, description="Последнее упоминание")

class UserInterestCreate(UserInterestBase):
    """Схема для создания интереса пользователя"""
    last_mentioned: datetime = Field(default_factory=datetime.utcnow)

class UserInterestUpdate(BaseModel):
    """Схема для обновления интереса пользователя"""
    weight: Optional[float] = Field(None, ge=0, le=10)
    last_mentioned: Optional[datetime] = None

class UserInterestResponse(UserInterestBase):
    """Схема ответа для интереса пользователя"""
    
    class Config:
        from_attributes = True

class UserInterestListResponse(BaseModel):
    """Схема ответа для списка интересов пользователя"""
    interests: List[UserInterestResponse] = Field(..., description="Список интересов")
    total: int = Field(..., description="Общее количество интересов")

# Схемы для Memory
class MemoryBase(BaseModel):
    """Базовая схема памяти"""
    user_id: int = Field(..., description="ID пользователя")
    session_id: Optional[str] = Field(None, description="ID сессии")
    utterance_id: Optional[str] = Field(None, description="ID реплики")
    kind: MemoryKind = Field(..., description="Тип памяти")
    content: str = Field(..., description="Содержимое памяти")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Метаданные")

class MemoryCreate(MemoryBase):
    """Схема для создания памяти"""
    pass

class MemoryUpdate(BaseModel):
    """Схема для обновления памяти"""
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    last_accessed: Optional[datetime] = None

class MemoryResponse(MemoryBase):
    """Схема ответа для памяти"""
    id: str = Field(..., description="UUID памяти")
    created_at: datetime = Field(..., description="Дата создания")
    last_accessed: Optional[datetime] = Field(None, description="Последний доступ")
    
    class Config:
        from_attributes = True

class MemoryListResponse(BaseModel):
    """Схема ответа для списка памяти"""
    memories: List[MemoryResponse] = Field(..., description="Список записей памяти")
    total: int = Field(..., description="Общее количество записей")

# Схемы для LearningPlan
class LearningPlanBase(BaseModel):
    """Базовая схема плана обучения"""
    user_id: int = Field(..., description="ID пользователя")
    target_level: str = Field(..., max_length=10, description="Целевой уровень")
    current_level: str = Field(..., max_length=10, description="Текущий уровень")
    topics: Dict[str, Any] = Field(..., description="Темы")
    milestones: Dict[str, Any] = Field(..., description="Этапы")
    is_active: bool = Field(True, description="Активен ли план")

class LearningPlanCreate(LearningPlanBase):
    """Схема для создания плана обучения"""
    pass

class LearningPlanUpdate(BaseModel):
    """Схема для обновления плана обучения"""
    target_level: Optional[str] = Field(None, max_length=10)
    current_level: Optional[str] = Field(None, max_length=10)
    topics: Optional[Dict[str, Any]] = None
    milestones: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class LearningPlanResponse(LearningPlanBase):
    """Схема ответа для плана обучения"""
    id: str = Field(..., description="UUID плана")
    created_at: datetime = Field(..., description="Дата создания")
    updated_at: datetime = Field(..., description="Дата обновления")
    
    class Config:
        from_attributes = True

class LearningPlanListResponse(BaseModel):
    """Схема ответа для списка планов обучения"""
    plans: List[LearningPlanResponse] = Field(..., description="Список планов")
    total: int = Field(..., description="Общее количество планов")

# Схемы для XPEvent
class XPEventBase(BaseModel):
    """Базовая схема события XP"""
    user_id: int = Field(..., description="ID пользователя")
    session_id: Optional[str] = Field(None, description="ID сессии")
    event_type: str = Field(..., max_length=50, description="Тип события")
    xp_delta: int = Field(..., description="Изменение XP")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Метаданные")

class XPEventCreate(XPEventBase):
    """Схема для создания события XP"""
    pass

class XPEventResponse(XPEventBase):
    """Схема ответа для события XP"""
    id: str = Field(..., description="UUID события")
    created_at: datetime = Field(..., description="Дата создания")
    
    class Config:
        from_attributes = True

class XPEventListResponse(BaseModel):
    """Схема ответа для списка событий XP"""
    events: List[XPEventResponse] = Field(..., description="Список событий")
    total: int = Field(..., description="Общее количество событий")

