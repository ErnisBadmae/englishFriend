from datetime import datetime
from typing import Optional, List
from sqlalchemy import BigInteger, String, DateTime, Text, ForeignKey, Float, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.core.database import Base
from app.models.enums_and_dimensions import CEFRLevel, MemoryKind, SessionStatus

class User(Base):
    """Модель пользователя в PostgreSQL"""
    
    __tablename__ = "users"
    
    # Основные поля
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language_level: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # CEFR уровень
    accent_pref: Mapped[Optional[str]] = mapped_column(String(20), ForeignKey("dim_accent.code"), nullable=True)
    pii_envelope: Mapped[Optional[bytes]] = mapped_column(Text, nullable=True)  # зашифрованный PII
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Связи с другими таблицами
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    interests: Mapped[List["UserInterest"]] = relationship("UserInterest", back_populates="user", cascade="all, delete-orphan")
    memories: Mapped[List["Memory"]] = relationship("Memory", back_populates="user", cascade="all, delete-orphan")
    learning_plans: Mapped[List["LearningPlan"]] = relationship("LearningPlan", back_populates="user", cascade="all, delete-orphan")
    xp_events: Mapped[List["XPEvent"]] = relationship("XPEvent", back_populates="user", cascade="all, delete-orphan")
    emotional_logs: Mapped[List["EmotionalStateLog"]] = relationship("EmotionalStateLog", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username='{self.username}')>"

class Session(Base):
    """Модель сессии в PostgreSQL"""
    
    __tablename__ = "sessions"
    
    # Основные поля
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Медиа и контент
    audio_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lang_code: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    
    # Качество связи и анализ
    call_quality: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    transcript_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    topics_detected: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    emotion_detected: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    grammar_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pronunciation_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Статус сессии
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    
    # Связи
    user: Mapped["User"] = relationship("User", back_populates="sessions")
    utterances: Mapped[List["Utterance"]] = relationship("Utterance", back_populates="session", cascade="all, delete-orphan")
    feedback: Mapped[Optional["Feedback"]] = relationship("Feedback", back_populates="session", cascade="all, delete-orphan")
    corrections: Mapped[List["Correction"]] = relationship("Correction", back_populates="session", cascade="all, delete-orphan")
    xp_events: Mapped[List["XPEvent"]] = relationship("XPEvent", back_populates="session", cascade="all, delete-orphan")
    emotional_logs: Mapped[List["EmotionalStateLog"]] = relationship("EmotionalStateLog", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Session(id={self.id}, user_id={self.user_id}, started_at={self.started_at})>"

class Utterance(Base):
    """Модель реплики в диалоге"""
    
    __tablename__ = "utterances"
    
    # Основные поля
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    speaker: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user' или 'assistant'
    
    # Временные метки
    t_start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    t_end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Контент
    text: Mapped[str] = mapped_column(Text, nullable=False)
    phonemes: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Анализ
    topics: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # [{topic_id, score}]
    emotion_code: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("dim_emotion.code"), nullable=True)
    emotion_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    grammar_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pronunciation_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Связи
    session: Mapped["Session"] = relationship("Session", back_populates="utterances")
    emotion: Mapped[Optional["DimEmotion"]] = relationship("DimEmotion")
    
    def __repr__(self) -> str:
        return f"<Utterance(id={self.id}, session_id={self.session_id}, speaker='{self.speaker}')>"

class Feedback(Base):
    """Модель обратной связи по сессии"""
    
    __tablename__ = "feedback"
    
    # Основные поля
    session_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True)
    overall_grammar: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    overall_pronunciation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    summary_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tips_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Детализированная обратная связь
    corrected_phrases: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    grammar_tips: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pronunciation_tips: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vocabulary_suggestions: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Связи
    session: Mapped["Session"] = relationship("Session", back_populates="feedback")
    
    def __repr__(self) -> str:
        return f"<Feedback(session_id={self.session_id}, grammar={self.overall_grammar})>"

class Correction(Base):
    """Модель исправления ошибок"""
    
    __tablename__ = "corrections"
    
    # Основные поля
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    utterance_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("utterances.id", ondelete="SET NULL"), nullable=True)
    
    # Исправление
    user_text: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_text: Mapped[str] = mapped_column(Text, nullable=False)
    rule_tag: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    explanation_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Связи
    session: Mapped["Session"] = relationship("Session", back_populates="corrections")
    utterance: Mapped[Optional["Utterance"]] = relationship("Utterance")
    
    def __repr__(self) -> str:
        return f"<Correction(id={self.id}, session_id={self.session_id})>"
