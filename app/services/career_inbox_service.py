"""Career Inbox v0 (Slice A of career/CAREER_TELEGRAM_COCKPIT_SPEC.md).

Owner-curated leads from manual paste today; schema-ready for Slice B's
deterministic telegram-digest import later, but this module wires no import
path and makes no network or LLM call on its own persistence path. PostgreSQL
is canonical. The LLM (when injected) is an untrusted extractor only: it may
*suggest* company/role/category/evidence/next action, but nothing it proposes
becomes canonical state without an explicit owner confirm step.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Optional, Protocol
from uuid import uuid4

from sqlalchemy import String, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.career import CareerFeedbackEvent, CareerInboxItem
from app.models.core_tables import User
from app.services.career_ledger_service import (
    CareerLedgerError,
    CareerLedgerService,
)

COMPANY_MAX_LEN = 200
ROLE_TITLE_MAX_LEN = 200
LOCATION_MAX_LEN = 200
URL_MAX_LEN = 500
RAW_TEXT_MAX_LEN = 4000
NEXT_ACTION_MAX_LEN = 200
EVIDENCE_MAX_LEN = 1000
INBOX_DISPLAY_LIMIT = 7

SOURCE_MANUAL = "manual"
SOURCE_LINKEDIN_INBOUND = "linkedin_inbound"
SOURCE_HEADHUNTER_INBOUND = "headhunter_inbound"
SOURCE_TELEGRAM_INBOUND = "telegram_inbound"
SOURCE_TELEGRAM_DIGEST = "telegram_digest"
MANUAL_LEAD_SOURCES = {
    SOURCE_MANUAL,
    SOURCE_LINKEDIN_INBOUND,
    SOURCE_HEADHUNTER_INBOUND,
    SOURCE_TELEGRAM_INBOUND,
}
VALID_INBOX_SOURCES = MANUAL_LEAD_SOURCES | {SOURCE_TELEGRAM_DIGEST}

MAX_PASTED_LEADS = 10
_NUMBERED_MARKER_RE = re.compile(r"^\s*\d+[.)]\s*", re.MULTILINE)
_BLANK_LINE_RE = re.compile(r"\n\s*\n")

# Slice B: telegram-digest import envelope (career/CAREER_TELEGRAM_COCKPIT_SPEC.md
# section 5). Only these two routes are ever exported/imported.
IMPORT_ROUTES = {"apply_candidate", "outreach"}
IMPORT_GATE_NAMES = ("legal_hire_from_rf", "language_path", "comp_threshold", "role_scope")
IMPORT_SCHEMA_VERSION = 1
_CONTENT_HASH_RE = re.compile(r"^[0-9a-f]{64}$")

VERDICT_ASK = "ask"
VERDICT_PREPARE = "prepare"
VERDICT_SKIP = "skip"
VERDICT_FALSE_POSITIVE = "false_positive"
VERDICT_APPLIED = "applied"
VALID_MANUAL_VERDICTS = {VERDICT_ASK, VERDICT_PREPARE, VERDICT_SKIP, VERDICT_FALSE_POSITIVE}

FEEDBACK_CATEGORIES = {
    "positive_next_step",
    "role_scope_mismatch",
    "legal_or_authorization",
    "language",
    "compensation",
    "technical_gap",
    "seniority_or_management",
    "generic_rejection",
    "process_delay",
    "unknown",
}
FEEDBACK_CATEGORY_UNKNOWN = "unknown"

ACTOR_TYPE_OWNER = "owner"


class CareerInboxError(ValueError):
    """Base validation error for the Career Inbox boundary."""


class CareerInboxConflictError(CareerInboxError):
    """Typed duplicate/stale-write outcome, e.g. a non-idempotent race."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _bounded_text(name: str, value: str, max_len: int, *, required: bool) -> str:
    trimmed = (value or "").strip()
    if required and not trimmed:
        raise CareerInboxError(f"{name} is required")
    if len(trimmed) > max_len:
        raise CareerInboxError(f"{name} cannot exceed {max_len} characters")
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
        raise CareerInboxError(f"{name} cannot exceed {max_len} characters")
    return trimmed


def _normalize_for_grounding(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    for dash in ("‒", "–", "—", "―", "−"):
        text = text.replace(dash, "-")
    return " ".join(text.split())


def is_grounded(quote: Optional[str], raw_text: str) -> bool:
    """A quote is grounded only if it is a continuous substring of raw_text
    after whitespace/case/dash normalization - no gluing, no paraphrase."""
    if not quote:
        return False
    return _normalize_for_grounding(quote) in _normalize_for_grounding(raw_text)


def split_pasted_leads(raw_text: str, *, max_leads: int = MAX_PASTED_LEADS) -> list[str]:
    """Deterministic, pure segmenter for a batch-pasted blob of recruiter
    messages (Career Inbox batch paste v0). No LLM, no I/O.

    Primary split: lines beginning with a numbered marker (`1.`, `2)`, ...).
    Requires at least two markers to count as a real numbered list, so a
    single incidental "1." inside one message does not misfire. Fallback:
    blank-line separated blocks. Identity case: no pattern matches, the whole
    text is one segment - a single-message paste is unchanged (zero
    regression). Result is capped at ``max_leads``; overflow is dropped."""
    text = raw_text.strip()
    if not text:
        return []

    markers = list(_NUMBERED_MARKER_RE.finditer(text))
    if len(markers) >= 2:
        segments = []
        for i, marker in enumerate(markers):
            start = marker.end()
            end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
            segment = text[start:end].strip()
            if segment:
                segments.append(segment)
        if segments:
            return segments[:max_leads]

    blocks = [b.strip() for b in _BLANK_LINE_RE.split(text) if b.strip()]
    if len(blocks) >= 2:
        return blocks[:max_leads]

    return [text][:max_leads]


def validate_import_envelope(envelope: dict[str, Any]) -> Optional[str]:
    """Strict schema check for a Slice B telegram-digest import envelope
    (SPEC section 5/13: "import envelope проходит strict validation"). Returns
    an error string, or None if the envelope is safe to import."""
    if envelope.get("schema_version") != IMPORT_SCHEMA_VERSION:
        return f"unsupported schema_version: {envelope.get('schema_version')!r}"
    if not envelope.get("external_id"):
        return "external_id is required"
    if not _CONTENT_HASH_RE.match(str(envelope.get("content_hash") or "")):
        return "content_hash must be a 64-char lowercase hex sha256"
    if envelope.get("route") not in IMPORT_ROUTES:
        return f"route must be one of {sorted(IMPORT_ROUTES)}"
    if "raw_text" in envelope:
        return "raw_text must not be present in an import envelope"
    if len(envelope.get("questions_for_recruiter") or []) > 2:
        return "questions_for_recruiter exceeds 2"
    gates = envelope.get("gates")
    if not isinstance(gates, dict) or set(gates.keys()) != set(IMPORT_GATE_NAMES):
        return f"gates must contain exactly {IMPORT_GATE_NAMES}"
    for name, gate in gates.items():
        if not isinstance(gate, dict):
            return f"gates.{name} must be an object"
        if "model_status" in gate:
            return f"gates.{name}.model_status must not be imported (untrusted, non-final)"
    return None


def _content_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _inbox_item_dict(row: CareerInboxItem) -> dict[str, Any]:
    return {
        "inbox_item_id": str(row.id),
        "source": row.source,
        "external_id": row.external_id,
        "content_hash": row.content_hash,
        "company": row.company,
        "role_title": row.role_title,
        "location": row.location,
        "url": row.url,
        "route": row.route,
        "gates": dict(row.gates) if row.gates else None,
        "questions_for_recruiter": list(row.questions_for_recruiter or []),
        "owner_verdict": row.owner_verdict,
        "owner_reason": row.owner_reason,
        "linked_application_id": row.linked_application_id,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
    }


def _feedback_event_dict(row: CareerFeedbackEvent) -> dict[str, Any]:
    return {
        "feedback_event_id": str(row.id),
        "application_id": row.application_id,
        "inbox_item_id": row.inbox_item_id,
        "category": row.category,
        "raw_feedback": row.raw_feedback,
        "evidence_quote": row.evidence_quote,
        "next_action": row.next_action,
        "actor_type": row.actor_type,
        "actor_id": row.actor_id,
        "occurred_at": row.occurred_at.isoformat(),
    }


class CareerInboxService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.ledger = CareerLedgerService(db)

    async def _ensure_user_exists(self, user_id: int) -> None:
        exists = await self.db.scalar(select(User.id).where(User.id == user_id))
        if exists is None:
            raise CareerInboxError(f"user {user_id} not found")

    async def _inbox_item_by_idempotency_key(
        self, user_id: int, idempotency_key: str
    ) -> Optional[CareerInboxItem]:
        return await self.db.scalar(
            select(CareerInboxItem).where(
                CareerInboxItem.user_id == user_id,
                CareerInboxItem.idempotency_key == idempotency_key,
            )
        )

    async def _feedback_by_idempotency_key(
        self, user_id: int, idempotency_key: str
    ) -> Optional[CareerFeedbackEvent]:
        return await self.db.scalar(
            select(CareerFeedbackEvent).where(
                CareerFeedbackEvent.user_id == user_id,
                CareerFeedbackEvent.idempotency_key == idempotency_key,
            )
        )

    async def confirm_manual_lead(
        self,
        user_id: int,
        *,
        source: str,
        raw_text: str,
        company: Optional[str],
        role_title: Optional[str],
        location: Optional[str] = None,
        url: Optional[str] = None,
        questions_for_recruiter: Optional[list[str]] = None,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        """Owner-confirmed manual lead. Nothing is written until this call -
        the LLM suggestion the owner saw in preview is not canonical on its
        own (SPEC section 7)."""
        if source not in MANUAL_LEAD_SOURCES:
            raise CareerInboxError(f"unsupported manual lead source: {source}")
        idempotency_key = _bounded_text(
            "idempotency_key", idempotency_key, 200, required=True
        )
        actor_id = _bounded_text("actor_id", actor_id, 160, required=True)
        raw_text = _bounded_text("raw_text", raw_text, RAW_TEXT_MAX_LEN, required=True)
        company = _bounded_optional_text("company", company, COMPANY_MAX_LEN)
        role_title = _bounded_optional_text("role_title", role_title, ROLE_TITLE_MAX_LEN)
        location = _bounded_optional_text("location", location, LOCATION_MAX_LEN)
        url = _bounded_optional_text("url", url, URL_MAX_LEN)
        questions = [q.strip() for q in (questions_for_recruiter or []) if q.strip()][:2]

        await self._ensure_user_exists(user_id)

        existing = await self._inbox_item_by_idempotency_key(user_id, idempotency_key)
        if existing is not None:
            return {"created": False, "inbox_item": _inbox_item_dict(existing)}

        now = _utcnow()
        content_hash = _content_hash(
            {"raw_text": raw_text, "company": company, "role_title": role_title}
        )
        item_id = str(uuid4())
        try:
            result_id = await self.db.scalar(
                pg_insert(CareerInboxItem)
                .values(
                    id=item_id,
                    user_id=user_id,
                    source=source,
                    external_id=None,
                    content_hash=content_hash,
                    source_snapshot={"raw_text": raw_text},
                    company=company,
                    role_title=role_title,
                    location=location,
                    url=url,
                    route=None,
                    gates=None,
                    questions_for_recruiter=questions,
                    owner_verdict=None,
                    idempotency_key=idempotency_key,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing()
                .returning(CareerInboxItem.id)
            )
            if result_id is None:
                await self.db.rollback()
                winner = await self._inbox_item_by_idempotency_key(
                    user_id, idempotency_key
                )
                if winner is None:
                    raise CareerInboxConflictError("duplicate career inbox item")
                return {"created": False, "inbox_item": _inbox_item_dict(winner)}
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise CareerInboxConflictError("duplicate or conflicting inbox item") from exc

        row = await self.db.get(CareerInboxItem, item_id)
        return {"created": True, "inbox_item": _inbox_item_dict(row)}

    async def import_snapshot(
        self,
        user_id: int,
        *,
        external_id: str,
        content_hash: str,
        company: Optional[str],
        role_title: Optional[str],
        location: Optional[str] = None,
        url: Optional[str] = None,
        route: str,
        gates: dict[str, Any],
        questions_for_recruiter: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Slice B: idempotent import of one telegram-digest envelope. Stable
        key is (user_id, telegram_digest, external_id, content_hash) - a
        repeated import of the exact same envelope creates no duplicate. A
        DIFFERENT content_hash for the same external_id inserts a NEW
        immutable row rather than overwriting the old one (SPEC section 6);
        :meth:`list_inbox_items` surfaces only the latest version. No fetch
        or Qwen call happens here - the caller already has the JSONL file."""
        if route not in IMPORT_ROUTES:
            raise CareerInboxError(f"unsupported import route: {route}")
        external_id = _bounded_text("external_id", external_id, 200, required=True)
        content_hash = _bounded_text("content_hash", content_hash, 64, required=True)
        if not _CONTENT_HASH_RE.match(content_hash):
            raise CareerInboxError("content_hash must be a 64-char lowercase hex sha256")
        company = _bounded_optional_text("company", company, COMPANY_MAX_LEN)
        role_title = _bounded_optional_text("role_title", role_title, ROLE_TITLE_MAX_LEN)
        location = _bounded_optional_text("location", location, LOCATION_MAX_LEN)
        url = _bounded_optional_text("url", url, URL_MAX_LEN)
        questions = [q.strip() for q in (questions_for_recruiter or []) if q.strip()][:2]
        if set((gates or {}).keys()) != set(IMPORT_GATE_NAMES):
            raise CareerInboxError(f"gates must contain exactly {IMPORT_GATE_NAMES}")

        await self._ensure_user_exists(user_id)

        idempotency_key = f"{SOURCE_TELEGRAM_DIGEST}:{external_id}:{content_hash}"
        existing = await self._inbox_item_by_idempotency_key(user_id, idempotency_key)
        if existing is not None:
            return {"created": False, "inbox_item": _inbox_item_dict(existing)}

        now = _utcnow()
        item_id = str(uuid4())
        try:
            result_id = await self.db.scalar(
                pg_insert(CareerInboxItem)
                .values(
                    id=item_id,
                    user_id=user_id,
                    source=SOURCE_TELEGRAM_DIGEST,
                    external_id=external_id,
                    content_hash=content_hash,
                    source_snapshot={},
                    company=company,
                    role_title=role_title,
                    location=location,
                    url=url,
                    route=route,
                    gates=gates,
                    questions_for_recruiter=questions,
                    owner_verdict=None,
                    idempotency_key=idempotency_key,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing()
                .returning(CareerInboxItem.id)
            )
            if result_id is None:
                await self.db.rollback()
                winner = await self._inbox_item_by_idempotency_key(
                    user_id, idempotency_key
                )
                if winner is None:
                    raise CareerInboxConflictError("duplicate career inbox import")
                return {"created": False, "inbox_item": _inbox_item_dict(winner)}
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise CareerInboxConflictError(
                "duplicate or conflicting inbox import"
            ) from exc

        row = await self.db.get(CareerInboxItem, item_id)
        return {"created": True, "inbox_item": _inbox_item_dict(row)}

    async def list_inbox_items(
        self, user_id: int, *, limit: int = INBOX_DISPLAY_LIMIT
    ) -> list[dict[str, Any]]:
        """Bounded, latest-version-only view: for imported rows that share a
        stable key (source, external_id), only the newest content_hash
        version is shown - older immutable snapshots stay in the table for
        audit but are not surfaced (SPEC section 6). Manual leads have no
        external_id, so each one is its own group."""
        await self._ensure_user_exists(user_id)
        bounded_limit = max(1, min(limit, INBOX_DISPLAY_LIMIT))
        group_key = func.coalesce(
            CareerInboxItem.external_id, func.cast(CareerInboxItem.id, String)
        )
        rank = (
            func.row_number()
            .over(
                partition_by=(CareerInboxItem.source, group_key),
                order_by=CareerInboxItem.created_at.desc(),
            )
            .label("rn")
        )
        ranked = (
            select(CareerInboxItem, rank)
            .where(CareerInboxItem.user_id == user_id)
            .subquery()
        )
        latest = aliased(CareerInboxItem, ranked)
        rows = (
            await self.db.execute(
                select(latest)
                .where(ranked.c.rn == 1)
                .order_by(ranked.c.created_at.desc(), ranked.c.id.desc())
                .limit(bounded_limit)
            )
        ).scalars().all()
        return [_inbox_item_dict(row) for row in rows]

    async def get_inbox_item(
        self, user_id: int, inbox_item_id: str
    ) -> Optional[dict[str, Any]]:
        await self._ensure_user_exists(user_id)
        row = await self.db.scalar(
            select(CareerInboxItem).where(
                CareerInboxItem.user_id == user_id,
                CareerInboxItem.id == inbox_item_id,
            )
        )
        return _inbox_item_dict(row) if row is not None else None

    async def set_verdict(
        self,
        user_id: int,
        *,
        inbox_item_id: str,
        verdict: str,
        reason: Optional[str] = None,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        """Owner-only. ``applied`` is not allowed here - it requires
        :meth:`confirm_applied` after ``prepare`` (SPEC section 9)."""
        if verdict not in VALID_MANUAL_VERDICTS:
            raise CareerInboxError(f"unsupported inbox verdict: {verdict}")
        idempotency_key = _bounded_text(
            "idempotency_key", idempotency_key, 200, required=True
        )
        actor_id = _bounded_text("actor_id", actor_id, 160, required=True)
        reason = _bounded_optional_text("reason", reason, RAW_TEXT_MAX_LEN)

        await self._ensure_user_exists(user_id)

        row = await self.db.scalar(
            select(CareerInboxItem)
            .where(
                CareerInboxItem.user_id == user_id,
                CareerInboxItem.id == inbox_item_id,
            )
            .with_for_update()
        )
        if row is None:
            raise CareerInboxError(f"unknown career inbox_item_id: {inbox_item_id}")
        if row.idempotency_key == idempotency_key and row.owner_verdict == verdict:
            return {"created": False, "inbox_item": _inbox_item_dict(row)}

        row.owner_verdict = verdict
        row.owner_reason = reason
        row.idempotency_key = idempotency_key
        row.updated_at = _utcnow()
        row.decided_at = _utcnow()
        await self.db.commit()
        await self.db.refresh(row)
        return {"created": True, "inbox_item": _inbox_item_dict(row)}

    async def confirm_applied(
        self,
        user_id: int,
        *,
        inbox_item_id: str,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        """Owner-only, second confirmation step after ``prepare``. Links a
        real :class:`CareerApplication` created via the existing ledger
        idempotent path - no new send/apply logic is introduced here."""
        idempotency_key = _bounded_text(
            "idempotency_key", idempotency_key, 200, required=True
        )
        actor_id = _bounded_text("actor_id", actor_id, 160, required=True)

        await self._ensure_user_exists(user_id)

        row = await self.db.scalar(
            select(CareerInboxItem)
            .where(
                CareerInboxItem.user_id == user_id,
                CareerInboxItem.id == inbox_item_id,
            )
            .with_for_update()
        )
        if row is None:
            raise CareerInboxError(f"unknown career inbox_item_id: {inbox_item_id}")
        if row.owner_verdict == VERDICT_APPLIED and row.linked_application_id:
            application = await self.ledger.get_application(
                user_id, row.linked_application_id
            )
            return {
                "created": False,
                "inbox_item": _inbox_item_dict(row),
                "application": application,
            }
        if row.owner_verdict != VERDICT_PREPARE:
            raise CareerInboxError(
                "confirm_applied requires a prior 'prepare' verdict"
            )

        try:
            ledger_result = await self.ledger.record_manual_application(
                user_id,
                company=row.company or "Unknown",
                role_title=row.role_title or "Unknown",
                url=row.url,
                source="telegram_manual",
                external_id=row.external_id,
                idempotency_key=idempotency_key,
                actor_id=actor_id,
            )
        except CareerLedgerError as exc:
            raise CareerInboxError(str(exc)) from exc

        row.owner_verdict = VERDICT_APPLIED
        row.linked_application_id = ledger_result["application"]["application_id"]
        row.idempotency_key = idempotency_key
        row.updated_at = _utcnow()
        row.decided_at = _utcnow()
        await self.db.commit()
        await self.db.refresh(row)
        return {
            "created": True,
            "inbox_item": _inbox_item_dict(row),
            "application": ledger_result["application"],
        }

    async def confirm_feedback(
        self,
        user_id: int,
        *,
        application_id: Optional[str] = None,
        inbox_item_id: Optional[str] = None,
        category: str,
        raw_feedback: str,
        evidence_quote: Optional[str],
        next_action: Optional[str] = None,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        """Owner-only, append-only. A category is stored only when its
        evidence quote is a grounded, continuous substring of raw_feedback;
        otherwise the record is fail-closed to ``unknown`` with no quote
        (SPEC section 8, rules 2-3)."""
        if application_id is None and inbox_item_id is None:
            raise CareerInboxError("feedback needs an application_id or inbox_item_id")
        if category not in FEEDBACK_CATEGORIES:
            raise CareerInboxError(f"unsupported feedback category: {category}")
        idempotency_key = _bounded_text(
            "idempotency_key", idempotency_key, 200, required=True
        )
        actor_id = _bounded_text("actor_id", actor_id, 160, required=True)
        raw_feedback = _bounded_text(
            "raw_feedback", raw_feedback, RAW_TEXT_MAX_LEN, required=True
        )
        next_action = _bounded_optional_text(
            "next_action", next_action, NEXT_ACTION_MAX_LEN
        )

        if category != FEEDBACK_CATEGORY_UNKNOWN and not is_grounded(
            evidence_quote, raw_feedback
        ):
            category = FEEDBACK_CATEGORY_UNKNOWN
            evidence_quote = None
        evidence_quote = _bounded_optional_text(
            "evidence_quote", evidence_quote, EVIDENCE_MAX_LEN
        )

        await self._ensure_user_exists(user_id)

        if application_id is not None:
            application = await self.ledger.get_application(user_id, application_id)
            if application is None:
                raise CareerInboxError(f"unknown career application_id: {application_id}")
        if inbox_item_id is not None:
            item = await self.get_inbox_item(user_id, inbox_item_id)
            if item is None:
                raise CareerInboxError(f"unknown career inbox_item_id: {inbox_item_id}")

        existing = await self._feedback_by_idempotency_key(user_id, idempotency_key)
        if existing is not None:
            return {"created": False, "feedback_event": _feedback_event_dict(existing)}

        now = _utcnow()
        event_id = str(uuid4())
        try:
            result_id = await self.db.scalar(
                pg_insert(CareerFeedbackEvent)
                .values(
                    id=event_id,
                    user_id=user_id,
                    application_id=application_id,
                    inbox_item_id=inbox_item_id,
                    category=category,
                    raw_feedback=raw_feedback,
                    evidence_quote=evidence_quote,
                    next_action=next_action,
                    actor_type=ACTOR_TYPE_OWNER,
                    actor_id=actor_id,
                    idempotency_key=idempotency_key,
                    occurred_at=now,
                )
                .on_conflict_do_nothing()
                .returning(CareerFeedbackEvent.id)
            )
            if result_id is None:
                await self.db.rollback()
                winner = await self._feedback_by_idempotency_key(
                    user_id, idempotency_key
                )
                if winner is None:
                    raise CareerInboxConflictError("duplicate career feedback event")
                return {"created": False, "feedback_event": _feedback_event_dict(winner)}
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise CareerInboxConflictError(
                "duplicate or conflicting feedback event"
            ) from exc

        row = await self.db.get(CareerFeedbackEvent, event_id)
        return {"created": True, "feedback_event": _feedback_event_dict(row)}


# ─── LLM suggestion (untrusted extractor; never writes canonical state) ──────


class SuggestionLLM(Protocol):
    async def generate(
        self,
        user_message: str,
        system_prompt: str,
        conversation_history: Optional[list[dict]] = None,
        max_tokens: int = 400,
    ) -> str:
        ...


_MANUAL_LEAD_SYSTEM_PROMPT = (
    "You extract a possible recruiter/company lead from a pasted Russian or "
    "English message. Reply with ONLY a JSON object, no markdown fence: "
    '{"company": string|null, "role_title": string|null, "event_kind": string, '
    '"questions_for_recruiter": [string] (max 2), '
    '"evidence_quote": string|null (one continuous verbatim substring of the '
    "input, or null if you cannot quote one continuously)}. Never invent facts "
    "not present in the text."
)

_FEEDBACK_SYSTEM_PROMPT = (
    "You classify pasted recruiter feedback about one job application. Reply "
    "with ONLY a JSON object, no markdown fence: "
    '{"category": one of '
    + ", ".join(sorted(FEEDBACK_CATEGORIES))
    + ', "evidence_quote": string|null (one continuous verbatim substring of '
    'the input), "suggested_status_change": string|null, '
    '"suggested_next_action": string|null, "rationale": string (short)}. '
    "Never invent facts not present in the text."
)


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    return text.strip()


async def suggest_manual_lead(raw_text: str, provider: Optional[SuggestionLLM]) -> dict[str, Any]:
    """Untrusted suggestion only. Any parse/timeout error, or missing
    provider, falls back to an empty suggestion the owner fills in by hand
    (SPEC section 8, rule 6)."""
    fallback = {
        "company": None,
        "role_title": None,
        "event_kind": "unknown",
        "questions_for_recruiter": [],
        "evidence_quote": None,
    }
    if provider is None:
        return fallback
    try:
        content = await provider.generate(raw_text, _MANUAL_LEAD_SYSTEM_PROMPT, max_tokens=400)
        parsed = json.loads(_strip_fence(content))
    except Exception:
        return fallback
    evidence_quote = parsed.get("evidence_quote")
    if not is_grounded(evidence_quote, raw_text):
        evidence_quote = None
    return {
        "company": parsed.get("company") or None,
        "role_title": parsed.get("role_title") or None,
        "event_kind": parsed.get("event_kind") or "unknown",
        "questions_for_recruiter": [
            q for q in (parsed.get("questions_for_recruiter") or []) if isinstance(q, str)
        ][:2],
        "evidence_quote": evidence_quote,
    }


async def suggest_feedback(raw_text: str, provider: Optional[SuggestionLLM]) -> dict[str, Any]:
    """Untrusted suggestion only. Ungrounded evidence or any failure
    downgrades to ``category=unknown`` (SPEC section 8, rules 3 and 6)."""
    fallback = {
        "category": FEEDBACK_CATEGORY_UNKNOWN,
        "evidence_quote": None,
        "suggested_status_change": None,
        "suggested_next_action": None,
        "rationale": "",
    }
    if provider is None:
        return fallback
    try:
        content = await provider.generate(raw_text, _FEEDBACK_SYSTEM_PROMPT, max_tokens=400)
        parsed = json.loads(_strip_fence(content))
    except Exception:
        return fallback
    category = parsed.get("category")
    if category not in FEEDBACK_CATEGORIES:
        category = FEEDBACK_CATEGORY_UNKNOWN
    evidence_quote = parsed.get("evidence_quote")
    if category != FEEDBACK_CATEGORY_UNKNOWN and not is_grounded(evidence_quote, raw_text):
        category = FEEDBACK_CATEGORY_UNKNOWN
        evidence_quote = None
    elif not is_grounded(evidence_quote, raw_text):
        evidence_quote = None
    return {
        "category": category,
        "evidence_quote": evidence_quote,
        "suggested_status_change": parsed.get("suggested_status_change") or None,
        "suggested_next_action": parsed.get("suggested_next_action") or None,
        "rationale": str(parsed.get("rationale") or "")[:400],
    }


__all__ = [
    "CareerInboxConflictError",
    "CareerInboxError",
    "CareerInboxService",
    "FEEDBACK_CATEGORIES",
    "FEEDBACK_CATEGORY_UNKNOWN",
    "IMPORT_GATE_NAMES",
    "IMPORT_ROUTES",
    "IMPORT_SCHEMA_VERSION",
    "INBOX_DISPLAY_LIMIT",
    "MANUAL_LEAD_SOURCES",
    "MAX_PASTED_LEADS",
    "SOURCE_HEADHUNTER_INBOUND",
    "SOURCE_LINKEDIN_INBOUND",
    "SOURCE_MANUAL",
    "SOURCE_TELEGRAM_DIGEST",
    "SOURCE_TELEGRAM_INBOUND",
    "VALID_INBOX_SOURCES",
    "VALID_MANUAL_VERDICTS",
    "VERDICT_APPLIED",
    "VERDICT_ASK",
    "VERDICT_FALSE_POSITIVE",
    "VERDICT_PREPARE",
    "VERDICT_SKIP",
    "is_grounded",
    "split_pasted_leads",
    "suggest_feedback",
    "suggest_manual_lead",
    "validate_import_envelope",
]
