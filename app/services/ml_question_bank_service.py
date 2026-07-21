"""Versioned PostgreSQL question bank for the ``ml_technical`` track.

The checked-in Python pack is a migration/reference fixture only. Runtime
callers consume approved revisions from this service. Question content is
immutable; lifecycle changes and QA evidence are explicit and append-only.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.ml_technical_questions import ML_TECHNICAL_TOPICS
from app.models.ml_technical import MlQuestionReview, MlQuestionRevision


ALLOWED_TOPIC_IDS = frozenset(topic["id"] for topic in ML_TECHNICAL_TOPICS)
ALLOWED_DIFFICULTIES = frozenset({"easy", "medium", "hard"})
ALLOWED_SOURCE_KINDS = frozenset(
    {
        "owner_authored",
        "public_official",
        "public_secondary",
        "private_corpus",
        "model_authored",
    }
)
ALLOWED_DERIVATION_KINDS = frozenset({"original", "paraphrase", "synthetic"})
ALLOWED_PUBLICATION_SCOPES = frozenset(
    {"internal_only", "public_paraphrase", "public_verbatim"}
)
ALLOWED_REVIEW_KINDS = frozenset({"schema", "technical", "source_ip"})
ALLOWED_REVIEW_VERDICTS = frozenset({"pass", "fail", "needs_changes"})
ALLOWED_REVIEWER_TYPES = frozenset({"deterministic", "model", "human"})

_QUESTION_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
_RUBRIC_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
_PRIVATE_MARKERS = (
    "t.me/",
    "telegram.me/",
    "tg://",
    "file://",
    "c:\\",
    "\\users\\",
    "/users/",
    "/home/",
)

_CONTENT_FIELDS = (
    "question_key",
    "track_id",
    "topic_id",
    "question_ru",
    "difficulty",
    "tags",
    "rubric_points",
    "reference_explanation_ru",
    "follow_ups",
    "rubric_version",
    "source_kind",
    "source_label",
    "source_uri_public",
    "source_fingerprint",
    "derivation_kind",
    "publication_scope",
    "license_note",
    "model_id",
    "prompt_version",
)


class MlQuestionBankConflictError(ValueError):
    """Stale hash, idempotency mismatch, or conflicting lifecycle change."""


class MlQuestionBankPermissionError(PermissionError):
    """A curator/admin-only operation was attempted without capability."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_question_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical immutable content shape used for hashing/storage."""
    question_key = str(payload.get("question_key") or payload.get("id") or "").strip()
    normalized = {
        "question_key": question_key,
        "track_id": "ml_technical",
        "topic_id": str(payload.get("topic_id") or "").strip(),
        "question_ru": str(payload.get("question_ru") or "").strip(),
        "difficulty": str(payload.get("difficulty") or "").strip().lower(),
        "tags": [str(item).strip().lower() for item in (payload.get("tags") or [])],
        "rubric_points": [
            {
                "id": str(point.get("id") or "").strip().lower(),
                "point_ru": str(point.get("point_ru") or "").strip(),
            }
            for point in (payload.get("rubric_points") or [])
            if isinstance(point, dict)
        ],
        "reference_explanation_ru": str(
            payload.get("reference_explanation_ru") or ""
        ).strip(),
        "follow_ups": [str(item).strip() for item in (payload.get("follow_ups") or [])],
        "rubric_version": str(payload.get("rubric_version") or "").strip(),
        "source_kind": str(payload.get("source_kind") or "").strip().lower(),
        "source_label": str(payload.get("source_label") or "").strip(),
        "source_uri_public": (
            str(payload.get("source_uri_public")).strip()
            if payload.get("source_uri_public")
            else None
        ),
        "source_fingerprint": (
            str(payload.get("source_fingerprint")).strip().lower()
            if payload.get("source_fingerprint")
            else None
        ),
        "derivation_kind": str(payload.get("derivation_kind") or "").strip().lower(),
        "publication_scope": str(payload.get("publication_scope") or "internal_only")
        .strip()
        .lower(),
        "license_note": (
            str(payload.get("license_note")).strip()
            if payload.get("license_note")
            else None
        ),
        "model_id": (
            str(payload.get("model_id")).strip() if payload.get("model_id") else None
        ),
        "prompt_version": (
            str(payload.get("prompt_version")).strip()
            if payload.get("prompt_version")
            else None
        ),
    }
    return normalized


def question_content_hash(payload: dict[str, Any]) -> str:
    normalized = normalize_question_payload(payload)
    canonical = {field: normalized[field] for field in _CONTENT_FIELDS}
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_question_payload(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Deterministic validation. Empty list means schema/provenance PASS."""
    value = normalize_question_payload(payload)
    issues: list[dict[str, str]] = []

    def issue(code: str, field: str, message: str) -> None:
        issues.append({"code": code, "field": field, "message": message})

    if not _QUESTION_KEY_RE.fullmatch(value["question_key"]):
        issue(
            "invalid_question_key", "question_key", "Use 3-64 lowercase id characters."
        )
    if value["topic_id"] not in ALLOWED_TOPIC_IDS:
        issue("unknown_topic", "topic_id", "Topic is outside the approved taxonomy.")
    if len(value["question_ru"]) < 10:
        issue("empty_question", "question_ru", "Question text is required.")
    if value["difficulty"] not in ALLOWED_DIFFICULTIES:
        issue(
            "invalid_difficulty",
            "difficulty",
            "Difficulty must be easy, medium or hard.",
        )

    tags = value["tags"]
    if not 1 <= len(tags) <= 12:
        issue("invalid_tag_count", "tags", "Provide 1-12 tags.")
    if len(tags) != len(set(tags)) or any(not tag for tag in tags):
        issue("invalid_tags", "tags", "Tags must be non-empty and unique.")

    rubric = value["rubric_points"]
    rubric_ids = [point["id"] for point in rubric]
    if not 3 <= len(rubric) <= 8:
        issue("invalid_rubric_count", "rubric_points", "Provide 3-8 rubric points.")
    if len(rubric_ids) != len(set(rubric_ids)):
        issue("duplicate_rubric_id", "rubric_points", "Rubric ids must be unique.")
    if any(
        not _RUBRIC_ID_RE.fullmatch(point["id"]) or len(point["point_ru"]) < 5
        for point in rubric
    ):
        issue(
            "invalid_rubric_point",
            "rubric_points",
            "Every rubric point needs a valid id and text.",
        )

    if len(value["reference_explanation_ru"]) < 20:
        issue(
            "empty_reference",
            "reference_explanation_ru",
            "Reference explanation is required.",
        )
    follow_ups = value["follow_ups"]
    if len(follow_ups) != 2 or len({item.casefold() for item in follow_ups}) != 2:
        issue(
            "invalid_follow_ups",
            "follow_ups",
            "Provide exactly two distinct follow-ups.",
        )
    if any(len(item) < 5 for item in follow_ups):
        issue("empty_follow_up", "follow_ups", "Follow-up text is required.")
    if not value["rubric_version"]:
        issue("missing_rubric_version", "rubric_version", "Rubric version is required.")

    if value["source_kind"] not in ALLOWED_SOURCE_KINDS:
        issue("unknown_source_kind", "source_kind", "Source kind is not approved.")
    if not value["source_label"]:
        issue("missing_source_label", "source_label", "Safe source label is required.")
    if value["derivation_kind"] not in ALLOWED_DERIVATION_KINDS:
        issue(
            "invalid_derivation", "derivation_kind", "Derivation kind is not approved."
        )
    if value["publication_scope"] not in ALLOWED_PUBLICATION_SCOPES:
        issue(
            "invalid_publication_scope",
            "publication_scope",
            "Publication scope is not approved.",
        )
    if not value["license_note"]:
        issue(
            "missing_license_note",
            "license_note",
            "License or consent note is required.",
        )
    if value["source_fingerprint"] and not re.fullmatch(
        r"[0-9a-f]{64}", value["source_fingerprint"]
    ):
        issue(
            "invalid_source_fingerprint",
            "source_fingerprint",
            "Fingerprint must be SHA-256.",
        )
    if value["source_kind"] == "private_corpus":
        if value["publication_scope"] != "internal_only":
            issue(
                "private_source_scope",
                "publication_scope",
                "Private corpus must default to internal_only.",
            )
        if value["source_uri_public"]:
            issue(
                "private_source_uri",
                "source_uri_public",
                "Private source URI must not be stored.",
            )
    if value["source_kind"] == "model_authored" and (
        not value["model_id"] or not value["prompt_version"]
    ):
        issue(
            "missing_model_provenance",
            "model_id",
            "Model-authored content needs model and prompt versions.",
        )

    public_text = " ".join(
        str(item or "")
        for item in (
            value["question_ru"],
            value["reference_explanation_ru"],
            value["source_label"],
            value["source_uri_public"],
            value["license_note"],
            *value["follow_ups"],
            *[point["point_ru"] for point in rubric],
        )
    ).casefold()
    for marker in _PRIVATE_MARKERS:
        if marker.casefold() in public_text:
            issue(
                "private_locator",
                "public_fields",
                "Private Telegram/local locator is forbidden.",
            )
            break
    return issues


def revision_to_question(row: MlQuestionRevision) -> dict[str, Any]:
    """Runtime authority shape compatible with the original question dictionary."""
    return {
        "id": row.question_key,
        "question_revision_id": str(row.id),
        "revision_no": row.revision_no,
        "track_id": row.track_id,
        "topic_id": row.topic_id,
        "question_ru": row.question_ru,
        "difficulty": row.difficulty,
        "tags": list(row.tags or []),
        "rubric_points": [dict(point) for point in (row.rubric_points or [])],
        "reference_explanation_ru": row.reference_explanation_ru,
        "follow_ups": list(row.follow_ups or []),
        "rubric_version": row.rubric_version,
        "provenance_id": f"ml-question-revision:{row.id}",
    }


def public_question_view(row: MlQuestionRevision | dict[str, Any]) -> dict[str, Any]:
    question = revision_to_question(row) if isinstance(row, MlQuestionRevision) else row
    return {
        "id": question["id"],
        "question_revision_id": question.get("question_revision_id"),
        "topic_id": question["topic_id"],
        "question_ru": question["question_ru"],
        "difficulty": question["difficulty"],
        "tags": list(question.get("tags") or []),
    }


def _review_dict(row: MlQuestionReview) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "review_kind": row.review_kind,
        "verdict": row.verdict,
        "findings": list(row.findings or []),
        "reviewer_type": row.reviewer_type,
        "reviewer_id": row.reviewer_id,
        "model_id": row.model_id,
        "prompt_version": row.prompt_version,
        "input_content_hash": row.input_content_hash,
        "created_at": row.created_at.isoformat(),
    }


def revision_dict(
    row: MlQuestionRevision,
    *,
    include_authority: bool = True,
    reviews: Optional[list[MlQuestionReview]] = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": str(row.id),
        "question_key": row.question_key,
        "revision_no": row.revision_no,
        "supersedes_id": str(row.supersedes_id) if row.supersedes_id else None,
        "track_id": row.track_id,
        "status": row.status,
        "topic_id": row.topic_id,
        "question_ru": row.question_ru,
        "difficulty": row.difficulty,
        "tags": list(row.tags or []),
        "rubric_version": row.rubric_version,
        "source_kind": row.source_kind,
        "source_label": row.source_label,
        "source_uri_public": None
        if row.source_kind == "private_corpus"
        else row.source_uri_public,
        "source_fingerprint": row.source_fingerprint,
        "derivation_kind": row.derivation_kind,
        "publication_scope": row.publication_scope,
        "license_note": row.license_note,
        "model_id": row.model_id,
        "prompt_version": row.prompt_version,
        "content_hash": row.content_hash,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat(),
        "approved_by": row.approved_by,
        "approved_at": row.approved_at.isoformat() if row.approved_at else None,
        "retired_by": row.retired_by,
        "retired_at": row.retired_at.isoformat() if row.retired_at else None,
        "retirement_reason": row.retirement_reason,
    }
    if include_authority:
        result.update(
            {
                "rubric_points": [dict(point) for point in (row.rubric_points or [])],
                "reference_explanation_ru": row.reference_explanation_ru,
                "follow_ups": list(row.follow_ups or []),
            }
        )
    if reviews is not None:
        result["reviews"] = [_review_dict(review) for review in reviews]
    return result


class MlQuestionBankService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_approved_questions(
        self, topic_id: Optional[str] = None
    ) -> list[dict[str, Any]]:
        stmt = select(MlQuestionRevision).where(MlQuestionRevision.status == "approved")
        if topic_id is not None:
            stmt = stmt.where(MlQuestionRevision.topic_id == topic_id)
        rows = (
            await self.db.scalars(stmt.order_by(MlQuestionRevision.question_key.asc()))
        ).all()
        return [revision_to_question(row) for row in rows]

    async def get_approved_question(
        self, question_key: str
    ) -> Optional[dict[str, Any]]:
        row = await self.db.scalar(
            select(MlQuestionRevision).where(
                MlQuestionRevision.question_key == question_key,
                MlQuestionRevision.status == "approved",
            )
        )
        return revision_to_question(row) if row is not None else None

    async def get_question_by_revision_id(
        self, revision_id: str
    ) -> Optional[dict[str, Any]]:
        row = await self.db.get(MlQuestionRevision, revision_id)
        return revision_to_question(row) if row is not None else None

    async def coverage(self) -> dict[str, Any]:
        rows = (
            await self.db.execute(
                select(
                    MlQuestionRevision.status,
                    MlQuestionRevision.topic_id,
                    func.count(MlQuestionRevision.id),
                ).group_by(MlQuestionRevision.status, MlQuestionRevision.topic_id)
            )
        ).all()
        by_status: dict[str, int] = {"draft": 0, "approved": 0, "retired": 0}
        topic_counts = {
            topic_id: {"draft": 0, "approved": 0, "retired": 0}
            for topic_id in ALLOWED_TOPIC_IDS
        }
        for status, topic_id, count in rows:
            by_status[str(status)] = by_status.get(str(status), 0) + int(count)
            topic_counts.setdefault(
                str(topic_id), {"draft": 0, "approved": 0, "retired": 0}
            )[str(status)] = int(count)
        return {
            "track_id": "ml_technical",
            "by_status": by_status,
            "topics": [
                {"topic_id": topic["id"], **topic_counts[topic["id"]]}
                for topic in ML_TECHNICAL_TOPICS
            ],
        }

    async def list_drafts(self, topic_id: Optional[str] = None) -> list[dict[str, Any]]:
        stmt = select(MlQuestionRevision).where(MlQuestionRevision.status == "draft")
        if topic_id is not None:
            stmt = stmt.where(MlQuestionRevision.topic_id == topic_id)
        rows = (
            await self.db.scalars(stmt.order_by(MlQuestionRevision.created_at.desc()))
        ).all()
        return [revision_dict(row, include_authority=True) for row in rows]

    async def get_revision(
        self, revision_id: str, *, include_authority: bool = True
    ) -> dict[str, Any]:
        row = await self.db.get(MlQuestionRevision, revision_id)
        if row is None:
            raise ValueError(f"unknown ml question revision: {revision_id}")
        reviews = (
            await self.db.scalars(
                select(MlQuestionReview)
                .where(MlQuestionReview.question_revision_id == revision_id)
                .order_by(MlQuestionReview.created_at.asc())
            )
        ).all()
        return revision_dict(
            row, include_authority=include_authority, reviews=list(reviews)
        )

    async def create_draft(
        self,
        payload: dict[str, Any],
        *,
        idempotency_key: str,
        created_by: str,
        supersedes_id: Optional[str] = None,
    ) -> dict[str, Any]:
        normalized = normalize_question_payload(payload)
        content_hash = question_content_hash(normalized)
        idempotency_key = idempotency_key.strip()
        created_by = created_by.strip()
        if not idempotency_key or not created_by:
            raise ValueError("idempotency_key and created_by are required")
        if normalized["source_kind"] not in ALLOWED_SOURCE_KINDS:
            raise ValueError("unknown source_kind")
        if normalized["derivation_kind"] not in ALLOWED_DERIVATION_KINDS:
            raise ValueError("unknown derivation_kind")
        if normalized["publication_scope"] not in ALLOWED_PUBLICATION_SCOPES:
            raise ValueError("unknown publication_scope")

        try:
            existing = await self.db.scalar(
                select(MlQuestionRevision).where(
                    MlQuestionRevision.idempotency_key == idempotency_key
                )
            )
            if existing is not None:
                if existing.content_hash != content_hash:
                    raise MlQuestionBankConflictError(
                        "idempotency_key already exists with different content_hash"
                    )
                result = revision_dict(existing, include_authority=True)
                await self.db.rollback()
                return result

            # Serialize revision number allocation and branch validation for a
            # stable question key. This is transaction-scoped and works across
            # all application workers, unlike an in-process lock.
            await self.db.execute(
                text("select pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": normalized["question_key"]},
            )

            # The same idempotency key may have won while we waited.
            existing = await self.db.scalar(
                select(MlQuestionRevision).where(
                    MlQuestionRevision.idempotency_key == idempotency_key
                )
            )
            if existing is not None:
                if existing.content_hash != content_hash:
                    raise MlQuestionBankConflictError(
                        "idempotency_key already exists with different content_hash"
                    )
                result = revision_dict(existing, include_authority=True)
                await self.db.rollback()
                return result

            revisions = (
                await self.db.scalars(
                    select(MlQuestionRevision)
                    .where(
                        MlQuestionRevision.question_key == normalized["question_key"]
                    )
                    .order_by(MlQuestionRevision.revision_no.asc())
                    .with_for_update()
                )
            ).all()
            current_approved = next(
                (revision for revision in revisions if revision.status == "approved"),
                None,
            )
            active_draft = next(
                (revision for revision in revisions if revision.status == "draft"),
                None,
            )

            if revisions:
                if supersedes_id is None:
                    raise MlQuestionBankConflictError(
                        "supersedes_id is required for a new revision"
                    )
                if current_approved is None:
                    raise MlQuestionBankConflictError(
                        "new revision must supersede the current approved revision"
                    )
                if str(current_approved.id) != str(supersedes_id):
                    raise MlQuestionBankConflictError(
                        "supersedes_id is not the current approved revision"
                    )
                if active_draft is not None:
                    raise MlQuestionBankConflictError(
                        "an active draft already exists for this question_key"
                    )
            elif supersedes_id is not None:
                raise MlQuestionBankConflictError(
                    "first revision cannot specify supersedes_id"
                )

            latest_revision = max(
                (revision.revision_no for revision in revisions), default=0
            )
            row = MlQuestionRevision(
                id=str(uuid4()),
                revision_no=int(latest_revision) + 1,
                supersedes_id=supersedes_id,
                status="draft",
                idempotency_key=idempotency_key,
                content_hash=content_hash,
                created_by=created_by,
                created_at=_utcnow(),
                **normalized,
            )
            self.db.add(row)
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            winner = await self.db.scalar(
                select(MlQuestionRevision).where(
                    MlQuestionRevision.idempotency_key == idempotency_key
                )
            )
            if winner is not None and winner.content_hash == content_hash:
                return revision_dict(winner, include_authority=True)
            raise MlQuestionBankConflictError(
                "concurrent question revision/idempotency conflict"
            ) from exc
        except Exception:
            await self.db.rollback()
            raise
        return revision_dict(row, include_authority=True)

    async def validate_draft(
        self, revision_id: str, *, expected_content_hash: str
    ) -> dict[str, Any]:
        row = await self.db.get(MlQuestionRevision, revision_id)
        if row is None:
            raise ValueError(f"unknown ml question revision: {revision_id}")
        self._require_draft_hash(row, expected_content_hash)
        issues = validate_question_payload(
            revision_to_question(row)
            | {
                "source_kind": row.source_kind,
                "source_label": row.source_label,
                "source_uri_public": row.source_uri_public,
                "source_fingerprint": row.source_fingerprint,
                "derivation_kind": row.derivation_kind,
                "publication_scope": row.publication_scope,
                "license_note": row.license_note,
                "model_id": row.model_id,
                "prompt_version": row.prompt_version,
            }
        )
        review = MlQuestionReview(
            id=str(uuid4()),
            question_revision_id=str(row.id),
            review_kind="schema",
            verdict="fail" if issues else "pass",
            findings=issues,
            reviewer_type="deterministic",
            reviewer_id="ml-question-schema-v1",
            model_id=None,
            prompt_version="ml-question-schema-v1",
            input_content_hash=row.content_hash,
            created_at=_utcnow(),
        )
        self.db.add(review)
        await self.db.commit()
        return _review_dict(review)

    async def append_qa_review(
        self,
        revision_id: str,
        *,
        expected_content_hash: str,
        review_kind: str,
        verdict: str,
        findings: list[dict[str, Any]],
        reviewer_type: str,
        reviewer_id: str,
        model_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
    ) -> dict[str, Any]:
        if review_kind not in {"technical", "source_ip"}:
            raise ValueError("QA review_kind must be technical or source_ip")
        if verdict not in ALLOWED_REVIEW_VERDICTS:
            raise ValueError("unknown QA verdict")
        if reviewer_type not in ALLOWED_REVIEWER_TYPES:
            raise ValueError("unknown reviewer_type")
        if not reviewer_id.strip():
            raise ValueError("reviewer_id is required")
        if reviewer_type == "model" and (not model_id or not prompt_version):
            raise ValueError("model QA requires model_id and prompt_version")
        row = await self.db.get(MlQuestionRevision, revision_id)
        if row is None:
            raise ValueError(f"unknown ml question revision: {revision_id}")
        self._require_draft_hash(row, expected_content_hash)
        review = MlQuestionReview(
            id=str(uuid4()),
            question_revision_id=str(row.id),
            review_kind=review_kind,
            verdict=verdict,
            findings=list(findings or []),
            reviewer_type=reviewer_type,
            reviewer_id=reviewer_id.strip(),
            model_id=model_id,
            prompt_version=prompt_version,
            input_content_hash=row.content_hash,
            created_at=_utcnow(),
        )
        self.db.add(review)
        await self.db.commit()
        return _review_dict(review)

    async def approve(
        self,
        revision_id: str,
        *,
        expected_content_hash: str,
        approved_by: str,
        admin_enabled: bool,
    ) -> dict[str, Any]:
        if not admin_enabled:
            raise MlQuestionBankPermissionError(
                "question bank admin writes are disabled"
            )
        approved_by = approved_by.strip()
        if not approved_by:
            raise ValueError("approved_by is required")
        try:
            candidate_key = await self.db.scalar(
                select(MlQuestionRevision.question_key).where(
                    MlQuestionRevision.id == revision_id
                )
            )
            if candidate_key is None:
                raise ValueError(f"unknown ml question revision: {revision_id}")
            await self.db.execute(
                text("select pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": candidate_key},
            )
            row = await self.db.scalar(
                select(MlQuestionRevision)
                .where(MlQuestionRevision.id == revision_id)
                .with_for_update()
            )
            if row is None:
                raise ValueError(f"unknown ml question revision: {revision_id}")
            self._require_draft_hash(row, expected_content_hash)
            reviews = (
                await self.db.scalars(
                    select(MlQuestionReview)
                    .where(
                        MlQuestionReview.question_revision_id == revision_id,
                        MlQuestionReview.input_content_hash == row.content_hash,
                    )
                    .order_by(
                        MlQuestionReview.created_at.desc(),
                        MlQuestionReview.id.desc(),
                    )
                )
            ).all()
            latest: dict[str, MlQuestionReview] = {}
            for review in reviews:
                latest.setdefault(review.review_kind, review)
            missing = [
                kind
                for kind in ("schema", "technical", "source_ip")
                if kind not in latest or latest[kind].verdict != "pass"
            ]
            if missing:
                raise MlQuestionBankConflictError(
                    f"approval requires latest PASS reviews: {', '.join(missing)}"
                )
            previous = await self.db.scalar(
                select(MlQuestionRevision)
                .where(
                    MlQuestionRevision.question_key == row.question_key,
                    MlQuestionRevision.status == "approved",
                    MlQuestionRevision.id != row.id,
                )
                .with_for_update()
            )
            if row.revision_no == 1:
                if row.supersedes_id is not None or previous is not None:
                    raise MlQuestionBankConflictError(
                        "first revision cannot supersede another revision"
                    )
            elif previous is None or str(row.supersedes_id) != str(previous.id):
                raise MlQuestionBankConflictError(
                    "draft no longer supersedes the current approved revision"
                )
            now = _utcnow()
            if previous is not None:
                previous.status = "retired"
                previous.retired_by = approved_by
                previous.retired_at = now
                previous.retirement_reason = f"superseded by revision {row.revision_no}"
                # Retire first so the partial unique approved-key index never
                # observes two approved rows, while both writes remain atomic
                # in the same transaction.
                await self.db.flush([previous])
            row.status = "approved"
            row.approved_by = approved_by
            row.approved_at = now
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
        return revision_dict(row, include_authority=True)

    async def retire(
        self,
        revision_id: str,
        *,
        expected_content_hash: str,
        retired_by: str,
        reason: str,
        admin_enabled: bool,
    ) -> dict[str, Any]:
        if not admin_enabled:
            raise MlQuestionBankPermissionError(
                "question bank admin writes are disabled"
            )
        if not retired_by.strip() or not reason.strip():
            raise ValueError("retired_by and reason are required")
        row = await self.db.scalar(
            select(MlQuestionRevision)
            .where(MlQuestionRevision.id == revision_id)
            .with_for_update()
        )
        if row is None:
            raise ValueError(f"unknown ml question revision: {revision_id}")
        if row.content_hash != expected_content_hash:
            await self.db.rollback()
            raise MlQuestionBankConflictError("stale content_hash")
        if row.status == "retired":
            await self.db.rollback()
            return revision_dict(row, include_authority=True)
        row.status = "retired"
        row.retired_by = retired_by.strip()
        row.retired_at = _utcnow()
        row.retirement_reason = reason.strip()
        await self.db.commit()
        return revision_dict(row, include_authority=True)

    @staticmethod
    def _require_draft_hash(
        row: MlQuestionRevision, expected_content_hash: str
    ) -> None:
        if row.status != "draft":
            raise MlQuestionBankConflictError("question revision is not draft")
        if row.content_hash != expected_content_hash:
            raise MlQuestionBankConflictError("stale content_hash")


__all__ = [
    "MlQuestionBankConflictError",
    "MlQuestionBankPermissionError",
    "MlQuestionBankService",
    "normalize_question_payload",
    "public_question_view",
    "question_content_hash",
    "revision_to_question",
    "validate_question_payload",
]
