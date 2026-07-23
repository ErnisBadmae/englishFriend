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
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _uuid() -> str:
    return str(uuid4())


class CareerVacancySnapshot(Base):
    """Immutable, content-hashed vacancy snapshot for one owner action."""

    __tablename__ = "career_vacancy_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "id", "user_id", name="career_vacancy_snapshots_id_user_id_key"
        ),
        UniqueConstraint(
            "user_id",
            "source",
            "content_hash",
            name="career_vacancy_snapshots_idempotency_key",
        ),
        CheckConstraint(
            "source in ('telegram_manual', 'web_manual')",
            name="career_vacancy_snapshots_source_check",
        ),
        Index("career_vacancy_snapshots_user_created_idx", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    role_title: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class CareerApplication(Base):
    """Current application status; history lives only in career_application_events."""

    __tablename__ = "career_applications"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="career_applications_id_user_id_key"),
        ForeignKeyConstraint(
            ["vacancy_snapshot_id", "user_id"],
            ["career_vacancy_snapshots.id", "career_vacancy_snapshots.user_id"],
            ondelete="RESTRICT",
            name="career_applications_snapshot_fkey",
        ),
        CheckConstraint(
            "status in ('applied', 'screening', 'technical', 'rejected', "
            "'offer', 'withdrawn')",
            name="career_applications_status_check",
        ),
        Index(
            "career_applications_one_active_key",
            "user_id",
            "vacancy_snapshot_id",
            unique=True,
            postgresql_where=text("status in ('applied', 'screening', 'technical')"),
        ),
        Index("career_applications_user_status_idx", "user_id", "status"),
        Index("career_applications_user_updated_idx", "user_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    vacancy_snapshot_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="applied")
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    resume_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resume_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    cover_letter_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cover_letter_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    next_action: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    next_action_due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class CareerApplicationEvent(Base):
    """Append-only event history for one application."""

    __tablename__ = "career_application_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["application_id", "user_id"],
            ["career_applications.id", "career_applications.user_id"],
            ondelete="CASCADE",
            name="career_application_events_app_user_fkey",
        ),
        CheckConstraint(
            "event_type in ('created', 'status_changed', 'note')",
            name="career_application_events_type_check",
        ),
        CheckConstraint(
            "actor_type in ('owner', 'system')",
            name="career_application_events_actor_type_check",
        ),
        Index(
            "career_application_events_idempotency_key",
            "user_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key is not null"),
        ),
        Index(
            "career_application_events_app_occurred_idx",
            "application_id",
            "occurred_at",
        ),
        Index("career_application_events_user_occurred_idx", "user_id", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    application_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class CareerTelegramPendingInput(Base):
    """The owner's single active Telegram pending intent, if any.

    PostgreSQL is canonical here; this table replaces any in-memory FSM or
    reliance on Telegram reply metadata for routing correctness. ``payload``
    holds an ephemeral LLM-suggested draft (manual lead / feedback) awaiting
    owner confirm or cancel - it never becomes canonical state on its own.
    """

    __tablename__ = "career_telegram_pending_inputs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["application_id", "user_id"],
            ["career_applications.id", "career_applications.user_id"],
            ondelete="CASCADE",
            name="career_telegram_pending_inputs_application_fkey",
        ),
        CheckConstraint(
            "intent in ('career_add', 'career_next_action', "
            "'career_manual_lead', 'career_feedback')",
            name="career_telegram_pending_inputs_intent_check",
        ),
        CheckConstraint(
            "(intent in ('career_next_action', 'career_feedback') "
            "and application_id is not null) "
            "or (intent in ('career_add', 'career_manual_lead') "
            "and application_id is null)",
            name="career_telegram_pending_inputs_application_scope_check",
        ),
        Index("career_telegram_pending_inputs_expires_idx", "expires_at"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    intent: Mapped[str] = mapped_column(String(30), nullable=False)
    application_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class CareerInboxItem(Base):
    """Owner-curated lead: manual paste today, Slice B import later.

    Not an application. A verdict of ``applied`` requires a separate
    confirmation step that links a real ``CareerApplication`` row.
    """

    __tablename__ = "career_inbox_items"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="career_inbox_items_id_user_id_key"),
        ForeignKeyConstraint(
            ["linked_application_id", "user_id"],
            ["career_applications.id", "career_applications.user_id"],
            ondelete="SET NULL",
            name="career_inbox_items_linked_application_fkey",
        ),
        CheckConstraint(
            "source in ('telegram_digest', 'linkedin_inbound', "
            "'headhunter_inbound', 'telegram_inbound', 'manual')",
            name="career_inbox_items_source_check",
        ),
        CheckConstraint(
            "owner_verdict is null or owner_verdict in "
            "('ask', 'prepare', 'skip', 'false_positive', 'applied')",
            name="career_inbox_items_verdict_check",
        ),
        CheckConstraint(
            "route is null or route in ('apply_candidate', 'outreach')",
            name="career_inbox_items_route_check",
        ),
        Index("career_inbox_items_user_created_idx", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    company: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    role_title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    route: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    gates: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    questions_for_recruiter: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    owner_verdict: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    owner_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    linked_application_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class CareerFeedbackEvent(Base):
    """Append-only owner-confirmed feedback, attached to an application or
    an inbox item. LLM is an untrusted extractor; only owner confirmation
    persists a category/evidence/next_action here."""

    __tablename__ = "career_feedback_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["application_id", "user_id"],
            ["career_applications.id", "career_applications.user_id"],
            ondelete="CASCADE",
            name="career_feedback_events_app_user_fkey",
        ),
        ForeignKeyConstraint(
            ["inbox_item_id", "user_id"],
            ["career_inbox_items.id", "career_inbox_items.user_id"],
            ondelete="CASCADE",
            name="career_feedback_events_inbox_user_fkey",
        ),
        CheckConstraint(
            "application_id is not null or inbox_item_id is not null",
            name="career_feedback_events_target_check",
        ),
        CheckConstraint(
            "category in ('positive_next_step', 'role_scope_mismatch', "
            "'legal_or_authorization', 'language', 'compensation', "
            "'technical_gap', 'seniority_or_management', 'generic_rejection', "
            "'process_delay', 'unknown')",
            name="career_feedback_events_category_check",
        ),
        CheckConstraint(
            "actor_type in ('owner', 'system')",
            name="career_feedback_events_actor_type_check",
        ),
        Index(
            "career_feedback_events_app_occurred_idx",
            "application_id",
            "occurred_at",
        ),
        Index("career_feedback_events_user_occurred_idx", "user_id", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    application_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )
    inbox_item_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False), nullable=True
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    raw_feedback: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_quote: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_action: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


__all__ = [
    "CareerVacancySnapshot",
    "CareerApplication",
    "CareerApplicationEvent",
    "CareerTelegramPendingInput",
    "CareerInboxItem",
    "CareerFeedbackEvent",
]
