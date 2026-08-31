"""Private Telegram adapter for Russian ML/DL interview practice.

The module deliberately imports aiogram only inside runtime/markup functions,
so its controller and persistence boundary are testable without Telegram or
network access. PostgreSQL is the only source of active-session state.
"""

from __future__ import annotations

from datetime import datetime, timezone

import asyncio
import base64
import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, Protocol
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.database import get_async_session
from app.data.ml_technical_questions import (
    get_ml_technical_topic,
    list_ml_technical_topics,
)
from app.models.core_tables import User
from app.services.career_inbox_service import (
    DRAFT_STATUS_APPROVED,
    DRAFT_STATUS_REJECTED,
    FACTS_BANK_PATH,
    PACKAGE_STATUS_READY,
    ACTIONABLE_IMPORT_ROUTES,
    ROUTE_REVIEW,
    VERDICT_LATER,
    VERDICT_APPLIED,
    VERDICT_FALSE_POSITIVE,
    VERDICT_PREPARE,
    VERDICT_SKIP,
    CareerInboxError,
    CareerInboxService,
    load_facts_bank,
    split_pasted_leads,
    suggest_feedback as suggest_feedback_impl,
    suggest_manual_lead as suggest_manual_lead_impl,
)
from app.services.career_ledger_service import (
    ALLOWED_TRANSITIONS,
    INTENT_CAREER_ADD,
    INTENT_CAREER_ADD_VACANCY_SOURCE,
    INTENT_CAREER_FEEDBACK,
    INTENT_CAREER_MANUAL_LEAD,
    INTENT_CAREER_NEXT_ACTION,
    STATUS_APPLIED,
    STATUS_OFFER,
    STATUS_REJECTED,
    STATUS_SCREENING,
    STATUS_TECHNICAL,
    STATUS_WITHDRAWN,
    CareerLedgerError,
    CareerLedgerService,
    CareerLedgerTransitionError,
)
from app.services.ml_technical_service import (
    ANSWER_KIND_DONT_KNOW,
    ANSWER_KIND_NORMAL,
    MlTechnicalConflictError,
    MlTechnicalService,
)
from app.services.vacancy_refresh_service import (
    SOURCE_ENTRY_MAX_LEN,
    add_vacancy_channel,
    list_vacancy_channels,
    refresh_vacancies,
    resolve_vacancy_channel_names,
)

MAX_SESSION_QUESTIONS = 5
RECENT_APPLICATIONS_DISPLAY_LIMIT = 10

_VACANCY_LINK_PATTERNS = (
    re.compile(r"hh\.ru/vacancy/", re.IGNORECASE),
    re.compile(r"linkedin\.com/jobs/", re.IGNORECASE),
    re.compile(r"greenhouse\.io/[^\s]*?/jobs/", re.IGNORECASE),
    re.compile(r"lever\.co/", re.IGNORECASE),
)

STATUS_LABELS_RU: dict[str, str] = {
    STATUS_APPLIED: "Отклик отправлен",
    STATUS_SCREENING: "Скрининг",
    STATUS_TECHNICAL: "Техническое интервью",
    STATUS_REJECTED: "Отказ",
    STATUS_OFFER: "Оффер",
    STATUS_WITHDRAWN: "Отозвано",
}


def _contains_vacancy_link(text: str) -> bool:
    return any(pattern.search(text) for pattern in _VACANCY_LINK_PATTERNS)


def _parse_direct_career_payload(text: str) -> Optional[tuple[str, str, str]]:
    """Stateless fallback: exactly three non-empty ``|``-separated fields
    whose third field is a recognized vacancy URL. Runs without any pending
    intent, so a plain ``Company | Role | https://hh.ru/vacancy/1`` message
    is recorded even if the owner never opened the career prompt.
    """
    parts = [part.strip() for part in text.split("|")]
    if len(parts) != 3 or not all(parts):
        return None
    company, role_title, url = parts
    if not _contains_vacancy_link(url):
        return None
    return company, role_title, url


@dataclass(frozen=True)
class FallbackButton:
    text: str
    callback_data: str


@dataclass(frozen=True)
class FallbackMarkup:
    inline_keyboard: list[list[FallbackButton]]


def _markup(rows: list[list[tuple[str, str]]]) -> Any:
    """Build aiogram markup at runtime, with a dependency-free test fallback."""
    try:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError:
        return FallbackMarkup(
            [[FallbackButton(text, data) for text, data in row] for row in rows]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=data) for text, data in row]
            for row in rows
        ]
    )


def _compact_uuid(value: str) -> str:
    return base64.urlsafe_b64encode(UUID(value).bytes).decode("ascii").rstrip("=")


def _expand_uuid(value: str) -> str:
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    return str(UUID(bytes=raw))


def _item_callback(action: str, session_id: str, item_id: str) -> str:
    return f"{action}:{_compact_uuid(session_id)}:{_compact_uuid(item_id)}"


def _parse_item_callback(data: str, action: str) -> tuple[str, str]:
    prefix, session_id, item_id = data.split(":", 2)
    if prefix != action:
        raise ValueError("unexpected callback action")
    return _expand_uuid(session_id), _expand_uuid(item_id)


def _career_app_callback(action: str, application_id: str) -> str:
    return f"career:{action}:{_compact_uuid(application_id)}"


def _career_status_callback(application_id: str, to_status: str) -> str:
    return f"career:status:{_compact_uuid(application_id)}:{to_status}"


def _career_item_callback(inbox_item_id: str) -> str:
    return f"career:item:{_compact_uuid(inbox_item_id)}"


def _career_verdict_callback(
    inbox_item_id: str, verdict: str, reason: Optional[str] = None
) -> str:
    tail = f":{reason}" if reason else ""
    return f"career:iv:{_compact_uuid(inbox_item_id)}:{verdict}{tail}"


def _career_favorite_callback(inbox_item_id: str) -> str:
    return f"career:fav:{_compact_uuid(inbox_item_id)}"


def _career_reject_callback(inbox_item_id: str) -> str:
    return f"career:no:{_compact_uuid(inbox_item_id)}"


def _career_applied_callback(inbox_item_id: str) -> str:
    return f"career:ia:{_compact_uuid(inbox_item_id)}"


def _career_feedback_start_callback(application_id: str) -> str:
    return f"career:fb:{_compact_uuid(application_id)}"


def _career_draft_callback(inbox_item_id: str) -> str:
    return f"career:draft:{_compact_uuid(inbox_item_id)}"


def _career_draft_approve_callback(draft_id: str) -> str:
    return f"career:draftok:{_compact_uuid(draft_id)}"


def _career_draft_reject_callback(draft_id: str) -> str:
    return f"career:draftno:{_compact_uuid(draft_id)}"


def _career_draft_copy_callback(draft_id: str) -> str:
    return f"career:draftcopy:{_compact_uuid(draft_id)}"


def _career_draft_facts_callback(inbox_item_id: str) -> str:
    return f"career:draftfacts:{_compact_uuid(inbox_item_id)}"


def _career_package_start_callback(draft_id: str) -> str:
    return f"career:pkg:{_compact_uuid(draft_id)}"


def _career_package_cv_callback(draft_id: str, cv_variant_id: str) -> str:
    return f"career:pkgcv:{_compact_uuid(draft_id)}:{cv_variant_id}"


def _career_package_item_callback(package_id: str) -> str:
    return f"career:pkgitem:{_compact_uuid(package_id)}"


def _career_package_send_callback(package_id: str) -> str:
    return f"career:pkgsend:{_compact_uuid(package_id)}"


def _career_package_confirm_callback(package_id: str, hash_prefix: str) -> str:
    return f"career:pkgok:{_compact_uuid(package_id)}:{hash_prefix}"


def _career_package_cancel_callback() -> str:
    return "career:pkgno"


def _career_prepare_callback(inbox_item_id: str) -> str:
    return f"career:prep:{_compact_uuid(inbox_item_id)}"


def _career_tech_callback(inbox_item_id: str) -> str:
    return f"career:tech:{_compact_uuid(inbox_item_id)}"


def _career_package_applied_callback(package_id: str, hash_prefix: str) -> str:
    return f"career:pkgapplied:{_compact_uuid(package_id)}:{hash_prefix}"


def _parse_career_callback(data: str) -> tuple[str, list[str]]:
    parts = data.split(":")
    if not parts or parts[0] != "career":
        raise ValueError("unexpected callback namespace")
    return parts[1], parts[2:]


class TelegramPracticeGateway(Protocol):
    async def resolve_user(self, telegram_id: int) -> Optional[int]:
        ...

    async def start_daily(
        self, user_id: int, *, practice_date: Any, seed: str
    ) -> dict[str, Any]:
        ...

    async def start_topic(
        self, user_id: int, *, topic_id: str, seed: str
    ) -> dict[str, Any]:
        ...

    async def active(self, user_id: int) -> Optional[dict[str, Any]]:
        ...

    async def progress(self, user_id: int) -> dict[str, Any]:
        ...

    async def skip(
        self, user_id: int, *, session_id: str, item_id: str
    ) -> dict[str, Any]:
        ...

    async def cancel(self, user_id: int) -> dict[str, Any]:
        ...

    async def submit(
        self,
        user_id: int,
        *,
        session_id: str,
        question_id: str,
        answer_text: str,
        answer_kind: str,
        source_event_id: str,
    ) -> dict[str, Any]:
        ...

    async def record_application(
        self,
        user_id: int,
        *,
        company: str,
        role_title: str,
        url: Optional[str],
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        ...

    async def applications_overview(self, user_id: int) -> dict[str, Any]:
        ...

    async def get_application(
        self, user_id: int, application_id: str
    ) -> Optional[dict[str, Any]]:
        ...

    async def update_application_status(
        self,
        user_id: int,
        *,
        application_id: str,
        to_status: str,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        ...

    async def set_application_next_action(
        self,
        user_id: int,
        *,
        application_id: str,
        next_action: str,
        next_action_due_date: Optional[date],
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        ...

    async def set_pending_intent(
        self,
        user_id: int,
        *,
        intent: str,
        application_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        ...

    async def get_active_pending_intent(self, user_id: int) -> Optional[dict[str, Any]]:
        ...

    async def clear_pending_intent(self, user_id: int) -> None:
        ...

    async def discard_expired_pending_intents(self, user_id: int) -> int:
        ...

    async def suggest_manual_lead(self, raw_text: str) -> dict[str, Any]:
        ...

    async def suggest_feedback(self, raw_text: str) -> dict[str, Any]:
        ...

    async def confirm_manual_lead(
        self,
        user_id: int,
        *,
        source: str,
        raw_text: str,
        company: Optional[str],
        role_title: Optional[str],
        questions_for_recruiter: list[str],
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        ...

    async def list_inbox_items(
        self,
        user_id: int,
        *,
        routes: Optional[list[str]] = None,
        include_manual: bool = True,
        only_verdicts: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        ...

    async def get_inbox_item(
        self, user_id: int, inbox_item_id: str
    ) -> Optional[dict[str, Any]]:
        ...

    async def set_inbox_verdict(
        self,
        user_id: int,
        *,
        inbox_item_id: str,
        verdict: str,
        reason: Optional[str] = None,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        ...

    async def confirm_inbox_applied(
        self,
        user_id: int,
        *,
        inbox_item_id: str,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        ...

    async def confirm_feedback(
        self,
        user_id: int,
        *,
        application_id: str,
        category: str,
        raw_feedback: str,
        evidence_quote: Optional[str],
        next_action: Optional[str],
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        ...

    async def generate_cover_letter_draft(
        self,
        user_id: int,
        *,
        inbox_item_id: str,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        ...

    async def approve_cover_letter_draft(
        self, user_id: int, *, draft_id: str, actor_id: str
    ) -> dict[str, Any]:
        ...

    async def reject_cover_letter_draft(
        self, user_id: int, *, draft_id: str, actor_id: str
    ) -> dict[str, Any]:
        ...

    async def get_cover_letter_draft(
        self, user_id: int, draft_id: str
    ) -> Optional[dict[str, Any]]:
        ...

    async def prepare_application_package(
        self,
        user_id: int,
        *,
        inbox_item_id: str,
        cover_draft_id: str,
        cv_variant_id: str,
        actor_id: str,
    ) -> dict[str, Any]:
        ...

    async def list_ready_application_packages(
        self, user_id: int, *, limit: int = 7
    ) -> list[dict[str, Any]]:
        ...

    async def get_application_package(
        self, user_id: int, package_id: str
    ) -> Optional[dict[str, Any]]:
        ...

    async def submit_application_package(
        self,
        user_id: int,
        *,
        package_id: str,
        expected_package_hash: str,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        ...


class DbTelegramPracticeGateway:
    """Thin adapter opening a fresh DB session for every operation."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def resolve_user(self, telegram_id: int) -> Optional[int]:
        async with self.session_factory() as db:
            return await db.scalar(
                select(User.id).where(
                    User.telegram_id == telegram_id,
                    User.deleted_at.is_(None),
                )
            )

    async def start_daily(
        self, user_id: int, *, practice_date: Any, seed: str
    ) -> dict[str, Any]:
        async with self.session_factory() as db:
            return await MlTechnicalService(db).start_daily_session(
                user_id,
                practice_date=practice_date,
                session_seed=seed,
                channel="telegram",
                max_questions=MAX_SESSION_QUESTIONS,
            )

    async def start_topic(
        self, user_id: int, *, topic_id: str, seed: str
    ) -> dict[str, Any]:
        async with self.session_factory() as db:
            result = await MlTechnicalService(db).start_topic_session(
                user_id,
                topic_id,
                seed,
                channel="telegram",
                max_questions=MAX_SESSION_QUESTIONS,
            )
            return await MlTechnicalService(db).get_session_snapshot(
                user_id, result["session_id"]
            )

    async def active(self, user_id: int) -> Optional[dict[str, Any]]:
        async with self.session_factory() as db:
            return await MlTechnicalService(db).get_active_telegram_session(user_id)

    async def progress(self, user_id: int) -> dict[str, Any]:
        async with self.session_factory() as db:
            return await MlTechnicalService(db).get_progress(user_id)

    async def skip(
        self, user_id: int, *, session_id: str, item_id: str
    ) -> dict[str, Any]:
        async with self.session_factory() as db:
            return await MlTechnicalService(db).skip_telegram_item(
                user_id, session_id=session_id, item_id=item_id
            )

    async def cancel(self, user_id: int) -> dict[str, Any]:
        async with self.session_factory() as db:
            return await MlTechnicalService(db).cancel_active_telegram_session(user_id)

    async def submit(
        self,
        user_id: int,
        *,
        session_id: str,
        question_id: str,
        answer_text: str,
        answer_kind: str,
        source_event_id: str,
    ) -> dict[str, Any]:
        # Clean-session contract: user resolution and current-item lookup happen
        # in other sessions. This new session has no implicit transaction before
        # submit_answer takes ownership of its transaction boundaries.
        async with self.session_factory() as db:
            return await MlTechnicalService(db).submit_answer(
                user_id,
                session_id=session_id,
                question_id=question_id,
                answer_text=answer_text,
                answer_kind=answer_kind,
                source_channel="telegram",
                source_event_id=source_event_id,
            )

    async def record_application(
        self,
        user_id: int,
        *,
        company: str,
        role_title: str,
        url: Optional[str],
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        async with self.session_factory() as db:
            return await CareerLedgerService(db).record_manual_application(
                user_id,
                company=company,
                role_title=role_title,
                url=url,
                source="telegram_manual",
                idempotency_key=idempotency_key,
                actor_id=actor_id,
            )

    async def applications_overview(self, user_id: int) -> dict[str, Any]:
        async with self.session_factory() as db:
            service = CareerLedgerService(db)
            summary = await service.get_pipeline_summary(user_id)
            recent = await service.list_applications(
                user_id, limit=RECENT_APPLICATIONS_DISPLAY_LIMIT
            )
            return {"summary": summary, "recent": recent}

    async def get_application(
        self, user_id: int, application_id: str
    ) -> Optional[dict[str, Any]]:
        async with self.session_factory() as db:
            return await CareerLedgerService(db).get_application(
                user_id, application_id
            )

    async def update_application_status(
        self,
        user_id: int,
        *,
        application_id: str,
        to_status: str,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        async with self.session_factory() as db:
            return await CareerLedgerService(db).append_application_event(
                user_id,
                application_id=application_id,
                to_status=to_status,
                idempotency_key=idempotency_key,
                actor_id=actor_id,
            )

    async def set_application_next_action(
        self,
        user_id: int,
        *,
        application_id: str,
        next_action: str,
        next_action_due_date: Optional[date],
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        async with self.session_factory() as db:
            return await CareerLedgerService(db).set_next_action(
                user_id,
                application_id=application_id,
                next_action=next_action,
                next_action_due_date=next_action_due_date,
                idempotency_key=idempotency_key,
                actor_id=actor_id,
            )

    async def set_pending_intent(
        self,
        user_id: int,
        *,
        intent: str,
        application_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        async with self.session_factory() as db:
            return await CareerLedgerService(db).set_pending_intent(
                user_id, intent=intent, application_id=application_id, payload=payload
            )

    async def get_active_pending_intent(self, user_id: int) -> Optional[dict[str, Any]]:
        async with self.session_factory() as db:
            return await CareerLedgerService(db).get_active_pending_intent(user_id)

    async def clear_pending_intent(self, user_id: int) -> None:
        async with self.session_factory() as db:
            await CareerLedgerService(db).clear_pending_intent(user_id)

    async def discard_expired_pending_intents(self, user_id: int) -> int:
        async with self.session_factory() as db:
            return await CareerLedgerService(db).discard_expired_pending_intents(
                user_id
            )

    async def suggest_manual_lead(self, raw_text: str) -> dict[str, Any]:
        from app.services.ai.llm_provider import get_llm_provider

        return await suggest_manual_lead_impl(raw_text, get_llm_provider())

    async def suggest_feedback(self, raw_text: str) -> dict[str, Any]:
        from app.services.ai.llm_provider import get_llm_provider

        return await suggest_feedback_impl(raw_text, get_llm_provider())

    async def confirm_manual_lead(
        self,
        user_id: int,
        *,
        source: str,
        raw_text: str,
        company: Optional[str],
        role_title: Optional[str],
        questions_for_recruiter: list[str],
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        async with self.session_factory() as db:
            return await CareerInboxService(db).confirm_manual_lead(
                user_id,
                source=source,
                raw_text=raw_text,
                company=company,
                role_title=role_title,
                questions_for_recruiter=questions_for_recruiter,
                idempotency_key=idempotency_key,
                actor_id=actor_id,
            )

    async def list_inbox_items(
        self,
        user_id: int,
        *,
        routes: Optional[list[str]] = None,
        include_manual: bool = True,
        only_verdicts: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        async with self.session_factory() as db:
            return await CareerInboxService(db).list_inbox_items(
                user_id,
                routes=routes,
                include_manual=include_manual,
                only_verdicts=only_verdicts,
            )

    async def get_inbox_item(
        self, user_id: int, inbox_item_id: str
    ) -> Optional[dict[str, Any]]:
        async with self.session_factory() as db:
            return await CareerInboxService(db).get_inbox_item(user_id, inbox_item_id)

    async def set_inbox_verdict(
        self,
        user_id: int,
        *,
        inbox_item_id: str,
        verdict: str,
        reason: Optional[str] = None,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        async with self.session_factory() as db:
            return await CareerInboxService(db).set_verdict(
                user_id,
                inbox_item_id=inbox_item_id,
                verdict=verdict,
                reason=reason,
                idempotency_key=idempotency_key,
                actor_id=actor_id,
            )

    async def confirm_inbox_applied(
        self,
        user_id: int,
        *,
        inbox_item_id: str,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        async with self.session_factory() as db:
            return await CareerInboxService(db).confirm_applied(
                user_id,
                inbox_item_id=inbox_item_id,
                idempotency_key=idempotency_key,
                actor_id=actor_id,
            )

    async def confirm_feedback(
        self,
        user_id: int,
        *,
        application_id: str,
        category: str,
        raw_feedback: str,
        evidence_quote: Optional[str],
        next_action: Optional[str],
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        async with self.session_factory() as db:
            return await CareerInboxService(db).confirm_feedback(
                user_id,
                application_id=application_id,
                category=category,
                raw_feedback=raw_feedback,
                evidence_quote=evidence_quote,
                next_action=next_action,
                idempotency_key=idempotency_key,
                actor_id=actor_id,
            )

    async def generate_cover_letter_draft(
        self,
        user_id: int,
        *,
        inbox_item_id: str,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        from app.services.ai.llm_provider import get_llm_provider

        async with self.session_factory() as db:
            return await CareerInboxService(db).generate_cover_letter_draft(
                user_id,
                inbox_item_id=inbox_item_id,
                provider=get_llm_provider(),
                idempotency_key=idempotency_key,
                actor_id=actor_id,
            )

    async def approve_cover_letter_draft(
        self, user_id: int, *, draft_id: str, actor_id: str
    ) -> dict[str, Any]:
        async with self.session_factory() as db:
            return await CareerInboxService(db).approve_cover_letter_draft(
                user_id, draft_id=draft_id, actor_id=actor_id
            )

    async def reject_cover_letter_draft(
        self, user_id: int, *, draft_id: str, actor_id: str
    ) -> dict[str, Any]:
        async with self.session_factory() as db:
            return await CareerInboxService(db).reject_cover_letter_draft(
                user_id, draft_id=draft_id, actor_id=actor_id
            )

    async def get_cover_letter_draft(
        self, user_id: int, draft_id: str
    ) -> Optional[dict[str, Any]]:
        async with self.session_factory() as db:
            return await CareerInboxService(db).get_cover_letter_draft(
                user_id, draft_id
            )

    async def prepare_application_package(
        self,
        user_id: int,
        *,
        inbox_item_id: str,
        cover_draft_id: str,
        cv_variant_id: str,
        actor_id: str,
    ) -> dict[str, Any]:
        async with self.session_factory() as db:
            return await CareerInboxService(db).prepare_application_package(
                user_id,
                inbox_item_id=inbox_item_id,
                cover_draft_id=cover_draft_id,
                cv_variant_id=cv_variant_id,
                actor_id=actor_id,
            )

    async def list_ready_application_packages(
        self, user_id: int, *, limit: int = 7
    ) -> list[dict[str, Any]]:
        async with self.session_factory() as db:
            return await CareerInboxService(db).list_ready_application_packages(
                user_id, limit=limit
            )

    async def get_application_package(
        self, user_id: int, package_id: str
    ) -> Optional[dict[str, Any]]:
        async with self.session_factory() as db:
            return await CareerInboxService(db).get_application_package(
                user_id, package_id
            )

    async def submit_application_package(
        self,
        user_id: int,
        *,
        package_id: str,
        expected_package_hash: str,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        async with self.session_factory() as db:
            return await CareerInboxService(db).submit_application_package(
                user_id,
                package_id=package_id,
                expected_package_hash=expected_package_hash,
                idempotency_key=idempotency_key,
                actor_id=actor_id,
            )


class MlTechnicalTelegramController:
    def __init__(
        self,
        gateway: TelegramPracticeGateway,
        *,
        allowed_ids: frozenset[int],
        timezone_name: str = "Europe/Moscow",
        career_inbox_enabled: bool = False,
        career_cover_letter_draft_enabled: bool = False,
        career_vacancy_refresh_enabled: bool = False,
        vacancy_refresh_repo_path: str = "",
        career_ready_queue_enabled: bool = False,
        facts_bank_path: Path = FACTS_BANK_PATH,
    ) -> None:
        self.gateway = gateway
        self.allowed_ids = allowed_ids
        self.career_inbox_enabled = career_inbox_enabled
        self.career_cover_letter_draft_enabled = career_cover_letter_draft_enabled
        self.career_vacancy_refresh_enabled = career_vacancy_refresh_enabled
        self.vacancy_refresh_repo_path = vacancy_refresh_repo_path
        self.career_ready_queue_enabled = career_ready_queue_enabled
        self.facts_bank_path = facts_bank_path
        self._vacancy_refresh_in_progress = False
        try:
            self.timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            if timezone_name != "Europe/Moscow":
                raise
            # Windows Python installations may not ship the IANA tz database.
            # Moscow has used fixed UTC+3 since 2014.
            self.timezone = timezone(timedelta(hours=3), name="Europe/Moscow")

    @staticmethod
    def _message(event: Any) -> Any:
        return getattr(event, "message", None) or event

    async def _callback_ack(self, event: Any, text: str = "") -> None:
        if hasattr(event, "answer") and getattr(event, "message", None) is not None:
            await event.answer(text)

    @staticmethod
    def _telegram_id(event: Any) -> int:
        message = MlTechnicalTelegramController._message(event)
        actor = (
            getattr(event, "from_user", None)
            if getattr(event, "message", None) is not None
            else getattr(message, "from_user", None)
        )
        return int(actor.id) if actor is not None else int(message.chat.id)

    async def _authorize(self, event: Any) -> Optional[int]:
        message = self._message(event)
        chat = message.chat
        if getattr(chat, "type", "private") != "private":
            await message.answer("Бот работает только в личном чате.")
            await self._callback_ack(event)
            return None
        telegram_id = self._telegram_id(event)
        if telegram_id not in self.allowed_ids:
            await message.answer(f"Доступ не настроен. Ваш Telegram ID: {telegram_id}.")
            await self._callback_ack(event)
            return None
        user_id = await self.gateway.resolve_user(telegram_id)
        if user_id is None:
            await message.answer(
                f"Telegram ID {telegram_id} разрешен, но не связан с профилем EnglishFriend. "
                "Добавьте его в существующую запись пользователя."
            )
            await self._callback_ack(event)
            return None
        return user_id

    @staticmethod
    def _home_markup() -> Any:
        return _markup(
            [
                [("Сегодня", "menu:today")],
                [("Срез по теме", "menu:slice")],
                [("Прогресс ML/DL", "menu:progress")],
                [("Карьера", "menu:career")],
            ]
        )

    def _career_markup(self) -> Any:
        """Compact Career root (one-flow UX v0.1): the actionable queue,
        refresh, applications/feedback and a low-frequency ``Ещё`` submenu.
        Low-frequency actions moved to :meth:`_career_more_markup` remain
        reachable there - no capability is deleted."""
        rows: list[list[tuple[str, str]]] = []
        if self.career_inbox_enabled:
            rows.append([("Вакансии", "career:inbox")])
        if self.career_vacancy_refresh_enabled:
            rows.append([("Обновить вакансии", "career:refresh")])
        rows.append([("Отклики и ответы", "career:list")])
        rows.append([("Ещё", "career:more")])
        rows.append([("Назад", "career:back")])
        return _markup(rows)

    def _career_more_markup(self) -> Any:
        rows: list[list[tuple[str, str]]] = [
            [("Записать отправленный отклик", "career:add")],
        ]
        if self.career_inbox_enabled:
            rows.append([("Добавить контакт или ответ", "career:lead")])
        if self.career_vacancy_refresh_enabled:
            rows.append([("Источники вакансий", "career:sources")])
            rows.append([("Добавить источник", "career:addsrc")])
        if self.career_ready_queue_enabled:
            rows.append([("Готовые (все пакеты)", "career:ready")])
        rows.append([("Назад", "career:back")])
        return _markup(rows)

    @staticmethod
    def _topics_markup(progress: dict[str, Any]) -> Any:
        rows: list[list[tuple[str, str]]] = []
        for topic_progress in progress.get("topics", []):
            topic = get_ml_technical_topic(topic_progress["topic_id"])
            count = int(topic_progress.get("total_questions") or 0)
            if topic is None:
                continue
            if count:
                rows.append(
                    [(f"{topic['title_ru']} ({count})", f"slice:{topic['id']}")]
                )
        return _markup(rows)

    @staticmethod
    def _task_markup(snapshot: dict[str, Any]) -> Any:
        item = snapshot["current_item"]
        return _markup(
            [
                [
                    (
                        "Не знаю - показать разбор",
                        _item_callback("dk", snapshot["session_id"], item["item_id"]),
                    )
                ],
                [
                    (
                        "Пропустить",
                        _item_callback("sk", snapshot["session_id"], item["item_id"]),
                    )
                ],
            ]
        )

    async def _show_current(
        self, message: Any, user_id: int, snapshot: Optional[dict[str, Any]] = None
    ) -> None:
        snapshot = snapshot or await self.gateway.active(user_id)
        if snapshot is None:
            await message.answer(
                "Нет активной тренировки. Выберите /today или /slice.",
                reply_markup=self._home_markup(),
            )
            return
        if snapshot.get("status") == "cancelled":
            await message.answer(
                "Дневная тренировка на эту дату была отменена. "
                "Она не возобновляется автоматически. Можно выбрать /slice.",
                reply_markup=self._home_markup(),
            )
            return
        item = snapshot.get("current_item")
        if item is None:
            await message.answer(
                "Тренировка завершена.", reply_markup=self._home_markup()
            )
            return
        question = item["question"]
        await message.answer(
            f"Вопрос {item['position']}/{snapshot['total_items']}\n\n"
            f"{question['question_ru']}\n\n"
            "Ответьте следующим сообщением.",
            reply_markup=self._task_markup(snapshot),
        )

    async def on_start(self, message: Any) -> None:
        user_id = await self._authorize(message)
        if user_id is None:
            return
        await self.gateway.clear_pending_intent(user_id)
        await message.answer(
            "Выберите тренировку по ML/DL, посмотрите прогресс или откройте "
            "карьерный раздел.",
            reply_markup=self._home_markup(),
        )

    async def on_today(self, message: Any) -> None:
        user_id = await self._authorize(message)
        if user_id is None:
            return
        await self._start_today(message, user_id)

    async def _start_today(self, message: Any, user_id: int) -> None:
        today = datetime.now(self.timezone).date()
        try:
            snapshot = await self.gateway.start_daily(
                user_id, practice_date=today, seed=f"{user_id}:{today.isoformat()}"
            )
        except MlTechnicalConflictError:
            snapshot = await self.gateway.active(user_id)
            await message.answer(
                "У вас уже есть активная тренировка. Сначала завершите или отмените ее."
            )
        await self._show_current(message, user_id, snapshot)

    async def on_slice(self, message: Any) -> None:
        user_id = await self._authorize(message)
        if user_id is None:
            return
        progress = await self.gateway.progress(user_id)
        await message.answer(
            "Выберите тему:", reply_markup=self._topics_markup(progress)
        )

    async def on_slice_topic(self, callback: Any) -> None:
        user_id = await self._authorize(callback)
        if user_id is None:
            return
        topic_id = str(callback.data).split(":", 1)[1]
        if get_ml_technical_topic(topic_id) is None:
            await callback.answer("Тема пока пуста")
            return
        try:
            snapshot = await self.gateway.start_topic(
                user_id,
                topic_id=topic_id,
                seed=f"telegram:{user_id}:{topic_id}",
            )
        except MlTechnicalConflictError:
            snapshot = await self.gateway.active(user_id)
            await callback.answer("Уже есть активная тренировка")
        except ValueError:
            await callback.answer("Тема пока пуста")
            return
        else:
            await callback.answer()
        await self._show_current(callback.message, user_id, snapshot)

    async def on_progress(self, message: Any) -> None:
        user_id = await self._authorize(message)
        if user_id is None:
            return
        await self._show_progress(message, user_id)

    async def _show_progress(self, message: Any, user_id: int) -> None:
        progress = await self.gateway.progress(user_id)
        topic_titles = {
            topic["id"]: topic["title_ru"] for topic in list_ml_technical_topics()
        }
        non_empty = [
            topic for topic in progress.get("topics", []) if topic["total_questions"]
        ]
        weakest = sorted(
            non_empty,
            key=lambda topic: (
                topic["average_latest_score_percent"]
                if topic["average_latest_score_percent"] is not None
                else -1,
                topic["topic_id"],
            ),
        )[:3]
        weak_lines = [
            f"- {topic_titles.get(t['topic_id'], t['topic_id'])}: "
            f"{t['average_latest_score_percent'] if t['average_latest_score_percent'] is not None else 0}%"
            for t in weakest
        ]
        await message.answer(
            "Прогресс ML/DL\n"
            f"Освоено: {progress['passed']}/{progress['total_questions']}\n"
            f"К повторению: {progress['due_for_repetition']}\n"
            f"Ожидают проверки: {progress['needs_review']}\n"
            "Слабые темы:\n"
            + ("\n".join(weak_lines) if weak_lines else "- пока нет данных"),
            reply_markup=self._home_markup(),
        )

    async def on_skip(self, message: Any) -> None:
        user_id = await self._authorize(message)
        if user_id is None:
            return
        snapshot = await self.gateway.active(user_id)
        if snapshot is None or snapshot.get("current_item") is None:
            await message.answer("Нет активного вопроса.")
            return
        item = snapshot["current_item"]
        result = await self.gateway.skip(
            user_id, session_id=snapshot["session_id"], item_id=item["item_id"]
        )
        await message.answer(
            "Вопрос пропущен." if result["changed"] else "Уже обработано."
        )
        await self._show_current(message, user_id, result["session"])

    async def on_skip_callback(self, callback: Any) -> None:
        user_id = await self._authorize(callback)
        if user_id is None:
            return
        try:
            session_id, item_id = _parse_item_callback(str(callback.data), "sk")
            result = await self.gateway.skip(
                user_id, session_id=session_id, item_id=item_id
            )
        except (ValueError, MlTechnicalConflictError):
            await callback.answer("Кнопка устарела")
            return
        await callback.answer("Пропущено" if result["changed"] else "Уже обработано")
        await self._show_current(callback.message, user_id, result["session"])

    async def on_cancel(self, message: Any) -> None:
        user_id = await self._authorize(message)
        if user_id is None:
            return
        await self.gateway.clear_pending_intent(user_id)
        result = await self.gateway.cancel(user_id)
        await message.answer(
            "Тренировка отменена."
            if result["cancelled"]
            else "Нет активной тренировки.",
            reply_markup=self._home_markup(),
        )

    async def _submit_current(
        self,
        event: Any,
        *,
        user_id: int,
        snapshot: dict[str, Any],
        answer_text: str,
        answer_kind: str,
        source_event_id: str,
    ) -> None:
        message = self._message(event)
        item = snapshot["current_item"]
        try:
            result = await self.gateway.submit(
                user_id,
                session_id=snapshot["session_id"],
                question_id=item["question"]["id"],
                answer_text=answer_text,
                answer_kind=answer_kind,
                source_event_id=source_event_id,
            )
        except MlTechnicalConflictError:
            await self._callback_ack(event, "Уже обработано")
            await self._show_current(message, user_id)
            return

        await self._callback_ack(event)
        review = result["review"]
        if review["status"] == "needs_review":
            summary = "Ответ сохранен и ожидает ручной проверки."
        else:
            summary = f"Оценка: {review['score_percent']}%."
            if review.get("feedback"):
                summary += f"\n{review['feedback']}"
        # Reference is emitted only after gateway.submit has persisted an attempt.
        await message.answer(
            f"{summary}\n\nРазбор:\n{result['reference_explanation_ru']}"
        )
        await self._show_current(message, user_id)

    async def on_dont_know(self, callback: Any) -> None:
        user_id = await self._authorize(callback)
        if user_id is None:
            return
        try:
            session_id, item_id = _parse_item_callback(str(callback.data), "dk")
        except ValueError:
            await callback.answer("Кнопка устарела")
            return
        snapshot = await self.gateway.active(user_id)
        if (
            snapshot is None
            or snapshot.get("current_item") is None
            or snapshot["session_id"] != session_id
            or snapshot["current_item"]["item_id"] != item_id
        ):
            await callback.answer("Кнопка устарела")
            return
        source_event_id = f"callback:{getattr(callback, 'id', str(callback.data))}"
        await self._submit_current(
            callback,
            user_id=user_id,
            snapshot=snapshot,
            answer_text="",
            answer_kind=ANSWER_KIND_DONT_KNOW,
            source_event_id=source_event_id,
        )

    async def on_text(self, message: Any) -> None:
        # Routing invariant: command -> active pending career intent ->
        # structurally valid direct career payload -> vacancy-link guard ->
        # active ML answer -> no-active-session help. A career message must
        # never reach local Qwen grading. Correctness never depends on
        # ``message.reply_to_message`` - PostgreSQL is the only pending state.
        if str(message.text or "").lstrip().startswith("/"):
            await self.on_unknown_command(message)
            return
        user_id = await self._authorize(message)
        if user_id is None:
            return

        await self.gateway.discard_expired_pending_intents(user_id)
        pending = await self.gateway.get_active_pending_intent(user_id)
        if pending is not None:
            if pending["intent"] == INTENT_CAREER_ADD:
                await self._handle_career_add_reply(message, user_id)
                return
            if pending["intent"] == INTENT_CAREER_NEXT_ACTION:
                await self._handle_career_next_action_reply(
                    message, user_id, pending["application_id"]
                )
                return
            if pending["intent"] == INTENT_CAREER_MANUAL_LEAD:
                await self._handle_manual_lead_paste(message, user_id)
                return
            if pending["intent"] == INTENT_CAREER_FEEDBACK:
                await self._handle_feedback_paste(
                    message, user_id, pending["application_id"]
                )
                return
            if pending["intent"] == INTENT_CAREER_ADD_VACANCY_SOURCE:
                await self._handle_add_vacancy_source_reply(message, user_id)
                return

        direct_payload = _parse_direct_career_payload(str(message.text or ""))
        if direct_payload is not None:
            company, role_title, url = direct_payload
            await self._record_and_confirm_application(
                message, user_id, company, role_title, url
            )
            return

        if _contains_vacancy_link(str(message.text or "")):
            await message.answer(
                "Похоже на ссылку на вакансию. Чтобы записать отклик, "
                "нажмите Карьера -> Записать отправленный отклик.",
                reply_markup=self._career_markup(),
            )
            return

        snapshot = await self.gateway.active(user_id)
        if snapshot is None or snapshot.get("current_item") is None:
            await message.answer("Нет активного вопроса. Выберите /today или /slice.")
            return
        source_event_id = f"message:{message.chat.id}:{message.message_id}"
        await self._submit_current(
            message,
            user_id=user_id,
            snapshot=snapshot,
            answer_text=str(message.text or ""),
            answer_kind=ANSWER_KIND_NORMAL,
            source_event_id=source_event_id,
        )

    _CAREER_ADD_PROMPT_TEXT = (
        "Добавление отклика\n"
        "Ответьте на это сообщение одной строкой:\n"
        "Компания | Роль | Ссылка\n\n"
        "Пример:\n"
        "Acme | ML Engineer | https://example.com/jobs/42"
    )
    _CAREER_NEXT_ACTION_PROMPT_TEXT = "Действие | ГГГГ-ММ-ДД (дата необязательна)"

    @staticmethod
    def _cancel_markup() -> Any:
        return _markup([[("Отмена", "career:cancel")]])

    async def _prompt_career_add(
        self, message: Any, *, error: Optional[str] = None
    ) -> None:
        text = self._CAREER_ADD_PROMPT_TEXT
        if error:
            text = f"{error}\n\n{text}"
        await message.answer(text, reply_markup=self._cancel_markup())

    @staticmethod
    def _career_add_validation_error(parts: list[str]) -> Optional[str]:
        if len(parts) > 3:
            return "Слишком много полей. Используйте два разделителя |."
        if not parts or not parts[0]:
            return "Не указана компания."
        if len(parts) < 2 or not parts[1]:
            return "Не указана роль."
        if len(parts) < 3 or not parts[2]:
            return "Не указана ссылка."
        return None

    async def _record_and_confirm_application(
        self, message: Any, user_id: int, company: str, role_title: str, url: str
    ) -> bool:
        """Record one application and reply. Returns whether it succeeded, so
        callers holding a pending intent know whether to clear it.
        """
        idempotency_key = f"telegram:{message.chat.id}:{message.message_id}"
        try:
            result = await self.gateway.record_application(
                user_id,
                company=company,
                role_title=role_title,
                url=url or None,
                idempotency_key=idempotency_key,
                actor_id=str(self._telegram_id(message)),
            )
        except CareerLedgerError as exc:
            await self._prompt_career_add(message, error=str(exc))
            return False
        application = result["application"]
        status_label = STATUS_LABELS_RU.get(
            application["status"], application["status"]
        )
        await message.answer(
            "Записано.\n"
            f"{application.get('company')} - {application.get('role_title')}\n"
            f"Статус: {status_label}",
            reply_markup=self._career_markup(),
        )
        return True

    async def _handle_career_add_reply(self, message: Any, user_id: int) -> None:
        parts = [part.strip() for part in str(message.text or "").split("|")]
        validation_error = self._career_add_validation_error(parts)
        if validation_error:
            await self._prompt_career_add(
                message, error=f"{validation_error} Повторите ввод."
            )
            return
        company, role_title, url = parts
        if await self._record_and_confirm_application(
            message, user_id, company, role_title, url
        ):
            await self.gateway.clear_pending_intent(user_id)

    async def on_applied(self, message: Any) -> None:
        user_id = await self._authorize(message)
        if user_id is None:
            return
        _command, _, rest = str(message.text or "").partition(" ")
        rest = rest.strip()
        if not rest:
            await self.gateway.set_pending_intent(user_id, intent=INTENT_CAREER_ADD)
            await self._prompt_career_add(message)
            return
        parts = [part.strip() for part in rest.split("|")]
        validation_error = self._career_add_validation_error(parts)
        if validation_error:
            await self.gateway.set_pending_intent(user_id, intent=INTENT_CAREER_ADD)
            await self._prompt_career_add(
                message, error=f"{validation_error} Повторите ввод."
            )
            return
        company, role_title, url = parts
        await self._record_and_confirm_application(
            message, user_id, company, role_title, url
        )

    async def _show_career_list(self, message: Any, user_id: int) -> None:
        overview = await self.gateway.applications_overview(user_id)
        summary = overview["summary"]
        lines = [f"Всего заявок: {summary['total']}"]
        for status, count in summary["by_status"].items():
            lines.append(f"- {STATUS_LABELS_RU.get(status, status)}: {count}")
        recent = overview["recent"][:RECENT_APPLICATIONS_DISPLAY_LIMIT]
        rows: list[list[tuple[str, str]]] = [
            [
                (
                    f"{item.get('company')} - {item.get('role_title')}",
                    _career_app_callback("app", item["application_id"]),
                )
            ]
            for item in recent
        ]
        rows.append([("Назад", "career:back")])
        await message.answer("\n".join(lines), reply_markup=_markup(rows))

    async def on_applications(self, message: Any) -> None:
        user_id = await self._authorize(message)
        if user_id is None:
            return
        await self._show_career_list(message, user_id)

    async def _show_career_application(
        self, message: Any, user_id: int, application_id: str
    ) -> None:
        application = await self.gateway.get_application(user_id, application_id)
        if application is None:
            await message.answer("Заявка не найдена.")
            return
        status = application["status"]
        lines = [
            f"{application.get('company')} - {application.get('role_title')}",
            f"Ссылка: {application.get('url') or 'не указана'}",
            f"Статус: {STATUS_LABELS_RU.get(status, status)}",
        ]
        next_action = application.get("next_action")
        if next_action:
            due_date = application.get("next_action_due_date")
            lines.append(
                f"Следующее действие: {next_action}"
                + (f" ({due_date})" if due_date else "")
            )
        rows: list[list[tuple[str, str]]] = [
            [
                (
                    STATUS_LABELS_RU.get(to_status, to_status),
                    _career_status_callback(application_id, to_status),
                )
            ]
            for to_status in sorted(ALLOWED_TRANSITIONS.get(status, frozenset()))
        ]
        rows.append(
            [
                (
                    "Задать следующее действие",
                    _career_app_callback("next", application_id),
                )
            ]
        )
        if self.career_inbox_enabled:
            rows.append(
                [("Добавить feedback", _career_feedback_start_callback(application_id))]
            )
        rows.append([("Назад", "career:list")])
        await message.answer("\n".join(lines), reply_markup=_markup(rows))

    async def _handle_career_status_callback(
        self, callback: Any, user_id: int, application_id: str, to_status: str
    ) -> None:
        idempotency_key = (
            f"telegram_callback:{getattr(callback, 'id', str(callback.data))}"
        )
        try:
            await self.gateway.update_application_status(
                user_id,
                application_id=application_id,
                to_status=to_status,
                idempotency_key=idempotency_key,
                actor_id=str(self._telegram_id(callback)),
            )
        except CareerLedgerTransitionError:
            await callback.answer("Недопустимый переход")
            return
        except CareerLedgerError:
            await callback.answer("Заявка не найдена")
            return
        await callback.answer("Статус обновлен")
        await self._show_career_application(callback.message, user_id, application_id)

    async def _prompt_career_next_action(
        self, message: Any, *, error: Optional[str] = None
    ) -> None:
        text = self._CAREER_NEXT_ACTION_PROMPT_TEXT
        if error:
            text = f"{error}\n\n{text}"
        await message.answer(text, reply_markup=self._cancel_markup())

    async def _handle_career_next_action_reply(
        self, message: Any, user_id: int, application_id: str
    ) -> None:
        parts = [part.strip() for part in str(message.text or "").split("|")]
        if len(parts) > 2:
            await self._prompt_career_next_action(
                message,
                error="Слишком много полей. Формат: Действие | ГГГГ-ММ-ДД",
            )
            return
        action_text = parts[0] if parts else ""
        date_text = parts[1] if len(parts) > 1 else ""
        if not action_text:
            await self._prompt_career_next_action(message, error="Не указано действие.")
            return
        due_date: Optional[date] = None
        if date_text:
            try:
                due_date = datetime.strptime(date_text, "%Y-%m-%d").date()
            except ValueError:
                await self._prompt_career_next_action(
                    message,
                    error="Неверный формат даты. Используйте ГГГГ-ММ-ДД.",
                )
                return
        idempotency_key = f"telegram:{message.chat.id}:{message.message_id}"
        try:
            await self.gateway.set_application_next_action(
                user_id,
                application_id=application_id,
                next_action=action_text,
                next_action_due_date=due_date,
                idempotency_key=idempotency_key,
                actor_id=str(self._telegram_id(message)),
            )
        except CareerLedgerError as exc:
            await self._prompt_career_next_action(message, error=str(exc))
            return
        await self.gateway.clear_pending_intent(user_id)
        await message.answer("Следующее действие обновлено.")
        await self._show_career_application(message, user_id, application_id)

    async def _career_resolve_application_id(
        self, callback: Any, raw: str
    ) -> Optional[str]:
        try:
            return _expand_uuid(raw)
        except (ValueError, TypeError):
            await callback.answer("Кнопка устарела")
            return None

    async def _on_career_callback_more(self, callback: Any, user_id: int) -> None:
        await callback.answer()
        await callback.message.answer("Ещё", reply_markup=self._career_more_markup())

    async def _on_career_callback_add(self, callback: Any, user_id: int) -> None:
        await self.gateway.set_pending_intent(user_id, intent=INTENT_CAREER_ADD)
        await callback.answer()
        await self._prompt_career_add(callback.message)

    async def _on_career_callback_list(self, callback: Any, user_id: int) -> None:
        await callback.answer()
        await self._show_career_list(callback.message, user_id)

    async def _on_career_callback_back(self, callback: Any, user_id: int) -> None:
        await self.gateway.clear_pending_intent(user_id)
        await callback.answer()
        await callback.message.answer("Главное меню", reply_markup=self._home_markup())

    async def _on_career_callback_cancel(self, callback: Any, user_id: int) -> None:
        await self.gateway.clear_pending_intent(user_id)
        await callback.answer("Отменено")
        await callback.message.answer(
            "Ввод отменен.", reply_markup=self._career_markup()
        )

    async def _on_career_callback_app(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        application_id = await self._career_resolve_application_id(callback, rest[0])
        if application_id is None:
            return
        await callback.answer()
        await self._show_career_application(callback.message, user_id, application_id)

    async def _on_career_callback_status(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        application_id = await self._career_resolve_application_id(callback, rest[0])
        if application_id is None:
            return
        await self._handle_career_status_callback(
            callback, user_id, application_id, rest[1]
        )

    async def _on_career_callback_next(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        application_id = await self._career_resolve_application_id(callback, rest[0])
        if application_id is None:
            return
        await self.gateway.set_pending_intent(
            user_id, intent=INTENT_CAREER_NEXT_ACTION, application_id=application_id
        )
        await callback.answer()
        await self._prompt_career_next_action(callback.message)

    # ── Career Inbox v0: manual lead (preview/confirm) ────────────────────

    _MANUAL_LEAD_PROMPT_TEXT = (
        "Добавление контакта или ответа\n"
        "Вставьте или перешлите сообщение рекрутера одним текстом."
    )

    def _lead_preview_markup(self, index: int) -> Any:
        return _markup(
            [
                [("Подтвердить", f"career:leadok:{index}")],
                [("Пропустить этот лид", f"career:leadskip:{index}")],
                [("Отмена", "career:cancel")],
            ]
        )

    @staticmethod
    def _lead_preview_text(entry: dict[str, Any], position: int, total: int) -> str:
        suggestion = entry.get("suggestion") or {}
        questions = suggestion.get("questions_for_recruiter") or []
        evidence = suggestion.get("evidence_quote")
        header = "Черновик лида (не сохранён, требует подтверждения)"
        if total > 1:
            header += f" — Лид {position} из {total}"
        lines = [
            header + ":",
            f"Компания: {suggestion.get('company') or 'не определена'}",
            f"Роль: {suggestion.get('role_title') or 'не определена'}",
            f"Тип: {suggestion.get('event_kind') or 'unknown'}",
        ]
        if questions:
            lines.append("Вопросы:")
            lines += [f"- {q}" for q in questions]
        lines.append(f"Цитата: {evidence or 'не найдена'}")
        return "\n".join(lines)

    @staticmethod
    def _active_lead_queue(
        pending: Optional[dict[str, Any]],
    ) -> tuple[Optional[list[dict[str, Any]]], Optional[int]]:
        if pending is None or pending.get("intent") != INTENT_CAREER_MANUAL_LEAD:
            return None, None
        payload = pending.get("payload") or {}
        queue = payload.get("queue")
        index = payload.get("index")
        if not queue or index is None or not (0 <= index < len(queue)):
            return None, None
        return queue, index

    async def _advance_lead_queue(
        self, callback: Any, user_id: int, queue: list[dict[str, Any]], index: int
    ) -> None:
        next_index = index + 1
        if next_index >= len(queue):
            await self.gateway.clear_pending_intent(user_id)
            await callback.message.answer(
                f"Готово: обработано {len(queue)} из {len(queue)}.",
                reply_markup=self._career_markup(),
            )
            return
        await self.gateway.set_pending_intent(
            user_id,
            intent=INTENT_CAREER_MANUAL_LEAD,
            payload={"queue": queue, "index": next_index},
        )
        await callback.message.answer(
            self._lead_preview_text(queue[next_index], next_index + 1, len(queue)),
            reply_markup=self._lead_preview_markup(next_index),
        )

    async def _on_career_callback_lead(self, callback: Any, user_id: int) -> None:
        if not self.career_inbox_enabled:
            await callback.answer("Функция выключена")
            return
        await self.gateway.set_pending_intent(user_id, intent=INTENT_CAREER_MANUAL_LEAD)
        await callback.answer()
        await callback.message.answer(
            self._MANUAL_LEAD_PROMPT_TEXT, reply_markup=self._cancel_markup()
        )

    async def _handle_manual_lead_paste(self, message: Any, user_id: int) -> None:
        raw_text = str(message.text or "").strip()
        if not raw_text:
            await message.answer(
                self._MANUAL_LEAD_PROMPT_TEXT, reply_markup=self._cancel_markup()
            )
            return
        segments = split_pasted_leads(raw_text)
        queue = []
        for segment in segments:
            suggestion = await self.gateway.suggest_manual_lead(segment)
            queue.append(
                {"segment_id": str(uuid4()), "raw_text": segment, "suggestion": suggestion}
            )
        await self.gateway.set_pending_intent(
            user_id,
            intent=INTENT_CAREER_MANUAL_LEAD,
            payload={"queue": queue, "index": 0},
        )
        total = len(queue)
        note = f"Распознано лидов: {total}.\n\n" if total > 1 else ""
        await message.answer(
            note + self._lead_preview_text(queue[0], 1, total),
            reply_markup=self._lead_preview_markup(0),
        )

    async def _on_career_callback_leadok(
        self, callback: Any, user_id: int, expected_index: str
    ) -> None:
        pending = await self.gateway.get_active_pending_intent(user_id)
        queue, index = self._active_lead_queue(pending)
        if queue is None or str(index) != expected_index:
            await callback.answer("Черновик устарел")
            return
        entry = queue[index]
        suggestion = entry.get("suggestion") or {}
        idempotency_key = f"telegram_lead:{entry['segment_id']}"
        try:
            result = await self.gateway.confirm_manual_lead(
                user_id,
                source="manual",
                raw_text=entry["raw_text"],
                company=suggestion.get("company"),
                role_title=suggestion.get("role_title"),
                questions_for_recruiter=suggestion.get("questions_for_recruiter") or [],
                idempotency_key=idempotency_key,
                actor_id=str(self._telegram_id(callback)),
            )
        except CareerInboxError as exc:
            await callback.answer("Ошибка")
            await callback.message.answer(str(exc))
            return
        await callback.answer("Сохранено")
        item = result["inbox_item"]
        await callback.message.answer(
            f"Добавлено во Входящие: {item.get('company') or 'без компании'} - "
            f"{item.get('role_title') or 'без роли'}"
        )
        await self._advance_lead_queue(callback, user_id, queue, index)

    async def _on_career_callback_leadskip(
        self, callback: Any, user_id: int, expected_index: str
    ) -> None:
        pending = await self.gateway.get_active_pending_intent(user_id)
        queue, index = self._active_lead_queue(pending)
        if queue is None or str(index) != expected_index:
            await callback.answer("Черновик устарел")
            return
        await callback.answer("Пропущено")
        await self._advance_lead_queue(callback, user_id, queue, index)

    # ── Career Inbox v0: bounded list, detail, verdicts ────────────────────

    _VERDICT_LABELS_RU: dict[str, str] = {
        "ask": "Спросить",
        "prepare": "Готовить",
        "skip": "Пропустить",
        "false_positive": "Ошибка парсера",
        "applied": "Отклик отправлен",
        "later": "В избранном",
    }

    # Why a vacancy was rejected, as a CLOSED vocabulary rather than free text.
    #
    # This is calibration data, not decoration: the stored value names the gate
    # that got it wrong, so "how often does role_scope let through something the
    # owner does not want" becomes countable. Free text would have to be
    # categorised by an LLM to be counted - and the LLM is the thing being
    # measured, so that argument is circular.
    #
    # (compact callback code, button label, stored owner_reason)
    _SKIP_REASONS: tuple[tuple[str, str, str], ...] = (
        ("role", "Не та роль", "role_scope"),
        ("legal", "Не берут из РФ", "legal_hire_from_rf"),
        ("comp", "Мало денег", "comp_threshold"),
        ("lang", "Английский", "language_path"),
        # Not a gate error: the gates were right when the post was written.
        ("closed", "Вакансия закрыта", "vacancy_closed"),
        # Also not a gate error - the role fits, the application channel does
        # not. Kept separate from "other" because lumping it in would read as
        # "the gates were wrong" during calibration, when in fact nothing about
        # the vacancy was misjudged.
        ("extreg", "Нужна регистрация на площадке", "external_platform_signup"),
        ("other", "Другое", "other"),
    )

    # Unknown codes are rejected as stale buttons rather than silently stored.
    _SKIP_REASON_BY_CODE: dict[str, tuple[str, str]] = {
        code: (label, stored) for code, label, stored in _SKIP_REASONS
    }

    @staticmethod
    async def _render_card(message: Any, text: str, markup: Any) -> None:
        """Edit the existing bot message in place when possible.

        Falls back to sending a new message when the transport has no
        edit_text (test doubles) or the edit itself fails (e.g. Telegram
        rejects a no-op edit), so the user always sees a response either way.
        """
        edit = getattr(message, "edit_text", None)
        if edit is not None:
            try:
                await edit(text, reply_markup=markup)
                return
            except Exception:
                pass
        await message.answer(text, reply_markup=markup)

    _ROUTE_REASON_RU = {
        "apply_candidate": "Похоже на прямое совпадение с вашим профилем.",
        "outreach": "Может подойти - стоит присмотреться.",
        ROUTE_REVIEW: "Гейты не смогли определить роль - решает владелец.",
    }

    async def _ready_package_for_item(
        self, user_id: int, inbox_item_id: str
    ) -> Optional[dict[str, Any]]:
        """Read-only composition over the existing bounded ready-packages
        list - no new service method, no per-item query added."""
        if not self.career_ready_queue_enabled:
            return None
        packages = await self.gateway.list_ready_application_packages(user_id, limit=7)
        for pkg in packages:
            if pkg.get("inbox_item_id") == inbox_item_id:
                return pkg
        return None

    @staticmethod
    def _waiting_days(item: dict[str, Any]) -> Optional[int]:
        """Сколько дней карточка ждёт подтверждения. Возраст показывается, потому
        что зависший отклик выглядит точно так же, как свежий, и без него забытое
        не отличить от начатого пять минут назад."""
        stamp = item.get("decided_at") or item.get("updated_at")
        if not stamp:
            return None
        try:
            decided = datetime.fromisoformat(stamp)
        except ValueError:
            return None
        if decided.tzinfo is None:
            decided = decided.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - decided).days)

    @staticmethod
    def _item_title(item: dict[str, Any]) -> str:
        company = item.get("company")
        role = item.get("role_title")
        if not company and not role:
            # Manual leads saved before company/role were filled in; naming
            # them plainly is what lets the owner recognise and close them.
            return "Пустой лид (без данных)"
        return f"{company or 'без компании'} - {role or 'без роли'}"

    def _queue_state_label(self, item: dict[str, Any], ready_ids: set[str]) -> str:
        verdict = item.get("owner_verdict")
        if verdict is None:
            return "Новая"
        if verdict == "ask":
            return "Нужно уточнить"
        if verdict == VERDICT_LATER:
            return "На будущее"
        if verdict == VERDICT_PREPARE:
            return (
                "Готово к отклику" if item["inbox_item_id"] in ready_ids else "Готовится"
            )
        return self._VERDICT_LABELS_RU.get(verdict, verdict)

    async def _render_queue(
        self,
        message: Any,
        user_id: int,
        *,
        items: list[dict[str, Any]],
        title: str,
        empty_text: str,
        back_callback: str,
        page: int = 0,
        page_callback: Optional[str] = None,
        lead_rows: Optional[list[list[tuple[str, str]]]] = None,
        extra_rows: Optional[list[list[tuple[str, str]]]] = None,
    ) -> None:
        if not items:
            rows = list(lead_rows or []) + list(extra_rows or []) + [[("Назад", back_callback)]]
            await self._render_card(message, empty_text, _markup(rows))
            return
        ready_ids: set[str] = set()
        if self.career_ready_queue_enabled:
            packages = await self.gateway.list_ready_application_packages(user_id, limit=7)
            ready_ids = {p["inbox_item_id"] for p in packages if p.get("inbox_item_id")}

        # Одна страница, а не вся выборка: сорок пять кнопок в одном сообщении
        # нечитаемы, а Telegram и вовсе может его не принять.
        start = max(0, page) * self._QUEUE_PAGE_SIZE
        visible = items[start : start + self._QUEUE_PAGE_SIZE]
        rows: list[list[tuple[str, str]]] = list(lead_rows or [])
        rows += [
            [
                (
                    f"{self._queue_state_label(item, ready_ids)}: "
                    f"{self._item_title(item)}",
                    _career_item_callback(item["inbox_item_id"]),
                )
            ]
            for item in visible
        ]
        shown = start + len(visible)
        if page_callback is not None and shown < len(items):
            rows.append(
                [(f"Показать ещё ({len(items) - shown})", f"{page_callback}:{page + 1}")]
            )
        rows += list(extra_rows or [])
        rows.append([("Назад", back_callback)])
        header = f"{title} ({len(items)})"
        if len(items) > self._QUEUE_PAGE_SIZE:
            header = f"{title} — {start + 1}-{shown} из {len(items)}"
        await self._render_card(message, header, _markup(rows))

    _QUEUE_PAGE_SIZE = 15

    # Код причины, которым upstream помечает «в названии целевая роль, но
    # подтвердить цитатой не вышло». Единственное, что бот знает о политике ролей:
    # сама политика живёт в telegram-digest и сюда не копируется.
    _TITLE_MATCH_REASON_CODE = "title_profile_match_unconfirmed"

    @classmethod
    def _title_matches_profile(cls, item: dict[str, Any]) -> bool:
        role_scope = (item.get("gates") or {}).get("role_scope") or {}
        code = (role_scope.get("authority") or {}).get("reason_code")
        return code == cls._TITLE_MATCH_REASON_CODE

    async def _show_career_inbox(
        self, message: Any, user_id: int, *, page: int = 0
    ) -> None:
        items = await self.gateway.list_inbox_items(
            user_id, routes=sorted(ACTIONABLE_IMPORT_ROUTES), include_manual=True
        )
        # The review bucket hangs off the vacancy screen rather than the Career
        # root: it is a second queue of the same thing, and the root menu is
        # deliberately capped at five rows (one-flow UX v0.1).
        review = await self.gateway.list_inbox_items(
            user_id, routes=[ROUTE_REVIEW], include_manual=False
        )
        pending = await self.gateway.list_inbox_items(
            user_id, only_verdicts=[VERDICT_PREPARE]
        )
        lead = (
            [[(f"Подтвердить отправку ({len(pending)})", "career:pending")]]
            if pending
            else []
        )
        extra = [[(f"На проверку ({len(review)})", "career:review")]] if review else []
        saved = await self.gateway.list_inbox_items(
            user_id, only_verdicts=[VERDICT_LATER]
        )
        if saved:
            extra.append([(f"Избранное ({len(saved)})", "career:saved")])
        await self._render_queue(
            message,
            user_id,
            items=items,
            title="Вакансии",
            empty_text="Вакансий нет.",
            back_callback="career:back",
            page=page,
            page_callback="career:inbox",
            lead_rows=lead,
            extra_rows=extra,
        )

    async def _show_career_pending(
        self, message: Any, user_id: int, *, page: int = 0
    ) -> None:
        """Начатое, но не подтверждённое как отправленное.

        Отклик уходит вне бота — человек читает вакансию, правит резюме, отправляет
        и назад уже не возвращается. Требовать «вспомни и найди карточку» — значит
        гарантированно терять данные: подтверждение должно само попадаться на глаза
        там, куда владелец и так заходит."""
        items = await self.gateway.list_inbox_items(
            user_id, only_verdicts=[VERDICT_PREPARE]
        )
        items.sort(key=lambda i: -(self._waiting_days(i) or 0))
        rows = []
        for item in items[: self._QUEUE_PAGE_SIZE]:
            days = self._waiting_days(item)
            age = f" · {days} дн." if days else ""
            rows.append(
                [
                    (
                        f"{self._item_title(item)}{age}",
                        _career_item_callback(item["inbox_item_id"]),
                    )
                ]
            )
        rows.append([("Назад", "career:inbox")])
        text = (
            f"Подтвердить отправку ({len(items)})\n"
            "Открой карточку и отметь «Я уже откликнулся», если отклик ушёл."
            if items
            else "Нечего подтверждать."
        )
        await self._render_card(message, text, _markup(rows))

    async def _show_career_saved(
        self, message: Any, user_id: int, *, page: int = 0
    ) -> None:
        """Отложенное, а не отклонённое: вакансии, к которым владелец вернётся."""
        items = await self.gateway.list_inbox_items(
            user_id, only_verdicts=[VERDICT_LATER]
        )
        await self._render_queue(
            message,
            user_id,
            items=items,
            title="Избранное",
            empty_text="В избранном пусто.",
            back_callback="career:inbox",
            page=page,
            page_callback="career:saved",
        )

    async def _show_career_review(
        self, message: Any, user_id: int, *, page: int = 0
    ) -> None:
        """Second, lower-priority bucket: vacancies whose role gate stayed
        unresolved upstream. They are shown, never silently dropped."""
        items = await self.gateway.list_inbox_items(
            user_id, routes=[ROUTE_REVIEW], include_manual=False
        )
        # Профильные роли наверх: корзина набирает сотни карточек, и три нужные
        # иначе теряются среди аналитиков и фронтендеров.
        items.sort(key=lambda i: not self._title_matches_profile(i))
        await self._render_queue(
            message,
            user_id,
            items=items,
            title="На проверку",
            empty_text="На проверку ничего нет.",
            back_callback="career:inbox",
            page=page,
            page_callback="career:review",
        )

    def _gate_warning_lines(self, item: dict[str, Any]) -> list[str]:
        lines = []
        for gate_name, gate in (item.get("gates") or {}).items():
            status = gate.get("status")
            if status in ("fail", "unknown"):
                lines.append(f"⚠ {gate_name}: {status}")
        return lines

    async def _render_primary_card(
        self, message: Any, item: dict[str, Any]
    ) -> None:
        inbox_item_id = item["inbox_item_id"]
        verdict = item.get("owner_verdict")
        lines = [
            f"{item.get('company') or 'без компании'} - {item.get('role_title') or 'без роли'}",
            f"Локация: {item.get('location') or 'не указана'}",
            f"Ссылка: {item.get('url') or 'не указана'}",
            f"Почему в очереди: {self._ROUTE_REASON_RU.get(item.get('route'), 'см. технические детали')}",
        ]
        lines += self._gate_warning_lines(item)
        questions = item.get("questions_for_recruiter") or []
        if questions:
            lines.append("Вопросы рекрутёру:")
            lines += [f"- {q}" for q in questions]

        rows: list[list[tuple[str, str]]] = []
        if verdict == VERDICT_PREPARE:
            lines.append("Статус: Готовится - черновик или пакет ещё не собраны.")
            rows.append([("Повторить подготовку", _career_prepare_callback(inbox_item_id))])
        else:
            rows.append([("Подготовить отклик", _career_prepare_callback(inbox_item_id))])
            # Рядом с вакансией, а не только в конце сборки пакета: отклик чаще
            # уходит прямо на сайте компании, и без этой кнопки его некуда было
            # записать — очередь выглядела необработанной, а калибровка пустой.
            rows.append([("Я уже откликнулся", _career_applied_callback(inbox_item_id))])
            if questions:
                rows.append([("Уточнить", _career_verdict_callback(inbox_item_id, "ask"))])
            rows.append([("В избранное", _career_favorite_callback(inbox_item_id))])
            rows.append([("Не подходит", _career_reject_callback(inbox_item_id))])
            rows.append(
                [("Ошибка данных", _career_verdict_callback(inbox_item_id, "false_positive"))]
            )
        rows.append([("Технические детали", _career_tech_callback(inbox_item_id))])
        rows.append([("Назад", "career:inbox")])
        await self._render_card(message, "\n".join(lines), _markup(rows))

    async def _render_ready_package_card(
        self, message: Any, pkg: dict[str, Any]
    ) -> None:
        hash_prefix = pkg["package_content_hash"][:12]
        lines = [
            f"Готово к отклику: {pkg['company']} - {pkg['role_title']}",
            f"Ссылка: {pkg.get('source_url') or 'не указана'}",
            f"CV: {self._cv_label(pkg['cv_variant_id'])}",
        ]
        for gate_name, gate in (pkg.get("gates_snapshot") or {}).items():
            if gate.get("status") in ("fail", "unknown"):
                lines.append(f"⚠ {gate_name}: {gate.get('status')}")
        for question in (pkg.get("questions_for_recruiter") or [])[:2]:
            lines.append(f"Вопрос рекрутёру: {question}")
        lines.append(f"Hash: {hash_prefix}")
        rows = [
            [("Скопировать сопровод", _career_draft_copy_callback(pkg["cover_draft_id"]))],
            [("Другой CV / изменить", _career_package_start_callback(pkg["cover_draft_id"]))],
            [
                (
                    "Я уже откликнулся",
                    _career_package_applied_callback(pkg["package_id"], hash_prefix),
                )
            ],
            [("Назад", "career:inbox")],
        ]
        await message.answer("\n".join(lines), reply_markup=_markup(rows))

    async def _render_applied_success(
        self, message: Any, user_id: int, application: dict[str, Any]
    ) -> None:
        rows: list[list[tuple[str, str]]] = []
        application_id = application.get("application_id")
        if application_id:
            rows.append(
                [("Добавить ответ / отказ", _career_feedback_start_callback(application_id))]
            )
        rows.append([("К откликам", "career:list")])
        await message.answer(
            f"Отклик зафиксирован.\n{application.get('company')} - "
            f"{application.get('role_title')}",
            reply_markup=_markup(rows),
        )

    async def _show_inbox_item(
        self, message: Any, user_id: int, inbox_item_id: str
    ) -> None:
        item = await self.gateway.get_inbox_item(user_id, inbox_item_id)
        if item is None:
            await message.answer("Карточка не найдена.")
            return
        if item.get("owner_verdict") == VERDICT_PREPARE:
            ready_pkg = await self._ready_package_for_item(user_id, inbox_item_id)
            if ready_pkg is not None:
                await self._render_ready_package_card(message, ready_pkg)
                return
        await self._render_primary_card(message, item)

    async def _on_career_callback_tech(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        inbox_item_id = await self._career_resolve_application_id(callback, rest[0])
        if inbox_item_id is None:
            return
        item = await self.gateway.get_inbox_item(user_id, inbox_item_id)
        if item is None:
            await callback.answer("Карточка не найдена")
            return
        lines = [f"Route: {item.get('route') or 'не указан'}"]
        for gate_name, gate in (item.get("gates") or {}).items():
            reason_code = (gate.get("authority") or {}).get("reason_code", "")
            lines.append(f"- {gate_name}: {gate.get('status')} [{reason_code}]")
        await callback.answer()
        await callback.message.answer("\n".join(lines))

    async def _on_career_callback_prepare(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        inbox_item_id = await self._career_resolve_application_id(callback, rest[0])
        if inbox_item_id is None:
            return
        await callback.answer("Готовлю отклик")
        await callback.message.answer("Готовлю черновик сопровода...")
        actor_id = str(self._telegram_id(callback))
        # Stable per-item key (not a fresh callback id) so a retry of the same
        # composite action reuses the same draft version instead of minting a
        # new one - the existing generate_cover_letter_draft idempotency
        # contract, not a second mechanism.
        idempotency_key = f"career_one_flow:{inbox_item_id}"
        try:
            await self.gateway.set_inbox_verdict(
                user_id,
                inbox_item_id=inbox_item_id,
                verdict=VERDICT_PREPARE,
                idempotency_key=idempotency_key,
                actor_id=actor_id,
            )
        except CareerInboxError as exc:
            await callback.message.answer(f"Не удалось подготовить: {exc}")
            return
        if not self.career_cover_letter_draft_enabled:
            await self._show_inbox_item(callback.message, user_id, inbox_item_id)
            return
        try:
            result = await self.gateway.generate_cover_letter_draft(
                user_id,
                inbox_item_id=inbox_item_id,
                idempotency_key=idempotency_key,
                actor_id=actor_id,
            )
        except CareerInboxError as exc:
            await callback.message.answer(f"Не удалось подготовить: {exc}")
            await self._show_inbox_item(callback.message, user_id, inbox_item_id)
            return
        if result.get("manual_path"):
            await callback.message.answer(
                "Не получилось подготовить черновик автоматически (нет провайдера, "
                "фактов или сбой генерации). Карточка осталась «Готовится».",
                reply_markup=_markup(
                    [[("Повторить подготовку", _career_prepare_callback(inbox_item_id))]]
                ),
            )
            return
        await self._render_draft_preview(callback.message, user_id, inbox_item_id, result["draft"])

    async def _render_draft_preview(
        self, message: Any, user_id: int, inbox_item_id: str, draft: dict[str, Any]
    ) -> None:
        item = await self.gateway.get_inbox_item(user_id, inbox_item_id)
        item = item or {}
        header = [
            f"{item.get('company') or 'без компании'} - {item.get('role_title') or 'без роли'}",
            f"Ссылка: {item.get('url') or 'не указана'}",
        ]
        header += self._gate_warning_lines(item)
        questions = item.get("questions_for_recruiter") or []
        if questions:
            header.append("Вопросы рекрутёру:")
            header += [f"- {q}" for q in questions]
        await message.answer("\n".join(header))

        report = draft.get("grounding_report") or {}
        flagged = report.get("flagged_sentences") or []
        body_lines = [draft["body"]]
        if flagged:
            body_lines.append("")
            body_lines.append(
                "⚠ Непроверяемые утверждения (проверьте вручную перед отправкой):"
            )
            body_lines += [f"- {f['sentence']}" for f in flagged]
        await message.answer("\n".join(body_lines))

        if not self.career_ready_queue_enabled:
            return
        facts_bank = load_facts_bank(self.facts_bank_path)
        role_types = (facts_bank or {}).get("role_types") or {}
        if not role_types:
            await message.answer("Нет доступных CV-вариантов (facts_bank недоступен).")
            return
        rows = [
            [(self._cv_label(key), _career_package_cv_callback(draft["draft_id"], key))]
            for key in list(role_types.keys())[:3]
        ]
        await message.answer(
            "Выберите резюме (CV) для отклика:", reply_markup=_markup(rows)
        )

    async def _on_career_callback_package_applied(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        if not self.career_ready_queue_enabled:
            await callback.answer("Функция выключена")
            return
        package_id = await self._career_resolve_application_id(callback, rest[0])
        if package_id is None:
            return
        hash_prefix = rest[1] if len(rest) > 1 else ""
        pkg = await self.gateway.get_application_package(user_id, package_id)
        if pkg is None:
            await callback.answer("Пакет недоступен")
            return
        if not pkg["package_content_hash"].startswith(hash_prefix):
            await callback.answer("Пакет изменился, откройте карточку заново")
            return
        if pkg["status"] != PACKAGE_STATUS_READY:
            # Already submitted by this or a concurrent replayed callback -
            # the state itself proves no duplicate is possible.
            await callback.answer("Уже зафиксировано")
            application = None
            if pkg.get("linked_application_id"):
                application = await self.gateway.get_application(
                    user_id, pkg["linked_application_id"]
                )
            await self._render_applied_success(callback.message, user_id, application or pkg)
            return
        idempotency_key = f"telegram_callback:{getattr(callback, 'id', str(callback.data))}"
        try:
            result = await self.gateway.submit_application_package(
                user_id,
                package_id=package_id,
                expected_package_hash=pkg["package_content_hash"],
                idempotency_key=idempotency_key,
                actor_id=str(self._telegram_id(callback)),
            )
        except CareerInboxError as exc:
            await callback.answer("Не получилось")
            await callback.message.answer(f"Не удалось отправить: {exc}")
            return
        await callback.answer("Отклик зафиксирован")
        await self._render_applied_success(callback.message, user_id, result["application"])

    @staticmethod
    def _queue_page(rest: list[str]) -> int:
        """Номер страницы из хвоста callback_data; мусор трактуем как первую."""
        if not rest:
            return 0
        try:
            return max(0, int(rest[0]))
        except ValueError:
            return 0

    async def _on_career_callback_inbox(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        if not self.career_inbox_enabled:
            await callback.answer("Функция выключена")
            return
        await callback.answer()
        await self._show_career_inbox(
            callback.message, user_id, page=self._queue_page(rest)
        )

    async def _on_career_callback_reject(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        """One extra tap buys a labelled rejection instead of an anonymous one.

        Without it the owner's judgement is unusable as calibration data: we would
        know the card was wrong but not which gate was wrong about it.
        """
        inbox_item_id = await self._career_resolve_application_id(callback, rest[0])
        if inbox_item_id is None:
            return
        await callback.answer()
        rows = [
            [(label, _career_verdict_callback(inbox_item_id, VERDICT_SKIP, code))]
            for code, label, _stored in self._SKIP_REASONS
        ]
        rows.append([("Назад", _career_item_callback(inbox_item_id))])
        await self._render_card(
            callback.message, "Почему не подходит?", _markup(rows)
        )

    async def _on_career_callback_favorite(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        """Отправляет карточку в избранное: один тап, без экрана-подтверждения."""
        inbox_item_id = await self._career_resolve_application_id(callback, rest[0])
        if inbox_item_id is None:
            return
        try:
            await self.gateway.set_inbox_verdict(
                user_id,
                inbox_item_id=inbox_item_id,
                verdict=VERDICT_LATER,
                idempotency_key=f"telegram_callback:{getattr(callback, 'id', str(callback.data))}",
                actor_id=str(self._telegram_id(callback)),
            )
        except CareerInboxError as exc:
            await callback.answer("Ошибка")
            await callback.message.answer(str(exc))
            return
        await callback.answer("В избранном")
        # Карточка ушла из рабочей очереди — показываем укоротившуюся очередь,
        # иначе повторная отрисовка выглядит как «ничего не произошло».
        await self._show_career_inbox(callback.message, user_id)

    async def _on_career_callback_pending(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        if not self.career_inbox_enabled:
            await callback.answer("Функция выключена")
            return
        await callback.answer()
        await self._show_career_pending(
            callback.message, user_id, page=self._queue_page(rest)
        )

    async def _on_career_callback_saved(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        if not self.career_inbox_enabled:
            await callback.answer("Функция выключена")
            return
        await callback.answer()
        await self._show_career_saved(
            callback.message, user_id, page=self._queue_page(rest)
        )

    async def _on_career_callback_review(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        if not self.career_inbox_enabled:
            await callback.answer("Функция выключена")
            return
        await callback.answer()
        await self._show_career_review(
            callback.message, user_id, page=self._queue_page(rest)
        )

    async def _on_career_callback_item(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        inbox_item_id = await self._career_resolve_application_id(callback, rest[0])
        if inbox_item_id is None:
            return
        await callback.answer()
        await self._show_inbox_item(callback.message, user_id, inbox_item_id)

    async def _on_career_callback_refresh(self, callback: Any, user_id: int) -> None:
        if not self.career_vacancy_refresh_enabled:
            await callback.answer("Функция выключена")
            return
        if self._vacancy_refresh_in_progress:
            await callback.answer("Уже проверяю, подождите")
            return
        await callback.answer("Запускаю проверку")
        self._vacancy_refresh_in_progress = True
        await callback.message.answer(
            "Проверяю новые вакансии в Telegram-каналах. "
            "Это может занять несколько минут."
        )
        try:
            result = await refresh_vacancies(
                digest_repo_path=self.vacancy_refresh_repo_path,
                telegram_id=self._telegram_id(callback),
            )
        finally:
            self._vacancy_refresh_in_progress = False
        if not result.ok:
            await callback.message.answer(
                f"Не получилось обновить вакансии.\n{result.message}"
            )
            return
        await callback.message.answer(
            f"Готово: {result.message}", reply_markup=self._career_markup()
        )

    async def _on_career_callback_sources(self, callback: Any, user_id: int) -> None:
        if not self.career_vacancy_refresh_enabled:
            await callback.answer("Функция выключена")
            return
        await callback.answer()
        channels = list_vacancy_channels(self.vacancy_refresh_repo_path)
        if not channels:
            await callback.message.answer(
                "Источники не настроены или конфиг недоступен.",
                reply_markup=self._career_markup(),
            )
            return
        names = await resolve_vacancy_channel_names(self.vacancy_refresh_repo_path)
        lines = []
        for c in channels:
            if c.startswith("@"):
                lines.append(f"- {c}")
            else:
                name = names.get(c)
                lines.append(f"- {name} ({c})" if name else f"- {c}")
        await callback.message.answer(
            f"Источники вакансий ({len(channels)}):\n" + "\n".join(lines),
            reply_markup=self._career_markup(),
        )

    _ADD_SOURCE_PROMPT_TEXT = (
        "Добавление источника вакансий\n"
        "Пришлите @username публичного канала или числовой chat_id "
        "приватного чата одной строкой.\n\n"
        "Источник добавляется в конфиг без проверки, что канал/чат реально "
        "существует и доступен - это выяснится при следующем ручном запуске "
        "«Проверить новые вакансии»."
    )

    async def _on_career_callback_add_source_start(
        self, callback: Any, user_id: int
    ) -> None:
        if not self.career_vacancy_refresh_enabled:
            await callback.answer("Функция выключена")
            return
        await callback.answer()
        await self.gateway.set_pending_intent(
            user_id, intent=INTENT_CAREER_ADD_VACANCY_SOURCE
        )
        await callback.message.answer(self._ADD_SOURCE_PROMPT_TEXT)

    async def _handle_add_vacancy_source_reply(
        self, message: Any, user_id: int
    ) -> None:
        entry = str(message.text or "").strip()
        if not entry or len(entry) > SOURCE_ENTRY_MAX_LEN:
            await message.answer(
                f"{self._ADD_SOURCE_PROMPT_TEXT}\n\nПустой или слишком длинный ввод. Повторите."
            )
            return
        ok, detail = add_vacancy_channel(self.vacancy_refresh_repo_path, entry)
        await self.gateway.clear_pending_intent(user_id)
        if not ok:
            await message.answer(
                f"Не добавлено: {detail}", reply_markup=self._career_markup()
            )
            return
        await message.answer(
            f"Источник добавлен: {detail}", reply_markup=self._career_markup()
        )

    async def _on_career_callback_verdict(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        inbox_item_id = await self._career_resolve_application_id(callback, rest[0])
        if inbox_item_id is None:
            return
        verdict = rest[1]
        reason: Optional[str] = None
        toast: Optional[str] = None
        if len(rest) > 2:
            known = self._SKIP_REASON_BY_CODE.get(rest[2])
            if known is None:
                await callback.answer("Кнопка устарела")
                return
            toast, reason = known
        idempotency_key = f"telegram_callback:{getattr(callback, 'id', str(callback.data))}"
        try:
            result = await self.gateway.set_inbox_verdict(
                user_id,
                inbox_item_id=inbox_item_id,
                verdict=verdict,
                reason=reason,
                idempotency_key=idempotency_key,
                actor_id=str(self._telegram_id(callback)),
            )
        except CareerInboxError as exc:
            await callback.answer("Ошибка")
            await callback.message.answer(str(exc))
            return
        await callback.answer(toast or self._VERDICT_LABELS_RU.get(verdict, "Сохранено"))
        if verdict == "ask":
            questions = result["inbox_item"].get("questions_for_recruiter") or []
            text = (
                "\n".join(f"- {q}" for q in questions)
                if questions
                else "Вопросов нет."
            )
            await callback.message.answer(text)
        if verdict in (VERDICT_SKIP, VERDICT_FALSE_POSITIVE):
            # The card is settled and has just left the queue - re-rendering it
            # would look like nothing happened, which is what made repeated
            # taps feel broken. Show the shortened queue instead.
            await self._show_career_inbox(callback.message, user_id)
            return
        await self._show_inbox_item(callback.message, user_id, inbox_item_id)

    async def _on_career_callback_applied(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        inbox_item_id = await self._career_resolve_application_id(callback, rest[0])
        if inbox_item_id is None:
            return
        idempotency_key = f"telegram_callback:{getattr(callback, 'id', str(callback.data))}"
        try:
            await self.gateway.confirm_inbox_applied(
                user_id,
                inbox_item_id=inbox_item_id,
                idempotency_key=idempotency_key,
                actor_id=str(self._telegram_id(callback)),
            )
        except CareerInboxError:
            # Единственный оставшийся отказ — карточка уже закрыта решением
            # (не подходит / ошибка данных); «Готовить» больше не требуется.
            await callback.answer("Карточка уже закрыта другим решением")
            return
        await callback.answer("Отклик отправлен")
        await self._show_inbox_item(callback.message, user_id, inbox_item_id)

    # ── Career Inbox v0: feedback (preview/confirm) ────────────────────────

    _FEEDBACK_PROMPT_TEXT = "Вставьте текст фидбэка или ответа рекрутера одним сообщением."

    def _feedback_preview_markup(self) -> Any:
        return _markup([[("Подтвердить", "career:fbok")], [("Отмена", "career:cancel")]])

    @staticmethod
    def _feedback_preview_text(payload: dict[str, Any]) -> str:
        suggestion = payload.get("suggestion") or {}
        lines = [
            "Черновик feedback (не сохранён, требует подтверждения):",
            f"Категория: {suggestion.get('category') or 'unknown'}",
            f"Цитата: {suggestion.get('evidence_quote') or 'не найдена'}",
        ]
        if suggestion.get("suggested_status_change"):
            lines.append(f"Возможная смена статуса: {suggestion['suggested_status_change']}")
        if suggestion.get("suggested_next_action"):
            lines.append(f"Следующее действие: {suggestion['suggested_next_action']}")
        return "\n".join(lines)

    async def _on_career_callback_feedback_start(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        if not self.career_inbox_enabled:
            await callback.answer("Функция выключена")
            return
        application_id = await self._career_resolve_application_id(callback, rest[0])
        if application_id is None:
            return
        await self.gateway.set_pending_intent(
            user_id, intent=INTENT_CAREER_FEEDBACK, application_id=application_id
        )
        await callback.answer()
        await callback.message.answer(
            self._FEEDBACK_PROMPT_TEXT, reply_markup=self._cancel_markup()
        )

    async def _handle_feedback_paste(
        self, message: Any, user_id: int, application_id: str
    ) -> None:
        raw_text = str(message.text or "").strip()
        if not raw_text:
            await message.answer(
                self._FEEDBACK_PROMPT_TEXT, reply_markup=self._cancel_markup()
            )
            return
        suggestion = await self.gateway.suggest_feedback(raw_text)
        payload = {"raw_text": raw_text, "suggestion": suggestion}
        await self.gateway.set_pending_intent(
            user_id,
            intent=INTENT_CAREER_FEEDBACK,
            application_id=application_id,
            payload=payload,
        )
        await message.answer(
            self._feedback_preview_text(payload),
            reply_markup=self._feedback_preview_markup(),
        )

    async def _on_career_callback_feedback_confirm(
        self, callback: Any, user_id: int
    ) -> None:
        pending = await self.gateway.get_active_pending_intent(user_id)
        if (
            pending is None
            or pending["intent"] != INTENT_CAREER_FEEDBACK
            or not pending.get("payload")
        ):
            await callback.answer("Черновик устарел")
            return
        payload = pending["payload"]
        suggestion = payload.get("suggestion") or {}
        idempotency_key = f"telegram_callback:{getattr(callback, 'id', str(callback.data))}"
        try:
            await self.gateway.confirm_feedback(
                user_id,
                application_id=pending["application_id"],
                category=suggestion.get("category") or "unknown",
                raw_feedback=payload["raw_text"],
                evidence_quote=suggestion.get("evidence_quote"),
                next_action=suggestion.get("suggested_next_action"),
                idempotency_key=idempotency_key,
                actor_id=str(self._telegram_id(callback)),
            )
        except CareerInboxError as exc:
            await callback.answer("Ошибка")
            await callback.message.answer(str(exc))
            return
        application_id = pending["application_id"]
        await self.gateway.clear_pending_intent(user_id)
        await callback.answer("Feedback сохранён")
        await self._show_career_application(callback.message, user_id, application_id)

    # ── Cover Letter Draft v0 (career/CAREER_COVER_LETTER_DRAFT_SPEC.md) ──────

    @staticmethod
    def _draft_card_text(draft: dict[str, Any]) -> str:
        report = draft.get("grounding_report") or {}
        used = report.get("used_facts") or []
        flagged = report.get("flagged_sentences") or []
        lines = [
            f"Черновик сопровода (версия {draft['version']}):",
            "",
            draft["body"],
            "",
            f"Использованные факты: {', '.join(used) if used else 'нет'}",
        ]
        if flagged:
            lines.append("⚠ Непроверяемые утверждения (проверьте вручную перед отправкой):")
            lines += [f"- {f['sentence']}" for f in flagged]
        lines.append(
            "\n(Одобрить — станет доступна сборка пакета на отправку. "
            "Отклонить — черновик не используется. Скопировать — текст в отдельном "
            "сообщении для ручной вставки.)"
        )
        return "\n".join(lines)

    @staticmethod
    def _draft_markup(draft_id: str) -> Any:
        return _markup(
            [
                [("Одобрить черновик", _career_draft_approve_callback(draft_id))],
                [("Отклонить черновик", _career_draft_reject_callback(draft_id))],
                [("Скопировать текст", _career_draft_copy_callback(draft_id))],
            ]
        )

    async def _on_career_callback_draft(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        inbox_item_id = await self._career_resolve_application_id(callback, rest[0])
        if inbox_item_id is None:
            return
        if not self.career_cover_letter_draft_enabled:
            await callback.answer("Функция выключена")
            return
        idempotency_key = f"telegram_callback:{getattr(callback, 'id', str(callback.data))}"
        try:
            result = await self.gateway.generate_cover_letter_draft(
                user_id,
                inbox_item_id=inbox_item_id,
                idempotency_key=idempotency_key,
                actor_id=str(self._telegram_id(callback)),
            )
        except CareerInboxError as exc:
            await callback.answer("Ошибка")
            await callback.message.answer(str(exc))
            return
        await callback.answer()
        if result.get("manual_path"):
            await callback.message.answer(
                "Черновик недоступен (нет провайдера, фактов или сбой генерации). "
                "Напишите вручную по career/COVER_LETTER_SKELETON.md — бот не "
                "меняет facts_bank и не отправляет ничего сам.",
                reply_markup=_markup(
                    [[("Обновить факты вручную", _career_draft_facts_callback(inbox_item_id))]]
                ),
            )
            return
        draft = result["draft"]
        await callback.message.answer(
            self._draft_card_text(draft), reply_markup=self._draft_markup(draft["draft_id"])
        )

    async def _on_career_callback_draft_approve(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        draft_id = await self._career_resolve_application_id(callback, rest[0])
        if draft_id is None:
            return
        try:
            result = await self.gateway.approve_cover_letter_draft(
                user_id, draft_id=draft_id, actor_id=str(self._telegram_id(callback))
            )
        except CareerInboxError as exc:
            await callback.answer("Ошибка")
            await callback.message.answer(str(exc))
            return
        await callback.answer("Одобрено")
        markup = None
        text = (
            f"Черновик (версия {result['draft']['version']}) одобрен. "
            "Отправка отклика и письма - только вручную, бот ничего не отправляет."
        )
        if self.career_ready_queue_enabled:
            text += "\n\nДальше: «Собрать пакет» объединит вакансию, резюме и этот сопровод в один пакет на отправку."
            markup = _markup(
                [[("Собрать пакет (резюме + сопровод)", _career_package_start_callback(draft_id))]]
            )
        await callback.message.answer(text, reply_markup=markup)

    async def _on_career_callback_draft_reject(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        draft_id = await self._career_resolve_application_id(callback, rest[0])
        if draft_id is None:
            return
        try:
            result = await self.gateway.reject_cover_letter_draft(
                user_id, draft_id=draft_id, actor_id=str(self._telegram_id(callback))
            )
        except CareerInboxError as exc:
            await callback.answer("Ошибка")
            await callback.message.answer(str(exc))
            return
        await callback.answer("Отклонено")
        await callback.message.answer(
            f"Черновик (версия {result['draft']['version']}) отклонён."
        )

    async def _on_career_callback_draft_copy(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        draft_id = await self._career_resolve_application_id(callback, rest[0])
        if draft_id is None:
            return
        draft = await self.gateway.get_cover_letter_draft(user_id, draft_id)
        if draft is None:
            await callback.answer("Не найдено")
            return
        await callback.answer()
        await callback.message.answer(draft["body"])

    async def _on_career_callback_draft_facts(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        inbox_item_id = await self._career_resolve_application_id(callback, rest[0])
        if inbox_item_id is None:
            return
        await callback.answer()
        await callback.message.answer(
            "Обновите career/facts_bank.yaml вручную (владелец фактов), затем "
            "снова нажмите «Черновик сопровода» для новой версии. Бот не "
            "редактирует факты сам."
        )

    # ── Application Package v0 (Slice D1b.1: package creation) ─────────────

    async def _on_career_callback_package_start(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        if not self.career_ready_queue_enabled:
            await callback.answer("Функция выключена")
            return
        draft_id = await self._career_resolve_application_id(callback, rest[0])
        if draft_id is None:
            return
        draft = await self.gateway.get_cover_letter_draft(user_id, draft_id)
        if draft is None or draft.get("status") != DRAFT_STATUS_APPROVED:
            await callback.answer("Сначала одобрите черновик")
            return
        facts_bank = load_facts_bank(self.facts_bank_path)
        role_types = (facts_bank or {}).get("role_types") or {}
        if not role_types:
            await callback.answer()
            await callback.message.answer("Нет доступных CV-вариантов (facts_bank недоступен).")
            return
        rows = [
            [(self._cv_label(key), _career_package_cv_callback(draft_id, key))]
            for key in list(role_types.keys())[:3]
        ]
        await callback.answer()
        await callback.message.answer(
            "Выберите резюме (CV) для этого пакета — под какую роль откликаетесь:",
            reply_markup=_markup(rows),
        )

    async def _on_career_callback_package_cv(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        if not self.career_ready_queue_enabled:
            await callback.answer("Функция выключена")
            return
        draft_id = await self._career_resolve_application_id(callback, rest[0])
        if draft_id is None:
            return
        cv_variant_id = rest[1]
        draft = await self.gateway.get_cover_letter_draft(user_id, draft_id)
        if draft is None:
            await callback.answer("Черновик не найден")
            return
        if draft.get("status") == DRAFT_STATUS_REJECTED:
            await callback.answer("Черновик отклонён")
            return
        try:
            # Clicking a CV button is the owner's explicit approval of the
            # exact draft just shown, in the same action - not a second,
            # separate "Одобрить" tap. approve_cover_letter_draft is
            # idempotent, so this is a no-op when already approved (old
            # Одобрить -> Собрать пакет path still works unchanged).
            if draft.get("status") != DRAFT_STATUS_APPROVED:
                approved = await self.gateway.approve_cover_letter_draft(
                    user_id, draft_id=draft_id, actor_id=str(self._telegram_id(callback))
                )
                draft = approved["draft"]
            result = await self.gateway.prepare_application_package(
                user_id,
                inbox_item_id=draft["inbox_item_id"],
                cover_draft_id=draft_id,
                cv_variant_id=cv_variant_id,
                actor_id=str(self._telegram_id(callback)),
            )
        except CareerInboxError as exc:
            await callback.answer("Ошибка")
            await callback.message.answer(str(exc))
            return
        await callback.answer("Пакет готов")
        await self._render_ready_package_card(callback.message, result["package"])

    def _cv_label(self, cv_variant_id: str) -> str:
        """Human-readable CV name from the same facts_bank role_types mapping
        used to build the CV choices - no new label registry."""
        facts_bank = load_facts_bank(self.facts_bank_path)
        variant = (facts_bank or {}).get("role_types", {}).get(cv_variant_id)
        if isinstance(variant, dict) and variant.get("cv"):
            return str(variant["cv"])
        return cv_variant_id

    async def _on_career_callback_ready_queue(self, callback: Any, user_id: int) -> None:
        if not self.career_ready_queue_enabled:
            await callback.answer("Функция выключена")
            return
        packages = await self.gateway.list_ready_application_packages(user_id, limit=7)
        await callback.answer()
        if not packages:
            await callback.message.answer(
                "Готовых пакетов нет.\n\n"
                "Пакет появится здесь после: Готовить → Черновик сопровода → "
                "Одобрить черновик → Собрать пакет.",
                reply_markup=self._career_markup(),
            )
            return
        rows = [
            [
                (
                    f"{i}. {p['company']} - {p['role_title']} ({p['package_content_hash'][:10]})",
                    _career_package_item_callback(p["package_id"]),
                )
            ]
            for i, p in enumerate(packages, start=1)
        ]
        rows.append([("Назад", "career:back")])
        await callback.message.answer(
            f"Готовые к отправке ({len(packages)}). Нажмите на пакет, чтобы открыть карточку.",
            reply_markup=_markup(rows),
        )

    async def _on_career_callback_package_item(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        if not self.career_ready_queue_enabled:
            await callback.answer("Функция выключена")
            return
        package_id = await self._career_resolve_application_id(callback, rest[0])
        if package_id is None:
            return
        pkg = await self.gateway.get_application_package(user_id, package_id)
        if pkg is None or pkg["status"] != PACKAGE_STATUS_READY:
            await callback.answer("Пакет недоступен")
            return
        lines = [
            f"{pkg['company']} - {pkg['role_title']}",
            f"CV: {self._cv_label(pkg['cv_variant_id'])}",
            f"Ссылка: {pkg['source_url'] or 'не указана'}",
        ]
        for gate_name, gate in (pkg.get("gates_snapshot") or {}).items():
            lines.append(f"- {gate_name}: {gate.get('status')}")
        for question in (pkg.get("questions_for_recruiter") or [])[:2]:
            lines.append(f"Вопрос: {question}")
        lines.append(f"Hash: {pkg['package_content_hash'][:12]}")
        lines.append(
            "\nНажмите «Отправлено», только если вы уже сами отправили этот отклик "
            "вне бота (например на hh.ru) — бот ничего не отправляет за вас."
        )
        rows = [
            [("Скопировать сопровод", _career_draft_copy_callback(pkg["cover_draft_id"]))],
            [("Отправлено (я уже откликнулся)", _career_package_send_callback(pkg["package_id"]))],
            [("Назад", "career:ready")],
        ]
        await callback.answer()
        await callback.message.answer("\n".join(lines), reply_markup=_markup(rows))

    async def _on_career_callback_package_send(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        if not self.career_ready_queue_enabled:
            await callback.answer("Функция выключена")
            return
        package_id = await self._career_resolve_application_id(callback, rest[0])
        if package_id is None:
            return
        pkg = await self.gateway.get_application_package(user_id, package_id)
        if pkg is None or pkg["status"] != PACKAGE_STATUS_READY:
            await callback.answer("Пакет недоступен")
            return
        hash_prefix = pkg["package_content_hash"][:12]
        await callback.answer()
        await callback.message.answer(
            f"Это последний шаг — запись факта отправки, а не сама отправка:\n\n"
            f"{pkg['company']} - {pkg['role_title']}\nHash: {hash_prefix}\n\n"
            "«Подтвердить» — только если отклик уже реально отправлен вами. "
            "«Отмена» — ничего не запишется.",
            reply_markup=_markup(
                [
                    [("Подтвердить, отклик уже отправлен", _career_package_confirm_callback(package_id, hash_prefix))],
                    [("Отмена", _career_package_cancel_callback())],
                ]
            ),
        )

    async def _on_career_callback_package_confirm(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        if not self.career_ready_queue_enabled:
            await callback.answer("Функция выключена")
            return
        package_id = await self._career_resolve_application_id(callback, rest[0])
        if package_id is None:
            return
        hash_prefix = rest[1]
        pkg = await self.gateway.get_application_package(user_id, package_id)
        if pkg is None:
            await callback.answer("Пакет недоступен")
            return
        if not pkg["package_content_hash"].startswith(hash_prefix):
            await callback.answer("Пакет изменился, откройте карточку заново")
            return
        if pkg["status"] != PACKAGE_STATUS_READY:
            # Already submitted by this or a concurrent replayed callback - the
            # state itself proves no duplicate is possible; show a safe result.
            await callback.answer("Уже отправлено")
            text = f"Уже обработано: {pkg['company']} - {pkg['role_title']}"
            if pkg.get("linked_application_id"):
                text += f"\napplication_id: {pkg['linked_application_id']}"
            await callback.message.answer(text)
            return
        idempotency_key = f"telegram_callback:{getattr(callback, 'id', str(callback.data))}"
        try:
            result = await self.gateway.submit_application_package(
                user_id,
                package_id=package_id,
                expected_package_hash=pkg["package_content_hash"],
                idempotency_key=idempotency_key,
                actor_id=str(self._telegram_id(callback)),
            )
        except CareerInboxError as exc:
            await callback.answer("Не получилось")
            await callback.message.answer(f"Не удалось отправить: {exc}")
            return
        application = result["application"]
        await callback.answer("Отправлено")
        await callback.message.answer(
            f"Отклик зафиксирован.\napplication_id: {application['application_id']}\n"
            f"status: {application['status']}"
        )

    async def _on_career_callback_package_cancel(self, callback: Any, user_id: int) -> None:
        await callback.answer("Отменено")

    async def on_career_callback(self, callback: Any) -> None:
        user_id = await self._authorize(callback)
        if user_id is None:
            return
        try:
            action, rest = _parse_career_callback(str(callback.data))
        except (ValueError, IndexError):
            await callback.answer("Кнопка устарела")
            return
        if action == "add":
            await self._on_career_callback_add(callback, user_id)
        elif action == "list":
            await self._on_career_callback_list(callback, user_id)
        elif action == "back":
            await self._on_career_callback_back(callback, user_id)
        elif action == "cancel":
            await self._on_career_callback_cancel(callback, user_id)
        elif action == "more":
            await self._on_career_callback_more(callback, user_id)
        elif action == "prep" and rest:
            await self._on_career_callback_prepare(callback, user_id, rest)
        elif action == "tech" and rest:
            await self._on_career_callback_tech(callback, user_id, rest)
        elif action == "pkgapplied" and len(rest) >= 2:
            await self._on_career_callback_package_applied(callback, user_id, rest)
        elif action == "app" and rest:
            await self._on_career_callback_app(callback, user_id, rest)
        elif action == "status" and len(rest) >= 2:
            await self._on_career_callback_status(callback, user_id, rest)
        elif action == "next" and rest:
            await self._on_career_callback_next(callback, user_id, rest)
        elif action == "inbox":
            await self._on_career_callback_inbox(callback, user_id, rest)
        elif action == "review":
            await self._on_career_callback_review(callback, user_id, rest)
        elif action == "no" and rest:
            await self._on_career_callback_reject(callback, user_id, rest)
        elif action == "fav" and rest:
            await self._on_career_callback_favorite(callback, user_id, rest)
        elif action == "saved":
            await self._on_career_callback_saved(callback, user_id, rest)
        elif action == "pending":
            await self._on_career_callback_pending(callback, user_id, rest)
        elif action == "item" and rest:
            await self._on_career_callback_item(callback, user_id, rest)
        elif action == "iv" and len(rest) >= 2:
            await self._on_career_callback_verdict(callback, user_id, rest)
        elif action == "ia" and rest:
            await self._on_career_callback_applied(callback, user_id, rest)
        elif action == "lead":
            await self._on_career_callback_lead(callback, user_id)
        elif action == "leadok" and rest:
            await self._on_career_callback_leadok(callback, user_id, rest[0])
        elif action == "leadskip" and rest:
            await self._on_career_callback_leadskip(callback, user_id, rest[0])
        elif action == "fb" and rest:
            await self._on_career_callback_feedback_start(callback, user_id, rest)
        elif action == "fbok":
            await self._on_career_callback_feedback_confirm(callback, user_id)
        elif action == "draft" and rest:
            await self._on_career_callback_draft(callback, user_id, rest)
        elif action == "draftok" and rest:
            await self._on_career_callback_draft_approve(callback, user_id, rest)
        elif action == "draftno" and rest:
            await self._on_career_callback_draft_reject(callback, user_id, rest)
        elif action == "draftcopy" and rest:
            await self._on_career_callback_draft_copy(callback, user_id, rest)
        elif action == "draftfacts" and rest:
            await self._on_career_callback_draft_facts(callback, user_id, rest)
        elif action == "refresh":
            await self._on_career_callback_refresh(callback, user_id)
        elif action == "sources":
            await self._on_career_callback_sources(callback, user_id)
        elif action == "addsrc":
            await self._on_career_callback_add_source_start(callback, user_id)
        elif action == "pkg" and rest:
            await self._on_career_callback_package_start(callback, user_id, rest)
        elif action == "pkgcv" and len(rest) >= 2:
            await self._on_career_callback_package_cv(callback, user_id, rest)
        elif action == "ready":
            await self._on_career_callback_ready_queue(callback, user_id)
        elif action == "pkgitem" and rest:
            await self._on_career_callback_package_item(callback, user_id, rest)
        elif action == "pkgsend" and rest:
            await self._on_career_callback_package_send(callback, user_id, rest)
        elif action == "pkgok" and len(rest) >= 2:
            await self._on_career_callback_package_confirm(callback, user_id, rest)
        elif action == "pkgno":
            await self._on_career_callback_package_cancel(callback, user_id)
        else:
            await callback.answer("Неизвестное действие")

    async def on_unknown_command(self, message: Any) -> None:
        if await self._authorize(message) is None:
            return
        await message.answer(
            "Неизвестная команда. Используйте /start, /today, /slice, "
            "/progress, /skip, /cancel, /applied или /applications."
        )

    async def on_menu(self, callback: Any) -> None:
        action = str(callback.data).split(":", 1)[1]
        user_id = await self._authorize(callback)
        if user_id is None:
            return
        if action == "today":
            await self._start_today(callback.message, user_id)
        elif action == "slice":
            progress = await self.gateway.progress(user_id)
            await callback.message.answer(
                "Выберите тему:", reply_markup=self._topics_markup(progress)
            )
        elif action == "progress":
            await self._show_progress(callback.message, user_id)
        elif action == "career":
            await callback.message.answer("Карьера", reply_markup=self._career_markup())
        else:
            await callback.answer("Неизвестное действие")
            return
        await callback.answer()


def build_dispatcher(controller: MlTechnicalTelegramController) -> Any:
    from aiogram import Dispatcher, F
    from aiogram.filters import Command, CommandStart

    dispatcher = Dispatcher()
    dispatcher.message.register(controller.on_start, CommandStart())
    dispatcher.message.register(controller.on_today, Command("today"))
    dispatcher.message.register(controller.on_slice, Command("slice"))
    dispatcher.message.register(controller.on_progress, Command("progress"))
    dispatcher.message.register(controller.on_skip, Command("skip"))
    dispatcher.message.register(controller.on_cancel, Command("cancel"))
    dispatcher.message.register(controller.on_applied, Command("applied"))
    dispatcher.message.register(controller.on_applications, Command("applications"))
    dispatcher.message.register(controller.on_unknown_command, F.text.startswith("/"))
    dispatcher.callback_query.register(controller.on_menu, F.data.startswith("menu:"))
    dispatcher.callback_query.register(
        controller.on_slice_topic, F.data.startswith("slice:")
    )
    dispatcher.callback_query.register(
        controller.on_dont_know, F.data.startswith("dk:")
    )
    dispatcher.callback_query.register(
        controller.on_skip_callback, F.data.startswith("sk:")
    )
    dispatcher.callback_query.register(
        controller.on_career_callback, F.data.startswith("career:")
    )
    dispatcher.message.register(controller.on_text, F.text)
    return dispatcher


async def _run() -> None:
    if not settings.ml_technical_telegram_bot_token:
        raise RuntimeError(
            "ML_TECHNICAL_TELEGRAM_BOT_TOKEN is empty; Telegram adapter is disabled"
        )
    from aiogram import Bot
    from aiogram.client.session.aiohttp import AiohttpSession
    from aiogram.types import BotCommand

    proxy = settings.proxy_url or os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    bot_session = AiohttpSession(proxy=proxy) if proxy else None
    bot = Bot(token=settings.ml_technical_telegram_bot_token, session=bot_session)
    controller = MlTechnicalTelegramController(
        DbTelegramPracticeGateway(get_async_session()),
        allowed_ids=settings.ml_technical_telegram_allowed_id_set,
        timezone_name=settings.ml_technical_telegram_timezone,
        career_inbox_enabled=settings.career_inbox_enabled,
        career_cover_letter_draft_enabled=settings.career_cover_letter_draft_enabled,
        career_vacancy_refresh_enabled=settings.career_vacancy_refresh_enabled,
        vacancy_refresh_repo_path=settings.vacancy_refresh_repo_path,
        career_ready_queue_enabled=settings.career_ready_queue_enabled,
    )
    dispatcher = build_dispatcher(controller)
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="today", description="Пять вопросов на сегодня"),
            BotCommand(command="slice", description="Срез по теме"),
            BotCommand(command="progress", description="Мой прогресс"),
            BotCommand(command="skip", description="Пропустить вопрос"),
            BotCommand(command="cancel", description="Отменить тренировку"),
            BotCommand(command="applied", description="Записать отклик на вакансию"),
            BotCommand(command="applications", description="Мои отклики"),
        ]
    )
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(_run())


if __name__ == "__main__":
    main()
