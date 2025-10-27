from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID

from app.models.enums_and_dimensions import CEFRLevel, MemoryKind, SessionStatus

# Справочники
class DimEmotionBase(BaseModel):
    """Базовая схема для справочника эмоций"""
    code: str = Field(..., max_length=50, description="Код эмоции")
    name_ru: str = Field(..., max_length=100, description="Название эмоции на русском")
    valence: int = Field(..., ge=-5, le=5, description="Валентность эмоции (-5 до 5)")
    arousal: int = Field(..., ge=0, le=5, description="Возбуждение эмоции (0 до 5)")

class DimEmotionCreate(DimEmotionBase):
    """Схема для создания записи в справочнике эмоций"""
    pass

class DimEmotionResponse(DimEmotionBase):
    """Схема ответа для справочника эмоций"""
    
    class Config:
        from_attributes = True

class DimTopicBase(BaseModel):
    """Базовая схема для справочника тем"""
    slug: str = Field(..., max_length=100, description="Уникальный слаг темы")
    display_name: str = Field(..., max_length=200, description="Отображаемое название темы")
    parent_id: Optional[str] = Field(None, description="ID родительской темы")

class DimTopicCreate(DimTopicBase):
    """Схема для создания записи в справочнике тем"""
    pass

class DimTopicResponse(DimTopicBase):
    """Схема ответа для справочника тем"""
    id: str = Field(..., description="UUID темы")
    
    class Config:
        from_attributes = True

class DimAccentBase(BaseModel):
    """Базовая схема для справочника акцентов"""
    code: str = Field(..., max_length=20, description="Код акцента")
    display_name: str = Field(..., max_length=100, description="Отображаемое название акцента")

class DimAccentCreate(DimAccentBase):
    """Схема для создания записи в справочнике акцентов"""
    pass

class DimAccentResponse(DimAccentBase):
    """Схема ответа для справочника акцентов"""
    
    class Config:
        from_attributes = True
