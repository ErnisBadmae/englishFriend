from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.adapters.telegram.ml_technical_bot import (
    MlTechnicalTelegramController,
    _career_applied_callback,
    _career_feedback_start_callback,
    _career_item_callback,
    _career_verdict_callback,
)
from app.services.career_inbox_service import CareerInboxError
from app.services.career_ledger_service import (
    INTENT_CAREER_FEEDBACK,
    INTENT_CAREER_MANUAL_LEAD,
)


class FakeChat:
    def __init__(self, chat_id: int, chat_type: str = "private") -> None:
        self.id = chat_id
        self.type = chat_type


class FakeMessage:
    def __init__(self, telegram_id: int, text: str = "", *, message_id: int = 1) -> None:
        self.chat = FakeChat(telegram_id)
        self.from_user = SimpleNamespace(id=telegram_id)
        self.text = text
        self.message_id = message_id
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


class FakeInboxGateway:
    """Minimal double covering the Slice A inbox/feedback surface only."""

    def __init__(self) -> None:
        self.links = {111: 11}
        self.pending_intents: dict[int, dict] = {}
        self.inbox_items: dict[str, dict] = {}
        self.inbox_order: list[str] = []
        self.applications: dict[str, dict] = {}
        self.feedback_events: list[dict] = []
        self.used_idempotency_keys: set[str] = set()
        self.suggestion_manual_lead: dict | None = None
        self.suggestion_feedback: dict | None = None
        self.suggestions_by_text: dict[str, dict] = {}
        self.suggest_manual_lead_calls: list[str] = []

    async def resolve_user(self, telegram_id: int):
        return self.links.get(telegram_id)

    async def set_pending_intent(self, user_id: int, *, intent: str, application_id=None, payload=None):
        pending = {"intent": intent, "application_id": application_id, "payload": payload}
        self.pending_intents[user_id] = pending
        return pending

    async def get_active_pending_intent(self, user_id: int):
        return self.pending_intents.get(user_id)

    async def clear_pending_intent(self, user_id: int):
        self.pending_intents.pop(user_id, None)

    async def discard_expired_pending_intents(self, user_id: int):
        return 0

    # ML-session no-ops (on_text falls through to them if nothing else matches)
    async def active(self, user_id: int):
        return None

    async def submit(self, user_id: int, **kwargs):
        raise AssertionError("submit must not be called for career-only tests")

    # Existing career-ledger surface (unused directly, but referenced by
    # controller helpers on the application detail screen).
    async def get_application(self, user_id: int, application_id: str):
        return self.applications.get(application_id)

    # Suggestion (LLM, untrusted extractor)
    async def suggest_manual_lead(self, raw_text: str):
        self.suggest_manual_lead_calls.append(raw_text)
        if raw_text in self.suggestions_by_text:
            return self.suggestions_by_text[raw_text]
        return self.suggestion_manual_lead or {
            "company": None,
            "role_title": None,
            "event_kind": "unknown",
            "questions_for_recruiter": [],
            "evidence_quote": None,
        }

    async def suggest_feedback(self, raw_text: str):
        return self.suggestion_feedback or {
            "category": "unknown",
            "evidence_quote": None,
            "suggested_status_change": None,
            "suggested_next_action": None,
            "rationale": "",
        }

    # Manual lead persistence
    async def confirm_manual_lead(
        self, user_id, *, source, raw_text, company, role_title, questions_for_recruiter, idempotency_key, actor_id
    ):
        if idempotency_key in self.used_idempotency_keys:
            existing = next(
                item for item in self.inbox_items.values() if item["_idempotency_key"] == idempotency_key
            )
            return {"created": False, "inbox_item": existing}
        item_id = str(uuid4())
        item = {
            "inbox_item_id": item_id,
            "source": source,
            "company": company,
            "role_title": role_title,
            "location": None,
            "url": None,
            "route": None,
            "gates": None,
            "questions_for_recruiter": questions_for_recruiter,
            "owner_verdict": None,
            "linked_application_id": None,
            "_idempotency_key": idempotency_key,
        }
        self.inbox_items[item_id] = item
        self.inbox_order.append(item_id)
        self.used_idempotency_keys.add(idempotency_key)
        return {"created": True, "inbox_item": item}

    async def list_inbox_items(self, user_id: int):
        return [self.inbox_items[i] for i in self.inbox_order[:7]]

    async def get_inbox_item(self, user_id: int, inbox_item_id: str):
        return self.inbox_items.get(inbox_item_id)

    async def set_inbox_verdict(self, user_id, *, inbox_item_id, verdict, idempotency_key, actor_id):
        item = self.inbox_items.get(inbox_item_id)
        if item is None:
            raise CareerInboxError(f"unknown career inbox_item_id: {inbox_item_id}")
        item["owner_verdict"] = verdict
        return {"created": True, "inbox_item": item}

    async def confirm_inbox_applied(self, user_id, *, inbox_item_id, idempotency_key, actor_id):
        item = self.inbox_items.get(inbox_item_id)
        if item is None or item["owner_verdict"] != "prepare":
            raise CareerInboxError("confirm_applied requires a prior 'prepare' verdict")
        application_id = str(uuid4())
        application = {
            "application_id": application_id,
            "company": item["company"],
            "role_title": item["role_title"],
        }
        self.applications[application_id] = application
        item["owner_verdict"] = "applied"
        item["linked_application_id"] = application_id
        return {"created": True, "inbox_item": item, "application": application}

    async def confirm_feedback(
        self, user_id, *, application_id, category, raw_feedback, evidence_quote, next_action, idempotency_key, actor_id
    ):
        if idempotency_key in self.used_idempotency_keys:
            return {"created": False, "feedback_event": self.feedback_events[-1]}
        event = {
            "application_id": application_id,
            "category": category,
            "raw_feedback": raw_feedback,
            "evidence_quote": evidence_quote,
            "next_action": next_action,
        }
        self.feedback_events.append(event)
        self.used_idempotency_keys.add(idempotency_key)
        return {"created": True, "feedback_event": event}


def _controller(gateway: FakeInboxGateway, *, enabled: bool) -> MlTechnicalTelegramController:
    return MlTechnicalTelegramController(
        gateway, allowed_ids=frozenset({111}), career_inbox_enabled=enabled
    )


def _flat_buttons(markup: object) -> list[tuple[str, str]]:
    rows = getattr(markup, "inline_keyboard", [])
    return [(button.text, button.callback_data) for row in rows for button in row]


# ---------------------------------------------------------------------------
# Feature flag gating
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flag_off_hides_inbox_and_lead_menu_items():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=False)
    callback = FakeCallback(111, "menu:career")

    await controller.on_menu(callback)

    labels = [text for text, _data in _flat_buttons(callback.message.markups[-1])]
    assert "Входящие" not in labels
    assert "Добавить контакт или ответ" not in labels


@pytest.mark.asyncio
async def test_flag_off_inbox_callback_fails_closed():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=False)
    callback = FakeCallback(111, "career:inbox")

    await controller.on_career_callback(callback)

    assert callback.answers == ["Функция выключена"]


@pytest.mark.asyncio
async def test_flag_on_shows_inbox_and_lead_menu_items():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True)
    callback = FakeCallback(111, "menu:career")

    await controller.on_menu(callback)

    labels = [text for text, _data in _flat_buttons(callback.message.markups[-1])]
    assert labels == [
        "Записать отправленный отклик",
        "Отклики",
        "Входящие",
        "Добавить контакт или ответ",
        "Назад",
    ]


# ---------------------------------------------------------------------------
# Manual lead: preview before confirm, nothing written until confirmed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manual_lead_paste_shows_preview_and_writes_nothing():
    gateway = FakeInboxGateway()
    gateway.suggestion_manual_lead = {
        "company": "TCS Group",
        "role_title": "ML Engineer",
        "event_kind": "inbound_message",
        "questions_for_recruiter": [],
        "evidence_quote": "TCS Group ищет ML Engineer",
    }
    controller = _controller(gateway, enabled=True)
    lead_callback = FakeCallback(111, "career:lead")
    await controller.on_career_callback(lead_callback)
    assert gateway.pending_intents[11]["intent"] == INTENT_CAREER_MANUAL_LEAD

    paste = FakeMessage(111, "TCS Group ищет ML Engineer, удалёнка.", message_id=10)
    await controller.on_text(paste)

    assert gateway.inbox_items == {}
    assert "TCS Group" in paste.replies[-1]
    assert ("Подтвердить", "career:leadok:0") in _flat_buttons(paste.markups[-1])


@pytest.mark.asyncio
async def test_manual_lead_confirm_creates_exactly_one_item():
    gateway = FakeInboxGateway()
    gateway.suggestion_manual_lead = {
        "company": "Andersen",
        "role_title": None,
        "event_kind": "inbound_message",
        "questions_for_recruiter": [],
        "evidence_quote": None,
    }
    controller = _controller(gateway, enabled=True)
    await controller.on_career_callback(FakeCallback(111, "career:lead"))
    await controller.on_text(FakeMessage(111, "Andersen recruiter message", message_id=11))

    confirm = FakeCallback(111, "career:leadok:0", callback_id="confirm-1")
    await controller.on_career_callback(confirm)

    assert len(gateway.inbox_items) == 1
    assert gateway.pending_intents == {}
    item = next(iter(gateway.inbox_items.values()))
    assert item["company"] == "Andersen"


@pytest.mark.asyncio
async def test_manual_lead_cancel_writes_nothing():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True)
    await controller.on_career_callback(FakeCallback(111, "career:lead"))
    await controller.on_text(FakeMessage(111, "Elinext recruiter message", message_id=12))

    cancel = FakeCallback(111, "career:cancel")
    await controller.on_career_callback(cancel)

    assert gateway.inbox_items == {}
    assert gateway.pending_intents == {}


@pytest.mark.asyncio
async def test_stale_confirm_without_pending_draft_fails_closed():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True)

    confirm = FakeCallback(111, "career:leadok:0")
    await controller.on_career_callback(confirm)

    assert confirm.answers == ["Черновик устарел"]
    assert gateway.inbox_items == {}


# ---------------------------------------------------------------------------
# Manual lead: batch paste (Career Inbox batch paste v0)
# ---------------------------------------------------------------------------

_REAL_BATCH_BLOB = (
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


@pytest.mark.asyncio
async def test_batch_paste_of_three_yields_three_previews_and_three_items():
    gateway = FakeInboxGateway()
    gateway.suggestion_manual_lead = {
        "company": "Some Co",
        "role_title": None,
        "event_kind": "rejection",
        "questions_for_recruiter": [],
        "evidence_quote": None,
    }
    controller = _controller(gateway, enabled=True)
    await controller.on_career_callback(FakeCallback(111, "career:lead"))

    paste = FakeMessage(111, _REAL_BATCH_BLOB, message_id=40)
    await controller.on_text(paste)

    assert len(gateway.suggest_manual_lead_calls) == 3
    assert "Лид 1 из 3" in paste.replies[-1]
    assert gateway.inbox_items == {}  # nothing written yet

    confirm1 = FakeCallback(111, "career:leadok:0", callback_id="batch-1")
    await controller.on_career_callback(confirm1)
    assert "Лид 2 из 3" in confirm1.message.replies[-1]

    confirm2 = FakeCallback(111, "career:leadok:1", callback_id="batch-2")
    await controller.on_career_callback(confirm2)
    assert "Лид 3 из 3" in confirm2.message.replies[-1]

    confirm3 = FakeCallback(111, "career:leadok:2", callback_id="batch-3")
    await controller.on_career_callback(confirm3)

    assert len(gateway.inbox_items) == 3
    assert gateway.pending_intents == {}
    assert "Готово: обработано 3 из 3" in confirm3.message.replies[-1]


@pytest.mark.asyncio
async def test_single_message_paste_still_yields_one_preview_and_one_item():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True)
    await controller.on_career_callback(FakeCallback(111, "career:lead"))

    paste = FakeMessage(111, "Just one recruiter message.", message_id=41)
    await controller.on_text(paste)

    assert "Лид 1 из" not in paste.replies[-1]  # no position marker for a single lead
    assert len(gateway.suggest_manual_lead_calls) == 1

    confirm = FakeCallback(111, "career:leadok:0", callback_id="single-1")
    await controller.on_career_callback(confirm)

    assert len(gateway.inbox_items) == 1
    assert gateway.pending_intents == {}


@pytest.mark.asyncio
async def test_confirm_replay_does_not_create_duplicate_item():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True)
    await controller.on_career_callback(FakeCallback(111, "career:lead"))
    await controller.on_text(FakeMessage(111, "Single lead text", message_id=42))

    first = FakeCallback(111, "career:leadok:0", callback_id="replay-1")
    await controller.on_career_callback(first)
    # Same segment_id-derived idempotency key would be replayed if Telegram
    # resends the same update before the pending intent advances/clears.
    replay = FakeCallback(111, "career:leadok:0", callback_id="replay-1")
    await controller.on_career_callback(replay)

    assert len(gateway.inbox_items) == 1


@pytest.mark.asyncio
async def test_skip_this_lead_advances_without_creating_item():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True)
    await controller.on_career_callback(FakeCallback(111, "career:lead"))
    await controller.on_text(FakeMessage(111, _REAL_BATCH_BLOB, message_id=43))

    skip1 = FakeCallback(111, "career:leadskip:0", callback_id="skip-1")
    await controller.on_career_callback(skip1)
    assert "Лид 2 из 3" in skip1.message.replies[-1]
    assert gateway.inbox_items == {}

    confirm2 = FakeCallback(111, "career:leadok:1", callback_id="skip-2")
    await controller.on_career_callback(confirm2)
    confirm3 = FakeCallback(111, "career:leadok:2", callback_id="skip-3")
    await controller.on_career_callback(confirm3)

    assert len(gateway.inbox_items) == 2  # lead 1 was skipped, not saved
    assert gateway.pending_intents == {}


@pytest.mark.asyncio
async def test_stale_leadskip_without_pending_draft_fails_closed():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True)

    skip = FakeCallback(111, "career:leadskip:0")
    await controller.on_career_callback(skip)

    assert skip.answers == ["Черновик устарел"]
    assert gateway.inbox_items == {}


@pytest.mark.asyncio
async def test_batch_cancel_clears_whole_queue():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True)
    await controller.on_career_callback(FakeCallback(111, "career:lead"))
    await controller.on_text(FakeMessage(111, _REAL_BATCH_BLOB, message_id=44))

    await controller.on_career_callback(FakeCallback(111, "career:cancel"))

    assert gateway.inbox_items == {}
    assert gateway.pending_intents == {}


# ---------------------------------------------------------------------------
# Inbox list/detail/verdict
# ---------------------------------------------------------------------------


async def _seeded_item(gateway: FakeInboxGateway, controller: MlTechnicalTelegramController) -> str:
    await controller.on_career_callback(FakeCallback(111, "career:lead"))
    await controller.on_text(FakeMessage(111, "Some recruiter text", message_id=20))
    await controller.on_career_callback(FakeCallback(111, "career:leadok:0", callback_id="seed-1"))
    return next(iter(gateway.inbox_items))


@pytest.mark.asyncio
async def test_inbox_list_shows_seeded_item():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True)
    await _seeded_item(gateway, controller)

    list_callback = FakeCallback(111, "career:inbox")
    await controller.on_career_callback(list_callback)

    assert "Входящие" in list_callback.message.replies[-1]
    buttons = _flat_buttons(list_callback.message.markups[-1])
    assert len(buttons) == 2  # one item + Назад


@pytest.mark.asyncio
async def test_prepare_then_applied_links_one_application():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True)
    item_id = await _seeded_item(gateway, controller)

    prepare = FakeCallback(111, _career_verdict_callback(item_id, "prepare"))
    await controller.on_career_callback(prepare)
    assert gateway.inbox_items[item_id]["owner_verdict"] == "prepare"

    applied = FakeCallback(111, _career_applied_callback(item_id))
    await controller.on_career_callback(applied)

    assert gateway.inbox_items[item_id]["owner_verdict"] == "applied"
    assert len(gateway.applications) == 1


@pytest.mark.asyncio
async def test_applied_without_prior_prepare_fails_closed_and_creates_nothing():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True)
    item_id = await _seeded_item(gateway, controller)

    applied = FakeCallback(111, _career_applied_callback(item_id))
    await controller.on_career_callback(applied)

    assert applied.answers == ["Сначала нажмите Готовить"]
    assert gateway.applications == {}
    assert gateway.inbox_items[item_id]["owner_verdict"] is None


@pytest.mark.asyncio
async def test_skip_verdict_never_creates_application():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True)
    item_id = await _seeded_item(gateway, controller)

    skip = FakeCallback(111, _career_verdict_callback(item_id, "skip"))
    await controller.on_career_callback(skip)

    assert gateway.inbox_items[item_id]["owner_verdict"] == "skip"
    assert gateway.applications == {}


@pytest.mark.asyncio
async def test_ask_verdict_shows_questions_and_sends_nothing_external():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True)
    item_id = await _seeded_item(gateway, controller)
    gateway.inbox_items[item_id]["questions_for_recruiter"] = ["Доступна ли удалёнка?"]

    ask = FakeCallback(111, _career_verdict_callback(item_id, "ask"))
    await controller.on_career_callback(ask)

    assert gateway.inbox_items[item_id]["owner_verdict"] == "ask"
    assert any("Доступна ли удалёнка?" in reply for reply in ask.message.replies)


@pytest.mark.asyncio
async def test_stale_item_callback_fails_closed():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True)

    callback = FakeCallback(111, "career:item:not-a-valid-id")
    await controller.on_career_callback(callback)

    assert callback.answers == ["Кнопка устарела"]


# ---------------------------------------------------------------------------
# Feedback: preview before confirm, append-only afterwards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_feedback_start_requires_flag():
    gateway = FakeInboxGateway()
    application_id = str(uuid4())
    gateway.applications[application_id] = {"application_id": application_id, "company": "Acme"}
    controller = _controller(gateway, enabled=False)

    start = FakeCallback(111, _career_feedback_start_callback(application_id))
    await controller.on_career_callback(start)

    assert start.answers == ["Функция выключена"]
    assert gateway.pending_intents == {}


@pytest.mark.asyncio
async def test_feedback_paste_then_confirm_creates_one_event():
    gateway = FakeInboxGateway()
    application_id = str(uuid4())
    gateway.suggestion_feedback = {
        "category": "role_scope_mismatch",
        "evidence_quote": "DWH/ETL/Greenplum",
        "suggested_status_change": "rejected",
        "suggested_next_action": None,
        "rationale": "role scope gap",
    }
    controller = _controller(gateway, enabled=True)

    start = FakeCallback(111, _career_feedback_start_callback(application_id))
    await controller.on_career_callback(start)
    assert gateway.pending_intents[11]["intent"] == INTENT_CAREER_FEEDBACK

    paste = FakeMessage(111, "Отказ: ищем опыт с DWH/ETL/Greenplum", message_id=30)
    await controller.on_text(paste)
    assert gateway.feedback_events == []
    assert "role_scope_mismatch" in paste.replies[-1]

    confirm = FakeCallback(111, "career:fbok", callback_id="fb-confirm-1")
    await controller.on_career_callback(confirm)

    assert len(gateway.feedback_events) == 1
    assert gateway.feedback_events[0]["category"] == "role_scope_mismatch"
    assert gateway.pending_intents == {}


@pytest.mark.asyncio
async def test_feedback_cancel_writes_nothing():
    gateway = FakeInboxGateway()
    application_id = str(uuid4())
    controller = _controller(gateway, enabled=True)
    await controller.on_career_callback(
        FakeCallback(111, _career_feedback_start_callback(application_id))
    )
    await controller.on_text(FakeMessage(111, "Generic rejection text", message_id=31))

    await controller.on_career_callback(FakeCallback(111, "career:cancel"))

    assert gateway.feedback_events == []
    assert gateway.pending_intents == {}
