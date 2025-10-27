from datetime import datetime
from typing import Optional, List
from sqlalchemy import BigInteger, String, DateTime, Text, ForeignKey, Float, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.core.database import Base
from app.models.enums_and_dimensions import MemoryKind

class UserInterest(Base):
    """Модель интересов пользователя"""
    
    __tablename__ = "user_interest"
    
    # Основные поля
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    topic_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("dim_topic.id", ondelete="CASCADE"), primary_key=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    last_mentioned: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Связи
    user: Mapped["User"] = relationship("User", back_populates="interests")
    topic: Mapped["DimTopic"] = relationship("DimTopic")
    
    def __repr__(self) -> str:
        return f"<UserInterest(user_id={self.user_id}, topic_id={self.topic_id}, weight={self.weight})>"

class Memory(Base):
    """Модель канонических записей памяти"""
    
    __tablename__ = "memories"
    
    # Основные поля
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)
    utterance_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("utterances.id", ondelete="SET NULL"), nullable=True)
    
    # Тип и контент памяти
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # MemoryKind
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_accessed: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Связи
    user: Mapped["User"] = relationship("User", back_populates="memories")
    session: Mapped[Optional["Session"]] = relationship("Session")
    utterance: Mapped[Optional["Utterance"]] = relationship("Utterance")
    
    def __repr__(self) -> str:
        return f"<Memory(id={self.id}, user_id={self.user_id}, kind='{self.kind}')>"

class LearningPlan(Base):
    """Модель плана обучения"""
    
    __tablename__ = "learning_plan"
    
    # Основные поля
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # План
    target_level: Mapped[str] = mapped_column(String(10), nullable=False)  # CEFR уровень
    current_level: Mapped[str] = mapped_column(String(10), nullable=False)  # CEFR уровень
    topics: Mapped[dict] = mapped_column(JSONB, nullable=False)  # [{topic_id, priority, status}]
    milestones: Mapped[dict] = mapped_column(JSONB, nullable=False)  # [{milestone, target_date, achieved}]
    
    # Статус
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    user: Mapped["User"] = relationship("User", back_populates="learning_plans")
    
    def __repr__(self) -> str:
        return f"<LearningPlan(id={self.id}, user_id={self.user_id}, target_level='{self.target_level}')>"

class XPEvent(Base):
    """Модель игровых событий и очков"""
    
    __tablename__ = "xp_events"
    
    # Основные поля
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)
    
    # Событие
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'grammar_improvement', 'pronunciation_good', etc.
    xp_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Связи
    user: Mapped["User"] = relationship("User", back_populates="xp_events")
    session: Mapped[Optional["Session"]] = relationship("Session", back_populates="xp_events")
    
    def __repr__(self) -> str:
        return f"<XPEvent(id={self.id}, user_id={self.user_id}, event_type='{self.event_type}', xp={self.xp_delta})>"

class EmotionalStateLog(Base):
    """Модель лога эмоционального состояния"""
    
    __tablename__ = "emotional_state_log"
    
    # Основные поля
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)
    
    # Эмоция
    emotion_code: Mapped[str] = mapped_column(String(50), ForeignKey("dim_emotion.code"), nullable=False)
    intensity: Mapped[float] = mapped_column(Float, nullable=False)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Связи
    user: Mapped["User"] = relationship("User", back_populates="emotional_logs")
    session: Mapped[Optional["Session"]] = relationship("Session", back_populates="emotional_logs")
    emotion: Mapped["DimEmotion"] = relationship("DimEmotion")
    
    def __repr__(self) -> str:
        return f"<EmotionalStateLog(id={self.id}, user_id={self.user_id}, emotion='{self.emotion_code}')>"
