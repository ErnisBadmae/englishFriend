from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.career import CareerApplicationEvent, CareerApplicationPackage
from app.models.core_tables import User
from app.services.career_inbox_service import (
    PACKAGE_STATUS_READY,
    PACKAGE_STATUS_SUBMITTED,
    VERDICT_PREPARE,
    VERDICT_SKIP,
    CareerInboxError,
    CareerInboxService,
)
from app.services.career_ledger_service import CareerLedgerService

TEST_DATABASE_URL = os.getenv("ML_TECHNICAL_PG_TEST_URL")


class _DraftProvider:
    def __init__(self, content: str):
        self.content = content

    async def generate(self, user_message, system_prompt, conversation_history=None, max_tokens=600):
        return self.content


def _facts_bank_with_cv(
    tmp_path: Path, *, cv_name: str = "CV_TEST.md", cv_text: str = "CV: Applied AI Engineer.\n"
) -> Path:
    (tmp_path / cv_name).write_text(cv_text, encoding="utf-8")
    facts_path = tmp_path / "facts_bank.yaml"
    facts_path.write_text(
        "role_types:\n"
        "  test_variant:\n"
        f"    cv: {cv_name}\n"
        "facts:\n"
        "  - id: profile_core\n"
        "    tier: A\n"
        "    text: >-\n"
        "      Applied AI инженер: Python backend, прикладной ML, LLM RAG системы.\n",
        encoding="utf-8",
    )
    return facts_path


@pytest_asyncio.fixture()
async def pg_session_maker():
    if not TEST_DATABASE_URL or "postgresql" not in TEST_DATABASE_URL:
        pytest.skip("ML_TECHNICAL_PG_TEST_URL is not configured for PostgreSQL")
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1 from career_application_packages limit 0"))
    except (OperationalError, ProgrammingError) as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL migration 020 unavailable: {exc.__class__.__name__}")
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


async def _create_user(db: AsyncSession) -> int:
    user_id = await db.scalar(
        insert(User).values(username=f"pkg_test_{uuid4().hex}").returning(User.id)
    )
    await db.commit()
    return int(user_id)


async def _ready_package(
    service: CareerInboxService, user_id: int, facts_path: Path, *, verdict: str = VERDICT_PREPARE
) -> dict:
    lead = await service.confirm_manual_lead(
        user_id,
        source="manual",
        raw_text="Acme reached out about an ML Engineer role.",
        company="Acme",
        role_title="ML Engineer",
        idempotency_key=f"telegram:{uuid4().hex}",
        actor_id="123456",
    )
    inbox_item_id = lead["inbox_item"]["inbox_item_id"]
    await service.set_verdict(
        user_id,
        inbox_item_id=inbox_item_id,
        verdict=verdict,
        idempotency_key=f"telegram_callback:{uuid4().hex}",
        actor_id="123456",
    )
    if verdict != VERDICT_PREPARE:
        return {"inbox_item_id": inbox_item_id, "draft_id": None, "package": None}

    generated = await service.generate_cover_letter_draft(
        user_id,
        inbox_item_id=inbox_item_id,
        provider=_DraftProvider("Здравствуйте! Применяю CatBoost."),
        idempotency_key=f"telegram:{uuid4().hex}",
        actor_id="123456",
        facts_bank_path=facts_path,
    )
    draft_id = generated["draft"]["draft_id"]
    await service.approve_cover_letter_draft(user_id, draft_id=draft_id, actor_id="123456")

    result = await service.prepare_application_package(
        user_id,
        inbox_item_id=inbox_item_id,
        cover_draft_id=draft_id,
        cv_variant_id="test_variant",
        actor_id="123456",
        facts_bank_path=facts_path,
    )
    return {
        "inbox_item_id": inbox_item_id,
        "draft_id": draft_id,
        "package": result["package"],
    }


@pytest.mark.integration
async def test_prepare_package_from_valid_prepare_draft_and_cv(pg_session_maker, tmp_path):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        facts_path = _facts_bank_with_cv(tmp_path)

        state = await _ready_package(service, user_id, facts_path)

        pkg = state["package"]
        assert pkg["status"] == PACKAGE_STATUS_READY
        assert pkg["cv_variant_id"] == "test_variant"
        assert pkg["package_kind"] == "application"
        assert len(pkg["package_content_hash"]) == 64


@pytest.mark.integration
async def test_prepare_package_is_idempotent_on_identical_inputs(pg_session_maker, tmp_path):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        facts_path = _facts_bank_with_cv(tmp_path)
        state = await _ready_package(service, user_id, facts_path)

        second = await service.prepare_application_package(
            user_id,
            inbox_item_id=state["inbox_item_id"],
            cover_draft_id=state["draft_id"],
            cv_variant_id="test_variant",
            actor_id="123456",
            facts_bank_path=facts_path,
        )

        assert second["created"] is False
        assert second["package"]["package_id"] == state["package"]["package_id"]
        count = await db.scalar(
            select(func.count(CareerApplicationPackage.id)).where(
                CareerApplicationPackage.user_id == user_id
            )
        )
        assert count == 1


@pytest.mark.integration
async def test_prepare_package_blocks_skip_verdict_item(pg_session_maker, tmp_path):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        facts_path = _facts_bank_with_cv(tmp_path)
        state = await _ready_package(service, user_id, facts_path, verdict=VERDICT_SKIP)

        with pytest.raises(CareerInboxError):
            await service.prepare_application_package(
                user_id,
                inbox_item_id=state["inbox_item_id"],
                cover_draft_id=str(uuid4()),
                cv_variant_id="test_variant",
                actor_id="123456",
                facts_bank_path=facts_path,
            )


@pytest.mark.integration
async def test_prepare_package_blocks_unapproved_draft(pg_session_maker, tmp_path):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        facts_path = _facts_bank_with_cv(tmp_path)
        lead = await service.confirm_manual_lead(
            user_id,
            source="manual",
            raw_text="Acme reached out.",
            company="Acme",
            role_title="ML Engineer",
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="123456",
        )
        inbox_item_id = lead["inbox_item"]["inbox_item_id"]
        await service.set_verdict(
            user_id,
            inbox_item_id=inbox_item_id,
            verdict=VERDICT_PREPARE,
            idempotency_key=f"telegram_callback:{uuid4().hex}",
            actor_id="123456",
        )
        generated = await service.generate_cover_letter_draft(
            user_id,
            inbox_item_id=inbox_item_id,
            provider=_DraftProvider("Здравствуйте!"),
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="123456",
            facts_bank_path=facts_path,
        )
        draft_id = generated["draft"]["draft_id"]  # still status='draft', not approved

        with pytest.raises(CareerInboxError):
            await service.prepare_application_package(
                user_id,
                inbox_item_id=inbox_item_id,
                cover_draft_id=draft_id,
                cv_variant_id="test_variant",
                actor_id="123456",
                facts_bank_path=facts_path,
            )


@pytest.mark.integration
async def test_prepare_package_blocks_rejected_draft(pg_session_maker, tmp_path):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        facts_path = _facts_bank_with_cv(tmp_path)
        lead = await service.confirm_manual_lead(
            user_id,
            source="manual",
            raw_text="Acme reached out.",
            company="Acme",
            role_title="ML Engineer",
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="123456",
        )
        inbox_item_id = lead["inbox_item"]["inbox_item_id"]
        await service.set_verdict(
            user_id,
            inbox_item_id=inbox_item_id,
            verdict=VERDICT_PREPARE,
            idempotency_key=f"telegram_callback:{uuid4().hex}",
            actor_id="123456",
        )
        generated = await service.generate_cover_letter_draft(
            user_id,
            inbox_item_id=inbox_item_id,
            provider=_DraftProvider("Здравствуйте!"),
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="123456",
            facts_bank_path=facts_path,
        )
        draft_id = generated["draft"]["draft_id"]
        await service.reject_cover_letter_draft(user_id, draft_id=draft_id, actor_id="123456")

        with pytest.raises(CareerInboxError):
            await service.prepare_application_package(
                user_id,
                inbox_item_id=inbox_item_id,
                cover_draft_id=draft_id,
                cv_variant_id="test_variant",
                actor_id="123456",
                facts_bank_path=facts_path,
            )


@pytest.mark.integration
async def test_prepare_package_blocks_unknown_cv_variant(pg_session_maker, tmp_path):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        facts_path = _facts_bank_with_cv(tmp_path)
        lead = await service.confirm_manual_lead(
            user_id,
            source="manual",
            raw_text="Acme reached out.",
            company="Acme",
            role_title="ML Engineer",
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="123456",
        )
        inbox_item_id = lead["inbox_item"]["inbox_item_id"]
        await service.set_verdict(
            user_id,
            inbox_item_id=inbox_item_id,
            verdict=VERDICT_PREPARE,
            idempotency_key=f"telegram_callback:{uuid4().hex}",
            actor_id="123456",
        )
        generated = await service.generate_cover_letter_draft(
            user_id,
            inbox_item_id=inbox_item_id,
            provider=_DraftProvider("Здравствуйте!"),
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="123456",
            facts_bank_path=facts_path,
        )
        draft_id = generated["draft"]["draft_id"]
        await service.approve_cover_letter_draft(user_id, draft_id=draft_id, actor_id="123456")

        with pytest.raises(CareerInboxError):
            await service.prepare_application_package(
                user_id,
                inbox_item_id=inbox_item_id,
                cover_draft_id=draft_id,
                cv_variant_id="does_not_exist",
                actor_id="123456",
                facts_bank_path=facts_path,
            )


@pytest.mark.integration
async def test_prepare_package_blocks_other_owner_draft(pg_session_maker, tmp_path):
    async with pg_session_maker() as db:
        owner_a = await _create_user(db)
        owner_b = await _create_user(db)
        service = CareerInboxService(db)
        facts_path = _facts_bank_with_cv(tmp_path)
        state_a = await _ready_package(service, owner_a, facts_path)

        with pytest.raises(CareerInboxError):
            await service.prepare_application_package(
                owner_b,
                inbox_item_id=state_a["inbox_item_id"],
                cover_draft_id=state_a["draft_id"],
                cv_variant_id="test_variant",
                actor_id="999",
                facts_bank_path=facts_path,
            )


@pytest.mark.integration
async def test_submit_links_exactly_one_application_and_event(pg_session_maker, tmp_path):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        facts_path = _facts_bank_with_cv(tmp_path)
        state = await _ready_package(service, user_id, facts_path)
        pkg = state["package"]

        result = await service.submit_application_package(
            user_id,
            package_id=pkg["package_id"],
            expected_package_hash=pkg["package_content_hash"],
            idempotency_key=f"telegram_callback:{uuid4().hex}",
            actor_id="123456",
            facts_bank_path=facts_path,
        )

        assert result["created"] is True
        assert result["package"]["status"] == PACKAGE_STATUS_SUBMITTED
        assert result["package"]["linked_application_id"] == result["application"]["application_id"]
        ledger = CareerLedgerService(db)
        summary = await ledger.get_pipeline_summary(user_id)
        assert summary["total"] == 1


@pytest.mark.integration
async def test_submit_replay_is_idempotent_creates_no_second_application(pg_session_maker, tmp_path):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        facts_path = _facts_bank_with_cv(tmp_path)
        state = await _ready_package(service, user_id, facts_path)
        pkg = state["package"]
        idempotency_key = f"telegram_callback:{uuid4().hex}"

        first = await service.submit_application_package(
            user_id,
            package_id=pkg["package_id"],
            expected_package_hash=pkg["package_content_hash"],
            idempotency_key=idempotency_key,
            actor_id="123456",
            facts_bank_path=facts_path,
        )
        second = await service.submit_application_package(
            user_id,
            package_id=pkg["package_id"],
            expected_package_hash=pkg["package_content_hash"],
            idempotency_key=idempotency_key,
            actor_id="123456",
            facts_bank_path=facts_path,
        )

        assert second["created"] is False
        assert (
            first["application"]["application_id"]
            == second["application"]["application_id"]
        )
        ledger = CareerLedgerService(db)
        summary = await ledger.get_pipeline_summary(user_id)
        assert summary["total"] == 1


@pytest.mark.integration
async def test_submit_requires_expected_hash_match(pg_session_maker, tmp_path):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        facts_path = _facts_bank_with_cv(tmp_path)
        state = await _ready_package(service, user_id, facts_path)
        pkg = state["package"]

        with pytest.raises(CareerInboxError):
            await service.submit_application_package(
                user_id,
                package_id=pkg["package_id"],
                expected_package_hash="0" * 64,
                idempotency_key=f"telegram_callback:{uuid4().hex}",
                actor_id="123456",
                facts_bank_path=facts_path,
            )
        ledger = CareerLedgerService(db)
        summary = await ledger.get_pipeline_summary(user_id)
        assert summary["total"] == 0


@pytest.mark.integration
async def test_submit_blocks_when_facts_bank_changed(pg_session_maker, tmp_path):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        facts_path = _facts_bank_with_cv(tmp_path)
        state = await _ready_package(service, user_id, facts_path)
        pkg = state["package"]

        # Facts bank changes after the package was already prepared.
        facts_path.write_text(
            facts_path.read_text(encoding="utf-8") + "  - id: extra\n    tier: A\n    text: New fact.\n",
            encoding="utf-8",
        )

        with pytest.raises(CareerInboxError, match="stale package"):
            await service.submit_application_package(
                user_id,
                package_id=pkg["package_id"],
                expected_package_hash=pkg["package_content_hash"],
                idempotency_key=f"telegram_callback:{uuid4().hex}",
                actor_id="123456",
                facts_bank_path=facts_path,
            )


@pytest.mark.integration
async def test_submit_blocks_when_cv_content_changed(pg_session_maker, tmp_path):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        facts_path = _facts_bank_with_cv(tmp_path)
        state = await _ready_package(service, user_id, facts_path)
        pkg = state["package"]

        (tmp_path / "CV_TEST.md").write_text("CV: totally rewritten.\n", encoding="utf-8")

        with pytest.raises(CareerInboxError, match="stale package"):
            await service.submit_application_package(
                user_id,
                package_id=pkg["package_id"],
                expected_package_hash=pkg["package_content_hash"],
                idempotency_key=f"telegram_callback:{uuid4().hex}",
                actor_id="123456",
                facts_bank_path=facts_path,
            )


@pytest.mark.integration
async def test_submit_blocks_when_newer_inbox_version_exists(pg_session_maker, tmp_path):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        facts_path = _facts_bank_with_cv(tmp_path)

        first_import = await service.import_snapshot(
            user_id,
            external_id="digest:1",
            content_hash="a" * 64,
            company="Acme",
            role_title="ML Engineer",
            route="apply_candidate",
            gates={
                "legal_hire_from_rf": {"status": "pass"},
                "language_path": {"status": "pass"},
                "comp_threshold": {"status": "pass"},
                "role_scope": {"status": "pass"},
            },
        )
        inbox_item_id = first_import["inbox_item"]["inbox_item_id"]
        await service.set_verdict(
            user_id,
            inbox_item_id=inbox_item_id,
            verdict=VERDICT_PREPARE,
            idempotency_key=f"telegram_callback:{uuid4().hex}",
            actor_id="123456",
        )
        generated = await service.generate_cover_letter_draft(
            user_id,
            inbox_item_id=inbox_item_id,
            provider=_DraftProvider("Здравствуйте!"),
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="123456",
            facts_bank_path=facts_path,
        )
        draft_id = generated["draft"]["draft_id"]
        await service.approve_cover_letter_draft(user_id, draft_id=draft_id, actor_id="123456")
        prepared = await service.prepare_application_package(
            user_id,
            inbox_item_id=inbox_item_id,
            cover_draft_id=draft_id,
            cv_variant_id="test_variant",
            actor_id="123456",
            facts_bank_path=facts_path,
        )
        pkg = prepared["package"]

        # A re-import with the same external_id but different content_hash
        # creates a NEW, newer inbox item row - the old one is now stale.
        await service.import_snapshot(
            user_id,
            external_id="digest:1",
            content_hash="b" * 64,
            company="Acme",
            role_title="ML Engineer (updated)",
            route="apply_candidate",
            gates={
                "legal_hire_from_rf": {"status": "pass"},
                "language_path": {"status": "pass"},
                "comp_threshold": {"status": "pass"},
                "role_scope": {"status": "pass"},
            },
        )

        with pytest.raises(CareerInboxError, match="stale package"):
            await service.submit_application_package(
                user_id,
                package_id=pkg["package_id"],
                expected_package_hash=pkg["package_content_hash"],
                idempotency_key=f"telegram_callback:{uuid4().hex}",
                actor_id="123456",
                facts_bank_path=facts_path,
            )


@pytest.mark.integration
async def test_submit_does_not_call_any_provider_or_network(pg_session_maker, tmp_path):
    """submit_application_package takes no LLM/HTTP provider argument at all -
    the write path is pure PostgreSQL + local file reads."""
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        facts_path = _facts_bank_with_cv(tmp_path)
        state = await _ready_package(service, user_id, facts_path)
        pkg = state["package"]
        import inspect

        sig = inspect.signature(service.submit_application_package)
        assert "provider" not in sig.parameters

        result = await service.submit_application_package(
            user_id,
            package_id=pkg["package_id"],
            expected_package_hash=pkg["package_content_hash"],
            idempotency_key=f"telegram_callback:{uuid4().hex}",
            actor_id="123456",
            facts_bank_path=facts_path,
        )
        assert result["created"] is True


@pytest.mark.integration
async def test_list_ready_packages_is_owner_only_newest_first_and_bounded(pg_session_maker, tmp_path):
    async with pg_session_maker() as db:
        owner_a = await _create_user(db)
        owner_b = await _create_user(db)
        service = CareerInboxService(db)
        facts_path = _facts_bank_with_cv(tmp_path)

        package_ids = []
        for _ in range(9):
            state = await _ready_package(service, owner_a, facts_path)
            package_ids.append(state["package"]["package_id"])
        other_state = await _ready_package(service, owner_b, facts_path)

        listed = await service.list_ready_application_packages(owner_a, limit=7)

        assert len(listed) == 7
        listed_ids = [p["package_id"] for p in listed]
        assert other_state["package"]["package_id"] not in listed_ids
        # newest first: the most recently prepared package leads the list.
        assert listed_ids[0] == package_ids[-1]


@pytest.mark.integration
async def test_list_ready_packages_excludes_submitted(pg_session_maker, tmp_path):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        facts_path = _facts_bank_with_cv(tmp_path)
        state = await _ready_package(service, user_id, facts_path)
        pkg = state["package"]
        await service.submit_application_package(
            user_id,
            package_id=pkg["package_id"],
            expected_package_hash=pkg["package_content_hash"],
            idempotency_key=f"telegram_callback:{uuid4().hex}",
            actor_id="123456",
            facts_bank_path=facts_path,
        )

        listed = await service.list_ready_application_packages(user_id)

        assert listed == []


@pytest.mark.integration
async def test_submit_replay_with_different_idempotency_keys_creates_no_duplicate(
    pg_session_maker, tmp_path
):
    """D1b.2b mandatory preflight: submitting the same package twice with two
    DIFFERENT idempotency keys (not a literal Telegram retry) must still never
    produce a second application/event - the second call is expected to fail
    closed on the package's own status guard instead of silently duplicating."""
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        facts_path = _facts_bank_with_cv(tmp_path)
        state = await _ready_package(service, user_id, facts_path)
        pkg = state["package"]

        first = await service.submit_application_package(
            user_id,
            package_id=pkg["package_id"],
            expected_package_hash=pkg["package_content_hash"],
            idempotency_key="key-A",
            actor_id="123456",
            facts_bank_path=facts_path,
        )
        assert first["created"] is True

        with pytest.raises(CareerInboxError):
            await service.submit_application_package(
                user_id,
                package_id=pkg["package_id"],
                expected_package_hash=pkg["package_content_hash"],
                idempotency_key="key-B",
                actor_id="123456",
                facts_bank_path=facts_path,
            )

        count = await db.scalar(
            select(func.count(CareerApplicationEvent.id)).where(
                CareerApplicationEvent.user_id == user_id
            )
        )
        assert count == 1
