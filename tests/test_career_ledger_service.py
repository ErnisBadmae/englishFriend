from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.career import (
    CareerApplication,
    CareerApplicationEvent,
    CareerVacancySnapshot,
)
from app.models.core_tables import User
from app.services.career_ledger_service import (
    ALLOWED_TRANSITIONS,
    STATUS_APPLIED,
    STATUS_OFFER,
    STATUS_REJECTED,
    STATUS_SCREENING,
    STATUS_TECHNICAL,
    STATUS_WITHDRAWN,
    CareerLedgerConflictError,
    CareerLedgerError,
    CareerLedgerService,
    CareerLedgerTransitionError,
)

TEST_DATABASE_URL = os.getenv("ML_TECHNICAL_PG_TEST_URL")


# ---------------------------------------------------------------------------
# Pure transition-map and validation tests - no DB access.
# ---------------------------------------------------------------------------


def test_transition_map_allows_only_the_conservative_funnel():
    assert ALLOWED_TRANSITIONS[STATUS_APPLIED] == frozenset(
        {STATUS_SCREENING, STATUS_TECHNICAL, STATUS_REJECTED, STATUS_WITHDRAWN}
    )
    assert ALLOWED_TRANSITIONS[STATUS_SCREENING] == frozenset(
        {STATUS_TECHNICAL, STATUS_REJECTED, STATUS_WITHDRAWN}
    )
    assert ALLOWED_TRANSITIONS[STATUS_TECHNICAL] == frozenset(
        {STATUS_OFFER, STATUS_REJECTED, STATUS_WITHDRAWN}
    )
    assert ALLOWED_TRANSITIONS[STATUS_OFFER] == frozenset({STATUS_WITHDRAWN})
    assert ALLOWED_TRANSITIONS[STATUS_REJECTED] == frozenset()
    assert ALLOWED_TRANSITIONS[STATUS_WITHDRAWN] == frozenset()


# ---------------------------------------------------------------------------
# PostgreSQL-backed integration tests. Skipped without a migrated test DB.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def pg_session_maker():
    if not TEST_DATABASE_URL or "postgresql" not in TEST_DATABASE_URL:
        pytest.skip("ML_TECHNICAL_PG_TEST_URL is not configured for PostgreSQL")
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1 from career_applications limit 0"))
    except (OperationalError, ProgrammingError) as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL migration 016 unavailable: {exc.__class__.__name__}")
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


async def _create_user(db: AsyncSession) -> int:
    user_id = await db.scalar(
        insert(User)
        .values(username=f"career_ledger_test_{uuid4().hex}")
        .returning(User.id)
    )
    await db.commit()
    return int(user_id)


@pytest.mark.integration
async def test_applied_command_creates_one_snapshot_application_and_event(
    pg_session_maker,
):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerLedgerService(db)

        result = await service.record_manual_application(
            user_id,
            company="Acme",
            role_title="ML Engineer",
            url="https://acme.example/jobs/42",
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="123456",
        )

        assert result["created"] is True
        assert result["application"]["status"] == STATUS_APPLIED
        snapshot_count = await db.scalar(
            select(func.count(CareerVacancySnapshot.id)).where(
                CareerVacancySnapshot.user_id == user_id
            )
        )
        application_count = await db.scalar(
            select(func.count(CareerApplication.id)).where(
                CareerApplication.user_id == user_id
            )
        )
        event_count = await db.scalar(
            select(func.count(CareerApplicationEvent.id)).where(
                CareerApplicationEvent.user_id == user_id
            )
        )
        assert (snapshot_count, application_count, event_count) == (1, 1, 1)


@pytest.mark.integration
async def test_replaying_same_idempotency_key_creates_no_additional_rows(
    pg_session_maker,
):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerLedgerService(db)
        idempotency_key = f"telegram:{uuid4().hex}"

        first = await service.record_manual_application(
            user_id,
            company="Acme",
            role_title="ML Engineer",
            url=None,
            idempotency_key=idempotency_key,
            actor_id="123456",
        )
        second = await service.record_manual_application(
            user_id,
            company="Acme",
            role_title="ML Engineer",
            url=None,
            idempotency_key=idempotency_key,
            actor_id="123456",
        )

        assert first["application"]["application_id"] == second["application"][
            "application_id"
        ]
        assert second["created"] is False
        application_count = await db.scalar(
            select(func.count(CareerApplication.id)).where(
                CareerApplication.user_id == user_id
            )
        )
        event_count = await db.scalar(
            select(func.count(CareerApplicationEvent.id)).where(
                CareerApplicationEvent.user_id == user_id
            )
        )
        assert (application_count, event_count) == (1, 1)


@pytest.mark.integration
async def test_applications_and_summary_read_the_same_service_truth(pg_session_maker):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerLedgerService(db)
        await service.record_manual_application(
            user_id,
            company="Acme",
            role_title="ML Engineer",
            url=None,
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="123456",
        )

        summary = await service.get_pipeline_summary(user_id)
        applications = await service.list_applications(user_id)

        assert summary["total"] == 1
        assert summary["by_status"] == {STATUS_APPLIED: 1}
        assert len(applications) == 1
        assert applications[0]["status"] == STATUS_APPLIED


@pytest.mark.integration
async def test_user_isolation_across_two_owners(pg_session_maker):
    async with pg_session_maker() as db:
        user_a = await _create_user(db)
        user_b = await _create_user(db)
        service = CareerLedgerService(db)
        await service.record_manual_application(
            user_a,
            company="Acme",
            role_title="ML Engineer",
            url=None,
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="1",
        )

        summary_a = await service.get_pipeline_summary(user_a)
        summary_b = await service.get_pipeline_summary(user_b)

        assert summary_a["total"] == 1
        assert summary_b["total"] == 0
        with pytest.raises(CareerLedgerError):
            await service.record_manual_application(
                999_999_999,
                company="Acme",
                role_title="ML Engineer",
                url=None,
                idempotency_key=f"telegram:{uuid4().hex}",
                actor_id="1",
            )


@pytest.mark.integration
async def test_allowed_transition_appends_event_and_updates_status(pg_session_maker):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerLedgerService(db)
        created = await service.record_manual_application(
            user_id,
            company="Acme",
            role_title="ML Engineer",
            url=None,
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="1",
        )
        application_id = created["application"]["application_id"]

        result = await service.append_application_event(
            user_id,
            application_id=application_id,
            to_status=STATUS_SCREENING,
            actor_id="1",
        )

        assert result["application"]["status"] == STATUS_SCREENING
        assert result["event"]["from_status"] == STATUS_APPLIED
        assert result["event"]["to_status"] == STATUS_SCREENING


@pytest.mark.integration
async def test_concurrent_transition_replay_is_serialized_and_idempotent(
    pg_session_maker,
):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        created = await CareerLedgerService(db).record_manual_application(
            user_id,
            company="Acme",
            role_title="ML Engineer",
            url=None,
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="1",
        )
        application_id = created["application"]["application_id"]

    transition_key = f"telegram:{uuid4().hex}"

    async def transition_once():
        async with pg_session_maker() as db:
            return await CareerLedgerService(db).append_application_event(
                user_id,
                application_id=application_id,
                to_status=STATUS_SCREENING,
                actor_id="1",
                idempotency_key=transition_key,
            )

    first, second = await asyncio.gather(transition_once(), transition_once())

    assert sorted((first["created"], second["created"])) == [False, True]
    assert first["application"]["status"] == STATUS_SCREENING
    assert second["application"]["status"] == STATUS_SCREENING
    async with pg_session_maker() as db:
        event_count = await db.scalar(
            select(func.count(CareerApplicationEvent.id)).where(
                CareerApplicationEvent.user_id == user_id,
                CareerApplicationEvent.application_id == application_id,
            )
        )
        assert event_count == 2


@pytest.mark.integration
async def test_forbidden_transition_fails_closed(pg_session_maker):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerLedgerService(db)
        created = await service.record_manual_application(
            user_id,
            company="Acme",
            role_title="ML Engineer",
            url=None,
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="1",
        )
        application_id = created["application"]["application_id"]

        with pytest.raises(CareerLedgerTransitionError):
            await service.append_application_event(
                user_id,
                application_id=application_id,
                to_status=STATUS_OFFER,
                actor_id="1",
            )


@pytest.mark.integration
async def test_bounded_fields_reject_oversized_company(pg_session_maker):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerLedgerService(db)
        with pytest.raises(CareerLedgerError):
            await service.record_manual_application(
                user_id,
                company="x" * 300,
                role_title="ML Engineer",
                url=None,
                idempotency_key=f"telegram:{uuid4().hex}",
                actor_id="1",
            )


@pytest.mark.integration
async def test_context_hash_is_stable_then_changes_after_new_event(pg_session_maker):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerLedgerService(db)
        created = await service.record_manual_application(
            user_id,
            company="Acme",
            role_title="ML Engineer",
            url=None,
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="1",
        )
        application_id = created["application"]["application_id"]

        first = await service.get_review_context(user_id)
        second = await service.get_review_context(user_id)
        assert first["context_hash"] == second["context_hash"]

        await service.append_application_event(
            user_id,
            application_id=application_id,
            to_status=STATUS_SCREENING,
            actor_id="1",
        )
        third = await service.get_review_context(user_id)
        assert third["context_hash"] != first["context_hash"]


@pytest.mark.integration
async def test_reapplying_migration_016_creates_no_duplicate_objects(pg_session_maker):
    async with pg_session_maker() as db:
        before = await db.scalar(
            text(
                "select count(*) from pg_trigger "
                "where tgname = 'career_application_event_append_only_guard_trigger'"
            )
        )
        assert before == 1
