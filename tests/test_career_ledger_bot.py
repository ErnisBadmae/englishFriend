from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.adapters.telegram.ml_technical_bot import (
    MlTechnicalTelegramController,
    INTENT_CAREER_ADD,
    INTENT_CAREER_NEXT_ACTION,
    _career_app_callback,
    _career_status_callback,
)
from app.services.career_ledger_service import (
    ALLOWED_TRANSITIONS,
    STATUS_APPLIED,
    STATUS_OFFER,
    STATUS_REJECTED,
    STATUS_SCREENING,
    CareerLedgerError,
    CareerLedgerTransitionError,
)


class FakeChat:
    def __init__(self, chat_id: int, chat_type: str = "private") -> None:
        self.id = chat_id
        self.type = chat_type


class FakeMessage:
    def __init__(
        self,
        telegram_id: int,
        text: str = "",
        *,
        message_id: int = 1,
        chat_type: str = "private",
        reply_to_message: "FakeMessage | None" = None,
    ) -> None:
        self.chat = FakeChat(telegram_id, chat_type)
        self.from_user = SimpleNamespace(id=telegram_id)
        self.text = text
        self.message_id = message_id
        self.reply_to_message = reply_to_message
        self.replies: list[str] = []
        self.markups: list[object | None] = []

    async def answer(self, text: str, **kwargs: object) -> None:
        self.replies.append(text)
        self.markups.append(kwargs.get("reply_markup"))


class FakeCallback:
    def __init__(self, telegram_id: int, data: str, *, callback_id: str = "cb-1"):
        self.message = FakeMessage(telegram_id)
        self.message.from_user = SimpleNamespace(id=999_999)
        self.from_user = SimpleNamespace(id=telegram_id)
        self.data = data
        self.id = callback_id
        self.answers: list[str] = []

    async def answer(self, text: str = "", **_kwargs: object) -> None:
        self.answers.append(text)


class FakeCareerGateway:
    """Combined career + ML-session double covering the v0.2 routing surface."""

    def __init__(self) -> None:
        self.links = {111: 11}
        self.applications: dict[str, dict] = {}
        self.applications_order: list[str] = []
        self.used_idempotency_keys: dict[str, dict] = {}
        self.status_events: list[tuple[str, str]] = []
        self.note_events: list[dict] = []
        self.active_session: dict | None = None
        self.submit_calls: list[dict] = []
        self.pending_intents: dict[int, dict[str, str | None]] = {}

    async def resolve_user(self, telegram_id: int):
        return self.links.get(telegram_id)

    async def set_pending_intent(
        self,
        user_id: int,
        *,
        intent: str,
        application_id: str | None = None,
    ):
        pending = {"intent": intent, "application_id": application_id}
        self.pending_intents[user_id] = pending
        return pending

    async def get_active_pending_intent(self, user_id: int):
        return self.pending_intents.get(user_id)

    async def clear_pending_intent(self, user_id: int):
        self.pending_intents.pop(user_id, None)

    async def cancel(self, user_id: int):
        del user_id
        cancelled = self.active_session is not None
        self.active_session = None
        return {"cancelled": cancelled}

    async def discard_expired_pending_intents(self, user_id: int):
        del user_id
        return 0

    async def record_application(
        self,
        user_id: int,
        *,
        company: str,
        role_title: str,
        url,
        idempotency_key: str,
        actor_id: str,
    ):
        del user_id, actor_id
        if not company.strip() or not role_title.strip():
            raise CareerLedgerError("company and role_title are required")
        if idempotency_key in self.used_idempotency_keys:
            return {
                "created": False,
                "application": self.used_idempotency_keys[idempotency_key],
            }
        application_id = str(uuid4())
        application = {
            "application_id": application_id,
            "company": company,
            "role_title": role_title,
            "url": url,
            "status": STATUS_APPLIED,
            "next_action": None,
            "next_action_due_date": None,
        }
        self.applications[application_id] = application
        self.applications_order.append(application_id)
        self.used_idempotency_keys[idempotency_key] = application
        return {"created": True, "application": application}

    async def applications_overview(self, user_id: int):
        del user_id
        by_status: dict[str, int] = {}
        for app in self.applications.values():
            by_status[app["status"]] = by_status.get(app["status"], 0) + 1
        recent = [self.applications[aid] for aid in reversed(self.applications_order)]
        return {
            "summary": {"total": len(self.applications), "by_status": by_status},
            "recent": recent,
        }

    async def get_application(self, user_id: int, application_id: str):
        del user_id
        return self.applications.get(application_id)

    async def update_application_status(
        self,
        user_id: int,
        *,
        application_id: str,
        to_status: str,
        idempotency_key: str,
        actor_id: str,
    ):
        del user_id, actor_id
        if idempotency_key in self.used_idempotency_keys:
            return {
                "created": False,
                "application": self.used_idempotency_keys[idempotency_key],
            }
        application = self.applications.get(application_id)
        if application is None:
            raise CareerLedgerError(f"unknown career application_id: {application_id}")
        current_status = application["status"]
        if to_status not in ALLOWED_TRANSITIONS.get(current_status, frozenset()):
            raise CareerLedgerTransitionError(
                f"transition {current_status} -> {to_status} is not allowed"
            )
        application["status"] = to_status
        self.status_events.append((application_id, to_status))
        self.used_idempotency_keys[idempotency_key] = application
        return {"created": True, "application": application}

    async def set_application_next_action(
        self,
        user_id: int,
        *,
        application_id: str,
        next_action: str,
        next_action_due_date,
        idempotency_key: str,
        actor_id: str,
    ):
        del user_id, actor_id
        if idempotency_key in self.used_idempotency_keys:
            return {
                "created": False,
                "application": self.used_idempotency_keys[idempotency_key],
            }
        application = self.applications.get(application_id)
        if application is None:
            raise CareerLedgerError(f"unknown career application_id: {application_id}")
        application["next_action"] = next_action
        application["next_action_due_date"] = (
            next_action_due_date.isoformat() if next_action_due_date else None
        )
        self.note_events.append(
            {"application_id": application_id, "next_action": next_action}
        )
        self.used_idempotency_keys[idempotency_key] = application
        return {"created": True, "application": application}

    async def active(self, user_id: int):
        del user_id
        return self.active_session

    async def submit(self, user_id: int, **kwargs: object):
        del user_id
        self.submit_calls.append(kwargs)
        return {
            "review": {"status": "graded", "score_percent": 0.0, "feedback": None},
            "reference_explanation_ru": "не должно вызываться",
        }


def _controller(gateway: FakeCareerGateway) -> MlTechnicalTelegramController:
    return MlTechnicalTelegramController(gateway, allowed_ids=frozenset({111}))


def _flat_buttons(markup: object) -> list[tuple[str, str]]:
    rows = getattr(markup, "inline_keyboard", [])
    return [(button.text, button.callback_data) for row in rows for button in row]


def _some_active_ml_session() -> dict:
    return {
        "session_id": str(uuid4()),
        "current_item": {
            "item_id": str(uuid4()),
            "position": 1,
            "question": {"id": "mltech_001", "question_ru": "?"},
        },
    }


# ---------------------------------------------------------------------------
# Menus
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_home_menu_includes_career_button():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    message = FakeMessage(111, "/start")

    await controller.on_start(message)

    buttons = _flat_buttons(message.markups[-1])
    assert ("Карьера", "menu:career") in buttons


@pytest.mark.asyncio
async def test_career_menu_shows_three_items():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    callback = FakeCallback(111, "menu:career")

    await controller.on_menu(callback)

    buttons = _flat_buttons(callback.message.markups[-1])
    labels = [text for text, _data in buttons]
    assert labels == ["Записать отправленный отклик", "Мои отклики", "Назад"]


# ---------------------------------------------------------------------------
# Adding an application
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_applied_without_payload_sets_pending_and_prompts_cleanly():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    message = FakeMessage(111, "/applied")

    await controller.on_applied(message)

    assert gateway.applications == {}
    assert gateway.pending_intents[11] == {
        "intent": INTENT_CAREER_ADD,
        "application_id": None,
    }
    assert "Компания | Роль | Ссылка" in message.replies[0]
    assert ("Отмена", "career:cancel") in _flat_buttons(message.markups[-1])


@pytest.mark.asyncio
async def test_pending_career_add_accepts_message_without_reply_metadata():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    await controller.on_applied(FakeMessage(111, "/applied"))

    reply = FakeMessage(
        111,
        "Acme | ML Engineer | https://acme.example/1",
        message_id=42,
    )

    await controller.on_text(reply)

    assert len(gateway.applications) == 1
    assert gateway.pending_intents == {}
    assert any("Acme" in text for text in reply.replies)


@pytest.mark.asyncio
async def test_invalid_pending_career_add_keeps_intent_active():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    await controller.on_applied(FakeMessage(111, "/applied"))

    reply = FakeMessage(111, "Acme", message_id=43)

    await controller.on_text(reply)

    assert gateway.applications == {}
    assert gateway.pending_intents[11]["intent"] == INTENT_CAREER_ADD
    assert "Компания | Роль | Ссылка" in reply.replies[-1]


@pytest.mark.asyncio
async def test_career_reply_during_active_ml_session_never_calls_submit():
    gateway = FakeCareerGateway()
    gateway.active_session = _some_active_ml_session()
    controller = _controller(gateway)
    await controller.on_applied(FakeMessage(111, "/applied"))

    reply = FakeMessage(
        111,
        "Acme | ML Engineer | https://acme.example/1",
        message_id=44,
    )

    await controller.on_text(reply)

    assert gateway.submit_calls == []
    assert len(gateway.applications) == 1


@pytest.mark.asyncio
async def test_direct_three_field_payload_records_without_pending_state():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    message = FakeMessage(
        111,
        "Непоправку|AI Engineer|https://spb.hh.ru/vacancy/135445141",
        message_id=45,
    )

    await controller.on_text(message)

    assert len(gateway.applications) == 1
    assert gateway.pending_intents == {}
    assert gateway.submit_calls == []


@pytest.mark.asyncio
async def test_pending_career_add_survives_controller_restart():
    gateway = FakeCareerGateway()
    first_controller = _controller(gateway)
    await first_controller.on_applied(FakeMessage(111, "/applied"))

    second_controller = _controller(gateway)
    reply = FakeMessage(
        111,
        "Acme | ML Engineer | https://acme.example/1",
        message_id=46,
    )

    await second_controller.on_text(reply)

    assert len(gateway.applications) == 1
    assert gateway.pending_intents == {}


@pytest.mark.parametrize(
    "url",
    [
        "https://hh.ru/vacancy/12345678",
        "https://www.linkedin.com/jobs/view/98765",
        "https://boards.greenhouse.io/acme/jobs/4242",
        "https://jobs.lever.co/acme/uuid-here",
    ],
)
@pytest.mark.asyncio
async def test_naked_vacancy_link_never_calls_ml_submit(url: str):
    gateway = FakeCareerGateway()
    gateway.active_session = _some_active_ml_session()
    controller = _controller(gateway)
    message = FakeMessage(111, f"Откликнулся вот сюда: {url}", message_id=50)

    await controller.on_text(message)

    assert gateway.submit_calls == []
    assert gateway.applications == {}
    assert any("Карьера" in text for text in message.replies)


@pytest.mark.asyncio
async def test_malformed_applied_command_reprompts_and_writes_nothing():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    message = FakeMessage(111, "/applied only one field")

    await controller.on_applied(message)

    assert gateway.applications == {}
    assert any("Не указана роль" in reply for reply in message.replies)
    assert ("Отмена", "career:cancel") in _flat_buttons(message.markups[-1])


@pytest.mark.asyncio
async def test_unauthorized_telegram_id_cannot_record_application():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    message = FakeMessage(999, "/applied Acme | ML Engineer | https://acme.example/1")

    await controller.on_applied(message)

    assert gateway.applications == {}


# ---------------------------------------------------------------------------
# Listing, details, transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_applications_command_reports_counts_and_offers_buttons():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    await controller.on_applied(
        FakeMessage(111, "/applied Acme | ML Engineer | https://acme.example/1")
    )

    message = FakeMessage(111, "/applications")
    await controller.on_applications(message)

    assert any("Всего заявок: 1" in reply for reply in message.replies)
    buttons = _flat_buttons(message.markups[-1])
    assert any("Acme" in text for text, _data in buttons)


@pytest.mark.asyncio
async def test_list_then_details_then_allowed_transition():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    await controller.on_applied(
        FakeMessage(111, "/applied Acme | ML Engineer | https://acme.example/1")
    )
    application_id = gateway.applications_order[0]

    list_callback = FakeCallback(111, "career:list")
    await controller.on_career_callback(list_callback)
    buttons = _flat_buttons(list_callback.message.markups[-1])
    app_callback_data = next(data for text, data in buttons if "Acme" in text)
    assert app_callback_data == _career_app_callback("app", application_id)

    details_callback = FakeCallback(111, app_callback_data)
    await controller.on_career_callback(details_callback)
    detail_buttons = _flat_buttons(details_callback.message.markups[-1])
    transition_data = _career_status_callback(application_id, STATUS_SCREENING)
    assert any(data == transition_data for _text, data in detail_buttons)

    transition_callback = FakeCallback(111, transition_data)
    await controller.on_career_callback(transition_callback)

    assert gateway.applications[application_id]["status"] == STATUS_SCREENING
    assert transition_callback.answers == ["Статус обновлен"]


@pytest.mark.asyncio
async def test_forbidden_transition_fails_closed():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    await controller.on_applied(
        FakeMessage(111, "/applied Acme | ML Engineer | https://acme.example/1")
    )
    application_id = gateway.applications_order[0]

    callback = FakeCallback(111, _career_status_callback(application_id, STATUS_OFFER))
    await controller.on_career_callback(callback)

    assert gateway.applications[application_id]["status"] == STATUS_APPLIED
    assert callback.answers == ["Недопустимый переход"]
    assert gateway.status_events == []


@pytest.mark.asyncio
async def test_stale_transition_after_reject_fails_closed():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    await controller.on_applied(
        FakeMessage(111, "/applied Acme | ML Engineer | https://acme.example/1")
    )
    application_id = gateway.applications_order[0]
    reject = FakeCallback(111, _career_status_callback(application_id, STATUS_REJECTED))
    await controller.on_career_callback(reject)

    stale = FakeCallback(
        111,
        _career_status_callback(application_id, STATUS_SCREENING),
        callback_id="cb-2",
    )
    await controller.on_career_callback(stale)

    assert gateway.applications[application_id]["status"] == STATUS_REJECTED
    assert stale.answers == ["Недопустимый переход"]


@pytest.mark.asyncio
async def test_status_callback_replay_is_idempotent():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    await controller.on_applied(
        FakeMessage(111, "/applied Acme | ML Engineer | https://acme.example/1")
    )
    application_id = gateway.applications_order[0]
    data = _career_status_callback(application_id, STATUS_SCREENING)

    first = FakeCallback(111, data, callback_id="cb-replay")
    replay = FakeCallback(111, data, callback_id="cb-replay")
    await controller.on_career_callback(first)
    await controller.on_career_callback(replay)

    assert gateway.status_events == [(application_id, STATUS_SCREENING)]
    assert gateway.applications[application_id]["status"] == STATUS_SCREENING


# ---------------------------------------------------------------------------
# Nearest action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_next_action_reply_updates_fields_and_appends_one_note_event():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    await controller.on_applied(
        FakeMessage(111, "/applied Acme | ML Engineer | https://acme.example/1")
    )
    application_id = gateway.applications_order[0]

    prompt_callback = FakeCallback(111, _career_app_callback("next", application_id))
    await controller.on_career_callback(prompt_callback)
    prompt_text = prompt_callback.message.replies[-1]

    reply = FakeMessage(
        111,
        "Прислать тестовое | 2026-08-01",
        message_id=60,
        reply_to_message=FakeMessage(111, prompt_text),
    )
    await controller.on_text(reply)

    assert gateway.note_events == [
        {"application_id": application_id, "next_action": "Прислать тестовое"}
    ]
    assert gateway.applications[application_id]["next_action"] == "Прислать тестовое"
    assert (
        gateway.applications[application_id]["next_action_due_date"]
        == date(2026, 8, 1).isoformat()
    )


@pytest.mark.asyncio
async def test_next_action_reply_allows_empty_date():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    await controller.on_applied(
        FakeMessage(111, "/applied Acme | ML Engineer | https://acme.example/1")
    )
    application_id = gateway.applications_order[0]

    prompt_callback = FakeCallback(111, _career_app_callback("next", application_id))
    await controller.on_career_callback(prompt_callback)
    prompt_text = prompt_callback.message.replies[-1]

    reply = FakeMessage(
        111,
        "Написать рекрутеру",
        message_id=61,
        reply_to_message=FakeMessage(111, prompt_text),
    )
    await controller.on_text(reply)

    assert gateway.note_events == [
        {"application_id": application_id, "next_action": "Написать рекрутеру"}
    ]
    assert gateway.applications[application_id]["next_action_due_date"] is None


@pytest.mark.asyncio
async def test_invalid_date_does_not_write():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    await controller.on_applied(
        FakeMessage(111, "/applied Acme | ML Engineer | https://acme.example/1")
    )
    application_id = gateway.applications_order[0]

    prompt_callback = FakeCallback(111, _career_app_callback("next", application_id))
    await controller.on_career_callback(prompt_callback)
    prompt_text = prompt_callback.message.replies[-1]

    reply = FakeMessage(
        111,
        "Прислать тестовое | завтра",
        message_id=62,
        reply_to_message=FakeMessage(111, prompt_text),
    )
    await controller.on_text(reply)

    assert gateway.note_events == []
    assert gateway.applications[application_id]["next_action"] is None
    assert "ГГГГ-ММ-ДД" in reply.replies[-1]
    assert ("Отмена", "career:cancel") in _flat_buttons(reply.markups[-1])
