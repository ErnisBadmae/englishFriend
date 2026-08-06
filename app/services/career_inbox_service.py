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
from pathlib import Path
from typing import Any, Optional, Protocol
from uuid import uuid4

import yaml
from sqlalchemy import String, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.career import (
    CareerApplicationPackage,
    CareerCoverLetterDraft,
    CareerFeedbackEvent,
    CareerInboxItem,
)
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
INBOX_DISPLAY_LIMIT = 15

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
# Settled = no further owner action expected on this card; kept out of the
# default inbox view so they stop crowding out cards still needing a look.
SETTLED_INBOX_VERDICTS = {VERDICT_SKIP, VERDICT_FALSE_POSITIVE, VERDICT_APPLIED}

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

# Cover Letter Draft v0 (career/CAREER_COVER_LETTER_DRAFT_SPEC.md). Grounding
# source is career/facts_bank.yaml - a sibling directory owned by career/, not
# a code repository; reading it directly is the design (spec section 3), not a
# "sibling-repo reads" violation like the telegram-digest Slice B rule.
FACTS_BANK_PATH = Path(__file__).resolve().parents[3] / "career" / "facts_bank.yaml"
COVER_LETTER_BODY_MAX_LEN = 8000
DRAFT_STATUS_DRAFT = "draft"
DRAFT_STATUS_APPROVED = "owner_approved"
DRAFT_STATUS_REJECTED = "rejected"
VALID_DRAFT_STATUSES = {DRAFT_STATUS_DRAFT, DRAFT_STATUS_APPROVED, DRAFT_STATUS_REJECTED}
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_NUMERIC_TOKEN_RE = re.compile(r"\d[\d.,]*%?\+?")

# Application Package v0 (career/CAREER_OPERATING_SYSTEM_V1_SPEC.md, Slice D1a).
# CV variant selection reuses the existing facts_bank.yaml `role_types` mapping
# (trigger keywords -> CV file) - no new matcher is built here; the owner or
# caller picks `cv_variant_id` explicitly from that mapping's keys.
PACKAGE_STATUS_READY = "ready"
PACKAGE_STATUS_SUBMITTED = "submitted"
PACKAGE_STATUS_EXPIRED = "expired"
PACKAGE_KIND_APPLICATION = "application"


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


def _cover_letter_draft_dict(row: CareerCoverLetterDraft) -> dict[str, Any]:
    return {
        "draft_id": str(row.id),
        "inbox_item_id": row.inbox_item_id,
        "version": row.version,
        "body": row.body,
        "grounding_report": dict(row.grounding_report or {}),
        "status": row.status,
        "actor_type": row.actor_type,
        "actor_id": row.actor_id,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _package_dict(row: CareerApplicationPackage) -> dict[str, Any]:
    return {
        "package_id": str(row.id),
        "inbox_item_id": row.inbox_item_id,
        "inbox_item_content_hash": row.inbox_item_content_hash,
        "company": row.company,
        "role_title": row.role_title,
        "source_url": row.source_url,
        "gates_snapshot": dict(row.gates_snapshot or {}),
        "gates_hash": row.gates_hash,
        "questions_for_recruiter": list(row.questions_for_recruiter or []),
        "policy_ref": row.policy_ref,
        "cover_draft_id": row.cover_draft_id,
        "cover_version": row.cover_version,
        "cover_text_hash": row.cover_text_hash,
        "used_fact_ids": list(row.used_fact_ids or []),
        "facts_bank_hash": row.facts_bank_hash,
        "cv_variant_id": row.cv_variant_id,
        "cv_content_hash": row.cv_content_hash,
        "package_kind": row.package_kind,
        "package_content_hash": row.package_content_hash,
        "status": row.status,
        "actor_id": row.actor_id,
        "created_at": row.created_at.isoformat(),
        "ready_at": row.ready_at.isoformat(),
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "linked_application_id": row.linked_application_id,
        "linked_event_id": row.linked_event_id,
    }


# ─── facts_bank grounding (read-only; never writes career/facts_bank.yaml) ───


def load_facts_bank(path: Path = FACTS_BANK_PATH) -> Optional[dict[str, Any]]:
    """Read-only load. Returns ``None`` on a missing, empty, or unparseable
    file - the caller must treat that as a manual-path signal, not an
    exception (SPEC section 5, rule 3). Never writes to the file."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not raw.strip():
        return None
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict) or not data.get("facts"):
        return None
    return data


def _tier_a_facts(facts_bank: dict[str, Any]) -> list[dict[str, Any]]:
    return [f for f in facts_bank.get("facts", []) if f.get("tier") == "A"]


def _tier_a_corpus(facts_bank: dict[str, Any]) -> str:
    parts: list[str] = []
    for fact in _tier_a_facts(facts_bank):
        if fact.get("text"):
            parts.append(str(fact["text"]))
        for variant in (fact.get("text_variants") or {}).values():
            parts.append(str(variant))
    return "\n".join(parts)


def build_grounding_report(draft_body: str, facts_bank: dict[str, Any]) -> dict[str, Any]:
    """Deterministic grounding check (spec section 2): a sentence carrying a
    concrete numeric claim (a number, percentage, or count) not found
    anywhere in tier-A facts is flagged, never silently kept. ``used_facts``
    is a best-effort signal - a tier-A fact is listed if enough of its
    distinctive vocabulary is reused in the draft."""
    corpus = _tier_a_corpus(facts_bank)
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(draft_body) if s.strip()]

    flagged: list[dict[str, Any]] = []
    for sentence in sentences:
        tokens = _NUMERIC_TOKEN_RE.findall(sentence)
        unmatched = [t for t in tokens if t not in corpus]
        if unmatched:
            flagged.append({"sentence": sentence, "unmatched_tokens": unmatched})

    used_facts: list[str] = []
    normalized_draft = draft_body.lower()
    for fact in _tier_a_facts(facts_bank):
        text = str(fact.get("text") or "")
        words = {w for w in re.findall(r"[a-zA-Zа-яА-ЯёЁ]{5,}", text.lower())}
        overlap = sum(1 for w in words if w in normalized_draft)
        if overlap >= 2:
            used_facts.append(fact["id"])

    return {"used_facts": used_facts, "flagged_sentences": flagged}


_COVER_LETTER_SYSTEM_PROMPT = (
    "You draft a short Russian cover letter (6-9 sentences) using ONLY the facts "
    "provided in the user message. Never invent a number, company name, "
    "technology, date, or metric that is not present in those facts. If unsure, "
    "omit it rather than guess. Reply with plain text only - no JSON, no "
    "markdown fence."
)


async def draft_cover_letter_body(
    vacancy_context: str,
    facts_bank: dict[str, Any],
    provider: Optional["SuggestionLLM"],
) -> Optional[str]:
    """Untrusted drafter call. Any missing provider, empty tier-A corpus, or
    generation failure/timeout returns ``None`` - the caller must treat that
    as a manual-path signal, never a partial/guessed draft."""
    if provider is None:
        return None
    facts_text = _tier_a_corpus(facts_bank)
    if not facts_text.strip():
        return None
    user_message = (
        f"{vacancy_context}\n\nФакты (тир A, использовать только их, ничего не "
        f"добавлять):\n{facts_text}"
    )
    try:
        body = await provider.generate(
            user_message, _COVER_LETTER_SYSTEM_PROMPT, max_tokens=600
        )
    except Exception:
        return None
    body = (body or "").strip()
    return body or None


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
        or Qwen call happens here - the caller already has the JSONL file.

        Exception: once the owner has decided anything about a vacancy, that
        vacancy is frozen and a re-import with a drifted content_hash adds no
        new version. Otherwise incidental churn in the source post (view
        counters, edits) would mint a verdict-less row and hand the owner a
        card they already worked - and would orphan the drafts and packages
        that reference the decided row's id."""
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

        decided = await self.db.scalar(
            select(CareerInboxItem)
            .where(
                CareerInboxItem.user_id == user_id,
                CareerInboxItem.source == SOURCE_TELEGRAM_DIGEST,
                CareerInboxItem.external_id == external_id,
                CareerInboxItem.owner_verdict.isnot(None),
            )
            .order_by(CareerInboxItem.created_at.desc())
            .limit(1)
        )
        if decided is not None:
            return {"created": False, "inbox_item": _inbox_item_dict(decided)}

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
        external_id, so each one is its own group.

        A settled decision belongs to the vacancy, not to the snapshot row
        that happened to be on screen when it was made: the whole group is
        excluded as soon as ANY of its versions is settled
        (SETTLED_INBOX_VERDICTS). Checking only the newest row would let a
        re-import with a changed content_hash mint a fresh verdict-less
        version and resurrect a vacancy the owner already skipped, marked a
        false positive, or applied to. Settled rows remain in the table and
        are still reachable individually via get_inbox_item / Отклики."""
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
        group_settled = (
            func.bool_or(CareerInboxItem.owner_verdict.in_(SETTLED_INBOX_VERDICTS))
            .over(partition_by=(CareerInboxItem.source, group_key))
            .label("group_settled")
        )
        ranked = (
            select(CareerInboxItem, rank, group_settled)
            .where(CareerInboxItem.user_id == user_id)
            .subquery()
        )
        latest = aliased(CareerInboxItem, ranked)
        rows = (
            await self.db.execute(
                select(latest)
                .where(
                    ranked.c.rn == 1,
                    # bool_or is NULL when every row in the group is
                    # unverdicted, so isnot(True) keeps those groups.
                    ranked.c.group_settled.isnot(True),
                )
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
        # Replay safety is judged on the resulting state (verdict + reason), not
        # on the incoming callback idempotency_key: `idempotency_key` on the row
        # is the immutable import/creation identity import_snapshot looks up by
        # and must never be overwritten after creation.
        if row.owner_verdict == verdict and row.owner_reason == reason:
            return {"created": False, "inbox_item": _inbox_item_dict(row)}

        row.owner_verdict = verdict
        row.owner_reason = reason
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

        # `idempotency_key` is passed to the ledger above, which owns replay
        # safety for the application it creates; the inbox row's own
        # idempotency_key (its import/creation identity) is intentionally
        # left untouched here.
        row.owner_verdict = VERDICT_APPLIED
        row.linked_application_id = ledger_result["application"]["application_id"]
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

    # ── Cover Letter Draft v0 (career/CAREER_COVER_LETTER_DRAFT_SPEC.md) ──────

    async def _draft_by_idempotency_key(
        self, user_id: int, idempotency_key: str
    ) -> Optional[CareerCoverLetterDraft]:
        return await self.db.scalar(
            select(CareerCoverLetterDraft).where(
                CareerCoverLetterDraft.user_id == user_id,
                CareerCoverLetterDraft.idempotency_key == idempotency_key,
            )
        )

    async def _next_draft_version(self, user_id: int, inbox_item_id: str) -> int:
        current_max = await self.db.scalar(
            select(func.max(CareerCoverLetterDraft.version)).where(
                CareerCoverLetterDraft.user_id == user_id,
                CareerCoverLetterDraft.inbox_item_id == inbox_item_id,
            )
        )
        return (current_max or 0) + 1

    async def generate_cover_letter_draft(
        self,
        user_id: int,
        *,
        inbox_item_id: str,
        provider: Optional["SuggestionLLM"],
        idempotency_key: str,
        actor_id: str,
        facts_bank_path: Path = FACTS_BANK_PATH,
    ) -> dict[str, Any]:
        """Owner-triggered draft generation, attached only to a ``prepare``
        inbox item. On empty/broken facts bank or any drafter failure,
        returns ``manual_path=True`` and writes NO row - the owner can still
        write by hand from the skeleton (SPEC section 5, rule 3). facts_bank
        is only ever read here, never written. ``facts_bank_path`` defaults to
        the real ``career/facts_bank.yaml`` and is overridable for tests."""
        idempotency_key = _bounded_text(
            "idempotency_key", idempotency_key, 200, required=True
        )
        actor_id = _bounded_text("actor_id", actor_id, 160, required=True)

        await self._ensure_user_exists(user_id)

        item = await self.get_inbox_item(user_id, inbox_item_id)
        if item is None:
            raise CareerInboxError(f"unknown career inbox_item_id: {inbox_item_id}")
        if item.get("owner_verdict") != VERDICT_PREPARE:
            raise CareerInboxError(
                "cover letter draft requires a prior 'prepare' verdict"
            )

        existing = await self._draft_by_idempotency_key(user_id, idempotency_key)
        if existing is not None:
            return {
                "created": False,
                "manual_path": False,
                "draft": _cover_letter_draft_dict(existing),
            }

        facts_bank = load_facts_bank(facts_bank_path)
        if facts_bank is None:
            return {
                "created": False,
                "manual_path": True,
                "reason": "facts_bank unavailable",
                "draft": None,
            }

        vacancy_context = (
            f"Компания: {item.get('company') or 'unknown'}\n"
            f"Роль: {item.get('role_title') or 'unknown'}\n"
            f"Локация: {item.get('location') or 'unknown'}"
        )
        body = await draft_cover_letter_body(vacancy_context, facts_bank, provider)
        if not body:
            return {
                "created": False,
                "manual_path": True,
                "reason": "draft generation unavailable",
                "draft": None,
            }

        grounding_report = build_grounding_report(body, facts_bank)
        version = await self._next_draft_version(user_id, inbox_item_id)
        now = _utcnow()
        draft_id = str(uuid4())
        try:
            result_id = await self.db.scalar(
                pg_insert(CareerCoverLetterDraft)
                .values(
                    id=draft_id,
                    user_id=user_id,
                    inbox_item_id=inbox_item_id,
                    version=version,
                    body=body[:COVER_LETTER_BODY_MAX_LEN],
                    grounding_report=grounding_report,
                    status=DRAFT_STATUS_DRAFT,
                    actor_type=ACTOR_TYPE_OWNER,
                    actor_id=actor_id,
                    idempotency_key=idempotency_key,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing()
                .returning(CareerCoverLetterDraft.id)
            )
            if result_id is None:
                await self.db.rollback()
                winner = await self._draft_by_idempotency_key(user_id, idempotency_key)
                if winner is None:
                    raise CareerInboxConflictError("duplicate cover letter draft")
                return {
                    "created": False,
                    "manual_path": False,
                    "draft": _cover_letter_draft_dict(winner),
                }
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise CareerInboxConflictError(
                "duplicate or conflicting cover letter draft"
            ) from exc

        row = await self.db.get(CareerCoverLetterDraft, draft_id)
        return {"created": True, "manual_path": False, "draft": _cover_letter_draft_dict(row)}

    async def _transition_draft_status(
        self, user_id: int, *, draft_id: str, to_status: str, actor_id: str
    ) -> dict[str, Any]:
        actor_id = _bounded_text("actor_id", actor_id, 160, required=True)
        await self._ensure_user_exists(user_id)

        row = await self.db.scalar(
            select(CareerCoverLetterDraft)
            .where(
                CareerCoverLetterDraft.user_id == user_id,
                CareerCoverLetterDraft.id == draft_id,
            )
            .with_for_update()
        )
        if row is None:
            raise CareerInboxError(f"unknown cover letter draft_id: {draft_id}")
        if row.status == to_status:
            # Same action replayed (e.g. Telegram update retry) - no-op.
            return {"created": False, "draft": _cover_letter_draft_dict(row)}
        if row.status != DRAFT_STATUS_DRAFT:
            raise CareerInboxError(
                f"draft already {row.status}; cannot transition again"
            )

        row.status = to_status
        row.updated_at = _utcnow()
        await self.db.commit()
        await self.db.refresh(row)
        return {"created": True, "draft": _cover_letter_draft_dict(row)}

    async def approve_cover_letter_draft(
        self, user_id: int, *, draft_id: str, actor_id: str
    ) -> dict[str, Any]:
        """Owner-only. Sets ``owner_approved``; creates no application and
        sends nothing - sending remains the owner's own action."""
        return await self._transition_draft_status(
            user_id, draft_id=draft_id, to_status=DRAFT_STATUS_APPROVED, actor_id=actor_id
        )

    async def reject_cover_letter_draft(
        self, user_id: int, *, draft_id: str, actor_id: str
    ) -> dict[str, Any]:
        """Owner-only. Sets ``rejected``; the owner may request a new
        version via :meth:`generate_cover_letter_draft`."""
        return await self._transition_draft_status(
            user_id, draft_id=draft_id, to_status=DRAFT_STATUS_REJECTED, actor_id=actor_id
        )

    async def list_cover_letter_drafts(
        self, user_id: int, *, inbox_item_id: str
    ) -> list[dict[str, Any]]:
        await self._ensure_user_exists(user_id)
        rows = (
            await self.db.execute(
                select(CareerCoverLetterDraft)
                .where(
                    CareerCoverLetterDraft.user_id == user_id,
                    CareerCoverLetterDraft.inbox_item_id == inbox_item_id,
                )
                .order_by(CareerCoverLetterDraft.version.asc())
            )
        ).scalars().all()
        return [_cover_letter_draft_dict(row) for row in rows]

    async def get_cover_letter_draft(
        self, user_id: int, draft_id: str
    ) -> Optional[dict[str, Any]]:
        await self._ensure_user_exists(user_id)
        row = await self.db.scalar(
            select(CareerCoverLetterDraft).where(
                CareerCoverLetterDraft.user_id == user_id,
                CareerCoverLetterDraft.id == draft_id,
            )
        )
        return _cover_letter_draft_dict(row) if row is not None else None

    # ── Application Package v0 (Slice D1a) ─────────────────────────────────

    async def _is_latest_inbox_version(
        self, user_id: int, item_row: CareerInboxItem
    ) -> bool:
        """True if no newer content_hash version exists for this item's
        (source, external_id) group - the same grouping :meth:`list_inbox_items`
        uses to decide which version is current."""
        group_key = item_row.external_id or str(item_row.id)
        newer = await self.db.scalar(
            select(func.count())
            .select_from(CareerInboxItem)
            .where(
                CareerInboxItem.user_id == user_id,
                CareerInboxItem.source == item_row.source,
                func.coalesce(
                    CareerInboxItem.external_id, func.cast(CareerInboxItem.id, String)
                )
                == group_key,
                CareerInboxItem.created_at > item_row.created_at,
            )
        )
        return not newer

    @staticmethod
    def _cv_variant_content_hash(
        cv_variant_id: str, facts_bank: dict[str, Any], facts_bank_path: Path
    ) -> str:
        role_types = facts_bank.get("role_types") or {}
        variant = role_types.get(cv_variant_id)
        if not isinstance(variant, dict) or not variant.get("cv"):
            raise CareerInboxError(f"unknown cv_variant_id: {cv_variant_id}")
        cv_path = facts_bank_path.parent / str(variant["cv"])
        try:
            cv_text = cv_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CareerInboxError(f"cv file unavailable: {cv_path.name}") from exc
        return hashlib.sha256(cv_text.encode("utf-8")).hexdigest()

    async def prepare_application_package(
        self,
        user_id: int,
        *,
        inbox_item_id: str,
        cover_draft_id: str,
        cv_variant_id: str,
        actor_id: str,
        facts_bank_path: Path = FACTS_BANK_PATH,
    ) -> dict[str, Any]:
        """Owner-triggered: builds an immutable ``ready`` package snapshot from
        a ``prepare``-verdict inbox item, its owner-approved cover draft and a
        chosen CV variant (from the existing facts_bank `role_types` mapping -
        no new CV matcher). Idempotent on package content: identical inputs
        return the existing package instead of a new row (invariant 5)."""
        actor_id = _bounded_text("actor_id", actor_id, 160, required=True)
        await self._ensure_user_exists(user_id)

        item_row = await self.db.scalar(
            select(CareerInboxItem).where(
                CareerInboxItem.user_id == user_id,
                CareerInboxItem.id == inbox_item_id,
            )
        )
        if item_row is None:
            raise CareerInboxError(f"unknown career inbox_item_id: {inbox_item_id}")
        if item_row.owner_verdict != VERDICT_PREPARE:
            raise CareerInboxError(
                "application package requires a prior 'prepare' verdict"
            )
        if not await self._is_latest_inbox_version(user_id, item_row):
            raise CareerInboxError(
                "inbox item has a newer version; refresh before packaging"
            )

        draft_row = await self.db.scalar(
            select(CareerCoverLetterDraft).where(
                CareerCoverLetterDraft.user_id == user_id,
                CareerCoverLetterDraft.id == cover_draft_id,
            )
        )
        if draft_row is None:
            raise CareerInboxError(f"unknown cover letter draft_id: {cover_draft_id}")
        if draft_row.inbox_item_id != inbox_item_id:
            raise CareerInboxError("cover draft does not belong to this inbox item")
        if draft_row.status != DRAFT_STATUS_APPROVED:
            raise CareerInboxError("cover draft must be owner_approved before packaging")

        facts_bank = load_facts_bank(facts_bank_path)
        if facts_bank is None:
            raise CareerInboxError("facts_bank unavailable; cannot package")
        cv_content_hash = self._cv_variant_content_hash(
            cv_variant_id, facts_bank, facts_bank_path
        )
        facts_bank_hash = hashlib.sha256(
            facts_bank_path.read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest()

        gates_snapshot = dict(item_row.gates or {})
        package_fields = {
            "inbox_item_id": inbox_item_id,
            "inbox_item_content_hash": item_row.content_hash,
            "company": item_row.company or "Unknown",
            "role_title": item_row.role_title or "Unknown",
            "source_url": item_row.url,
            "gates_snapshot": gates_snapshot,
            "gates_hash": _content_hash(gates_snapshot),
            "questions_for_recruiter": list(item_row.questions_for_recruiter or []),
            # References the final-gates decision already made by telegram-digest's
            # policy layer at import time (SPEC section 6) - no runtime read of
            # PERSONAL_STRATEGY.md or any other sibling policy doc.
            "policy_ref": f"telegram_digest_final_gates:{item_row.content_hash}",
            "cover_draft_id": cover_draft_id,
            "cover_version": draft_row.version,
            "cover_text_hash": hashlib.sha256(
                draft_row.body.encode("utf-8")
            ).hexdigest(),
            "used_fact_ids": list(
                (draft_row.grounding_report or {}).get("used_facts") or []
            ),
            "facts_bank_hash": facts_bank_hash,
            "cv_variant_id": cv_variant_id,
            "cv_content_hash": cv_content_hash,
            "package_kind": PACKAGE_KIND_APPLICATION,
        }
        package_content_hash = _content_hash(package_fields)

        existing = await self.db.scalar(
            select(CareerApplicationPackage).where(
                CareerApplicationPackage.user_id == user_id,
                CareerApplicationPackage.inbox_item_id == inbox_item_id,
                CareerApplicationPackage.package_content_hash == package_content_hash,
            )
        )
        if existing is not None:
            return {"created": False, "package": _package_dict(existing)}

        now = _utcnow()
        package_id = str(uuid4())
        try:
            result_id = await self.db.scalar(
                pg_insert(CareerApplicationPackage)
                .values(
                    id=package_id,
                    user_id=user_id,
                    package_content_hash=package_content_hash,
                    status=PACKAGE_STATUS_READY,
                    actor_id=actor_id,
                    created_at=now,
                    ready_at=now,
                    **package_fields,
                )
                .on_conflict_do_nothing()
                .returning(CareerApplicationPackage.id)
            )
            if result_id is None:
                await self.db.rollback()
                winner = await self.db.scalar(
                    select(CareerApplicationPackage).where(
                        CareerApplicationPackage.user_id == user_id,
                        CareerApplicationPackage.inbox_item_id == inbox_item_id,
                        CareerApplicationPackage.package_content_hash
                        == package_content_hash,
                    )
                )
                if winner is None:
                    raise CareerInboxConflictError("duplicate application package")
                return {"created": False, "package": _package_dict(winner)}
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise CareerInboxConflictError(
                "duplicate or conflicting application package"
            ) from exc

        row = await self.db.get(CareerApplicationPackage, package_id)
        return {"created": True, "package": _package_dict(row)}

    async def _package_staleness_reason(
        self,
        user_id: int,
        package_row: CareerApplicationPackage,
        facts_bank_path: Path,
    ) -> Optional[str]:
        """Read-only re-check of every input the package snapshot pinned.
        Blocks submit as stale (invariant 6) rather than running a background
        expiry sweep - no scheduler is introduced for D1a."""
        item_row = await self.db.scalar(
            select(CareerInboxItem).where(
                CareerInboxItem.user_id == user_id,
                CareerInboxItem.id == package_row.inbox_item_id,
            )
        )
        if item_row is None or item_row.content_hash != package_row.inbox_item_content_hash:
            return "inbox item vacancy content changed"
        if not await self._is_latest_inbox_version(user_id, item_row):
            return "inbox item has a newer version"
        if _content_hash(dict(item_row.gates or {})) != package_row.gates_hash:
            return "gates changed"

        draft_row = await self.db.scalar(
            select(CareerCoverLetterDraft).where(
                CareerCoverLetterDraft.user_id == user_id,
                CareerCoverLetterDraft.id == package_row.cover_draft_id,
            )
        )
        if draft_row is None or draft_row.status != DRAFT_STATUS_APPROVED:
            return "cover draft no longer approved"
        latest_approved_version = await self.db.scalar(
            select(func.max(CareerCoverLetterDraft.version)).where(
                CareerCoverLetterDraft.user_id == user_id,
                CareerCoverLetterDraft.inbox_item_id == package_row.inbox_item_id,
                CareerCoverLetterDraft.status == DRAFT_STATUS_APPROVED,
            )
        )
        if (
            latest_approved_version is not None
            and latest_approved_version != package_row.cover_version
        ):
            return "a newer approved cover draft version exists"

        facts_bank = load_facts_bank(facts_bank_path)
        if facts_bank is None:
            return "facts_bank unavailable"
        current_facts_bank_hash = hashlib.sha256(
            facts_bank_path.read_text(encoding="utf-8").encode("utf-8")
        ).hexdigest()
        if current_facts_bank_hash != package_row.facts_bank_hash:
            return "facts_bank changed"
        try:
            current_cv_hash = self._cv_variant_content_hash(
                package_row.cv_variant_id, facts_bank, facts_bank_path
            )
        except CareerInboxError:
            return "cv variant no longer available"
        if current_cv_hash != package_row.cv_content_hash:
            return "cv content changed"
        return None

    async def submit_application_package(
        self,
        user_id: int,
        *,
        package_id: str,
        expected_package_hash: str,
        idempotency_key: str,
        actor_id: str,
        facts_bank_path: Path = FACTS_BANK_PATH,
    ) -> dict[str, Any]:
        """Owner-confirmed second step after ``prepare_application_package``.
        Links a real application/event created via the existing ledger
        idempotent path - no new send/apply logic is introduced here, and no
        external message or submission happens on this write path."""
        idempotency_key = _bounded_text(
            "idempotency_key", idempotency_key, 200, required=True
        )
        actor_id = _bounded_text("actor_id", actor_id, 160, required=True)
        await self._ensure_user_exists(user_id)

        replay = await self.db.scalar(
            select(CareerApplicationPackage).where(
                CareerApplicationPackage.user_id == user_id,
                CareerApplicationPackage.idempotency_key == idempotency_key,
            )
        )
        if replay is not None:
            application = (
                await self.ledger.get_application(
                    user_id, replay.linked_application_id
                )
                if replay.linked_application_id
                else None
            )
            return {
                "created": False,
                "package": _package_dict(replay),
                "application": application,
            }

        row = await self.db.scalar(
            select(CareerApplicationPackage)
            .where(
                CareerApplicationPackage.user_id == user_id,
                CareerApplicationPackage.id == package_id,
            )
            .with_for_update()
        )
        if row is None:
            raise CareerInboxError(f"unknown application package_id: {package_id}")
        if row.package_content_hash != expected_package_hash:
            raise CareerInboxError("stale package: expected hash mismatch")
        if row.status != PACKAGE_STATUS_READY:
            raise CareerInboxError(f"package already {row.status}; cannot submit")

        staleness = await self._package_staleness_reason(user_id, row, facts_bank_path)
        if staleness:
            raise CareerInboxError(f"stale package: {staleness}")

        try:
            ledger_result = await self.ledger.record_manual_application(
                user_id,
                company=row.company,
                role_title=row.role_title,
                url=row.source_url,
                source="telegram_manual",
                idempotency_key=idempotency_key,
                actor_id=actor_id,
                event_metadata={"application_package_id": str(row.id)},
            )
        except CareerLedgerError as exc:
            raise CareerInboxError(str(exc)) from exc

        row.status = PACKAGE_STATUS_SUBMITTED
        row.idempotency_key = idempotency_key
        row.submitted_at = _utcnow()
        row.linked_application_id = ledger_result["application"]["application_id"]
        row.linked_event_id = ledger_result["event"]["event_id"]
        await self.db.commit()
        await self.db.refresh(row)
        return {
            "created": True,
            "package": _package_dict(row),
            "application": ledger_result["application"],
        }

    async def get_application_package(
        self, user_id: int, package_id: str
    ) -> Optional[dict[str, Any]]:
        await self._ensure_user_exists(user_id)
        row = await self.db.scalar(
            select(CareerApplicationPackage).where(
                CareerApplicationPackage.user_id == user_id,
                CareerApplicationPackage.id == package_id,
            )
        )
        return _package_dict(row) if row is not None else None

    async def list_ready_application_packages(
        self, user_id: int, *, limit: int = 7
    ) -> list[dict[str, Any]]:
        """Bounded, owner-only view of ready-to-send packages, newest first.
        Does not compute any score/matcher and makes no provider/network call."""
        await self._ensure_user_exists(user_id)
        bounded_limit = max(1, min(limit, 7))
        rows = (
            await self.db.execute(
                select(CareerApplicationPackage)
                .where(
                    CareerApplicationPackage.user_id == user_id,
                    CareerApplicationPackage.status == PACKAGE_STATUS_READY,
                )
                .order_by(CareerApplicationPackage.created_at.desc())
                .limit(bounded_limit)
            )
        ).scalars().all()
        return [_package_dict(row) for row in rows]


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
    "COVER_LETTER_BODY_MAX_LEN",
    "DRAFT_STATUS_APPROVED",
    "DRAFT_STATUS_DRAFT",
    "DRAFT_STATUS_REJECTED",
    "FACTS_BANK_PATH",
    "FEEDBACK_CATEGORIES",
    "FEEDBACK_CATEGORY_UNKNOWN",
    "IMPORT_GATE_NAMES",
    "IMPORT_ROUTES",
    "IMPORT_SCHEMA_VERSION",
    "INBOX_DISPLAY_LIMIT",
    "MANUAL_LEAD_SOURCES",
    "MAX_PASTED_LEADS",
    "PACKAGE_KIND_APPLICATION",
    "PACKAGE_STATUS_EXPIRED",
    "PACKAGE_STATUS_READY",
    "PACKAGE_STATUS_SUBMITTED",
    "SOURCE_HEADHUNTER_INBOUND",
    "SOURCE_LINKEDIN_INBOUND",
    "SOURCE_MANUAL",
    "SOURCE_TELEGRAM_DIGEST",
    "SOURCE_TELEGRAM_INBOUND",
    "VALID_DRAFT_STATUSES",
    "VALID_INBOX_SOURCES",
    "VALID_MANUAL_VERDICTS",
    "VERDICT_APPLIED",
    "VERDICT_ASK",
    "VERDICT_FALSE_POSITIVE",
    "VERDICT_PREPARE",
    "VERDICT_SKIP",
    "build_grounding_report",
    "draft_cover_letter_body",
    "is_grounded",
    "load_facts_bank",
    "split_pasted_leads",
    "suggest_feedback",
    "suggest_manual_lead",
    "validate_import_envelope",
]
