from datetime import datetime
from typing import Optional, List
from sqlalchemy import BigInteger, String, DateTime, Text, ForeignKey, Float, Integer, Boolean, Enum as SQLEnum, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
import enum

from app.core.database import Base

# Enum типы (синхронизированы с db/migrations/postgres/001_reference_tables.sql)
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
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PERSONA = "persona"
    SKILL = "skill"

class AccessChannel(str, enum.Enum):
    """Каналы доступа"""
    TELEGRAM = "telegram"
    MOBILE_APP = "mobile_app"
    WEB = "web"

class SessionStatus(str, enum.Enum):
    """Статусы сессии"""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

# Справочники (синхронизированы с db/migrations/postgres/001_reference_tables.sql)
class DimEmotion(Base):
    """Справочник эмоций"""
    __tablename__ = "dim_emotion"
    
    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name_ru: Mapped[str] = mapped_column(String(100), nullable=False)
    valence: Mapped[int] = mapped_column(Integer, nullable=False)
    arousal: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<DimEmotion(code={self.code}, name_ru='{self.name_ru}')>"

class DimTopic(Base):
    """Справочник тем"""
    __tablename__ = "dim_topic"
    
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("dim_topic.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
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
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<DimAccent(code={self.code}, name='{self.display_name}')>"