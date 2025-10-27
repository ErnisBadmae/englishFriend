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
    """Базовая схема интереса пользователя (соответствует 002_users.sql: weight check >= 0 and <= 1)"""
    user_id: int = Field(..., description="ID пользователя")
    topic_id: str = Field(..., description="ID темы")
    weight: float = Field(0.0, ge=0, le=1, description="Вес интереса (0-1)")
    last_mentioned: Optional[datetime] = Field(None, description="Последнее упоминание")

class UserInterestCreate(UserInterestBase):
    """Схема для создания интереса пользователя"""
    last_mentioned: datetime = Field(default_factory=datetime.utcnow)

class UserInterestUpdate(BaseModel):
    """Схема для обновления интереса пользователя"""
    weight: Optional[float] = Field(None, ge=0, le=1)
    last_mentioned: Optional[datetime] = None

class UserInterestResponse(UserInterestBase):
    """Схема ответа для интереса пользователя"""
    
    class Config:
        from_attributes = True

class UserInterestListResponse(BaseModel):
    """Схема ответа для списка интересов пользователя"""
    interests: List[UserInterestResponse] = Field(..., description="Список интересов")
    total: int = Field(..., description="Общее количество интересов")

# Схемы для Memory (соответствует 005_memories_learning_plan.sql)
class MemoryBase(BaseModel):
    """Базовая схема памяти"""
    user_id: int = Field(..., description="ID пользователя")
    kind: MemoryKind = Field(..., description="Тип памяти")
    content: str = Field(..., description="Содержимое памяти")
    meta: Optional[Dict[str, Any]] = Field(None, description="Метаданные (jsonb)")
    salience: float = Field(0.5, ge=0, le=1, description="Важность памяти (0-1)")

class MemoryCreate(MemoryBase):
    """Схема для создания памяти"""
    pass

class MemoryUpdate(BaseModel):
    """Схема для обновления памяти"""
    content: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    salience: Optional[float] = Field(None, ge=0, le=1)

class MemoryResponse(MemoryBase):
    """Схема ответа для памяти"""
    id: str = Field(..., description="UUID памяти")
    created_at: datetime = Field(..., description="Дата создания")
    last_refreshed: datetime = Field(..., description="Последнее обновление")
    
    class Config:
        from_attributes = True

class MemoryListResponse(BaseModel):
    """Схема ответа для списка памяти"""
    memories: List[MemoryResponse] = Field(..., description="Список записей памяти")
    total: int = Field(..., description="Общее количество записей")

# Схемы для LearningPlan (соответствует 005_memories_learning_plan.sql)
class LearningPlanBase(BaseModel):
    """Базовая схема плана обучения"""
    user_id: int = Field(..., description="ID пользователя")
    level_target: Optional[str] = Field(None, max_length=10, description="Целевой уровень CEFR")
    next_review_at: Optional[datetime] = Field(None, description="Дата следующего пересмотра")
    roadmap: Optional[Dict[str, Any]] = Field(None, description="Дорожная карта обучения (jsonb)")

class LearningPlanCreate(LearningPlanBase):
    """Схема для создания плана обучения"""
    pass

class LearningPlanUpdate(BaseModel):
    """Схема для обновления плана обучения"""
    level_target: Optional[str] = Field(None, max_length=10)
    next_review_at: Optional[datetime] = None
    roadmap: Optional[Dict[str, Any]] = None

class LearningPlanResponse(LearningPlanBase):
    """Схема ответа для плана обучения"""
    id: str = Field(..., description="UUID плана")
    updated_at: datetime = Field(..., description="Дата обновления")
    
    class Config:
        from_attributes = True

class LearningPlanListResponse(BaseModel):
    """Схема ответа для списка планов обучения"""
    plans: List[LearningPlanResponse] = Field(..., description="Список планов")
    total: int = Field(..., description="Общее количество планов")

# Схемы для XPEvent (соответствует 005_memories_learning_plan.sql)
class XPEventBase(BaseModel):
    """Базовая схема события XP"""
    user_id: int = Field(..., description="ID пользователя")
    session_id: Optional[str] = Field(None, description="ID сессии")
    kind: str = Field(..., max_length=50, description="Тип события")
    points: int = Field(..., description="Очки XP")

class XPEventCreate(XPEventBase):
    """Схема для создания события XP"""
    pass

class XPEventResponse(XPEventBase):
    """Схема ответа для события XP"""
    id: str = Field(..., description="UUID события")
    happened_at: datetime = Field(..., description="Дата события")
    
    class Config:
        from_attributes = True

class XPEventListResponse(BaseModel):
    """Схема ответа для списка событий XP"""
    events: List[XPEventResponse] = Field(..., description="Список событий")
    total: int = Field(..., description="Общее количество событий")

