"""PostgreSQL-only persistence regressions for ml_technical Slice A.

These tests intentionally do not use SQLite. Set `ML_TECHNICAL_PG_TEST_URL`
to a migrated PostgreSQL test database to run them.
"""

from __future__ import annotations

import asyncio
import os
from datetime import date
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.core_tables import User
from app.models.ml_technical import (
    MlQuestionRevision,
    MlTechnicalAttempt,
    MlTechnicalExternalReview,
    MlTechnicalSession,
    MlTechnicalSessionItem,
)
from app.services.ml_technical_service import (
    ANSWER_KIND_DONT_KNOW,
    MlTechnicalConflictError,
    MlTechnicalService,
    MlTechnicalTransactionError,
)


TEST_DATABASE_URL = os.getenv("ML_TECHNICAL_PG_TEST_URL")


@pytest_asyncio.fixture()
async def pg_session_maker():
    if not TEST_DATABASE_URL:
        pytest.skip(
            "ML_TECHNICAL_PG_TEST_URL is not configured; PostgreSQL-only checks skipped"
        )
    if "postgresql" not in TEST_DATABASE_URL:
        pytest.skip(
            "ML_TECHNICAL_PG_TEST_URL must point to PostgreSQL; SQLite fallback is not allowed"
        )

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1 from ml_technical_attempts limit 0"))
    except (OperationalError, ProgrammingError) as exc:
        await engine.dispose()
        pytest.skip(
            f"PostgreSQL ml_technical schema unavailable: {exc.__class__.__name__}"
        )

    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


async def _create_user(db: AsyncSession) -> int:
    username = f"mltech_test_{uuid4().hex}"
    user_id = await db.scalar(insert(User).values(username=username).returning(User.id))
    await db.commit()
    return int(user_id)


async def _create_session(
    db: AsyncSession,
    user_id: int,
    question_ids: list[str],
    *,
    mode: str = "topic",
    status: str = "active",
) -> str:
    session_id = str(uuid4())
    await db.execute(
        insert(MlTechnicalSession).values(
            id=session_id,
            user_id=user_id,
            mode=mode,
            channel="telegram" if mode == "daily" else "web",
            topic_id=None if mode == "daily" else "dl_training",
            practice_date=date.today() if mode == "daily" else None,
            status=status,
            created_at=text("now()"),
        )
    )
    for position, question_id in enumerate(question_ids, start=1):
        question_revision_id = await db.scalar(
            select(MlQuestionRevision.id).where(
                MlQuestionRevision.question_key == question_id,
                MlQuestionRevision.status == "approved",
            )
        )
        if question_revision_id is None:
            raise AssertionError(
                f"approved test question revision not found: {question_id}"
            )
        await db.execute(
            insert(MlTechnicalSessionItem).values(
                id=str(uuid4()),
                user_id=user_id,
                session_id=session_id,
                question_id=question_id,
                question_revision_id=question_revision_id,
                position=position,
                status="pending",
                created_at=text("now()"),
                updated_at=text("now()"),
            )
        )
    await db.commit()
    return session_id


@pytest.mark.integration
async def test_attempt_keeps_exact_session_question_revision(pg_session_maker):
    async with pg_session_maker() as setup_db:
        user_id = await _create_user(setup_db)
        session_id = await _create_session(setup_db, user_id, ["mltech_001"])
        session_revision_id = await setup_db.scalar(
            select(MlTechnicalSessionItem.question_revision_id).where(
                MlTechnicalSessionItem.session_id == session_id,
                MlTechnicalSessionItem.question_id == "mltech_001",
            )
        )

    try:
        async with pg_session_maker() as db:
            result = await MlTechnicalService(db).submit_answer(
                user_id,
                session_id=session_id,
                question_id="mltech_001",
                answer_text="",
                answer_kind=ANSWER_KIND_DONT_KNOW,
            )
            attempt_revision_id = await db.scalar(
                select(MlTechnicalAttempt.question_revision_id).where(
                    MlTechnicalAttempt.id == result["attempt_id"]
                )
            )
            recent = await MlTechnicalService(db).get_recent_attempts(user_id, limit=1)

        assert str(attempt_revision_id) == str(session_revision_id)
        assert recent[0]["question_revision_id"] == str(session_revision_id)
        assert recent[0]["question_ru"]
        assert recent[0]["rubric_points"]
    finally:
        async with pg_session_maker() as db:
            await _cleanup(db, user_id)


async def _cleanup(db: AsyncSession, user_id: int) -> None:
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()


@pytest.mark.integration
async def test_concurrent_different_questions_both_persist(pg_session_maker):
    async with pg_session_maker() as setup_db:
        user_id = await _create_user(setup_db)
        session_id = await _create_session(
            setup_db, user_id, ["mltech_001", "mltech_002"]
        )

    async def submit(question_id: str):
        async with pg_session_maker() as db:
            return await MlTechnicalService(db).submit_answer(
                user_id,
                session_id=session_id,
                question_id=question_id,
                answer_text="",
                answer_kind=ANSWER_KIND_DONT_KNOW,
            )

    try:
        results = await asyncio.gather(submit("mltech_001"), submit("mltech_002"))
        async with pg_session_maker() as db:
            attempts = await db.scalar(
                select(func.count())
                .select_from(MlTechnicalAttempt)
                .where(MlTechnicalAttempt.user_id == user_id)
            )
            session_status = await db.scalar(
                select(MlTechnicalSession.status).where(
                    MlTechnicalSession.id == session_id
                )
            )
        assert len(results) == 2
        assert attempts == 2
        assert session_status == "completed"
    finally:
        async with pg_session_maker() as db:
            await _cleanup(db, user_id)


@pytest.mark.integration
async def test_concurrent_today_calls_share_one_active_telegram_session(
    pg_session_maker,
):
    async with pg_session_maker() as setup_db:
        user_id = await _create_user(setup_db)

    async def start_today():
        async with pg_session_maker() as db:
            result = await MlTechnicalService(db).start_daily_session(
                user_id,
                practice_date=date.today(),
                session_seed=f"{user_id}:{date.today().isoformat()}",
            )
            return result["session_id"]

    try:
        session_ids = await asyncio.gather(start_today(), start_today())
        async with pg_session_maker() as db:
            active_count = await db.scalar(
                select(func.count())
                .select_from(MlTechnicalSession)
                .where(
                    MlTechnicalSession.user_id == user_id,
                    MlTechnicalSession.channel == "telegram",
                    MlTechnicalSession.status == "active",
                )
            )
        assert session_ids[0] == session_ids[1]
        assert active_count == 1
    finally:
        async with pg_session_maker() as db:
            await _cleanup(db, user_id)


@pytest.mark.integration
async def test_concurrent_today_and_slice_yield_one_controlled_conflict(
    pg_session_maker,
):
    async with pg_session_maker() as setup_db:
        user_id = await _create_user(setup_db)

    async def start_today():
        async with pg_session_maker() as db:
            try:
                await MlTechnicalService(db).start_daily_session(
                    user_id,
                    practice_date=date.today(),
                    session_seed=f"{user_id}:{date.today().isoformat()}",
                )
                return "ok"
            except MlTechnicalConflictError:
                return "conflict"

    async def start_slice():
        async with pg_session_maker() as db:
            try:
                await MlTechnicalService(db).start_topic_session(
                    user_id,
                    "dl_training",
                    f"telegram:{user_id}:dl_training",
                    channel="telegram",
                    max_questions=5,
                )
                return "ok"
            except MlTechnicalConflictError:
                return "conflict"

    try:
        outcomes = await asyncio.gather(start_today(), start_slice())
        async with pg_session_maker() as db:
            active_count = await db.scalar(
                select(func.count())
                .select_from(MlTechnicalSession)
                .where(
                    MlTechnicalSession.user_id == user_id,
                    MlTechnicalSession.channel == "telegram",
                    MlTechnicalSession.status == "active",
                )
            )
        assert sorted(outcomes) == ["conflict", "ok"]
        assert active_count == 1
    finally:
        async with pg_session_maker() as db:
            await _cleanup(db, user_id)


@pytest.mark.integration
async def test_cancelled_daily_snapshot_never_exposes_pending_question(
    pg_session_maker,
):
    async with pg_session_maker() as setup_db:
        user_id = await _create_user(setup_db)
        session_id = await _create_session(
            setup_db,
            user_id,
            ["mltech_001"],
            mode="daily",
            status="cancelled",
        )

    try:
        async with pg_session_maker() as db:
            snapshot = await MlTechnicalService(db).start_daily_session(
                user_id,
                practice_date=date.today(),
                session_seed=f"{user_id}:{date.today().isoformat()}",
            )
        assert snapshot["session_id"] == session_id
        assert snapshot["status"] == "cancelled"
        assert snapshot["current_item"] is None
    finally:
        async with pg_session_maker() as db:
            await _cleanup(db, user_id)


@pytest.mark.integration
async def test_concurrent_duplicate_question_yields_one_conflict(pg_session_maker):
    async with pg_session_maker() as setup_db:
        user_id = await _create_user(setup_db)
        session_id = await _create_session(setup_db, user_id, ["mltech_001"])

    async def submit():
        async with pg_session_maker() as db:
            try:
                await MlTechnicalService(db).submit_answer(
                    user_id,
                    session_id=session_id,
                    question_id="mltech_001",
                    answer_text="",
                    answer_kind=ANSWER_KIND_DONT_KNOW,
                )
                return "ok"
            except MlTechnicalConflictError:
                return "conflict"

    try:
        outcomes = await asyncio.gather(submit(), submit())
        async with pg_session_maker() as db:
            attempts = await db.scalar(
                select(func.count())
                .select_from(MlTechnicalAttempt)
                .where(MlTechnicalAttempt.user_id == user_id)
            )
        assert sorted(outcomes) == ["conflict", "ok"]
        assert attempts == 1
    finally:
        async with pg_session_maker() as db:
            await _cleanup(db, user_id)


@pytest.mark.integration
async def test_cross_user_session_ownership_is_rejected(pg_session_maker):
    async with pg_session_maker() as setup_db:
        owner_id = await _create_user(setup_db)
        other_id = await _create_user(setup_db)
        session_id = await _create_session(setup_db, owner_id, ["mltech_001"])

    try:
        async with pg_session_maker() as db:
            with pytest.raises(ValueError):
                await MlTechnicalService(db).submit_answer(
                    other_id,
                    session_id=session_id,
                    question_id="mltech_001",
                    answer_text="",
                    answer_kind=ANSWER_KIND_DONT_KNOW,
                )
    finally:
        async with pg_session_maker() as db:
            await _cleanup(db, owner_id)
            await _cleanup(db, other_id)


@pytest.mark.integration
async def test_external_reviews_are_append_only(pg_session_maker):
    async with pg_session_maker() as setup_db:
        user_id = await _create_user(setup_db)
        session_id = await _create_session(setup_db, user_id, ["mltech_001"])
        result = await MlTechnicalService(setup_db).submit_answer(
            user_id,
            session_id=session_id,
            question_id="mltech_001",
            answer_text="",
            answer_kind=ANSWER_KIND_DONT_KNOW,
        )
        attempt_id = result["attempt_id"]

    try:
        async with pg_session_maker() as db:
            first = await MlTechnicalService(db).append_external_review(
                user_id,
                attempt_id=attempt_id,
                reviewer="codex",
                verdict="agree",
                notes="first review",
            )
            second = await MlTechnicalService(db).append_external_review(
                user_id,
                attempt_id=attempt_id,
                reviewer="sonnet",
                verdict="score_too_high",
                notes="second review",
            )
            rows = (
                await db.scalars(
                    select(MlTechnicalExternalReview).where(
                        MlTechnicalExternalReview.user_id == user_id,
                        MlTechnicalExternalReview.attempt_id == attempt_id,
                    )
                )
            ).all()

        assert first["review_id"] != second["review_id"]
        assert len(rows) == 2
    finally:
        async with pg_session_maker() as db:
            await _cleanup(db, user_id)


@pytest.mark.integration
async def test_cancelled_session_rejects_pending_answer(pg_session_maker):
    async with pg_session_maker() as setup_db:
        user_id = await _create_user(setup_db)
        session_id = await _create_session(
            setup_db,
            user_id,
            ["mltech_001"],
            status="cancelled",
        )

    try:
        async with pg_session_maker() as db:
            with pytest.raises(MlTechnicalConflictError, match="is not active"):
                await MlTechnicalService(db).submit_answer(
                    user_id,
                    session_id=session_id,
                    question_id="mltech_001",
                    answer_text="",
                    answer_kind=ANSWER_KIND_DONT_KNOW,
                )
            attempt_count = await db.scalar(
                select(func.count())
                .select_from(MlTechnicalAttempt)
                .where(MlTechnicalAttempt.user_id == user_id)
            )
        assert attempt_count == 0
    finally:
        async with pg_session_maker() as db:
            await _cleanup(db, user_id)


@pytest.mark.integration
async def test_daily_session_accepts_question_from_any_topic(pg_session_maker):
    async with pg_session_maker() as setup_db:
        user_id = await _create_user(setup_db)
        session_id = await _create_session(
            setup_db,
            user_id,
            ["mltech_004"],
            mode="daily",
        )

    try:
        async with pg_session_maker() as db:
            result = await MlTechnicalService(db).submit_answer(
                user_id,
                session_id=session_id,
                question_id="mltech_004",
                answer_text="",
                answer_kind=ANSWER_KIND_DONT_KNOW,
                source_channel="telegram",
            )
            session_status = await db.scalar(
                select(MlTechnicalSession.status).where(
                    MlTechnicalSession.id == session_id
                )
            )

        assert result["attempt_id"]
        assert session_status == "completed"
    finally:
        async with pg_session_maker() as db:
            await _cleanup(db, user_id)


@pytest.mark.integration
async def test_submit_answer_does_not_rollback_caller_transaction(pg_session_maker):
    username = f"mltech_transaction_owner_{uuid4().hex}"

    async with pg_session_maker() as db:
        async with db.begin():
            pending_user = User(username=username)
            db.add(pending_user)
            await db.flush()

            with pytest.raises(MlTechnicalTransactionError):
                await MlTechnicalService(db).submit_answer(
                    int(pending_user.id),
                    session_id=str(uuid4()),
                    question_id="mltech_001",
                    answer_text="",
                    answer_kind=ANSWER_KIND_DONT_KNOW,
                )

            assert db.in_transaction()

        persisted_user_id = await db.scalar(
            select(User.id).where(User.username == username)
        )
        assert persisted_user_id == pending_user.id
        await _cleanup(db, int(pending_user.id))
