"""Service layer for the `ml_technical` interview track.

After Slice A cutover, runtime state is read from and written to the
relational `ml_technical_*` tables only. The old `LearningPlan.roadmap`
JSONB section is a migration archive and is not part of the service read path.
"""

from __future__ import annotations

import hashlib
import logging
import random
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.ml_technical_questions import (
    ML_TECHNICAL_TOPICS,
    get_ml_technical_question,
    list_ml_technical_questions,
)
from app.models.core_tables import User
from app.models.ml_technical import (
    MlQuestionRevision,
    MlTechnicalAttempt,
    MlTechnicalExternalReview,
    MlTechnicalSession,
    MlTechnicalSessionItem,
)
from app.services.ml_question_bank_service import (
    MlQuestionBankService,
    public_question_view as bank_public_question_view,
    revision_to_question,
)
from app.services.ml_technical_reviewer import ReviewOutcome, review_technical_answer

logger = logging.getLogger(__name__)

PASS_THRESHOLD_PERCENT = 70.0
"""A question counts as currently passed only from a valid rubric review at
or above this score. Configured here, not scattered across call sites."""

REPETITION_DUE_DAYS = 3
"""A passed question becomes due for repetition this many days after its
latest graded review."""

ANSWER_LANGUAGE_DEFAULT = "ru_knowledge"
ANSWER_KIND_NORMAL = "normal"
ANSWER_KIND_DONT_KNOW = "dont_know"
SOURCE_CHANNEL_DEFAULT = "web"


class MlTechnicalConflictError(ValueError):
    """Typed duplicate/stale-write outcome mapped to HTTP 409 by adapters."""


class MlTechnicalTransactionError(RuntimeError):
    """The write service was called with a caller-owned active transaction."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().isoformat()


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _parse_iso(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _empty_ml_technical_roadmap() -> dict[str, Any]:
    return {"attempts": [], "sessions": [], "external_reviews": []}


def _attempt_dict(row: MlTechnicalAttempt | dict[str, Any]) -> dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    result = {
        "attempt_id": str(row.id),
        "session_id": str(row.session_id),
        "question_id": row.question_id,
        "topic_id": row.topic_id,
        "answer_kind": row.answer_kind,
        "answer_language": row.answer_language,
        "raw_answer": row.raw_answer,
        "source_channel": row.source_channel,
        "source_event_id": row.source_event_id,
        "answered_at": _iso(row.answered_at),
        "provenance_id": row.provenance_id,
        "review": dict(row.review or {}),
    }
    if row.question_revision_id is not None:
        result["question_revision_id"] = str(row.question_revision_id)
    return result


def _external_review_dict(
    row: MlTechnicalExternalReview | dict[str, Any]
) -> dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    return {
        "review_id": str(row.id),
        "attempt_id": str(row.attempt_id),
        "reviewer": row.reviewer,
        "verdict": row.verdict,
        "notes": row.notes,
        "created_at": _iso(row.created_at),
    }


# ---------------------------------------------------------------------------
# Pure progress/selection logic - no DB access, directly testable.
# ---------------------------------------------------------------------------


def _question_fixture(
    questions: Optional[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Use the checked-in pack only as a unit-test/offline fixture."""
    return questions if questions is not None else list_ml_technical_questions()


def _question_by_id(
    question_id: str, questions: Optional[list[dict[str, Any]]]
) -> Optional[dict[str, Any]]:
    if questions is None:
        return get_ml_technical_question(question_id)
    return next((item for item in questions if item["id"] == question_id), None)


def _attempts_for_question(
    question_id: str,
    attempts: list[dict[str, Any]],
    question_revision_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    matching = [
        attempt
        for attempt in attempts
        if attempt.get("question_id") == question_id
        and (
            question_revision_id is None
            or attempt.get("question_revision_id") == question_revision_id
        )
    ]
    return sorted(matching, key=lambda a: a.get("answered_at") or "", reverse=True)


def question_state(
    question_id: str,
    attempts: list[dict[str, Any]],
    question_revision_id: Optional[str] = None,
) -> dict[str, Any]:
    """Aggregate attempts for one exact currently-authoritative revision.

    ``question_id`` remains the stable product identity, while readiness is
    deliberately revision-scoped. Older attempts stay in history but cannot
    make a newly approved revision look attempted or passed.
    """
    question_attempts = _attempts_for_question(
        question_id, attempts, question_revision_id
    )
    attempted = bool(question_attempts)
    latest_attempted_at = question_attempts[0].get("answered_at") if attempted else None

    graded = [
        a
        for a in question_attempts
        if (a.get("review") or {}).get("status") == "graded"
    ]
    needs_review_count = sum(
        1
        for a in question_attempts
        if (a.get("review") or {}).get("status") == "needs_review"
    )

    latest_graded = graded[0] if graded else None
    latest_graded_review = (latest_graded or {}).get("review") or {}
    latest_score = latest_graded_review.get("score_percent") if latest_graded else None
    best_score = (
        max(
            (a.get("review") or {}).get("score_percent")
            for a in graded
            if (a.get("review") or {}).get("score_percent") is not None
        )
        if graded
        else None
    )

    passed = bool(
        latest_graded
        and latest_score is not None
        and latest_score >= PASS_THRESHOLD_PERCENT
    )
    failed = bool(
        latest_graded
        and latest_score is not None
        and latest_score < PASS_THRESHOLD_PERCENT
    )

    due_for_repetition = False
    if passed:
        graded_at = _parse_iso(latest_graded.get("answered_at"))
        if graded_at is not None:
            due_for_repetition = _utcnow() - graded_at >= timedelta(
                days=REPETITION_DUE_DAYS
            )

    latest_status = None
    if attempted:
        latest_status = (question_attempts[0].get("review") or {}).get("status")

    return {
        "question_id": question_id,
        "question_revision_id": question_revision_id,
        "attempted": attempted,
        "attempt_count": len(question_attempts),
        "needs_review_count": needs_review_count,
        "last_attempted_at": latest_attempted_at,
        "latest_graded_at": latest_graded.get("answered_at") if latest_graded else None,
        "latest_status": latest_status,
        "passed": passed,
        "failed": failed,
        "due_for_repetition": due_for_repetition,
        "best_score": best_score,
        "latest_score": latest_score,
    }


def select_topic_queue(
    topic_id: str,
    attempts: list[dict[str, Any]],
    session_seed: Optional[str] = None,
    questions: Optional[list[dict[str, Any]]] = None,
) -> list[str]:
    """Order a topic's question ids by selection priority."""
    topic_questions = [
        question
        for question in _question_fixture(questions)
        if question["topic_id"] == topic_id
    ]
    question_ids = [q["id"] for q in topic_questions]
    states = {
        question["id"]: question_state(
            question["id"], attempts, question.get("question_revision_id")
        )
        for question in topic_questions
    }

    unseen = [qid for qid in question_ids if not states[qid]["attempted"]]
    failed = [qid for qid in question_ids if states[qid]["failed"]]
    due = [
        qid
        for qid in question_ids
        if states[qid]["passed"] and states[qid]["due_for_repetition"]
    ]
    already_placed = set(unseen) | set(failed) | set(due)
    rest = [qid for qid in question_ids if qid not in already_placed]

    due.sort(key=lambda qid: states[qid]["latest_graded_at"] or "")
    rest.sort(key=lambda qid: states[qid]["last_attempted_at"] or "")

    if session_seed:
        seed_int = int(hashlib.md5(session_seed.encode()).hexdigest(), 16) % (2**31)
        rng = random.Random(seed_int)
        rng.shuffle(unseen)

    return [*unseen, *failed, *due, *rest]


def select_daily_queue(
    attempts: list[dict[str, Any]],
    *,
    session_seed: str,
    limit: int = 5,
    questions: Optional[list[dict[str, Any]]] = None,
) -> list[str]:
    """Select a deterministic cross-topic daily queue without duplicates.

    Priority is the product contract: due repetitions, latest failed answers,
    unseen questions, then everything else. The seed only breaks ties inside a
    bucket, so the same user/date always gets the same queue.
    """
    if limit <= 0:
        return []

    available_questions = _question_fixture(questions)
    question_ids = [question["id"] for question in available_questions]
    states = {
        question["id"]: question_state(
            question["id"], attempts, question.get("question_revision_id")
        )
        for question in available_questions
    }

    due = [qid for qid in question_ids if states[qid]["due_for_repetition"]]
    failed = [qid for qid in question_ids if states[qid]["failed"]]
    unseen = [qid for qid in question_ids if not states[qid]["attempted"]]

    used = set(due)
    failed = [qid for qid in failed if qid not in used]
    used.update(failed)
    unseen = [qid for qid in unseen if qid not in used]
    used.update(unseen)
    remaining = [qid for qid in question_ids if qid not in used]

    def seeded_key(question_id: str) -> str:
        return hashlib.sha256(
            f"{session_seed}:{question_id}".encode("utf-8")
        ).hexdigest()

    due.sort(key=lambda qid: (states[qid]["latest_graded_at"] or "", seeded_key(qid)))
    failed.sort(
        key=lambda qid: (
            states[qid]["latest_graded_at"] or "",
            seeded_key(qid),
        ),
        reverse=True,
    )
    unseen.sort(key=seeded_key)
    remaining.sort(
        key=lambda qid: (states[qid]["last_attempted_at"] or "", seeded_key(qid))
    )
    return [*due, *failed, *unseen, *remaining][:limit]


def compute_question_progress(
    question_id: str,
    attempts: list[dict[str, Any]],
    questions: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    question = _question_by_id(question_id, questions)
    if not question:
        raise ValueError(f"unknown ml_technical question_id: {question_id}")
    state = question_state(question_id, attempts, question.get("question_revision_id"))
    return {
        "question_id": question_id,
        "question_revision_id": question.get("question_revision_id"),
        "topic_id": question["topic_id"],
        "unseen": not state["attempted"],
        "attempted": state["attempted"],
        "attempt_count": state["attempt_count"],
        "latest_pass": state["passed"],
        "needs_review": state["latest_status"] == "needs_review",
        "due_for_repetition": state["due_for_repetition"],
        "best_score_percent": state["best_score"],
        "latest_score_percent": state["latest_score"],
        "last_attempted_at": state["last_attempted_at"],
    }


def compute_topic_progress(
    topic_id: str,
    attempts: list[dict[str, Any]],
    questions: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    topic_questions = [
        question
        for question in _question_fixture(questions)
        if question["topic_id"] == topic_id
    ]
    question_progress = [
        compute_question_progress(q["id"], attempts, questions) for q in topic_questions
    ]

    total = len(question_progress)
    unseen = sum(1 for q in question_progress if q["unseen"])
    attempted = sum(1 for q in question_progress if q["attempted"])
    passed = sum(1 for q in question_progress if q["latest_pass"])
    needs_review = sum(1 for q in question_progress if q["needs_review"])
    due = sum(1 for q in question_progress if q["due_for_repetition"])
    scored = [
        q["latest_score_percent"]
        for q in question_progress
        if q["latest_score_percent"] is not None
    ]

    return {
        "topic_id": topic_id,
        "total_questions": total,
        "unseen": unseen,
        "attempted": attempted,
        "passed": passed,
        "needs_review": needs_review,
        "due_for_repetition": due,
        "average_latest_score_percent": round(sum(scored) / len(scored), 1)
        if scored
        else None,
        "questions": question_progress,
    }


def compute_track_progress(
    attempts: list[dict[str, Any]],
    questions: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    topics_progress = [
        compute_topic_progress(topic["id"], attempts, questions)
        for topic in ML_TECHNICAL_TOPICS
    ]
    total_questions = sum(t["total_questions"] for t in topics_progress)
    passed = sum(t["passed"] for t in topics_progress)
    attempted = sum(t["attempted"] for t in topics_progress)
    needs_review = sum(t["needs_review"] for t in topics_progress)
    due = sum(t["due_for_repetition"] for t in topics_progress)
    unseen = sum(t["unseen"] for t in topics_progress)

    return {
        "track_id": "ml_technical",
        "pass_threshold_percent": PASS_THRESHOLD_PERCENT,
        "repetition_due_days": REPETITION_DUE_DAYS,
        "total_questions": total_questions,
        "unseen": unseen,
        "attempted": attempted,
        "passed": passed,
        "needs_review": needs_review,
        "due_for_repetition": due,
        "readiness_percent": round(passed / total_questions * 100, 1)
        if total_questions
        else 0.0,
        "topics": topics_progress,
    }


def deterministic_dont_know_review(question: dict[str, Any]) -> ReviewOutcome:
    missing_points = [point["id"] for point in (question.get("rubric_points") or [])]
    return ReviewOutcome(
        status="graded",
        model_id="deterministic:dont_know",
        rubric_version=question.get("rubric_version"),
        score_percent=0.0,
        covered_points=[],
        missing_points=missing_points,
        incorrect_claims=[],
        feedback="Ответ не дан. Все пункты рубрики отмечены как отсутствующие.",
        follow_up_question=None,
        confidence=1.0,
    )


# ---------------------------------------------------------------------------
# DB-backed service.
# ---------------------------------------------------------------------------


class MlTechnicalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _ensure_user_exists(self, user_id: int) -> None:
        exists = await self.db.scalar(select(User.id).where(User.id == user_id))
        if exists is None:
            raise ValueError(f"user {user_id} not found")

    async def _attempts_for_user(self, user_id: int) -> list[dict[str, Any]]:
        rows = (
            await self.db.scalars(
                select(MlTechnicalAttempt)
                .where(MlTechnicalAttempt.user_id == user_id)
                .order_by(
                    MlTechnicalAttempt.answered_at.desc(), MlTechnicalAttempt.id.desc()
                )
            )
        ).all()
        return [_attempt_dict(row) for row in rows]

    async def get_progress(self, user_id: int) -> dict[str, Any]:
        await self._ensure_user_exists(user_id)
        attempts = await self._attempts_for_user(user_id)
        questions = await MlQuestionBankService(self.db).list_approved_questions()
        return compute_track_progress(attempts, questions)

    async def _approved_questions(self) -> list[dict[str, Any]]:
        return await MlQuestionBankService(self.db).list_approved_questions()

    async def _question_for_revision(self, revision_id: str) -> dict[str, Any]:
        row = await self.db.get(MlQuestionRevision, revision_id)
        if row is None:
            raise ValueError(f"unknown ml question revision_id: {revision_id}")
        return revision_to_question(row)

    async def start_topic_session(
        self,
        user_id: int,
        topic_id: str,
        session_seed: Optional[str] = None,
        *,
        channel: str = SOURCE_CHANNEL_DEFAULT,
        max_questions: Optional[int] = None,
    ) -> dict[str, Any]:
        approved_questions = await self._approved_questions()
        topic_questions = [
            question
            for question in approved_questions
            if question["topic_id"] == topic_id
        ]
        if not topic_questions:
            raise ValueError(f"unknown or empty ml_technical topic_id: {topic_id}")
        if channel not in {"web", "telegram", "mcp"}:
            raise ValueError(f"unsupported ml_technical channel: {channel}")

        await self._ensure_user_exists(user_id)
        attempts = await self._attempts_for_user(user_id)
        ordered_ids = select_topic_queue(
            topic_id,
            attempts,
            session_seed=session_seed,
            questions=approved_questions,
        )
        if max_questions is not None:
            ordered_ids = ordered_ids[: max(0, max_questions)]
        if not ordered_ids:
            raise ValueError(
                f"no ml_technical questions available for topic {topic_id}"
            )

        now = _utcnow()
        session_id = str(uuid4())
        session = MlTechnicalSession(
            id=session_id,
            user_id=user_id,
            mode="topic",
            channel=channel,
            topic_id=topic_id,
            session_seed=session_seed,
            status="active",
            created_at=now,
        )
        questions_by_id = {question["id"]: question for question in topic_questions}
        session.items = [
            MlTechnicalSessionItem(
                id=str(uuid4()),
                user_id=user_id,
                session_id=session_id,
                question_id=qid,
                question_revision_id=questions_by_id[qid]["question_revision_id"],
                position=index,
                status="pending",
                created_at=now,
                updated_at=now,
            )
            for index, qid in enumerate(ordered_ids, start=1)
        ]
        self.db.add(session)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise MlTechnicalConflictError(
                "ml_technical session already exists"
            ) from exc

        return {
            "session_id": session_id,
            "topic_id": topic_id,
            "questions": [
                bank_public_question_view(questions_by_id[qid]) for qid in ordered_ids
            ],
        }

    async def start_daily_session(
        self,
        user_id: int,
        *,
        practice_date: date,
        session_seed: str,
        channel: str = "telegram",
        max_questions: int = 5,
    ) -> dict[str, Any]:
        """Return the idempotent daily session for ``user_id`` and date."""
        if channel != "telegram":
            raise ValueError("daily v0 is available only through telegram")
        if max_questions <= 0 or max_questions > 5:
            raise ValueError("daily session size must be between 1 and 5")

        await self._ensure_user_exists(user_id)
        existing = await self.db.scalar(
            select(MlTechnicalSession).where(
                MlTechnicalSession.user_id == user_id,
                MlTechnicalSession.mode == "daily",
                MlTechnicalSession.practice_date == practice_date,
            )
        )
        if existing is not None:
            return await self.get_session_snapshot(user_id, str(existing.id))

        active = await self.db.scalar(
            select(MlTechnicalSession.id).where(
                MlTechnicalSession.user_id == user_id,
                MlTechnicalSession.channel == "telegram",
                MlTechnicalSession.status == "active",
            )
        )
        if active is not None:
            raise MlTechnicalConflictError("another telegram session is active")

        attempts = await self._attempts_for_user(user_id)
        approved_questions = await self._approved_questions()
        question_ids = select_daily_queue(
            attempts,
            session_seed=session_seed,
            limit=max_questions,
            questions=approved_questions,
        )
        if not question_ids:
            raise ValueError("ml_technical question bank is empty")

        now = _utcnow()
        session_id = str(uuid4())
        session = MlTechnicalSession(
            id=session_id,
            user_id=user_id,
            mode="daily",
            channel=channel,
            topic_id=None,
            session_seed=session_seed,
            practice_date=practice_date,
            status="active",
            created_at=now,
        )
        questions_by_id = {question["id"]: question for question in approved_questions}
        session.items = [
            MlTechnicalSessionItem(
                id=str(uuid4()),
                user_id=user_id,
                session_id=session_id,
                question_id=question_id,
                question_revision_id=questions_by_id[question_id][
                    "question_revision_id"
                ],
                position=position,
                status="pending",
                created_at=now,
                updated_at=now,
            )
            for position, question_id in enumerate(question_ids, start=1)
        ]
        self.db.add(session)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            winner = await self.db.scalar(
                select(MlTechnicalSession).where(
                    MlTechnicalSession.user_id == user_id,
                    MlTechnicalSession.mode == "daily",
                    MlTechnicalSession.practice_date == practice_date,
                )
            )
            if winner is None:
                raise MlTechnicalConflictError(
                    "another telegram session is active"
                ) from exc
            return await self.get_session_snapshot(user_id, str(winner.id))

        return await self.get_session_snapshot(user_id, session_id)

    async def get_session_snapshot(
        self, user_id: int, session_id: str
    ) -> dict[str, Any]:
        session = await self.db.scalar(
            select(MlTechnicalSession).where(
                MlTechnicalSession.user_id == user_id,
                MlTechnicalSession.id == session_id,
            )
        )
        if session is None:
            raise ValueError(f"unknown ml_technical session_id: {session_id}")
        items = (
            await self.db.scalars(
                select(MlTechnicalSessionItem)
                .where(
                    MlTechnicalSessionItem.user_id == user_id,
                    MlTechnicalSessionItem.session_id == session_id,
                )
                .order_by(MlTechnicalSessionItem.position.asc())
            )
        ).all()
        pending = (
            next((item for item in items if item.status == "pending"), None)
            if session.status == "active"
            else None
        )
        question = (
            await self._question_for_revision(str(pending.question_revision_id))
            if pending is not None
            else None
        )
        return {
            "session_id": str(session.id),
            "mode": session.mode,
            "topic_id": session.topic_id,
            "practice_date": session.practice_date.isoformat()
            if session.practice_date
            else None,
            "status": session.status,
            "total_items": len(items),
            "completed_items": sum(
                1 for item in items if item.status in {"answered", "skipped"}
            ),
            "current_item": {
                "item_id": str(pending.id),
                "position": pending.position,
                "question": bank_public_question_view(question),
            }
            if pending is not None and question is not None
            else None,
        }

    async def get_active_telegram_session(
        self, user_id: int
    ) -> Optional[dict[str, Any]]:
        await self._ensure_user_exists(user_id)
        session_id = await self.db.scalar(
            select(MlTechnicalSession.id)
            .where(
                MlTechnicalSession.user_id == user_id,
                MlTechnicalSession.channel == "telegram",
                MlTechnicalSession.status == "active",
            )
            .order_by(MlTechnicalSession.created_at.desc())
            .limit(1)
        )
        if session_id is None:
            return None
        return await self.get_session_snapshot(user_id, str(session_id))

    async def skip_telegram_item(
        self,
        user_id: int,
        *,
        session_id: str,
        item_id: str,
    ) -> dict[str, Any]:
        """Conditionally skip one pending item; stale calls are successful no-ops."""
        if self.db.in_transaction():
            raise MlTechnicalTransactionError(
                "skip_telegram_item requires a clean AsyncSession"
            )
        changed = False
        async with self.db.begin():
            session = await self.db.scalar(
                select(MlTechnicalSession)
                .where(
                    MlTechnicalSession.user_id == user_id,
                    MlTechnicalSession.id == session_id,
                    MlTechnicalSession.channel == "telegram",
                )
                .with_for_update()
            )
            if session is not None and session.status == "active":
                item = await self.db.scalar(
                    select(MlTechnicalSessionItem)
                    .where(
                        MlTechnicalSessionItem.user_id == user_id,
                        MlTechnicalSessionItem.session_id == session_id,
                        MlTechnicalSessionItem.id == item_id,
                    )
                    .with_for_update()
                )
                if item is not None and item.status == "pending":
                    changed = True
                    item.status = "skipped"
                    item.updated_at = _utcnow()
                    await self.db.flush()
                    pending_count = await self.db.scalar(
                        select(func.count())
                        .select_from(MlTechnicalSessionItem)
                        .where(
                            MlTechnicalSessionItem.user_id == user_id,
                            MlTechnicalSessionItem.session_id == session_id,
                            MlTechnicalSessionItem.status == "pending",
                        )
                    )
                    if pending_count == 0:
                        session.status = "completed"
                        session.closed_at = _utcnow()
        snapshot = await self.get_session_snapshot(user_id, session_id)
        return {"changed": changed, "session": snapshot}

    async def cancel_active_telegram_session(self, user_id: int) -> dict[str, Any]:
        """Persistently cancel the active Telegram session, if any."""
        if self.db.in_transaction():
            raise MlTechnicalTransactionError(
                "cancel_active_telegram_session requires a clean AsyncSession"
            )
        cancelled = False
        session_id: Optional[str] = None
        async with self.db.begin():
            session = await self.db.scalar(
                select(MlTechnicalSession)
                .where(
                    MlTechnicalSession.user_id == user_id,
                    MlTechnicalSession.channel == "telegram",
                    MlTechnicalSession.status == "active",
                )
                .with_for_update()
            )
            if session is not None:
                session_id = str(session.id)
                session.status = "cancelled"
                session.closed_at = _utcnow()
                cancelled = True
        return {"cancelled": cancelled, "session_id": session_id}

    async def _load_session_item(
        self,
        *,
        user_id: int,
        session_id: str,
        question_id: str,
        for_update: bool = False,
    ) -> tuple[MlTechnicalSession, MlTechnicalSessionItem]:
        stmt = (
            select(MlTechnicalSession, MlTechnicalSessionItem)
            .join(
                MlTechnicalSessionItem,
                (MlTechnicalSessionItem.session_id == MlTechnicalSession.id)
                & (MlTechnicalSessionItem.user_id == MlTechnicalSession.user_id),
            )
            .where(
                MlTechnicalSession.user_id == user_id,
                MlTechnicalSession.id == session_id,
                MlTechnicalSessionItem.question_id == question_id,
            )
        )
        if for_update:
            # The session row is the serialization point for all answers in a
            # session. Locking only the item rows lets two different final
            # answers both observe another pending item and leave the session
            # active forever.
            stmt = stmt.with_for_update(of=[MlTechnicalSession, MlTechnicalSessionItem])
        row = (await self.db.execute(stmt)).first()
        if row is None:
            raise ValueError(
                f"question {question_id} not found in session {session_id} for user {user_id}"
            )
        return row[0], row[1]

    async def _validate_answer_target(
        self,
        *,
        user_id: int,
        session_id: str,
        question_id: str,
        question: dict[str, Any],
        for_update: bool = False,
    ) -> tuple[MlTechnicalSession, MlTechnicalSessionItem]:
        session, item = await self._load_session_item(
            user_id=user_id,
            session_id=session_id,
            question_id=question_id,
            for_update=for_update,
        )
        if session.status != "active":
            raise MlTechnicalConflictError(f"session {session_id} is not active")
        if session.mode == "topic" and session.topic_id != question.get("topic_id"):
            raise ValueError(
                f"question topic {question.get('topic_id')} does not match session topic {session.topic_id}"
            )
        if item.status != "pending":
            raise MlTechnicalConflictError(
                f"question {question_id} already submitted in session {session_id}"
            )
        return session, item

    async def submit_answer(
        self,
        user_id: int,
        *,
        session_id: str,
        question_id: str,
        answer_text: str,
        answer_language: str = ANSWER_LANGUAGE_DEFAULT,
        answer_kind: str = ANSWER_KIND_NORMAL,
        source_channel: str = SOURCE_CHANNEL_DEFAULT,
        source_event_id: Optional[str] = None,
        llm: Any = None,
    ) -> dict[str, Any]:
        if answer_kind not in {ANSWER_KIND_NORMAL, ANSWER_KIND_DONT_KNOW}:
            raise ValueError(f"unsupported ml_technical answer_kind: {answer_kind}")
        if source_channel not in {"web", "telegram", "mcp"}:
            raise ValueError(
                f"unsupported ml_technical source_channel: {source_channel}"
            )

        # Transaction contract: submit_answer owns its short DB transactions.
        # Rejecting a caller-owned transaction is safer than rolling it back or
        # accidentally keeping it open during the LLM call.
        if self.db.in_transaction():
            raise MlTechnicalTransactionError(
                "submit_answer requires an AsyncSession without an active transaction"
            )

        async with self.db.begin():
            _, target_item = await self._load_session_item(
                user_id=user_id,
                session_id=session_id,
                question_id=question_id,
            )
            question = await self._question_for_revision(
                str(target_item.question_revision_id)
            )
            await self._validate_answer_target(
                user_id=user_id,
                session_id=session_id,
                question_id=question_id,
                question=question,
            )

        if answer_kind == ANSWER_KIND_DONT_KNOW:
            outcome = deterministic_dont_know_review(question)
            persisted_answer = answer_text or "[dont_know]"
        else:
            outcome = await review_technical_answer(
                question=question,
                answer_text=answer_text,
                answer_language=answer_language,
                llm=llm,
            )
            persisted_answer = answer_text

        attempt_id = str(uuid4())
        now = _utcnow()
        review_payload = outcome.to_dict()

        try:
            async with self.db.begin():
                session, item = await self._validate_answer_target(
                    user_id=user_id,
                    session_id=session_id,
                    question_id=question_id,
                    question=question,
                    for_update=True,
                )
                if str(item.question_revision_id) != str(
                    question.get("question_revision_id")
                ):
                    raise MlTechnicalConflictError(
                        "session question revision changed during answer review"
                    )
                insert_stmt = (
                    pg_insert(MlTechnicalAttempt)
                    .values(
                        id=attempt_id,
                        user_id=user_id,
                        session_id=session_id,
                        question_id=question_id,
                        question_revision_id=item.question_revision_id,
                        topic_id=question["topic_id"],
                        answer_kind=answer_kind,
                        answer_language=answer_language,
                        raw_answer=persisted_answer,
                        source_channel=source_channel,
                        source_event_id=source_event_id,
                        answered_at=now,
                        provenance_id=question.get("provenance_id"),
                        review=review_payload,
                    )
                    .on_conflict_do_nothing()
                    .returning(MlTechnicalAttempt.id)
                )
                inserted_id = await self.db.scalar(insert_stmt)
                if inserted_id is None:
                    raise MlTechnicalConflictError("duplicate ml_technical attempt")

                item.status = "answered"
                item.updated_at = now
                await self.db.flush()

                pending_count = await self.db.scalar(
                    select(func.count())
                    .select_from(MlTechnicalSessionItem)
                    .where(
                        MlTechnicalSessionItem.user_id == user_id,
                        MlTechnicalSessionItem.session_id == session_id,
                        MlTechnicalSessionItem.status == "pending",
                    )
                )
                if pending_count == 0:
                    session.status = "completed"
                    session.closed_at = now
        except MlTechnicalConflictError:
            raise
        except IntegrityError as exc:
            raise MlTechnicalConflictError("duplicate ml_technical attempt") from exc

        async with self.db.begin():
            attempts = await self._attempts_for_user(user_id)
            next_item = await self._next_question_in_session(
                user_id=user_id, session_id=session_id
            )
        next_question = (
            await self._question_for_revision(str(next_item.question_revision_id))
            if next_item
            else None
        )

        approved_questions = await self._approved_questions()

        review_response = self._review_response(question, outcome)
        return {
            "attempt_id": attempt_id,
            "review": review_response,
            "reference_explanation_ru": question["reference_explanation_ru"],
            "next_question": bank_public_question_view(next_question)
            if next_question
            else None,
            "question_progress": compute_question_progress(
                question_id, attempts, approved_questions
            ),
            "topic_progress": compute_topic_progress(
                question["topic_id"], attempts, approved_questions
            ),
        }

    def _review_response(
        self, question: dict[str, Any], outcome: ReviewOutcome
    ) -> dict[str, Any]:
        rubric_by_id = {
            p["id"]: p["point_ru"] for p in (question.get("rubric_points") or [])
        }
        review_payload = outcome.to_dict()
        review_payload["covered_points_text"] = [
            rubric_by_id.get(pid, pid) for pid in outcome.covered_points
        ]
        review_payload["missing_points_text"] = [
            rubric_by_id.get(pid, pid) for pid in outcome.missing_points
        ]
        return review_payload

    async def _next_question_in_session(
        self, *, user_id: int, session_id: str
    ) -> Optional[MlTechnicalSessionItem]:
        row = await self.db.scalar(
            select(MlTechnicalSessionItem)
            .where(
                MlTechnicalSessionItem.user_id == user_id,
                MlTechnicalSessionItem.session_id == session_id,
                MlTechnicalSessionItem.status == "pending",
            )
            .order_by(MlTechnicalSessionItem.position.asc())
            .limit(1)
        )
        return row

    async def get_recent_attempts(
        self,
        user_id: int,
        *,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        await self._ensure_user_exists(user_id)
        stmt = (
            select(MlTechnicalAttempt)
            .where(MlTechnicalAttempt.user_id == user_id)
            .order_by(
                MlTechnicalAttempt.answered_at.desc(), MlTechnicalAttempt.id.desc()
            )
            .limit(limit)
        )
        if status:
            stmt = stmt.where(MlTechnicalAttempt.review["status"].astext == status)

        attempts = (await self.db.scalars(stmt)).all()
        attempt_ids = [attempt.id for attempt in attempts]
        external_reviews_by_attempt: dict[str, list[dict[str, Any]]] = {
            str(attempt_id): [] for attempt_id in attempt_ids
        }
        if attempt_ids:
            reviews = (
                await self.db.scalars(
                    select(MlTechnicalExternalReview)
                    .where(
                        MlTechnicalExternalReview.user_id == user_id,
                        MlTechnicalExternalReview.attempt_id.in_(attempt_ids),
                    )
                    .order_by(
                        MlTechnicalExternalReview.created_at.desc(),
                        MlTechnicalExternalReview.id.desc(),
                    )
                )
            ).all()
            for review in reviews:
                external_reviews_by_attempt[str(review.attempt_id)].append(
                    _external_review_dict(review)
                )

        revision_ids = {attempt.question_revision_id for attempt in attempts}
        revisions = (
            (
                await self.db.scalars(
                    select(MlQuestionRevision).where(
                        MlQuestionRevision.id.in_(revision_ids)
                    )
                )
            ).all()
            if revision_ids
            else []
        )
        questions_by_revision = {
            str(revision.id): revision_to_question(revision) for revision in revisions
        }

        enriched: list[dict[str, Any]] = []
        for attempt_row in attempts:
            attempt = _attempt_dict(attempt_row)
            question = questions_by_revision.get(attempt["question_revision_id"], {})
            enriched.append(
                {
                    **attempt,
                    "question_ru": question.get("question_ru"),
                    "rubric_points": question.get("rubric_points"),
                    "reference_explanation_ru": question.get(
                        "reference_explanation_ru"
                    ),
                    "rubric_version": question.get("rubric_version"),
                    "external_reviews": external_reviews_by_attempt.get(
                        attempt["attempt_id"], []
                    ),
                }
            )
        return enriched

    async def append_external_review(
        self,
        user_id: int,
        *,
        attempt_id: str,
        reviewer: str,
        verdict: str,
        notes: Optional[str] = None,
    ) -> dict[str, Any]:
        attempt_exists = await self.db.scalar(
            select(MlTechnicalAttempt.id).where(
                MlTechnicalAttempt.user_id == user_id,
                MlTechnicalAttempt.id == attempt_id,
            )
        )
        if attempt_exists is None:
            raise ValueError(f"unknown ml_technical attempt_id: {attempt_id}")

        external_review = MlTechnicalExternalReview(
            id=str(uuid4()),
            user_id=user_id,
            attempt_id=attempt_id,
            reviewer=reviewer,
            verdict=verdict,
            notes=notes,
            created_at=_utcnow(),
        )
        self.db.add(external_review)
        await self.db.commit()
        return _external_review_dict(external_review)
