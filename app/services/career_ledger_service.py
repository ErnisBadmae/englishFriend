"""Career execution ledger v0: owner-confirmed manual applications only.

PostgreSQL is canonical. This service never sends an application, never
messages a recruiter, never generates a cover letter or CV, and never lets a
model conclusion change an application status or owner fact. It only records
what the owner explicitly reports (via Telegram today) and exposes a bounded,
hash-stamped read context for MCP.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.career import (
    CareerApplication,
    CareerApplicationEvent,
    CareerVacancySnapshot,
)
from app.models.core_tables import User

COMPANY_MAX_LEN = 200
ROLE_TITLE_MAX_LEN = 200
URL_MAX_LEN = 500
DESCRIPTION_MAX_LEN = 4000
NEXT_ACTION_MAX_LEN = 200
RECENT_APPLICATIONS_LIMIT_DEFAULT = 20
NEAREST_ACTIONS_LIMIT = 5

SOURCE_TELEGRAM_MANUAL = "telegram_manual"
SOURCE_WEB_MANUAL = "web_manual"
VALID_SOURCES = {SOURCE_TELEGRAM_MANUAL, SOURCE_WEB_MANUAL}

STATUS_APPLIED = "applied"
STATUS_SCREENING = "screening"
STATUS_TECHNICAL = "technical"
STATUS_REJECTED = "rejected"
STATUS_OFFER = "offer"
STATUS_WITHDRAWN = "withdrawn"

# Explicit, testable transition map. Invalid transitions fail closed.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_APPLIED: frozenset(
        {STATUS_SCREENING, STATUS_TECHNICAL, STATUS_REJECTED, STATUS_WITHDRAWN}
    ),
    STATUS_SCREENING: frozenset(
        {STATUS_TECHNICAL, STATUS_REJECTED, STATUS_WITHDRAWN}
    ),
    STATUS_TECHNICAL: frozenset({STATUS_OFFER, STATUS_REJECTED, STATUS_WITHDRAWN}),
    STATUS_OFFER: frozenset({STATUS_WITHDRAWN}),
    STATUS_REJECTED: frozenset(),
    STATUS_WITHDRAWN: frozenset(),
}

ACTOR_TYPE_OWNER = "owner"
ACTOR_TYPE_SYSTEM = "system"
VALID_ACTOR_TYPES = {ACTOR_TYPE_OWNER, ACTOR_TYPE_SYSTEM}


class CareerLedgerError(ValueError):
    """Base validation error for the career ledger boundary."""


class CareerLedgerConflictError(CareerLedgerError):
    """Typed duplicate/stale-write outcome, e.g. a non-idempotent race."""


class CareerLedgerTransitionError(CareerLedgerError):
    """The requested status transition is not in the allowed map."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _bounded_text(name: str, value: str, max_len: int, *, required: bool) -> str:
    trimmed = (value or "").strip()
    if required and not trimmed:
        raise CareerLedgerError(f"{name} is required")
    if len(trimmed) > max_len:
        raise CareerLedgerError(f"{name} cannot exceed {max_len} characters")
    return trimmed


def _bounded_optional_text(
    name: str, value: Optional[str], max_len: int
) -> Optional[str]:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > max_len:
        raise CareerLedgerError(f"{name} cannot exceed {max_len} characters")
    return trimmed


def _snapshot_content_hash(
    *,
    company: str,
    role_title: str,
    url: Optional[str],
    raw_description: Optional[str],
    external_id: Optional[str],
) -> str:
    payload = {
        "company": company,
        "role_title": role_title,
        "url": url,
        "raw_description": raw_description,
        "external_id": external_id,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _snapshot_dict(row: CareerVacancySnapshot) -> dict[str, Any]:
    return {
        "vacancy_snapshot_id": str(row.id),
        "source": row.source,
        "external_id": row.external_id,
        "company": row.company,
        "role_title": row.role_title,
        "url": row.url,
        "raw_description": row.raw_description,
        "content_hash": row.content_hash,
        "created_at": row.created_at.isoformat(),
    }


def _application_dict(
    row: CareerApplication, snapshot: Optional[CareerVacancySnapshot] = None
) -> dict[str, Any]:
    result = {
        "application_id": str(row.id),
        "vacancy_snapshot_id": str(row.vacancy_snapshot_id),
        "status": row.status,
        "applied_at": row.applied_at.isoformat(),
        "resume_ref": row.resume_ref,
        "resume_hash": row.resume_hash,
        "cover_letter_ref": row.cover_letter_ref,
        "cover_letter_hash": row.cover_letter_hash,
        "next_action": row.next_action,
        "next_action_due_date": row.next_action_due_date.isoformat()
        if row.next_action_due_date
        else None,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }
    if snapshot is not None:
        result["company"] = snapshot.company
        result["role_title"] = snapshot.role_title
        result["url"] = snapshot.url
    return result


def _event_dict(row: CareerApplicationEvent) -> dict[str, Any]:
    return {
        "event_id": str(row.id),
        "application_id": str(row.application_id),
        "event_type": row.event_type,
        "from_status": row.from_status,
        "to_status": row.to_status,
        "actor_type": row.actor_type,
        "actor_id": row.actor_id,
        "metadata": dict(row.event_metadata or {}),
        "occurred_at": row.occurred_at.isoformat(),
    }


class CareerLedgerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _ensure_user_exists(self, user_id: int) -> None:
        exists = await self.db.scalar(select(User.id).where(User.id == user_id))
        if exists is None:
            raise CareerLedgerError(f"user {user_id} not found")

    async def _event_by_idempotency_key(
        self, user_id: int, idempotency_key: str
    ) -> Optional[CareerApplicationEvent]:
        return await self.db.scalar(
            select(CareerApplicationEvent).where(
                CareerApplicationEvent.user_id == user_id,
                CareerApplicationEvent.idempotency_key == idempotency_key,
            )
        )

    async def record_manual_application(
        self,
        user_id: int,
        *,
        company: str,
        role_title: str,
        url: Optional[str] = None,
        raw_description: Optional[str] = None,
        source: str = SOURCE_TELEGRAM_MANUAL,
        external_id: Optional[str] = None,
        idempotency_key: str,
        actor_type: str = ACTOR_TYPE_OWNER,
        actor_id: str,
        applied_at: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Atomically create/reuse a snapshot, create the application and its
        first event. A repeated call with the same ``idempotency_key`` for
        this user returns the original result without creating new rows.
        """
        if source not in VALID_SOURCES:
            raise CareerLedgerError(f"unsupported career vacancy source: {source}")
        if actor_type != ACTOR_TYPE_OWNER:
            raise CareerLedgerError("record_manual_application is owner-originated only")
        idempotency_key = _bounded_text(
            "idempotency_key", idempotency_key, 200, required=True
        )
        actor_id = _bounded_text("actor_id", actor_id, 160, required=True)
        company = _bounded_text("company", company, COMPANY_MAX_LEN, required=True)
        role_title = _bounded_text(
            "role_title", role_title, ROLE_TITLE_MAX_LEN, required=True
        )
        url = _bounded_optional_text("url", url, URL_MAX_LEN)
        raw_description = _bounded_optional_text(
            "raw_description", raw_description, DESCRIPTION_MAX_LEN
        )
        external_id = _bounded_optional_text("external_id", external_id, 200)

        await self._ensure_user_exists(user_id)

        existing_event = await self._event_by_idempotency_key(user_id, idempotency_key)
        if existing_event is not None:
            application = await self.db.get(
                CareerApplication, existing_event.application_id
            )
            snapshot = await self.db.get(
                CareerVacancySnapshot, application.vacancy_snapshot_id
            )
            return {
                "created": False,
                "application": _application_dict(application, snapshot),
                "event": _event_dict(existing_event),
            }

        content_hash = _snapshot_content_hash(
            company=company,
            role_title=role_title,
            url=url,
            raw_description=raw_description,
            external_id=external_id,
        )
        now = _utcnow()

        snapshot_id = await self.db.scalar(
            pg_insert(CareerVacancySnapshot)
            .values(
                id=str(uuid4()),
                user_id=user_id,
                source=source,
                external_id=external_id,
                company=company,
                role_title=role_title,
                url=url,
                raw_description=raw_description,
                content_hash=content_hash,
                created_at=now,
            )
            .on_conflict_do_nothing()
            .returning(CareerVacancySnapshot.id)
        )
        if snapshot_id is None:
            snapshot_id = await self.db.scalar(
                select(CareerVacancySnapshot.id).where(
                    CareerVacancySnapshot.user_id == user_id,
                    CareerVacancySnapshot.source == source,
                    CareerVacancySnapshot.content_hash == content_hash,
                )
            )

        application_id = str(uuid4())
        applied_at = applied_at or now
        try:
            application_id = await self.db.scalar(
                pg_insert(CareerApplication)
                .values(
                    id=application_id,
                    user_id=user_id,
                    vacancy_snapshot_id=snapshot_id,
                    status=STATUS_APPLIED,
                    applied_at=applied_at,
                    created_at=now,
                    updated_at=now,
                )
                .returning(CareerApplication.id)
            )
            event_id = await self.db.scalar(
                pg_insert(CareerApplicationEvent)
                .values(
                    id=str(uuid4()),
                    user_id=user_id,
                    application_id=application_id,
                    event_type="created",
                    from_status=None,
                    to_status=STATUS_APPLIED,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    event_metadata={},
                    idempotency_key=idempotency_key,
                    occurred_at=now,
                )
                .on_conflict_do_nothing()
                .returning(CareerApplicationEvent.id)
            )
            if event_id is None:
                # Lost a concurrent race for the same idempotency key: roll back
                # this attempt's application row and return the winner's result.
                await self.db.rollback()
                winner_event = await self._event_by_idempotency_key(
                    user_id, idempotency_key
                )
                if winner_event is None:
                    raise CareerLedgerConflictError(
                        "duplicate career application event"
                    )
                application = await self.db.get(
                    CareerApplication, winner_event.application_id
                )
                snapshot = await self.db.get(
                    CareerVacancySnapshot, application.vacancy_snapshot_id
                )
                return {
                    "created": False,
                    "application": _application_dict(application, snapshot),
                    "event": _event_dict(winner_event),
                }
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise CareerLedgerConflictError(
                "duplicate or conflicting career application"
            ) from exc

        application = await self.db.get(CareerApplication, application_id)
        event = await self.db.get(CareerApplicationEvent, event_id)
        snapshot = await self.db.get(CareerVacancySnapshot, snapshot_id)
        return {
            "created": True,
            "application": _application_dict(application, snapshot),
            "event": _event_dict(event),
        }

    async def append_application_event(
        self,
        user_id: int,
        *,
        application_id: str,
        to_status: str,
        actor_type: str = ACTOR_TYPE_OWNER,
        actor_id: str,
        idempotency_key: Optional[str] = None,
        note: Optional[str] = None,
        next_action: Optional[str] = None,
        next_action_due_date: Optional[date] = None,
    ) -> dict[str, Any]:
        """Owner-originated allowed transition only. Invalid transitions and
        model-originated calls fail closed.
        """
        if actor_type not in VALID_ACTOR_TYPES or actor_type == ACTOR_TYPE_SYSTEM:
            raise CareerLedgerError(
                "append_application_event is owner-originated only"
            )
        actor_id = _bounded_text("actor_id", actor_id, 160, required=True)
        next_action = _bounded_optional_text(
            "next_action", next_action, NEXT_ACTION_MAX_LEN
        )
        note = _bounded_optional_text("note", note, DESCRIPTION_MAX_LEN)

        await self._ensure_user_exists(user_id)

        if idempotency_key:
            idempotency_key = _bounded_text(
                "idempotency_key", idempotency_key, 200, required=True
            )
            existing_event = await self._event_by_idempotency_key(
                user_id, idempotency_key
            )
            if existing_event is not None:
                application = await self.db.get(
                    CareerApplication, existing_event.application_id
                )
                return {
                    "created": False,
                    "application": _application_dict(application),
                    "event": _event_dict(existing_event),
                }

        application = await self.db.scalar(
            select(CareerApplication).where(
                CareerApplication.user_id == user_id,
                CareerApplication.id == application_id,
            ).with_for_update()
        )
        if application is None:
            raise CareerLedgerError(f"unknown career application_id: {application_id}")

        # The first lookup is a fast path. Re-check after locking the current
        # application row so concurrent Telegram/MCP-adjacent retries cannot
        # derive two transitions from the same stale status.
        if idempotency_key:
            existing_event = await self._event_by_idempotency_key(
                user_id, idempotency_key
            )
            if existing_event is not None:
                existing_application = await self.db.get(
                    CareerApplication, existing_event.application_id
                )
                return {
                    "created": False,
                    "application": _application_dict(existing_application),
                    "event": _event_dict(existing_event),
                }

        current_status = application.status
        if to_status not in ALLOWED_TRANSITIONS.get(current_status, frozenset()):
            raise CareerLedgerTransitionError(
                f"transition {current_status} -> {to_status} is not allowed"
            )

        now = _utcnow()
        metadata: dict[str, Any] = {}
        if note:
            metadata["note"] = note

        try:
            application.status = to_status
            if next_action is not None:
                application.next_action = next_action
            if next_action_due_date is not None:
                application.next_action_due_date = next_action_due_date
            application.updated_at = now

            event_id = await self.db.scalar(
                pg_insert(CareerApplicationEvent)
                .values(
                    id=str(uuid4()),
                    user_id=user_id,
                    application_id=application_id,
                    event_type="status_changed",
                    from_status=current_status,
                    to_status=to_status,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    event_metadata=metadata,
                    idempotency_key=idempotency_key,
                    occurred_at=now,
                )
                .on_conflict_do_nothing()
                .returning(CareerApplicationEvent.id)
            )
            if event_id is None:
                await self.db.rollback()
                raise CareerLedgerConflictError("duplicate career application event")
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise CareerLedgerConflictError(
                "duplicate or conflicting career application event"
            ) from exc

        await self.db.refresh(application)
        event = await self.db.get(CareerApplicationEvent, event_id)
        return {
            "created": True,
            "application": _application_dict(application),
            "event": _event_dict(event),
        }

    async def list_applications(
        self, user_id: int, *, limit: int = RECENT_APPLICATIONS_LIMIT_DEFAULT
    ) -> list[dict[str, Any]]:
        await self._ensure_user_exists(user_id)
        bounded_limit = max(1, min(limit, 100))
        rows = (
            await self.db.execute(
                select(CareerApplication, CareerVacancySnapshot)
                .join(
                    CareerVacancySnapshot,
                    CareerVacancySnapshot.id == CareerApplication.vacancy_snapshot_id,
                )
                .where(CareerApplication.user_id == user_id)
                .order_by(
                    CareerApplication.updated_at.desc(), CareerApplication.id.desc()
                )
                .limit(bounded_limit)
            )
        ).all()
        return [_application_dict(app_row, snap_row) for app_row, snap_row in rows]

    async def get_pipeline_summary(self, user_id: int) -> dict[str, Any]:
        await self._ensure_user_exists(user_id)
        rows = (
            await self.db.execute(
                select(CareerApplication, CareerVacancySnapshot)
                .join(
                    CareerVacancySnapshot,
                    CareerVacancySnapshot.id == CareerApplication.vacancy_snapshot_id,
                )
                .where(CareerApplication.user_id == user_id)
            )
        ).all()
        by_status: dict[str, int] = {}
        for app_row, _snap_row in rows:
            by_status[app_row.status] = by_status.get(app_row.status, 0) + 1

        nearest_actions = sorted(
            (
                _application_dict(app_row, snap_row)
                for app_row, snap_row in rows
                if app_row.next_action_due_date is not None
            ),
            key=lambda item: item["next_action_due_date"],
        )[:NEAREST_ACTIONS_LIMIT]

        return {
            "total": len(rows),
            "by_status": dict(sorted(by_status.items())),
            "nearest_actions": nearest_actions,
        }

    async def get_review_context(self, user_id: int) -> dict[str, Any]:
        """Bounded, evidence-only facts plus a stable SHA-256 context hash."""
        summary = await self.get_pipeline_summary(user_id)
        recent = await self.list_applications(user_id, limit=RECENT_APPLICATIONS_LIMIT_DEFAULT)
        context = {
            "schema_version": 1,
            "track_id": "career_ledger",
            "user_id": user_id,
            "summary": summary,
            "recent_applications": recent,
        }
        encoded = json.dumps(
            context, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        context_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        return {"context": context, "context_hash": context_hash}


__all__ = [
    "ALLOWED_TRANSITIONS",
    "CareerLedgerConflictError",
    "CareerLedgerError",
    "CareerLedgerService",
    "CareerLedgerTransitionError",
    "STATUS_APPLIED",
    "STATUS_OFFER",
    "STATUS_REJECTED",
    "STATUS_SCREENING",
    "STATUS_TECHNICAL",
    "STATUS_WITHDRAWN",
]
