from __future__ import annotations

import os
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.career import CareerFeedbackEvent, CareerInboxItem
from app.models.core_tables import User
from app.services.career_inbox_service import (
    FEEDBACK_CATEGORY_UNKNOWN,
    INBOX_DISPLAY_LIMIT,
    MAX_PASTED_LEADS,
    VERDICT_APPLIED,
    VERDICT_PREPARE,
    CareerInboxError,
    CareerInboxService,
    is_grounded,
    split_pasted_leads,
    suggest_feedback,
    suggest_manual_lead,
)
from app.services.career_ledger_service import CareerLedgerService

TEST_DATABASE_URL = os.getenv("ML_TECHNICAL_PG_TEST_URL")


# ---------------------------------------------------------------------------
# Pure validation and grounding tests - no DB, no network.
# ---------------------------------------------------------------------------


def test_is_grounded_accepts_exact_substring():
    raw = "Спасибо, но мы решили закрыть вакансию по причине заморозки бюджета."
    assert is_grounded("заморозки бюджета", raw) is True


def test_is_grounded_rejects_fabricated_quote():
    raw = "Обычный отказ без деталей."
    assert is_grounded("требуется гражданство ЕС", raw) is False


def test_is_grounded_rejects_empty_quote():
    assert is_grounded(None, "любой текст") is False
    assert is_grounded("", "любой текст") is False


# ---------------------------------------------------------------------------
# split_pasted_leads: Career Inbox batch paste v0 (pure, no DB, no network).
# ---------------------------------------------------------------------------


def test_split_pasted_leads_numbered_blob_of_three():
    raw = "1. Company A\ntext one\n2. Company B\ntext two\n3. Company C\ntext three"
    segments = split_pasted_leads(raw)
    assert len(segments) == 3
    assert segments[0].startswith("Company A")
    assert segments[1].startswith("Company B")
    assert segments[2].startswith("Company C")


def test_split_pasted_leads_real_owner_example_yields_three_segments():
    raw = (
        "1.Миролла\n"
        "Rejection\n"
        "Эрнис, здравствуйте!\n"
        "2. Технологический стартап внутри крупного холдинга\n"
        "\n"
        "Manager 2636887\n"
        "Rejection\n"
        "Эрнис, здравствуйте!\n"
        "\n"
        "Большое спасибо за интерес к нашей компании! К сожалению, сейчас мы не готовы\n"
        "3. Премьер Консалт\n"
        "Online now\n"
        "\n"
        "Vacancy\n"
        "Руководитель по искусственному интеллекту (Head of AI)\n"
        "\n"
        "Rejection\n"
        "Эрнис, здравствуйте!"
    )
    segments = split_pasted_leads(raw)
    assert len(segments) == 3
    assert segments[0].startswith("Миролла")
    assert segments[1].startswith("Технологический стартап")
    assert segments[2].startswith("Премьер Консалт")


def test_split_pasted_leads_blank_line_blob_of_three():
    raw = "Company A message\n\nCompany B message\n\nCompany C message"
    segments = split_pasted_leads(raw)
    assert segments == ["Company A message", "Company B message", "Company C message"]


def test_split_pasted_leads_single_message_is_identity():
    raw = "Just one recruiter message with no markers."
    assert split_pasted_leads(raw) == [raw]


def test_split_pasted_leads_single_incidental_number_is_not_a_list():
    raw = "We pay from 1. 5000 USD per month, no other numbering here."
    assert split_pasted_leads(raw) == [raw]


def test_split_pasted_leads_caps_at_max():
    raw = "\n".join(f"{i}. lead number {i}" for i in range(1, 15))
    segments = split_pasted_leads(raw)
    assert len(segments) == MAX_PASTED_LEADS


def test_split_pasted_leads_empty_text_is_empty_list():
    assert split_pasted_leads("   ") == []


def test_split_pasted_leads_is_deterministic():
    raw = "1. A\ntext\n2. B\ntext"
    assert split_pasted_leads(raw) == split_pasted_leads(raw)


async def test_confirm_manual_lead_rejects_unsupported_source():
    service = CareerInboxService(db=None)  # not reached before validation
    with pytest.raises(CareerInboxError):
        await service.confirm_manual_lead(
            1,
            source="telegram_digest",
            raw_text="hello",
            company=None,
            role_title=None,
            idempotency_key="k",
            actor_id="1",
        )


async def test_set_verdict_rejects_applied_directly():
    service = CareerInboxService(db=None)
    with pytest.raises(CareerInboxError):
        await service.set_verdict(
            1,
            inbox_item_id=str(uuid4()),
            verdict=VERDICT_APPLIED,
            idempotency_key="k",
            actor_id="1",
        )


async def test_set_verdict_rejects_unknown_verdict():
    service = CareerInboxService(db=None)
    with pytest.raises(CareerInboxError):
        await service.set_verdict(
            1,
            inbox_item_id=str(uuid4()),
            verdict="bogus",
            idempotency_key="k",
            actor_id="1",
        )


async def test_confirm_feedback_requires_a_target():
    service = CareerInboxService(db=None)
    with pytest.raises(CareerInboxError):
        await service.confirm_feedback(
            1,
            category="unknown",
            raw_feedback="text",
            evidence_quote=None,
            idempotency_key="k",
            actor_id="1",
        )


async def test_confirm_feedback_rejects_unknown_category():
    service = CareerInboxService(db=None)
    with pytest.raises(CareerInboxError):
        await service.confirm_feedback(
            1,
            application_id=str(uuid4()),
            category="not_a_real_category",
            raw_feedback="text",
            evidence_quote=None,
            idempotency_key="k",
            actor_id="1",
        )


# ---------------------------------------------------------------------------
# LLM suggestion: untrusted extractor, fail-closed on missing/broken provider.
# ---------------------------------------------------------------------------


class _FakeProvider:
    def __init__(self, content: str | None = None, *, raises: bool = False):
        self.content = content
        self.raises = raises
        self.calls: list[tuple[str, str]] = []

    async def generate(self, user_message, system_prompt, conversation_history=None, max_tokens=400):
        self.calls.append((user_message, system_prompt))
        if self.raises:
            raise RuntimeError("provider unavailable")
        return self.content or ""


async def test_suggest_manual_lead_without_provider_returns_safe_default():
    result = await suggest_manual_lead("any text", None)
    assert result == {
        "company": None,
        "role_title": None,
        "event_kind": "unknown",
        "questions_for_recruiter": [],
        "evidence_quote": None,
    }


async def test_suggest_manual_lead_falls_back_on_provider_error():
    provider = _FakeProvider(raises=True)
    result = await suggest_manual_lead("any text", provider)
    assert result["company"] is None
    assert result["evidence_quote"] is None


async def test_suggest_manual_lead_downgrades_ungrounded_evidence():
    raw = "TCS Group ищет ML Engineer, удалёнка."
    provider = _FakeProvider(
        content='{"company": "TCS Group", "role_title": "ML Engineer", '
        '"event_kind": "inbound_message", "questions_for_recruiter": [], '
        '"evidence_quote": "выдуманная цитата не из текста"}'
    )
    result = await suggest_manual_lead(raw, provider)
    assert result["company"] == "TCS Group"
    assert result["evidence_quote"] is None


async def test_suggest_manual_lead_keeps_grounded_evidence():
    raw = "TCS Group ищет ML Engineer, удалёнка."
    provider = _FakeProvider(
        content='{"company": "TCS Group", "role_title": "ML Engineer", '
        '"event_kind": "inbound_message", "questions_for_recruiter": [], '
        '"evidence_quote": "TCS Group ищет ML Engineer"}'
    )
    result = await suggest_manual_lead(raw, provider)
    assert result["evidence_quote"] == "TCS Group ищет ML Engineer"


async def test_suggest_feedback_without_provider_is_unknown():
    result = await suggest_feedback("any text", None)
    assert result["category"] == FEEDBACK_CATEGORY_UNKNOWN
    assert result["evidence_quote"] is None


async def test_suggest_feedback_downgrades_ungrounded_category():
    raw = "Спасибо, но мы решили закрыть вакансию по причине заморозки бюджета."
    provider = _FakeProvider(
        content='{"category": "role_scope_mismatch", '
        '"evidence_quote": "требуется гражданство ЕС", '
        '"suggested_status_change": null, "suggested_next_action": null, '
        '"rationale": "r"}'
    )
    result = await suggest_feedback(raw, provider)
    assert result["category"] == FEEDBACK_CATEGORY_UNKNOWN
    assert result["evidence_quote"] is None


async def test_suggest_feedback_keeps_grounded_category():
    raw = "Спасибо, но мы решили закрыть вакансию по причине заморозки бюджета."
    provider = _FakeProvider(
        content='{"category": "process_delay", '
        '"evidence_quote": "заморозки бюджета", '
        '"suggested_status_change": "rejected", "suggested_next_action": null, '
        '"rationale": "r"}'
    )
    result = await suggest_feedback(raw, provider)
    assert result["category"] == "process_delay"
    assert result["evidence_quote"] == "заморозки бюджета"


async def test_suggest_feedback_rejects_invalid_json():
    provider = _FakeProvider(content="not json at all")
    result = await suggest_feedback("text", provider)
    assert result["category"] == FEEDBACK_CATEGORY_UNKNOWN


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
        .values(username=f"career_inbox_test_{uuid4().hex}")
        .returning(User.id)
    )
    await db.commit()
    return int(user_id)


@pytest.mark.integration
async def test_confirm_manual_lead_creates_one_inbox_item(pg_session_maker):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)

        result = await service.confirm_manual_lead(
            user_id,
            source="linkedin_inbound",
            raw_text="TCS Group reached out about an ML Engineer role.",
            company="TCS Group",
            role_title="ML Engineer",
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="123456",
        )

        assert result["created"] is True
        count = await db.scalar(
            select(func.count(CareerInboxItem.id)).where(
                CareerInboxItem.user_id == user_id
            )
        )
        assert count == 1


@pytest.mark.integration
async def test_replaying_manual_lead_idempotency_key_creates_no_duplicate(
    pg_session_maker,
):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        idempotency_key = f"telegram:{uuid4().hex}"

        first = await service.confirm_manual_lead(
            user_id,
            source="manual",
            raw_text="Andersen recruiter pinged me on LinkedIn.",
            company="Andersen",
            role_title=None,
            idempotency_key=idempotency_key,
            actor_id="123456",
        )
        second = await service.confirm_manual_lead(
            user_id,
            source="manual",
            raw_text="Andersen recruiter pinged me on LinkedIn.",
            company="Andersen",
            role_title=None,
            idempotency_key=idempotency_key,
            actor_id="123456",
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
async def test_list_inbox_items_is_bounded_to_seven(pg_session_maker):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        for i in range(10):
            await service.confirm_manual_lead(
                user_id,
                source="manual",
                raw_text=f"lead number {i}",
                company=f"Company {i}",
                role_title="Engineer",
                idempotency_key=f"telegram:{uuid4().hex}",
                actor_id="123456",
            )

        items = await service.list_inbox_items(user_id)

        assert len(items) == INBOX_DISPLAY_LIMIT


@pytest.mark.integration
async def test_skip_verdict_never_creates_an_application(pg_session_maker):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        result = await service.confirm_manual_lead(
            user_id,
            source="manual",
            raw_text="ТЕХНОНИКОЛЬ отказ по причине несовпадения по грейду",
            company="ТЕХНОНИКОЛЬ",
            role_title="ML Engineer",
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="123456",
        )
        inbox_item_id = result["inbox_item"]["inbox_item_id"]

        await service.set_verdict(
            user_id,
            inbox_item_id=inbox_item_id,
            verdict="skip",
            idempotency_key=f"telegram_callback:{uuid4().hex}",
            actor_id="123456",
        )

        item = await service.get_inbox_item(user_id, inbox_item_id)
        assert item["owner_verdict"] == "skip"
        assert item["linked_application_id"] is None
        ledger = CareerLedgerService(db)
        summary = await ledger.get_pipeline_summary(user_id)
        assert summary["total"] == 0


@pytest.mark.integration
async def test_confirm_applied_requires_prior_prepare_verdict(pg_session_maker):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        result = await service.confirm_manual_lead(
            user_id,
            source="manual",
            raw_text="ГСП-Центр приглашает на техническое интервью",
            company="ГСП-Центр",
            role_title="Applied AI Engineer",
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="123456",
        )
        inbox_item_id = result["inbox_item"]["inbox_item_id"]

        with pytest.raises(CareerInboxError):
            await service.confirm_applied(
                user_id,
                inbox_item_id=inbox_item_id,
                idempotency_key=f"telegram_callback:{uuid4().hex}",
                actor_id="123456",
            )


@pytest.mark.integration
async def test_confirm_applied_after_prepare_links_one_application(pg_session_maker):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        service = CareerInboxService(db)
        result = await service.confirm_manual_lead(
            user_id,
            source="manual",
            raw_text="ЕСТП зовет на собеседование",
            company="ЕСТП",
            role_title="Applied AI Engineer",
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="123456",
        )
        inbox_item_id = result["inbox_item"]["inbox_item_id"]
        await service.set_verdict(
            user_id,
            inbox_item_id=inbox_item_id,
            verdict=VERDICT_PREPARE,
            idempotency_key=f"telegram_callback:{uuid4().hex}",
            actor_id="123456",
        )

        applied = await service.confirm_applied(
            user_id,
            inbox_item_id=inbox_item_id,
            idempotency_key=f"telegram_callback:{uuid4().hex}",
            actor_id="123456",
        )

        assert applied["created"] is True
        item = await service.get_inbox_item(user_id, inbox_item_id)
        assert item["owner_verdict"] == VERDICT_APPLIED
        assert item["linked_application_id"] == applied["application"]["application_id"]
        ledger = CareerLedgerService(db)
        summary = await ledger.get_pipeline_summary(user_id)
        assert summary["total"] == 1


@pytest.mark.integration
async def test_confirm_feedback_grounded_quote_is_stored_append_only(
    pg_session_maker,
):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        ledger = CareerLedgerService(db)
        service = CareerInboxService(db)
        record = await ledger.record_manual_application(
            user_id,
            company="ТЕХНОНИКОЛЬ",
            role_title="ML Engineer",
            url=None,
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="123456",
        )
        application_id = record["application"]["application_id"]
        raw_feedback = "Отказ: команда ищет специалиста с опытом DWH/ETL/Greenplum."

        result = await service.confirm_feedback(
            user_id,
            application_id=application_id,
            category="role_scope_mismatch",
            raw_feedback=raw_feedback,
            evidence_quote="опытом DWH/ETL/Greenplum",
            next_action=None,
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="123456",
        )

        assert result["created"] is True
        assert result["feedback_event"]["category"] == "role_scope_mismatch"
        count = await db.scalar(
            select(func.count(CareerFeedbackEvent.id)).where(
                CareerFeedbackEvent.user_id == user_id
            )
        )
        assert count == 1


@pytest.mark.integration
async def test_confirm_feedback_ungrounded_quote_downgrades_to_unknown(
    pg_session_maker,
):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        ledger = CareerLedgerService(db)
        service = CareerInboxService(db)
        record = await ledger.record_manual_application(
            user_id,
            company="Elinext",
            role_title="ML Engineer",
            url=None,
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="123456",
        )
        application_id = record["application"]["application_id"]

        result = await service.confirm_feedback(
            user_id,
            application_id=application_id,
            category="legal_or_authorization",
            raw_feedback="Общий отказ без деталей.",
            evidence_quote="выдуманная причина, которой нет в тексте",
            next_action=None,
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="123456",
        )

        assert result["feedback_event"]["category"] == FEEDBACK_CATEGORY_UNKNOWN
        assert result["feedback_event"]["evidence_quote"] is None


@pytest.mark.integration
async def test_feedback_replay_is_idempotent(pg_session_maker):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        ledger = CareerLedgerService(db)
        service = CareerInboxService(db)
        record = await ledger.record_manual_application(
            user_id,
            company="Andersen",
            role_title="ML Engineer",
            url=None,
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="123456",
        )
        application_id = record["application"]["application_id"]
        idempotency_key = f"telegram_callback:{uuid4().hex}"

        first = await service.confirm_feedback(
            user_id,
            application_id=application_id,
            category="positive_next_step",
            raw_feedback="Спасибо, ждите тестовое задание.",
            evidence_quote="ждите тестовое задание",
            next_action="Ждать тестовое",
            idempotency_key=idempotency_key,
            actor_id="123456",
        )
        second = await service.confirm_feedback(
            user_id,
            application_id=application_id,
            category="positive_next_step",
            raw_feedback="Спасибо, ждите тестовое задание.",
            evidence_quote="ждите тестовое задание",
            next_action="Ждать тестовое",
            idempotency_key=idempotency_key,
            actor_id="123456",
        )

        assert second["created"] is False
        count = await db.scalar(
            select(func.count(CareerFeedbackEvent.id)).where(
                CareerFeedbackEvent.user_id == user_id
            )
        )
        assert count == 1


@pytest.mark.integration
async def test_user_isolation_across_two_owners(pg_session_maker):
    async with pg_session_maker() as db:
        user_a = await _create_user(db)
        user_b = await _create_user(db)
        service = CareerInboxService(db)
        await service.confirm_manual_lead(
            user_a,
            source="manual",
            raw_text="lead for owner A",
            company="A Corp",
            role_title="Engineer",
            idempotency_key=f"telegram:{uuid4().hex}",
            actor_id="1",
        )

        items_a = await service.list_inbox_items(user_a)
        items_b = await service.list_inbox_items(user_b)

        assert len(items_a) == 1
        assert len(items_b) == 0
