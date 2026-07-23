"""Private Telegram adapter for Russian ML/DL interview practice.

The module deliberately imports aiogram only inside runtime/markup functions,
so its controller and persistence boundary are testable without Telegram or
network access. PostgreSQL is the only source of active-session state.
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional, Protocol
from uuid import UUID
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
    CareerInboxError,
    CareerInboxService,
    suggest_feedback as suggest_feedback_impl,
    suggest_manual_lead as suggest_manual_lead_impl,
)
from app.services.career_ledger_service import (
    ALLOWED_TRANSITIONS,
    INTENT_CAREER_ADD,
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


def _career_verdict_callback(inbox_item_id: str, verdict: str) -> str:
    return f"career:iv:{_compact_uuid(inbox_item_id)}:{verdict}"


def _career_applied_callback(inbox_item_id: str) -> str:
    return f"career:ia:{_compact_uuid(inbox_item_id)}"


def _career_feedback_start_callback(application_id: str) -> str:
    return f"career:fb:{_compact_uuid(application_id)}"


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

    async def list_inbox_items(self, user_id: int) -> list[dict[str, Any]]:
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

    async def list_inbox_items(self, user_id: int) -> list[dict[str, Any]]:
        async with self.session_factory() as db:
            return await CareerInboxService(db).list_inbox_items(user_id)

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
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        async with self.session_factory() as db:
            return await CareerInboxService(db).set_verdict(
                user_id,
                inbox_item_id=inbox_item_id,
                verdict=verdict,
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


class MlTechnicalTelegramController:
    def __init__(
        self,
        gateway: TelegramPracticeGateway,
        *,
        allowed_ids: frozenset[int],
        timezone_name: str = "Europe/Moscow",
        career_inbox_enabled: bool = False,
    ) -> None:
        self.gateway = gateway
        self.allowed_ids = allowed_ids
        self.career_inbox_enabled = career_inbox_enabled
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
        rows = [
            [("Записать отправленный отклик", "career:add")],
            [("Отклики", "career:list")],
        ]
        if self.career_inbox_enabled:
            rows.append([("Входящие", "career:inbox")])
            rows.append([("Добавить контакт или ответ", "career:lead")])
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

    def _lead_preview_markup(self) -> Any:
        return _markup([[("Подтвердить", "career:leadok")], [("Отмена", "career:cancel")]])

    @staticmethod
    def _lead_preview_text(payload: dict[str, Any]) -> str:
        suggestion = payload.get("suggestion") or {}
        questions = suggestion.get("questions_for_recruiter") or []
        evidence = suggestion.get("evidence_quote")
        lines = [
            "Черновик лида (не сохранён, требует подтверждения):",
            f"Компания: {suggestion.get('company') or 'не определена'}",
            f"Роль: {suggestion.get('role_title') or 'не определена'}",
            f"Тип: {suggestion.get('event_kind') or 'unknown'}",
        ]
        if questions:
            lines.append("Вопросы:")
            lines += [f"- {q}" for q in questions]
        lines.append(f"Цитата: {evidence or 'не найдена'}")
        return "\n".join(lines)

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
        suggestion = await self.gateway.suggest_manual_lead(raw_text)
        payload = {"raw_text": raw_text, "suggestion": suggestion}
        await self.gateway.set_pending_intent(
            user_id, intent=INTENT_CAREER_MANUAL_LEAD, payload=payload
        )
        await message.answer(
            self._lead_preview_text(payload), reply_markup=self._lead_preview_markup()
        )

    async def _on_career_callback_leadok(self, callback: Any, user_id: int) -> None:
        pending = await self.gateway.get_active_pending_intent(user_id)
        if (
            pending is None
            or pending["intent"] != INTENT_CAREER_MANUAL_LEAD
            or not pending.get("payload")
        ):
            await callback.answer("Черновик устарел")
            return
        payload = pending["payload"]
        suggestion = payload.get("suggestion") or {}
        idempotency_key = f"telegram_callback:{getattr(callback, 'id', str(callback.data))}"
        try:
            result = await self.gateway.confirm_manual_lead(
                user_id,
                source="manual",
                raw_text=payload["raw_text"],
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
        await self.gateway.clear_pending_intent(user_id)
        await callback.answer("Сохранено")
        item = result["inbox_item"]
        await callback.message.answer(
            f"Добавлено во Входящие: {item.get('company') or 'без компании'} - "
            f"{item.get('role_title') or 'без роли'}",
            reply_markup=self._career_markup(),
        )

    # ── Career Inbox v0: bounded list, detail, verdicts ────────────────────

    _VERDICT_LABELS_RU: dict[str, str] = {
        "ask": "Спросить",
        "prepare": "Готовить",
        "skip": "Пропустить",
        "false_positive": "Ошибка парсера",
        "applied": "Отклик отправлен",
    }

    async def _show_career_inbox(self, message: Any, user_id: int) -> None:
        items = await self.gateway.list_inbox_items(user_id)
        if not items:
            await message.answer("Входящих нет.", reply_markup=self._career_markup())
            return
        rows: list[list[tuple[str, str]]] = [
            [
                (
                    f"{item.get('company') or 'без компании'} - "
                    f"{item.get('role_title') or 'без роли'}",
                    _career_item_callback(item["inbox_item_id"]),
                )
            ]
            for item in items
        ]
        rows.append([("Назад", "career:back")])
        await message.answer(
            f"Входящие ({len(items)})", reply_markup=_markup(rows)
        )

    async def _show_inbox_item(
        self, message: Any, user_id: int, inbox_item_id: str
    ) -> None:
        item = await self.gateway.get_inbox_item(user_id, inbox_item_id)
        if item is None:
            await message.answer("Карточка не найдена.")
            return
        lines = [
            f"{item.get('company') or 'без компании'} - {item.get('role_title') or 'без роли'}",
            f"Локация: {item.get('location') or 'не указана'}",
            f"Ссылка: {item.get('url') or 'не указана'}",
        ]
        if item.get("route"):
            lines.append(f"Route: {item['route']}")
        gates = item.get("gates") or {}
        for gate_name, gate in gates.items():
            reason_code = (gate.get("authority") or {}).get("reason_code", "")
            lines.append(f"- {gate_name}: {gate.get('status')} [{reason_code}]")
        verdict = item.get("owner_verdict")
        if verdict:
            lines.append(f"Вердикт: {self._VERDICT_LABELS_RU.get(verdict, verdict)}")
        rows: list[list[tuple[str, str]]] = [
            [("Спросить", _career_verdict_callback(inbox_item_id, "ask"))],
            [("Готовить", _career_verdict_callback(inbox_item_id, "prepare"))],
            [("Пропустить", _career_verdict_callback(inbox_item_id, "skip"))],
            [("Ошибка парсера", _career_verdict_callback(inbox_item_id, "false_positive"))],
            [("Отклик отправлен", _career_applied_callback(inbox_item_id))],
            [("Назад", "career:inbox")],
        ]
        await message.answer("\n".join(lines), reply_markup=_markup(rows))

    async def _on_career_callback_inbox(self, callback: Any, user_id: int) -> None:
        if not self.career_inbox_enabled:
            await callback.answer("Функция выключена")
            return
        await callback.answer()
        await self._show_career_inbox(callback.message, user_id)

    async def _on_career_callback_item(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        inbox_item_id = await self._career_resolve_application_id(callback, rest[0])
        if inbox_item_id is None:
            return
        await callback.answer()
        await self._show_inbox_item(callback.message, user_id, inbox_item_id)

    async def _on_career_callback_verdict(
        self, callback: Any, user_id: int, rest: list[str]
    ) -> None:
        inbox_item_id = await self._career_resolve_application_id(callback, rest[0])
        if inbox_item_id is None:
            return
        verdict = rest[1]
        idempotency_key = f"telegram_callback:{getattr(callback, 'id', str(callback.data))}"
        try:
            result = await self.gateway.set_inbox_verdict(
                user_id,
                inbox_item_id=inbox_item_id,
                verdict=verdict,
                idempotency_key=idempotency_key,
                actor_id=str(self._telegram_id(callback)),
            )
        except CareerInboxError as exc:
            await callback.answer("Ошибка")
            await callback.message.answer(str(exc))
            return
        await callback.answer(self._VERDICT_LABELS_RU.get(verdict, "Сохранено"))
        if verdict == "ask":
            questions = result["inbox_item"].get("questions_for_recruiter") or []
            text = (
                "\n".join(f"- {q}" for q in questions)
                if questions
                else "Вопросов нет."
            )
            await callback.message.answer(text)
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
            await callback.answer("Сначала нажмите Готовить")
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
        elif action == "app" and rest:
            await self._on_career_callback_app(callback, user_id, rest)
        elif action == "status" and len(rest) >= 2:
            await self._on_career_callback_status(callback, user_id, rest)
        elif action == "next" and rest:
            await self._on_career_callback_next(callback, user_id, rest)
        elif action == "inbox":
            await self._on_career_callback_inbox(callback, user_id)
        elif action == "item" and rest:
            await self._on_career_callback_item(callback, user_id, rest)
        elif action == "iv" and len(rest) >= 2:
            await self._on_career_callback_verdict(callback, user_id, rest)
        elif action == "ia" and rest:
            await self._on_career_callback_applied(callback, user_id, rest)
        elif action == "lead":
            await self._on_career_callback_lead(callback, user_id)
        elif action == "leadok":
            await self._on_career_callback_leadok(callback, user_id)
        elif action == "fb" and rest:
            await self._on_career_callback_feedback_start(callback, user_id, rest)
        elif action == "fbok":
            await self._on_career_callback_feedback_confirm(callback, user_id)
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
    asyncio.run(_run())


if __name__ == "__main__":
    main()
