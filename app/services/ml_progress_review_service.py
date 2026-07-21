"""Bounded, evidence-only context for senior ML progress analysis.

PostgreSQL remains canonical. The service exposes a stable snapshot and can
append recommendations that reference its hash, but it has no code path that
updates attempts, scores, sessions or question revisions.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

import yaml
from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core_tables import User
from app.models.ml_technical import (
    MlProgressReview,
    MlQuestionRevision,
    MlTechnicalAttempt,
    MlTechnicalExternalReview,
    MlTechnicalSession,
)

CONTEXT_SCHEMA_VERSION = 1
RECENT_ATTEMPT_LIMIT = 30
RECENT_SESSION_LIMIT = 10
MAX_REVIEW_ITEMS = 50
MAX_REVIEW_PAYLOAD_BYTES = 64_000

CAREER_BRIEF_START = "<!-- career-brief:start -->"
CAREER_BRIEF_END = "<!-- career-brief:end -->"
DEFAULT_CAREER_STRATEGY_PATH = (
    Path(__file__).resolve().parents[3] / "PERSONAL_STRATEGY.md"
)


class MlProgressReviewError(ValueError):
    """Base validation error for the progress-review boundary."""


class MlProgressContextStaleError(MlProgressReviewError):
    """The practice evidence changed after the reviewer read its context."""


class CareerBriefError(MlProgressReviewError):
    """The marked career brief cannot be read safely."""


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that treats duplicate mapping keys as invalid."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate key: {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    return value


def canonical_json(payload: dict[str, Any]) -> str:
    """Serialize a context identically across key order and process restarts."""
    return json.dumps(
        _json_safe(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def context_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def read_career_brief(path: Path = DEFAULT_CAREER_STRATEGY_PATH) -> dict[str, Any]:
    """Read only the fenced YAML between the two canonical strategy markers."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CareerBriefError(f"cannot read career brief: {exc}") from exc

    if text.count(CAREER_BRIEF_START) != 1 or text.count(CAREER_BRIEF_END) != 1:
        raise CareerBriefError("career brief markers must each occur exactly once")

    start = text.index(CAREER_BRIEF_START) + len(CAREER_BRIEF_START)
    end = text.index(CAREER_BRIEF_END)
    if end <= start:
        raise CareerBriefError("career brief markers are out of order")
    exact_block = text[start:end]

    fenced = re.fullmatch(
        r"\s*```yaml[ \t]*\r?\n(?P<yaml>.*?)(?:\r?\n)```[ \t]*\s*",
        exact_block,
        flags=re.DOTALL,
    )
    if fenced is None:
        raise CareerBriefError("career brief must contain exactly one yaml fence")

    try:
        parsed = yaml.load(fenced.group("yaml"), Loader=_UniqueKeySafeLoader)
    except yaml.YAMLError as exc:
        raise CareerBriefError(f"invalid career brief YAML: {exc}") from exc
    if not isinstance(parsed, dict):
        raise CareerBriefError("career brief YAML root must be an object")

    safe_data = _json_safe(parsed)
    return {
        "data": safe_data,
        "block_sha256": hashlib.sha256(exact_block.encode("utf-8")).hexdigest(),
    }


def _validate_review_items(
    name: str, items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        raise MlProgressReviewError(f"{name} must be an array")
    if len(items) > MAX_REVIEW_ITEMS:
        raise MlProgressReviewError(
            f"{name} cannot contain more than {MAX_REVIEW_ITEMS} items"
        )
    if any(not isinstance(item, dict) or not item for item in items):
        raise MlProgressReviewError(f"every {name} item must be a non-empty object")
    try:
        encoded = canonical_json({name: items}).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MlProgressReviewError(f"{name} must be valid JSON") from exc
    if len(encoded) > MAX_REVIEW_PAYLOAD_BYTES:
        raise MlProgressReviewError(f"{name} payload is too large")
    return _json_safe(items)


def _review_row(row: MlProgressReview) -> dict[str, Any]:
    return {
        "review_id": str(row.id),
        "user_id": row.user_id,
        "context_schema_version": row.context_schema_version,
        "context_hash": row.context_hash,
        "findings": list(row.findings or []),
        "recommendations": list(row.recommendations or []),
        "reviewer_type": row.reviewer_type,
        "reviewer_id": row.reviewer_id,
        "model_id": row.model_id,
        "prompt_version": row.prompt_version,
        "created_at": row.created_at.isoformat(),
    }


class MlProgressReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _ensure_user_exists(self, user_id: int) -> None:
        if await self.db.scalar(select(User.id).where(User.id == user_id)) is None:
            raise MlProgressReviewError(f"user {user_id} not found")

    async def build_context(self, user_id: int) -> dict[str, Any]:
        """Build a bounded snapshot from stored evidence, without conclusions."""
        await self._ensure_user_exists(user_id)

        approved = (
            await self.db.execute(
                select(
                    MlQuestionRevision.id,
                    MlQuestionRevision.question_key,
                    MlQuestionRevision.topic_id,
                    MlQuestionRevision.content_hash,
                )
                .where(MlQuestionRevision.status == "approved")
                .order_by(MlQuestionRevision.question_key.asc())
            )
        ).all()
        bank_rows = [
            {
                "revision_id": str(row.id),
                "question_id": row.question_key,
                "topic_id": row.topic_id,
                "content_hash": row.content_hash,
            }
            for row in approved
        ]
        bank_topics = Counter(row["topic_id"] for row in bank_rows)

        session_counts = (
            await self.db.execute(
                select(
                    MlTechnicalSession.status,
                    MlTechnicalSession.mode,
                    func.count(MlTechnicalSession.id),
                )
                .where(MlTechnicalSession.user_id == user_id)
                .group_by(MlTechnicalSession.status, MlTechnicalSession.mode)
                .order_by(MlTechnicalSession.status, MlTechnicalSession.mode)
            )
        ).all()
        recent_sessions = (
            await self.db.scalars(
                select(MlTechnicalSession)
                .where(MlTechnicalSession.user_id == user_id)
                .order_by(
                    MlTechnicalSession.created_at.desc(),
                    MlTechnicalSession.id.desc(),
                )
                .limit(RECENT_SESSION_LIMIT)
            )
        ).all()

        review_status_expr = literal_column("ml_technical_attempts.review ->> 'status'")
        attempt_groups = (
            await self.db.execute(
                select(
                    MlTechnicalAttempt.topic_id,
                    MlTechnicalAttempt.answer_kind,
                    review_status_expr,
                    func.count(MlTechnicalAttempt.id),
                    func.max(MlTechnicalAttempt.answered_at),
                )
                .where(MlTechnicalAttempt.user_id == user_id)
                .group_by(
                    MlTechnicalAttempt.topic_id,
                    MlTechnicalAttempt.answer_kind,
                    review_status_expr,
                )
                .order_by(
                    MlTechnicalAttempt.topic_id,
                    MlTechnicalAttempt.answer_kind,
                    review_status_expr,
                )
            )
        ).all()
        recent_pairs = (
            await self.db.execute(
                select(MlTechnicalAttempt, MlQuestionRevision)
                .join(
                    MlQuestionRevision,
                    MlQuestionRevision.id == MlTechnicalAttempt.question_revision_id,
                )
                .where(MlTechnicalAttempt.user_id == user_id)
                .order_by(
                    MlTechnicalAttempt.answered_at.desc(),
                    MlTechnicalAttempt.id.desc(),
                )
                .limit(RECENT_ATTEMPT_LIMIT)
            )
        ).all()
        attempt_ids = [attempt.id for attempt, _revision in recent_pairs]
        external_rows = (
            (
                await self.db.scalars(
                    select(MlTechnicalExternalReview)
                    .where(
                        MlTechnicalExternalReview.user_id == user_id,
                        MlTechnicalExternalReview.attempt_id.in_(attempt_ids),
                    )
                    .order_by(
                        MlTechnicalExternalReview.created_at.asc(),
                        MlTechnicalExternalReview.id.asc(),
                    )
                )
            ).all()
            if attempt_ids
            else []
        )
        external_total = int(
            await self.db.scalar(
                select(func.count(MlTechnicalExternalReview.id)).where(
                    MlTechnicalExternalReview.user_id == user_id
                )
            )
            or 0
        )
        external_by_attempt: dict[str, list[dict[str, Any]]] = {
            str(attempt_id): [] for attempt_id in attempt_ids
        }
        for review in external_rows:
            external_by_attempt[str(review.attempt_id)].append(
                {
                    "review_id": str(review.id),
                    "reviewer": review.reviewer,
                    "verdict": review.verdict,
                    "notes": review.notes,
                    "created_at": review.created_at,
                }
            )

        recent_attempts: list[dict[str, Any]] = []
        for attempt, revision in recent_pairs:
            raw_answer = attempt.raw_answer or ""
            recent_attempts.append(
                {
                    "attempt_id": str(attempt.id),
                    "session_id": str(attempt.session_id),
                    "question_id": attempt.question_id,
                    "question_revision_id": str(attempt.question_revision_id),
                    "topic_id": attempt.topic_id,
                    "answer_kind": attempt.answer_kind,
                    "answer_language": attempt.answer_language,
                    "answered_at": attempt.answered_at,
                    "raw_answer": raw_answer[:6000],
                    "raw_answer_length": len(raw_answer),
                    "raw_answer_truncated": len(raw_answer) > 6000,
                    "review": dict(attempt.review or {}),
                    "question_ru": revision.question_ru,
                    "rubric_points": list(revision.rubric_points or []),
                    "rubric_version": revision.rubric_version,
                    "external_reviews": external_by_attempt.get(str(attempt.id), []),
                }
            )

        sessions_by_status: Counter[str] = Counter()
        sessions_by_mode: Counter[str] = Counter()
        for status, mode, count in session_counts:
            sessions_by_status[str(status)] += int(count)
            sessions_by_mode[str(mode)] += int(count)

        attempts_by_status: Counter[str] = Counter()
        attempts_by_kind: Counter[str] = Counter()
        per_topic: dict[str, dict[str, Any]] = {}
        latest_answered_at: Optional[datetime] = None
        for topic_id, answer_kind, review_status, count, latest_at in attempt_groups:
            count_int = int(count)
            status_key = str(review_status or "missing")
            attempts_by_status[status_key] += count_int
            attempts_by_kind[str(answer_kind)] += count_int
            topic = per_topic.setdefault(
                str(topic_id),
                {
                    "attempt_count": 0,
                    "by_review_status": {},
                    "latest_answered_at": None,
                },
            )
            topic["attempt_count"] += count_int
            topic["by_review_status"][status_key] = (
                topic["by_review_status"].get(status_key, 0) + count_int
            )
            if latest_at is not None and (
                topic["latest_answered_at"] is None
                or latest_at > topic["latest_answered_at"]
            ):
                topic["latest_answered_at"] = latest_at
            if latest_at is not None and (
                latest_answered_at is None or latest_at > latest_answered_at
            ):
                latest_answered_at = latest_at

        snapshot = {
            "schema_version": CONTEXT_SCHEMA_VERSION,
            "track_id": "ml_technical",
            "user_id": user_id,
            "question_bank": {
                "approved_count": len(bank_rows),
                "approved_by_topic": dict(sorted(bank_topics.items())),
                "revision_set_hash": context_hash({"revisions": bank_rows}),
            },
            "sessions": {
                "total": sum(sessions_by_status.values()),
                "by_status": dict(sorted(sessions_by_status.items())),
                "by_mode": dict(sorted(sessions_by_mode.items())),
                "recent_limit": RECENT_SESSION_LIMIT,
                "recent": [
                    {
                        "session_id": str(row.id),
                        "mode": row.mode,
                        "channel": row.channel,
                        "topic_id": row.topic_id,
                        "practice_date": row.practice_date,
                        "status": row.status,
                        "created_at": row.created_at,
                        "closed_at": row.closed_at,
                    }
                    for row in recent_sessions
                ],
            },
            "attempts": {
                "total": sum(attempts_by_status.values()),
                "by_review_status": dict(sorted(attempts_by_status.items())),
                "by_answer_kind": dict(sorted(attempts_by_kind.items())),
                "latest_answered_at": latest_answered_at,
                "external_review_count": external_total,
                "per_topic": dict(sorted(per_topic.items())),
                "recent_limit": RECENT_ATTEMPT_LIMIT,
                "recent": recent_attempts,
            },
        }
        return _json_safe(snapshot)

    async def get_context(self, user_id: int) -> dict[str, Any]:
        snapshot = await self.build_context(user_id)
        return {"context": snapshot, "context_hash": context_hash(snapshot)}

    async def append_review(
        self,
        user_id: int,
        *,
        expected_context_hash: str,
        findings: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
        reviewer_type: str,
        reviewer_id: str,
        model_id: Optional[str],
        prompt_version: str,
    ) -> dict[str, Any]:
        if not re.fullmatch(r"[0-9a-f]{64}", expected_context_hash or ""):
            raise MlProgressReviewError("expected_context_hash must be SHA-256 hex")
        if reviewer_type not in {"model", "human"}:
            raise MlProgressReviewError("reviewer_type must be model or human")
        if not reviewer_id.strip():
            raise MlProgressReviewError("reviewer_id is required")
        if reviewer_type == "model" and not (model_id or "").strip():
            raise MlProgressReviewError("model_id is required for a model review")
        if not prompt_version.strip():
            raise MlProgressReviewError("prompt_version is required")

        safe_findings = _validate_review_items("findings", findings)
        safe_recommendations = _validate_review_items(
            "recommendations", recommendations
        )

        # All reads and the insert use this AsyncSession transaction. A fresh
        # MCP session is created per call; no state is accepted from the model
        # except the expected hash and its explicitly structured analysis.
        snapshot = await self.build_context(user_id)
        actual_hash = context_hash(snapshot)
        if actual_hash != expected_context_hash:
            raise MlProgressContextStaleError(
                "ml progress context changed; read a fresh context before appending"
            )

        row = MlProgressReview(
            id=str(uuid4()),
            user_id=user_id,
            context_schema_version=CONTEXT_SCHEMA_VERSION,
            context_hash=actual_hash,
            context_snapshot=snapshot,
            findings=safe_findings,
            recommendations=safe_recommendations,
            reviewer_type=reviewer_type,
            reviewer_id=reviewer_id.strip(),
            model_id=(model_id or "").strip() or None,
            prompt_version=prompt_version.strip(),
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(row)
        await self.db.commit()
        return _review_row(row)


__all__ = [
    "CareerBriefError",
    "MlProgressContextStaleError",
    "MlProgressReviewError",
    "MlProgressReviewService",
    "canonical_json",
    "context_hash",
    "read_career_brief",
]
