from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid4())


class MlTechnicalSession(Base):
    __tablename__ = "ml_technical_sessions"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="ml_technical_sessions_id_user_id_key"),
        CheckConstraint(
            "mode in ('topic', 'daily')", name="ml_technical_sessions_mode_check"
        ),
        CheckConstraint(
            "channel in ('web', 'telegram', 'mcp')",
            name="ml_technical_sessions_channel_check",
        ),
        CheckConstraint(
            "status in ('active', 'completed', 'cancelled')",
            name="ml_technical_sessions_status_check",
        ),
        CheckConstraint(
            "(mode = 'daily' and practice_date is not null and topic_id is null) "
            "or (mode = 'topic' and practice_date is null and topic_id is not null)",
            name="ml_technical_sessions_mode_shape_check",
        ),
        Index(
            "ml_technical_sessions_user_daily_key",
            "user_id",
            "practice_date",
            unique=True,
            postgresql_where=text("mode = 'daily'"),
        ),
        Index(
            "ml_technical_sessions_one_active_telegram_key",
            "user_id",
            unique=True,
            postgresql_where=text("channel = 'telegram' and status = 'active'"),
        ),
        Index("ml_technical_sessions_user_created_idx", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False, default="web")
    topic_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session_seed: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    practice_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    items: Mapped[list["MlTechnicalSessionItem"]] = relationship(
        "MlTechnicalSessionItem",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="MlTechnicalSessionItem.position",
    )
    attempts: Mapped[list["MlTechnicalAttempt"]] = relationship(
        "MlTechnicalAttempt",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class MlTechnicalSessionItem(Base):
    __tablename__ = "ml_technical_session_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "user_id"],
            ["ml_technical_sessions.id", "ml_technical_sessions.user_id"],
            ondelete="CASCADE",
            name="ml_technical_session_items_session_user_fkey",
        ),
        UniqueConstraint(
            "session_id",
            "question_id",
            name="ml_technical_session_items_session_question_key",
        ),
        UniqueConstraint(
            "session_id",
            "position",
            name="ml_technical_session_items_session_position_key",
        ),
        CheckConstraint(
            "position > 0", name="ml_technical_session_items_position_check"
        ),
        CheckConstraint(
            "status in ('pending', 'answered', 'skipped')",
            name="ml_technical_session_items_status_check",
        ),
        Index("ml_technical_session_items_user_updated_idx", "user_id", "updated_at"),
        Index("ml_technical_session_items_session_status_idx", "session_id", "status"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    session_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    question_id: Mapped[str] = mapped_column(Text, nullable=False)
    question_revision_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("ml_question_revisions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    session: Mapped[MlTechnicalSession] = relationship(
        "MlTechnicalSession", back_populates="items"
    )


class MlTechnicalAttempt(Base):
    __tablename__ = "ml_technical_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "user_id"],
            ["ml_technical_sessions.id", "ml_technical_sessions.user_id"],
            ondelete="CASCADE",
            name="ml_technical_attempts_session_user_fkey",
        ),
        UniqueConstraint("id", "user_id", name="ml_technical_attempts_id_user_id_key"),
        UniqueConstraint(
            "session_id",
            "question_id",
            name="ml_technical_attempts_session_question_key",
        ),
        CheckConstraint(
            "answer_kind in ('normal', 'dont_know')",
            name="ml_technical_attempts_answer_kind_check",
        ),
        CheckConstraint(
            "source_channel in ('web', 'telegram', 'mcp')",
            name="ml_technical_attempts_source_channel_check",
        ),
        Index(
            "ml_technical_attempts_source_event_key",
            "source_channel",
            "source_event_id",
            unique=True,
            postgresql_where=text("source_event_id is not null"),
        ),
        Index("ml_technical_attempts_user_answered_idx", "user_id", "answered_at"),
        Index("ml_technical_attempts_question_idx", "question_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    session_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    question_id: Mapped[str] = mapped_column(Text, nullable=False)
    question_revision_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("ml_question_revisions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    topic_id: Mapped[str] = mapped_column(Text, nullable=False)
    answer_kind: Mapped[str] = mapped_column(Text, nullable=False, default="normal")
    answer_language: Mapped[str] = mapped_column(Text, nullable=False)
    raw_answer: Mapped[str] = mapped_column(Text, nullable=False)
    source_channel: Mapped[str] = mapped_column(Text, nullable=False, default="web")
    source_event_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    provenance_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    session: Mapped[MlTechnicalSession] = relationship(
        "MlTechnicalSession", back_populates="attempts"
    )
    external_reviews: Mapped[list["MlTechnicalExternalReview"]] = relationship(
        "MlTechnicalExternalReview",
        back_populates="attempt",
        cascade="all, delete-orphan",
    )


class MlTechnicalExternalReview(Base):
    __tablename__ = "ml_technical_external_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["attempt_id", "user_id"],
            ["ml_technical_attempts.id", "ml_technical_attempts.user_id"],
            ondelete="CASCADE",
            name="ml_technical_external_reviews_attempt_user_fkey",
        ),
        Index(
            "ml_technical_external_reviews_user_created_idx", "user_id", "created_at"
        ),
        Index("ml_technical_external_reviews_attempt_idx", "attempt_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    attempt_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    reviewer: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    attempt: Mapped[MlTechnicalAttempt] = relationship(
        "MlTechnicalAttempt", back_populates="external_reviews"
    )


class MlQuestionRevision(Base):
    """Immutable content revision for one ML interview question.

    Only lifecycle fields may change after creation. Database triggers installed
    by migration 014 enforce the same boundary for non-ORM writers.
    """

    __tablename__ = "ml_question_revisions"
    __table_args__ = (
        UniqueConstraint(
            "question_key",
            "revision_no",
            name="ml_question_revisions_key_revision_key",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="ml_question_revisions_idempotency_key_key",
        ),
        CheckConstraint(
            "track_id = 'ml_technical'",
            name="ml_question_revisions_track_check",
        ),
        CheckConstraint(
            "status in ('draft', 'approved', 'retired')",
            name="ml_question_revisions_status_check",
        ),
        CheckConstraint(
            "difficulty in ('easy', 'medium', 'hard')",
            name="ml_question_revisions_difficulty_check",
        ),
        CheckConstraint(
            "source_kind in ('owner_authored', 'public_official', "
            "'public_secondary', 'private_corpus', 'model_authored')",
            name="ml_question_revisions_source_kind_check",
        ),
        CheckConstraint(
            "derivation_kind in ('original', 'paraphrase', 'synthetic')",
            name="ml_question_revisions_derivation_check",
        ),
        CheckConstraint(
            "publication_scope in ('internal_only', 'public_paraphrase', "
            "'public_verbatim')",
            name="ml_question_revisions_publication_scope_check",
        ),
        Index(
            "ml_question_revisions_one_approved_key",
            "question_key",
            unique=True,
            postgresql_where=text("status = 'approved'"),
        ),
        Index("ml_question_revisions_status_topic_idx", "status", "topic_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    question_key: Mapped[str] = mapped_column(String(64), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("ml_question_revisions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    track_id: Mapped[str] = mapped_column(
        String(40), nullable=False, default="ml_technical"
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    topic_id: Mapped[str] = mapped_column(String(80), nullable=False)
    question_ru: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    rubric_points: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False)
    reference_explanation_ru: Mapped[str] = mapped_column(Text, nullable=False)
    follow_ups: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    rubric_version: Mapped[str] = mapped_column(String(120), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    source_label: Mapped[str] = mapped_column(String(240), nullable=False)
    source_uri_public: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    derivation_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    publication_scope: Mapped[str] = mapped_column(String(40), nullable=False)
    license_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(240), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    approved_by: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retired_by: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    retired_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retirement_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    reviews: Mapped[list["MlQuestionReview"]] = relationship(
        "MlQuestionReview",
        back_populates="question_revision",
        order_by="MlQuestionReview.created_at",
    )


class MlQuestionReview(Base):
    """Append-only validation/QA evidence for a question content hash."""

    __tablename__ = "ml_question_reviews"
    __table_args__ = (
        CheckConstraint(
            "review_kind in ('schema', 'technical', 'source_ip')",
            name="ml_question_reviews_kind_check",
        ),
        CheckConstraint(
            "verdict in ('pass', 'fail', 'needs_changes')",
            name="ml_question_reviews_verdict_check",
        ),
        CheckConstraint(
            "reviewer_type in ('deterministic', 'model', 'human')",
            name="ml_question_reviews_reviewer_type_check",
        ),
        Index(
            "ml_question_reviews_revision_created_idx",
            "question_revision_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    question_revision_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("ml_question_revisions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    review_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    verdict: Mapped[str] = mapped_column(String(30), nullable=False)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    reviewer_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(160), nullable=False)
    model_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    input_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    question_revision: Mapped[MlQuestionRevision] = relationship(
        "MlQuestionRevision", back_populates="reviews"
    )


class MlProgressReview(Base):
    """Append-only analysis bound to an exact canonical progress snapshot."""

    __tablename__ = "ml_progress_reviews"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="ml_progress_reviews_id_user_id_key"),
        CheckConstraint(
            "context_schema_version = 1",
            name="ml_progress_reviews_schema_version_check",
        ),
        CheckConstraint(
            "context_hash ~ '^[0-9a-f]{64}$'",
            name="ml_progress_reviews_context_hash_check",
        ),
        CheckConstraint(
            "reviewer_type in ('model', 'human')",
            name="ml_progress_reviews_reviewer_type_check",
        ),
        CheckConstraint(
            "reviewer_type <> 'model' or model_id is not null",
            name="ml_progress_reviews_model_provenance_check",
        ),
        Index(
            "ml_progress_reviews_user_created_idx",
            "user_id",
            "created_at",
            "id",
        ),
        Index("ml_progress_reviews_user_context_idx", "user_id", "context_hash"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    context_schema_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    recommendations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    reviewer_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(160), nullable=False)
    model_id: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


__all__ = [
    "MlTechnicalSession",
    "MlTechnicalSessionItem",
    "MlTechnicalAttempt",
    "MlTechnicalExternalReview",
    "MlQuestionRevision",
    "MlQuestionReview",
    "MlProgressReview",
]
