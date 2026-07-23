from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.career import (
    CareerApplication,
    CareerApplicationEvent,
    CareerTelegramPendingInput,
    CareerVacancySnapshot,
)
from app.models.core_tables import User
from app.services.career_ledger_service import (
    ALLOWED_TRANSITIONS,
    INTENT_CAREER_ADD,
    INTENT_CAREER_FEEDBACK,
    INTENT_CAREER_MANUAL_LEAD,
    INTENT_CAREER_NEXT_ACTION,
    PENDING_INPUT_TTL_MINUTES,
    STATUS_APPLIED,
    STATUS_OFFER,
    STATUS_REJECTED,
    STATUS_SCREENING,
    STATUS_TECHNICAL,
    STATUS_WITHDRAWN,
    VALID_PENDING_INTENTS,
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


def test_pending_intent_vocabulary_and_ttl():
    assert VALID_PENDING_INTENTS == {
        INTENT_CAREER_ADD,
        INTENT_CAREER_NEXT_ACTION,
        INTENT_CAREER_MANUAL_LEAD,
        INTENT_CAREER_FEEDBACK,
    }
    assert PENDING_INPUT_TTL_MINUTES == 30


async def test_set_pending_intent_rejects_unknown_intent():
    service = CareerLedgerService(db=None)  # not reached before validation
    with pytest.raises(CareerLedgerError):
        await service.set_pending_intent(1, intent="bogus")


async def test_set_pending_intent_rejects_next_action_without_application_id():
    service = CareerLedgerService(db=None)
    with pytest.raises(CareerLedgerError):
        await service.set_pending_intent(1, intent=INTENT_CAREER_NEXT_ACTION)


async def test_set_pending_intent_rejects_career_add_with_application_id():
    service = CareerLedgerService(db=None)
    with pytest.raises(CareerLedgerError):
        await service.set_pending_intent(
            1, intent=INTENT_CAREER_ADD, application_id=str(uuid4())
        )


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

        assert (
            first["application"]["application_id"]
            == second["application"]["application_id"]
        )
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


@pytest.mark.integration
async def test_set_next_action_updates_fields_and_appends_note_event(
    pg_session_maker,
):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerLedgerService(db)

        created = await service.record_manual_application(
            user_id,
            company="Globex",
            role_title="SDE",
            url=None,
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="1",
        )
        application_id = created["application"]["application_id"]

        due = date(2026, 8, 1)
        idempotency_key = f"next_action:{uuid4().hex}"

        result = await service.set_next_action(
            user_id,
            application_id=application_id,
            next_action="Schedule coding interview",
            next_action_due_date=due,
            idempotency_key=idempotency_key,
            actor_id="1",
        )

        assert result["created"] is True
        assert result["application"]["next_action"] == "Schedule coding interview"
        assert result["application"]["next_action_due_date"] == due.isoformat()
        events = (
            await db.scalars(
                select(CareerApplicationEvent).where(
                    CareerApplicationEvent.user_id == user_id,
                    CareerApplicationEvent.application_id == application_id,
                )
            )
        ).all()
        note_events = [e for e in events if e.event_type == "note"]
        assert len(note_events) == 1
        meta = note_events[0].event_metadata or {}
        assert meta["next_action"] == "Schedule coding interview"
        assert meta["next_action_due_date"] == due.isoformat()


@pytest.mark.integration
async def test_set_next_action_replay_creates_no_second_event(
    pg_session_maker,
):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerLedgerService(db)

        created = await service.record_manual_application(
            user_id,
            company="Initech",
            role_title="PM",
            url=None,
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="1",
        )
        application_id = created["application"]["application_id"]

        idempotency_key = f"next_action:{uuid4().hex}"
        due = date(2026, 9, 15)

        first = await service.set_next_action(
            user_id,
            application_id=application_id,
            next_action="Send offer letter",
            next_action_due_date=due,
            idempotency_key=idempotency_key,
            actor_id="1",
        )
        second = await service.set_next_action(
            user_id,
            application_id=application_id,
            next_action="Send offer letter",
            next_action_due_date=due,
            idempotency_key=idempotency_key,
            actor_id="1",
        )

        assert first["created"] is True
        assert second["created"] is False
        events = (
            await db.scalars(
                select(CareerApplicationEvent).where(
                    CareerApplicationEvent.user_id == user_id,
                    CareerApplicationEvent.application_id == application_id,
                )
            )
        ).all()
        note_events = [e for e in events if e.event_type == "note"]
        assert len(note_events) == 1


# ---------------------------------------------------------------------------
# Career Telegram pending input (migration 017). Skipped without a migrated
# test DB - same isolated-DB convention as the fixture above.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def pending_pg_session_maker():
    if not TEST_DATABASE_URL or "postgresql" not in TEST_DATABASE_URL:
        pytest.skip("ML_TECHNICAL_PG_TEST_URL is not configured for PostgreSQL")
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(
                text("select 1 from career_telegram_pending_inputs limit 0")
            )
    except (OperationalError, ProgrammingError) as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL migration 017 unavailable: {exc.__class__.__name__}")
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


@pytest.mark.integration
async def test_reapplying_migration_017_creates_no_duplicate_objects(
    pending_pg_session_maker,
):
    async with pending_pg_session_maker() as db:
        policy_count = await db.scalar(
            text(
                "select count(*) from pg_policies "
                "where tablename = 'career_telegram_pending_inputs' "
                "and policyname = 'career_telegram_pending_inputs_isolation'"
            )
        )
        assert policy_count == 1


@pytest.mark.integration
async def test_replacing_one_pending_intent_with_another_works(
    pending_pg_session_maker,
):
    async with pending_pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerLedgerService(db)

        first = await service.set_pending_intent(user_id, intent=INTENT_CAREER_ADD)
        assert first["intent"] == INTENT_CAREER_ADD
        assert first["application_id"] is None

        created = await service.record_manual_application(
            user_id,
            company="Acme",
            role_title="ML Engineer",
            url=None,
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="1",
        )
        application_id = created["application"]["application_id"]

        second = await service.set_pending_intent(
            user_id,
            intent=INTENT_CAREER_NEXT_ACTION,
            application_id=application_id,
        )
        assert second["intent"] == INTENT_CAREER_NEXT_ACTION
        assert second["application_id"] == application_id

        row_count = await db.scalar(
            select(func.count(CareerTelegramPendingInput.user_id)).where(
                CareerTelegramPendingInput.user_id == user_id
            )
        )
        assert row_count == 1


@pytest.mark.integration
async def test_active_pending_intent_survives_a_new_db_session(
    pending_pg_session_maker,
):
    async with pending_pg_session_maker() as db:
        user_id = await _create_user(db)
        await CareerLedgerService(db).set_pending_intent(
            user_id, intent=INTENT_CAREER_ADD
        )

    async with pending_pg_session_maker() as db:
        active = await CareerLedgerService(db).get_active_pending_intent(user_id)
        assert active is not None
        assert active["intent"] == INTENT_CAREER_ADD


@pytest.mark.integration
async def test_expired_pending_intent_is_not_returned(pending_pg_session_maker):
    async with pending_pg_session_maker() as db:
        user_id = await _create_user(db)
        now = datetime.now(timezone.utc)
        await db.execute(
            insert(CareerTelegramPendingInput).values(
                user_id=user_id,
                intent=INTENT_CAREER_ADD,
                application_id=None,
                created_at=now - timedelta(minutes=45),
                expires_at=now - timedelta(minutes=15),
            )
        )
        await db.commit()

        active = await CareerLedgerService(db).get_active_pending_intent(user_id)
        assert active is None


@pytest.mark.integration
async def test_another_user_cannot_read_or_clear_pending_intent(
    pending_pg_session_maker,
):
    async with pending_pg_session_maker() as db:
        owner = await _create_user(db)
        other = await _create_user(db)
        service = CareerLedgerService(db)
        await service.set_pending_intent(owner, intent=INTENT_CAREER_ADD)

        assert await service.get_active_pending_intent(other) is None

        await service.clear_pending_intent(other)
        still_active = await service.get_active_pending_intent(owner)
        assert still_active is not None


@pytest.mark.integration
async def test_clear_pending_intent_removes_the_row(pending_pg_session_maker):
    async with pending_pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerLedgerService(db)
        await service.set_pending_intent(user_id, intent=INTENT_CAREER_ADD)

        await service.clear_pending_intent(user_id)

        assert await service.get_active_pending_intent(user_id) is None


@pytest.mark.integration
async def test_next_action_application_id_must_belong_to_same_user(
    pending_pg_session_maker,
):
    async with pending_pg_session_maker() as db:
        owner = await _create_user(db)
        other = await _create_user(db)
        service = CareerLedgerService(db)
        created = await service.record_manual_application(
            owner,
            company="Acme",
            role_title="ML Engineer",
            url=None,
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="1",
        )
        application_id = created["application"]["application_id"]

        with pytest.raises(CareerLedgerError):
            await service.set_pending_intent(
                other,
                intent=INTENT_CAREER_NEXT_ACTION,
                application_id=application_id,
            )


@pytest.mark.integration
async def test_discard_expired_pending_intents_removes_only_expired_rows(
    pending_pg_session_maker,
):
    async with pending_pg_session_maker() as db:
        fresh_user = await _create_user(db)
        stale_user = await _create_user(db)
        now = datetime.now(timezone.utc)
        await db.execute(
            insert(CareerTelegramPendingInput).values(
                user_id=fresh_user,
                intent=INTENT_CAREER_ADD,
                application_id=None,
                created_at=now,
                expires_at=now + timedelta(minutes=30),
            )
        )
        await db.execute(
            insert(CareerTelegramPendingInput).values(
                user_id=stale_user,
                intent=INTENT_CAREER_ADD,
                application_id=None,
                created_at=now - timedelta(minutes=45),
                expires_at=now - timedelta(minutes=15),
            )
        )
        await db.commit()

        service = CareerLedgerService(db)
        removed_for_fresh = await service.discard_expired_pending_intents(fresh_user)
        removed_for_stale = await service.discard_expired_pending_intents(stale_user)

        assert removed_for_fresh == 0
        assert removed_for_stale == 1
        assert await service.get_active_pending_intent(fresh_user) is not None
        assert await service.get_active_pending_intent(stale_user) is None
