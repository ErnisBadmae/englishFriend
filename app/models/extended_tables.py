from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import BigInteger, String, DateTime, Text, ForeignKey, Float, Integer, Boolean, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.core.database import Base
from app.models.enums_and_dimensions import MemoryKind, CEFRLevel
from app.models.enum_cast import PostgresEnum

if TYPE_CHECKING:
    from app.models.core_tables import User

class UserInterest(Base):
    """
    Модель интересов пользователя (синхронизирована с db/migrations/postgres/002_users.sql)
    
    Соответствует SQL схеме:
    - weight real not null default 0 check (weight >= 0 and weight <= 1)
    """
    
    __tablename__ = "user_interest"
    
    # Основные поля
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    topic_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("dim_topic.id", ondelete="CASCADE"), primary_key=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, 
                                          comment="Weight between 0 and 1 per SQL check constraint")
    last_mentioned: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    __table_args__ = (
        CheckConstraint('weight >= 0 AND weight <= 1', name='weight_check'),
    )
    
    # Связи
    user: Mapped["User"] = relationship("User", back_populates="interests")
    topic: Mapped["DimTopic"] = relationship("DimTopic")
    
    def __repr__(self) -> str:
        return f"<UserInterest(user_id={self.user_id}, topic_id={self.topic_id}, weight={self.weight})>"

class Memory(Base):
    """
    Модель канонических записей памяти (синхронизирована с db/migrations/postgres/005_memories_learning_plan.sql)
    
    Соответствует SQL схеме:
    - salience real not null default 0.5 check (salience between 0 and 1)
    """
    
    __tablename__ = "memories"
    
    # Основные поля
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Тип и контент памяти  
    kind: Mapped[MemoryKind] = mapped_column(PostgresEnum('memory_kind', MemoryKind), nullable=False)  # MemoryKind
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    salience: Mapped[float] = mapped_column(Float, nullable=False, default=0.5,
                                            comment="Salience between 0 and 1 per SQL check constraint")
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_refreshed: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint('salience >= 0 AND salience <= 1', name='salience_check'),
    )
    
    # Связи
    user: Mapped["User"] = relationship("User", back_populates="memories")
    
    def __repr__(self) -> str:
        return f"<Memory(id={self.id}, user_id={self.user_id}, kind='{self.kind}')>"

class LearningPlan(Base):
    """Модель плана обучения (синхронизирована с db/migrations/postgres/005_memories_learning_plan.sql)"""
    
    __tablename__ = "learning_plan"
    
    # Основные поля
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # План
    level_target: Mapped[Optional[CEFRLevel]] = mapped_column(PostgresEnum('cefr_level', CEFRLevel), nullable=True)  # CEFR уровень
    next_review_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    roadmap: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Статус
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Связи
    user: Mapped["User"] = relationship("User", back_populates="learning_plans")
    
    def __repr__(self) -> str:
        return f"<LearningPlan(id={self.id}, user_id={self.user_id}, level_target='{self.level_target}')>"

class XPEvent(Base):
    """
    Модель игровых событий и очков (синхронизирована с db/migrations/postgres/005_memories_learning_plan.sql)

    ВАЖНО: Таблица партиционирована по range (happened_at) в SQL миграциях.
    SQL: PRIMARY KEY (id, happened_at) - composite key для партиционирования.
    SQLAlchemy не поддерживает composite PK напрямую для партиционированных таблиц,
    поэтому используем только id как PK на уровне ORM.
    """

    __tablename__ = "xp_events"

    # Основные поля (строго по SQL схеме коллеги)
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)

    # Событие
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)

    # Временные метки
    happened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="xp_events")
    session: Mapped[Optional["Session"]] = relationship("Session", back_populates="xp_events")

    def __repr__(self) -> str:
        return f"<XPEvent(id={self.id}, user_id={self.user_id}, kind='{self.kind}', points={self.points})>"


class VocabularyCard(Base):
    """
    Модель словарной карточки с FSRS spaced repetition.

    Синхронизирована с db/migrations/postgres/009_vocabulary_srs.sql
    """

    __tablename__ = "vocabulary_cards"

    # Основные поля
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Слово и контекст
    word: Mapped[str] = mapped_column(Text, nullable=False)
    translation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    example_sentence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phonetic: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # FSRS параметры
    fsrs_state: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0=New, 1=Learning, 2=Review, 3=Relearning
    fsrs_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fsrs_stability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fsrs_difficulty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Планирование
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Статистика
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Мета (no FK due to partitioned sessions table)
    source_session_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="vocabulary_cards")
    reviews: Mapped[List["VocabularyReview"]] = relationship("VocabularyReview", back_populates="card", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<VocabularyCard(id={self.id}, word='{self.word}', state={self.fsrs_state})>"


class VocabularyReview(Base):
    """
    Модель истории повторений карточки.

    Синхронизирована с db/migrations/postgres/009_vocabulary_srs.sql
    """

    __tablename__ = "vocabulary_reviews"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    card_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("vocabulary_cards.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Результат review
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1=Again, 2=Hard, 3=Good, 4=Easy

    # Состояние ДО review
    prev_state: Mapped[int] = mapped_column(Integer, nullable=False)
    prev_stability: Mapped[float] = mapped_column(Float, nullable=False)
    prev_difficulty: Mapped[float] = mapped_column(Float, nullable=False)

    # Когда
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    review_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Контекст (no FK due to partitioned sessions table)
    session_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), nullable=True)

    # Связи
    card: Mapped["VocabularyCard"] = relationship("VocabularyCard", back_populates="reviews")
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<VocabularyReview(card_id={self.card_id}, rating={self.rating})>"
