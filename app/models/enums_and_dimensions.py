from datetime import datetime
from typing import Optional, List
from sqlalchemy import BigInteger, String, DateTime, Text, ForeignKey, Float, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import Enum as SQLEnum
import uuid
import enum

from app.core.database import Base

# Enum типы
class CEFRLevel(str, enum.Enum):
    """Уровни английского языка по CEFR"""
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

class MemoryKind(str, enum.Enum):
    """Типы памяти"""
    EPISODIC = "episodic"    # эпизодическая память
    SEMANTIC = "semantic"    # семантическая память
    PERSONA = "persona"     # память о личности
    SKILL = "skill"         # память о навыках

class SessionStatus(str, enum.Enum):
    """Статусы сессии"""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

# Справочники
class DimEmotion(Base):
    """Справочник эмоций"""
    __tablename__ = "dim_emotion"
    
    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name_ru: Mapped[str] = mapped_column(String(100), nullable=False)
    valence: Mapped[int] = mapped_column(Integer, nullable=False)  # -5 до 5
    arousal: Mapped[int] = mapped_column(Integer, nullable=False)  # 0 до 5
    
    def __repr__(self) -> str:
        return f"<DimEmotion(code={self.code}, name_ru='{self.name_ru}')>"

class DimTopic(Base):
    """Справочник тем"""
    __tablename__ = "dim_topic"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("dim_topic.id", ondelete="SET NULL"), nullable=True)
    
    # Связи
    parent: Mapped[Optional["DimTopic"]] = relationship("DimTopic", remote_side=[id], back_populates="children")
    children: Mapped[List["DimTopic"]] = relationship("DimTopic", back_populates="parent")
    
    def __repr__(self) -> str:
        return f"<DimTopic(id={self.id}, slug='{self.slug}', name='{self.display_name}')>"

class DimAccent(Base):
    """Справочник акцентов"""
    __tablename__ = "dim_accent"
    
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    def __repr__(self) -> str:
        return f"<DimAccent(code={self.code}, name='{self.display_name}')>"
