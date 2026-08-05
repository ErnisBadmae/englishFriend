from __future__ import annotations

import os
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.career import CareerInboxItem
from app.models.core_tables import User
from app.services.career_inbox_service import (
    INBOX_DISPLAY_LIMIT,
    CareerInboxError,
    CareerInboxService,
    validate_import_envelope,
)
from app.services.career_ledger_service import CareerLedgerService

TEST_DATABASE_URL = os.getenv("ML_TECHNICAL_PG_TEST_URL")


def gate(status="pass", reason="r", evidence=None, basis="post_evidence"):
    return {
        "status": status,
        "reason": reason,
        "evidence": evidence,
        "basis": basis,
        "authority": {"decision": "confirmed", "reason_code": "x"},
    }


def envelope(external_id: str, content_hash: str, *, route: str = "outreach") -> dict:
    return {
        "schema_version": 1,
        "source": "telegram_digest",
        "external_id": external_id,
        "content_hash": content_hash,
        "fetched_at": "2026-07-24T00:00:00+00:00",
        "company": "Acme",
        "role_title": "ML Engineer",
        "location": "Remote",
        "url": f"https://t.me/{external_id.replace(':', '/')}",
        "route": route,
        "gates": {
            "legal_hire_from_rf": gate(),
            "language_path": gate(basis="source_policy"),
            "comp_threshold": gate(status="unknown", evidence=None, basis="none"),
            "role_scope": gate(evidence="Разрабатывать RAG-архитектуру"),
        },
        "questions_for_recruiter": ["Доступен ли contractor?"],
        "evidence_excerpt": "Разрабатывать RAG-архитектуру",
    }


# ---------------------------------------------------------------------------
# Pure schema validation - no DB, no network.
# ---------------------------------------------------------------------------


def test_validate_import_envelope_accepts_valid_envelope():
    assert validate_import_envelope(envelope("@chan:1", "a" * 64)) is None


def test_validate_import_envelope_rejects_bad_schema_version():
    env = envelope("@chan:1", "a" * 64)
    env["schema_version"] = 2
    assert validate_import_envelope(env) is not None


def test_validate_import_envelope_rejects_skip_route():
    env = envelope("@chan:1", "a" * 64, route="skip")
    assert validate_import_envelope(env) is not None


def test_validate_import_envelope_rejects_raw_text_leak():
    env = envelope("@chan:1", "a" * 64)
    env["raw_text"] = "leaked full post text"
    assert validate_import_envelope(env) is not None


def test_validate_import_envelope_rejects_model_status_leak():
    env = envelope("@chan:1", "a" * 64)
    env["gates"]["role_scope"]["model_status"] = "pass"
    assert validate_import_envelope(env) is not None


def test_validate_import_envelope_rejects_bad_content_hash():
    env = envelope("@chan:1", "not-a-hash")
    assert validate_import_envelope(env) is not None


def test_validate_import_envelope_rejects_missing_gate():
    env = envelope("@chan:1", "a" * 64)
    del env["gates"]["comp_threshold"]
    assert validate_import_envelope(env) is not None


async def test_import_snapshot_rejects_skip_route_before_touching_db():
    service = CareerInboxService(db=None)  # not reached before validation
    with pytest.raises(CareerInboxError):
        await service.import_snapshot(
            1,
            external_id="@chan:1",
            content_hash="a" * 64,
            company="Acme",
            role_title="ML Engineer",
            route="skip",
            gates={
                "legal_hire_from_rf": gate(),
                "language_path": gate(),
                "comp_threshold": gate(),
                "role_scope": gate(),
            },
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
            await conn.execute(text("select 1 from career_inbox_items limit 0"))
    except (OperationalError, ProgrammingError) as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL migration 018 unavailable: {exc.__class__.__name__}")
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


async def _create_user(db: AsyncSession) -> int:
    user_id = await db.scalar(
        insert(User)
        .values(username=f"career_inbox_import_test_{uuid4().hex}")
        .returning(User.id)
    )
    await db.commit()
    return int(user_id)


def _gates_kwargs() -> dict:
    return {
        "legal_hire_from_rf": gate(),
        "language_path": gate(basis="source_policy"),
        "comp_threshold": gate(status="unknown", evidence=None, basis="none"),
        "role_scope": gate(evidence="Разрабатывать RAG-архитектуру"),
    }


@pytest.mark.integration
async def test_import_snapshot_creates_one_row(pg_session_maker):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)

        result = await service.import_snapshot(
            user_id,
            external_id="@chan:1",
            content_hash="a" * 64,
            company="Acme",
            role_title="ML Engineer",
            location="Remote",
            url="https://t.me/chan/1",
            route="outreach",
            gates=_gates_kwargs(),
            questions_for_recruiter=["Доступен ли contractor?"],
        )

        assert result["created"] is True
        count = await db.scalar(
            select(func.count(CareerInboxItem.id)).where(
                CareerInboxItem.user_id == user_id
            )
        )
        assert count == 1


@pytest.mark.integration
async def test_repeated_import_of_same_envelope_creates_no_duplicate(
    pg_session_maker,
):
    """Slice B stop condition: повторный import не должен создавать дубли."""
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)

        first = await service.import_snapshot(
            user_id,
            external_id="@chan:1",
            content_hash="a" * 64,
            company="Acme",
            role_title="ML Engineer",
            route="outreach",
            gates=_gates_kwargs(),
        )
        second = await service.import_snapshot(
            user_id,
            external_id="@chan:1",
            content_hash="a" * 64,
            company="Acme",
            role_title="ML Engineer",
            route="outreach",
            gates=_gates_kwargs(),
        )

        assert second["created"] is False
        assert (
            first["inbox_item"]["inbox_item_id"]
            == second["inbox_item"]["inbox_item_id"]
        )
        count = await db.scalar(
            select(func.count(CareerInboxItem.id)).where(
                CareerInboxItem.user_id == user_id
            )
        )
        assert count == 1


@pytest.mark.integration
async def test_importing_full_batch_twice_is_fully_idempotent(pg_session_maker):
    """Simulates re-running the CLI import over the same exported file."""
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        batch = [
            {"external_id": f"@chan:{i}", "content_hash": f"{i}" * 64}
            for i in range(5)
        ]

        for _pass_num in (1, 2):
            for item in batch:
                await service.import_snapshot(
                    user_id,
                    external_id=item["external_id"],
                    content_hash=item["content_hash"],
                    company="Acme",
                    role_title="ML Engineer",
                    route="outreach",
                    gates=_gates_kwargs(),
                )

        count = await db.scalar(
            select(func.count(CareerInboxItem.id)).where(
                CareerInboxItem.user_id == user_id
            )
        )
        assert count == 5


@pytest.mark.integration
async def test_changed_content_hash_creates_new_row_but_list_shows_only_latest(
    pg_session_maker,
):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)

        await service.import_snapshot(
            user_id,
            external_id="@chan:1",
            content_hash="a" * 64,
            company="Acme",
            role_title="ML Engineer (v1)",
            route="outreach",
            gates=_gates_kwargs(),
        )
        await service.import_snapshot(
            user_id,
            external_id="@chan:1",
            content_hash="b" * 64,
            company="Acme",
            role_title="ML Engineer (v2, edited)",
            route="outreach",
            gates=_gates_kwargs(),
        )

        total_rows = await db.scalar(
            select(func.count(CareerInboxItem.id)).where(
                CareerInboxItem.user_id == user_id
            )
        )
        assert total_rows == 2  # both immutable snapshots preserved

        items = await service.list_inbox_items(user_id)
        assert len(items) == 1  # only the latest version is surfaced
        assert items[0]["role_title"] == "ML Engineer (v2, edited)"
        assert items[0]["content_hash"] == "b" * 64


@pytest.mark.integration
async def test_list_inbox_items_stays_bounded_after_import(
    pg_session_maker,
):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        for i in range(INBOX_DISPLAY_LIMIT + 5):
            await service.import_snapshot(
                user_id,
                external_id=f"@chan:{i}",
                content_hash=f"{i:064x}",
                company=f"Company {i}",
                role_title="ML Engineer",
                route="outreach",
                gates=_gates_kwargs(),
            )

        items = await service.list_inbox_items(user_id)

        assert len(items) == INBOX_DISPLAY_LIMIT


@pytest.mark.integration
async def test_import_never_creates_an_application(pg_session_maker):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)

        result = await service.import_snapshot(
            user_id,
            external_id="@chan:1",
            content_hash="a" * 64,
            company="Acme",
            role_title="ML Engineer",
            route="apply_candidate",
            gates=_gates_kwargs(),
        )

        assert result["inbox_item"]["owner_verdict"] is None
        assert result["inbox_item"]["linked_application_id"] is None
        ledger = CareerLedgerService(db)
        summary = await ledger.get_pipeline_summary(user_id)
        assert summary["total"] == 0


@pytest.mark.integration
async def test_import_rejects_bad_route(pg_session_maker):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        with pytest.raises(CareerInboxError):
            await service.import_snapshot(
                user_id,
                external_id="@chan:1",
                content_hash="a" * 64,
                company="Acme",
                role_title="ML Engineer",
                route="skip",
                gates=_gates_kwargs(),
            )


@pytest.mark.integration
async def test_set_verdict_preserves_import_identity_for_reimport(pg_session_maker):
    """Corrective regression: once the owner sets a verdict, re-importing the
    exact same envelope must still resolve to the same row, not a new one."""
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)

        first = await service.import_snapshot(
            user_id,
            external_id="@chan:1",
            content_hash="a" * 64,
            company="Acme",
            role_title="ML Engineer",
            route="outreach",
            gates=_gates_kwargs(),
        )
        await service.set_verdict(
            user_id,
            inbox_item_id=first["inbox_item"]["inbox_item_id"],
            verdict="skip",
            idempotency_key=f"telegram_callback:{uuid4().hex}",
            actor_id="123456",
        )

        second = await service.import_snapshot(
            user_id,
            external_id="@chan:1",
            content_hash="a" * 64,
            company="Acme",
            role_title="ML Engineer",
            route="outreach",
            gates=_gates_kwargs(),
        )

        assert second["created"] is False
        assert (
            second["inbox_item"]["inbox_item_id"]
            == first["inbox_item"]["inbox_item_id"]
        )
        assert second["inbox_item"]["owner_verdict"] == "skip"
        count = await db.scalar(
            select(func.count(CareerInboxItem.id)).where(
                CareerInboxItem.user_id == user_id
            )
        )
        assert count == 1


@pytest.mark.integration
async def test_confirm_applied_preserves_import_identity_for_reimport(pg_session_maker):
    """Corrective regression: the applied state and its linked application
    must survive an identical re-import of the same envelope."""
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)

        first = await service.import_snapshot(
            user_id,
            external_id="@chan:2",
            content_hash="b" * 64,
            company="Acme",
            role_title="ML Engineer",
            route="outreach",
            gates=_gates_kwargs(),
        )
        inbox_item_id = first["inbox_item"]["inbox_item_id"]
        await service.set_verdict(
            user_id,
            inbox_item_id=inbox_item_id,
            verdict="prepare",
            idempotency_key=f"telegram_callback:{uuid4().hex}",
            actor_id="123456",
        )
        await service.confirm_applied(
            user_id,
            inbox_item_id=inbox_item_id,
            idempotency_key=f"telegram_callback:{uuid4().hex}",
            actor_id="123456",
        )

        second = await service.import_snapshot(
            user_id,
            external_id="@chan:2",
            content_hash="b" * 64,
            company="Acme",
            role_title="ML Engineer",
            route="outreach",
            gates=_gates_kwargs(),
        )

        assert second["created"] is False
        assert second["inbox_item"]["inbox_item_id"] == inbox_item_id
        assert second["inbox_item"]["owner_verdict"] == "applied"
        assert second["inbox_item"]["linked_application_id"] is not None

        item_count = await db.scalar(
            select(func.count(CareerInboxItem.id)).where(
                CareerInboxItem.user_id == user_id
            )
        )
        assert item_count == 1
        ledger = CareerLedgerService(db)
        summary = await ledger.get_pipeline_summary(user_id)
        assert summary["total"] == 1


@pytest.mark.integration
async def test_set_verdict_replay_same_state_is_noop_but_change_is_real(
    pg_session_maker,
):
    """Replaying the same verdict+reason is a no-op; a genuine state change
    is still a real, idempotency-key-independent state transition."""
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)

        first = await service.import_snapshot(
            user_id,
            external_id="@chan:3",
            content_hash="c" * 64,
            company="Acme",
            role_title="ML Engineer",
            route="outreach",
            gates=_gates_kwargs(),
        )
        inbox_item_id = first["inbox_item"]["inbox_item_id"]

        set_1 = await service.set_verdict(
            user_id,
            inbox_item_id=inbox_item_id,
            verdict="ask",
            reason="looks interesting",
            idempotency_key=f"telegram_callback:{uuid4().hex}",
            actor_id="123456",
        )
        assert set_1["created"] is True

        replay = await service.set_verdict(
            user_id,
            inbox_item_id=inbox_item_id,
            verdict="ask",
            reason="looks interesting",
            idempotency_key=f"telegram_callback:{uuid4().hex}",
            actor_id="123456",
        )
        assert replay["created"] is False
        assert replay["inbox_item"]["owner_verdict"] == "ask"

        changed = await service.set_verdict(
            user_id,
            inbox_item_id=inbox_item_id,
            verdict="skip",
            idempotency_key=f"telegram_callback:{uuid4().hex}",
            actor_id="123456",
        )
        assert changed["created"] is True
        assert changed["inbox_item"]["owner_verdict"] == "skip"


@pytest.mark.integration
async def test_manual_lead_import_identity_survives_owner_verdict(pg_session_maker):
    """Optional coverage: confirm_manual_lead's creation key is also never
    overwritten by set_verdict."""
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        idempotency_key = f"telegram:{uuid4().hex}"

        first = await service.confirm_manual_lead(
            user_id,
            source="manual",
            raw_text="synthetic lead text",
            company="Acme",
            role_title="ML Engineer",
            idempotency_key=idempotency_key,
            actor_id="123456",
        )
        inbox_item_id = first["inbox_item"]["inbox_item_id"]
        await service.set_verdict(
            user_id,
            inbox_item_id=inbox_item_id,
            verdict="skip",
            idempotency_key=f"telegram_callback:{uuid4().hex}",
            actor_id="123456",
        )

        second = await service.confirm_manual_lead(
            user_id,
            source="manual",
            raw_text="synthetic lead text",
            company="Acme",
            role_title="ML Engineer",
            idempotency_key=idempotency_key,
            actor_id="123456",
        )

        assert second["created"] is False
        assert second["inbox_item"]["inbox_item_id"] == inbox_item_id
        assert second["inbox_item"]["owner_verdict"] == "skip"


@pytest.mark.integration
async def test_import_user_isolation_across_two_owners(pg_session_maker):
    async with pg_session_maker() as db:
        user_a = await _create_user(db)
        user_b = await _create_user(db)
        service = CareerInboxService(db)
        await service.import_snapshot(
            user_a,
            external_id="@chan:1",
            content_hash="a" * 64,
            company="Acme",
            role_title="ML Engineer",
            route="outreach",
            gates=_gates_kwargs(),
        )

        items_a = await service.list_inbox_items(user_a)
        items_b = await service.list_inbox_items(user_b)

        assert len(items_a) == 1
        assert len(items_b) == 0
