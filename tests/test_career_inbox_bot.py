from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.adapters.telegram.ml_technical_bot as ml_technical_bot
from app.adapters.telegram.ml_technical_bot import (
    MlTechnicalTelegramController,
    _career_applied_callback,
    _career_draft_approve_callback,
    _career_draft_callback,
    _career_draft_copy_callback,
    _career_draft_facts_callback,
    _career_draft_reject_callback,
    _career_feedback_start_callback,
    _career_item_callback,
    _career_package_cancel_callback,
    _career_package_confirm_callback,
    _career_package_cv_callback,
    _career_package_item_callback,
    _career_package_send_callback,
    _career_package_start_callback,
    _career_verdict_callback,
)
from app.services.career_inbox_service import CareerInboxError
from app.services.career_ledger_service import (
    INTENT_CAREER_FEEDBACK,
    INTENT_CAREER_MANUAL_LEAD,
)
from app.services.vacancy_refresh_service import RefreshResult


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
        self.cover_letter_drafts: dict[str, dict] = {}
        self.generate_draft_calls: list[str] = []
        self.manual_path_result: dict | None = None
        self.draft_body_by_call: str = "Черновик текста."
        self.application_packages: dict[str, dict] = {}
        self.prepare_package_calls: list[dict] = []
        self.prepare_package_error: Exception | None = None
        self._pkg_seq = 0
        self.submit_idempotency_keys: dict[str, str] = {}

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

    # Cover Letter Draft v0
    async def generate_cover_letter_draft(self, user_id, *, inbox_item_id, idempotency_key, actor_id):
        self.generate_draft_calls.append(inbox_item_id)
        if self.manual_path_result is not None:
            return self.manual_path_result
        if idempotency_key in self.used_idempotency_keys:
            existing = next(
                d for d in self.cover_letter_drafts.values() if d["_idempotency_key"] == idempotency_key
            )
            return {"created": False, "manual_path": False, "draft": existing}
        item = self.inbox_items.get(inbox_item_id)
        if item is None or item.get("owner_verdict") != "prepare":
            raise CareerInboxError("cover letter draft requires a prior 'prepare' verdict")
        version = (
            sum(1 for d in self.cover_letter_drafts.values() if d["inbox_item_id"] == inbox_item_id) + 1
        )
        draft_id = str(uuid4())
        draft = {
            "draft_id": draft_id,
            "inbox_item_id": inbox_item_id,
            "version": version,
            "body": self.draft_body_by_call,
            "grounding_report": {"used_facts": [], "flagged_sentences": []},
            "status": "draft",
            "_idempotency_key": idempotency_key,
        }
        self.cover_letter_drafts[draft_id] = draft
        self.used_idempotency_keys.add(idempotency_key)
        return {"created": True, "manual_path": False, "draft": draft}

    async def approve_cover_letter_draft(self, user_id, *, draft_id, actor_id):
        draft = self.cover_letter_drafts.get(draft_id)
        if draft is None:
            raise CareerInboxError(f"unknown cover letter draft_id: {draft_id}")
        if draft["status"] == "owner_approved":
            return {"created": False, "draft": draft}
        if draft["status"] != "draft":
            raise CareerInboxError(f"draft already {draft['status']}; cannot transition again")
        draft["status"] = "owner_approved"
        return {"created": True, "draft": draft}

    async def reject_cover_letter_draft(self, user_id, *, draft_id, actor_id):
        draft = self.cover_letter_drafts.get(draft_id)
        if draft is None:
            raise CareerInboxError(f"unknown cover letter draft_id: {draft_id}")
        if draft["status"] == "rejected":
            return {"created": False, "draft": draft}
        if draft["status"] != "draft":
            raise CareerInboxError(f"draft already {draft['status']}; cannot transition again")
        draft["status"] = "rejected"
        return {"created": True, "draft": draft}

    async def get_cover_letter_draft(self, user_id, draft_id):
        return self.cover_letter_drafts.get(draft_id)

    # Application Package v0 (Slice D1a/D1b.1/D1b.2a)
    async def prepare_application_package(
        self, user_id, *, inbox_item_id, cover_draft_id, cv_variant_id, actor_id
    ):
        self.prepare_package_calls.append(
            {
                "inbox_item_id": inbox_item_id,
                "cover_draft_id": cover_draft_id,
                "cv_variant_id": cv_variant_id,
            }
        )
        if self.prepare_package_error is not None:
            raise self.prepare_package_error
        for existing in self.application_packages.values():
            if (
                existing["inbox_item_id"] == inbox_item_id
                and existing["cover_draft_id"] == cover_draft_id
                and existing["cv_variant_id"] == cv_variant_id
            ):
                return {"created": False, "package": existing}
        self._pkg_seq += 1
        package_id = str(uuid4())
        package = {
            "package_id": package_id,
            "inbox_item_id": inbox_item_id,
            "cover_draft_id": cover_draft_id,
            "cv_variant_id": cv_variant_id,
            "company": self.inbox_items.get(inbox_item_id, {}).get("company"),
            "role_title": self.inbox_items.get(inbox_item_id, {}).get("role_title"),
            "source_url": self.inbox_items.get(inbox_item_id, {}).get("url"),
            "gates_snapshot": self.inbox_items.get(inbox_item_id, {}).get("gates") or {},
            "questions_for_recruiter": [],
            "package_content_hash": "f" * 64,
            "status": "ready",
            "_seq": self._pkg_seq,
        }
        self.application_packages[package_id] = package
        return {"created": True, "package": package}

    async def list_ready_application_packages(self, user_id, *, limit=7):
        ready = [p for p in self.application_packages.values() if p["status"] == "ready"]
        ready.sort(key=lambda p: p["_seq"], reverse=True)
        return ready[: max(1, min(limit, 7))]

    async def get_application_package(self, user_id, package_id):
        return self.application_packages.get(package_id)

    async def submit_application_package(
        self, user_id, *, package_id, expected_package_hash, idempotency_key, actor_id
    ):
        if idempotency_key in self.submit_idempotency_keys:
            application_id = self.submit_idempotency_keys[idempotency_key]
            return {"created": False, "application": self.applications[application_id]}
        pkg = self.application_packages.get(package_id)
        if pkg is None:
            raise CareerInboxError(f"unknown application package_id: {package_id}")
        if pkg["package_content_hash"] != expected_package_hash:
            raise CareerInboxError("stale package: expected hash mismatch")
        if pkg["status"] != "ready":
            raise CareerInboxError(f"package already {pkg['status']}; cannot submit")
        application_id = str(uuid4())
        application = {
            "application_id": application_id,
            "company": pkg["company"],
            "role_title": pkg["role_title"],
            "status": "applied",
        }
        self.applications[application_id] = application
        pkg["status"] = "submitted"
        pkg["linked_application_id"] = application_id
        self.submit_idempotency_keys[idempotency_key] = application_id
        return {"created": True, "application": application}


def _controller(
    gateway: FakeInboxGateway,
    *,
    enabled: bool,
    draft_enabled: bool = False,
    refresh_enabled: bool = False,
    ready_queue_enabled: bool = False,
    facts_bank_path: Path | None = None,
) -> MlTechnicalTelegramController:
    kwargs = {}
    if facts_bank_path is not None:
        kwargs["facts_bank_path"] = facts_bank_path
    return MlTechnicalTelegramController(
        gateway,
        allowed_ids=frozenset({111}),
        career_inbox_enabled=enabled,
        career_cover_letter_draft_enabled=draft_enabled,
        career_vacancy_refresh_enabled=refresh_enabled,
        vacancy_refresh_repo_path="C:/fake/telegram-digest",
        career_ready_queue_enabled=ready_queue_enabled,
        **kwargs,
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


# ---------------------------------------------------------------------------
# Cover Letter Draft v0 (career/CAREER_COVER_LETTER_DRAFT_SPEC.md, Slice 2)
# ---------------------------------------------------------------------------


async def _prepared_item(
    gateway: FakeInboxGateway, controller: MlTechnicalTelegramController
) -> str:
    inbox_item_id = await _seeded_item(gateway, controller)
    await controller.on_career_callback(
        FakeCallback(111, _career_verdict_callback(inbox_item_id, "prepare"), callback_id="prep-1")
    )
    return inbox_item_id


@pytest.mark.asyncio
async def test_draft_button_appears_only_after_prepare():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, draft_enabled=True)
    inbox_item_id = await _seeded_item(gateway, controller)

    detail = FakeCallback(111, _career_item_callback(inbox_item_id))
    await controller.on_career_callback(detail)
    labels_before = [t for t, _d in _flat_buttons(detail.message.markups[-1])]
    assert "Черновик сопровода" not in labels_before

    await controller.on_career_callback(
        FakeCallback(111, _career_verdict_callback(inbox_item_id, "prepare"), callback_id="prep-1")
    )
    detail2 = FakeCallback(111, _career_item_callback(inbox_item_id))
    await controller.on_career_callback(detail2)
    labels_after = [t for t, _d in _flat_buttons(detail2.message.markups[-1])]
    assert "Черновик сопровода" in labels_after


@pytest.mark.asyncio
async def test_draft_flag_off_fails_closed():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, draft_enabled=False)
    inbox_item_id = await _prepared_item(gateway, controller)

    draft_cb = FakeCallback(111, _career_draft_callback(inbox_item_id))
    await controller.on_career_callback(draft_cb)

    assert draft_cb.answers == ["Функция выключена"]
    assert gateway.cover_letter_drafts == {}


@pytest.mark.asyncio
async def test_generate_draft_shows_body_and_grounding_report():
    gateway = FakeInboxGateway()
    gateway.draft_body_by_call = "Здравствуйте! Откликаюсь на роль ML Engineer."
    controller = _controller(gateway, enabled=True, draft_enabled=True)
    inbox_item_id = await _prepared_item(gateway, controller)

    draft_cb = FakeCallback(111, _career_draft_callback(inbox_item_id))
    await controller.on_career_callback(draft_cb)

    assert len(gateway.cover_letter_drafts) == 1
    reply = draft_cb.message.replies[-1]
    assert "Откликаюсь на роль ML Engineer" in reply
    buttons = [t for t, _d in _flat_buttons(draft_cb.message.markups[-1])]
    assert buttons == ["Одобрить черновик", "Отклонить черновик", "Скопировать текст"]


@pytest.mark.asyncio
async def test_manual_path_signal_when_generation_unavailable():
    gateway = FakeInboxGateway()
    gateway.manual_path_result = {"created": False, "manual_path": True, "draft": None}
    controller = _controller(gateway, enabled=True, draft_enabled=True)
    inbox_item_id = await _prepared_item(gateway, controller)

    draft_cb = FakeCallback(111, _career_draft_callback(inbox_item_id))
    await controller.on_career_callback(draft_cb)

    assert gateway.cover_letter_drafts == {}
    assert "COVER_LETTER_SKELETON" in draft_cb.message.replies[-1]
    buttons = [t for t, _d in _flat_buttons(draft_cb.message.markups[-1])]
    assert buttons == ["Обновить факты вручную"]


@pytest.mark.asyncio
async def test_approve_creates_no_application_and_sends_nothing():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, draft_enabled=True)
    inbox_item_id = await _prepared_item(gateway, controller)
    draft_cb = FakeCallback(111, _career_draft_callback(inbox_item_id))
    await controller.on_career_callback(draft_cb)
    draft_id = next(iter(gateway.cover_letter_drafts))

    approve = FakeCallback(111, _career_draft_approve_callback(draft_id), callback_id="app-1")
    await controller.on_career_callback(approve)

    assert gateway.cover_letter_drafts[draft_id]["status"] == "owner_approved"
    assert gateway.applications == {}
    assert approve.answers == ["Одобрено"]


@pytest.mark.asyncio
async def test_approve_replay_creates_no_duplicate_version_or_state_change():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, draft_enabled=True)
    inbox_item_id = await _prepared_item(gateway, controller)
    draft_cb = FakeCallback(111, _career_draft_callback(inbox_item_id))
    await controller.on_career_callback(draft_cb)
    draft_id = next(iter(gateway.cover_letter_drafts))

    first = FakeCallback(111, _career_draft_approve_callback(draft_id), callback_id="replay-1")
    await controller.on_career_callback(first)
    replay = FakeCallback(111, _career_draft_approve_callback(draft_id), callback_id="replay-1")
    await controller.on_career_callback(replay)

    assert len(gateway.cover_letter_drafts) == 1
    assert gateway.cover_letter_drafts[draft_id]["status"] == "owner_approved"


@pytest.mark.asyncio
async def test_reject_records_state_without_side_effects():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, draft_enabled=True)
    inbox_item_id = await _prepared_item(gateway, controller)
    draft_cb = FakeCallback(111, _career_draft_callback(inbox_item_id))
    await controller.on_career_callback(draft_cb)
    draft_id = next(iter(gateway.cover_letter_drafts))

    reject = FakeCallback(111, _career_draft_reject_callback(draft_id))
    await controller.on_career_callback(reject)

    assert gateway.cover_letter_drafts[draft_id]["status"] == "rejected"
    assert gateway.applications == {}


@pytest.mark.asyncio
async def test_copy_only_displays_text_and_changes_nothing():
    gateway = FakeInboxGateway()
    gateway.draft_body_by_call = "Текст письма для копирования."
    controller = _controller(gateway, enabled=True, draft_enabled=True)
    inbox_item_id = await _prepared_item(gateway, controller)
    draft_cb = FakeCallback(111, _career_draft_callback(inbox_item_id))
    await controller.on_career_callback(draft_cb)
    draft_id = next(iter(gateway.cover_letter_drafts))

    copy_cb = FakeCallback(111, _career_draft_copy_callback(draft_id))
    await controller.on_career_callback(copy_cb)

    assert copy_cb.message.replies[-1] == "Текст письма для копирования."
    assert gateway.cover_letter_drafts[draft_id]["status"] == "draft"


@pytest.mark.asyncio
async def test_draft_facts_button_never_writes_anything():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, draft_enabled=True)
    inbox_item_id = await _prepared_item(gateway, controller)

    facts_cb = FakeCallback(111, _career_draft_facts_callback(inbox_item_id))
    await controller.on_career_callback(facts_cb)

    assert "facts_bank.yaml" in facts_cb.message.replies[-1]
    assert gateway.cover_letter_drafts == {}


@pytest.mark.asyncio
async def test_stale_draft_callback_fails_closed():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, draft_enabled=True)

    stale = FakeCallback(111, "career:draft:not-a-valid-id")
    await controller.on_career_callback(stale)

    assert stale.answers == ["Кнопка устарела"]


@pytest.mark.asyncio
async def test_stale_draft_action_ids_fail_closed():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, draft_enabled=True)

    for cb_fn in (
        _career_draft_approve_callback,
        _career_draft_reject_callback,
        _career_draft_copy_callback,
    ):
        callback = FakeCallback(111, cb_fn(str(uuid4())))
        await controller.on_career_callback(callback)
        # Either fails closed with an explicit error answer, or "Не найдено"
        # (copy) - never silently succeeds on an unknown draft id.
        assert callback.answers


# ---------------------------------------------------------------------------
# Vacancy refresh (owner-triggered Telegram parser button)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_button_hidden_when_flag_off():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, refresh_enabled=False)
    callback = FakeCallback(111, "menu:career")

    await controller.on_menu(callback)

    labels = [text for text, _data in _flat_buttons(callback.message.markups[-1])]
    assert "Проверить новые вакансии" not in labels


@pytest.mark.asyncio
async def test_refresh_button_shown_when_flag_on():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, refresh_enabled=True)
    callback = FakeCallback(111, "menu:career")

    await controller.on_menu(callback)

    labels = [text for text, _data in _flat_buttons(callback.message.markups[-1])]
    assert "Проверить новые вакансии" in labels


@pytest.mark.asyncio
async def test_refresh_flag_off_fails_closed():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, refresh_enabled=False)
    callback = FakeCallback(111, "career:refresh")

    await controller.on_career_callback(callback)

    assert callback.answers == ["Функция выключена"]


@pytest.mark.asyncio
async def test_refresh_success_shows_summary(monkeypatch):
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, refresh_enabled=True)

    async def fake_refresh_vacancies(*, digest_repo_path, telegram_id):
        assert digest_repo_path == "C:/fake/telegram-digest"
        assert telegram_id == 111
        return RefreshResult(
            True, "DONE. imported=3 skipped_duplicate=0 rejected=0 total_read=3"
        )

    monkeypatch.setattr(
        ml_technical_bot, "refresh_vacancies", fake_refresh_vacancies
    )

    callback = FakeCallback(111, "career:refresh")
    await controller.on_career_callback(callback)

    assert callback.answers[0] == "Запускаю проверку"
    assert any("imported=3" in reply for reply in callback.message.replies)
    assert controller._vacancy_refresh_in_progress is False


@pytest.mark.asyncio
async def test_refresh_failure_shows_error(monkeypatch):
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, refresh_enabled=True)

    async def fake_refresh_vacancies(*, digest_repo_path, telegram_id):
        return RefreshResult(False, "Парсер вакансий упал:\nboom")

    monkeypatch.setattr(
        ml_technical_bot, "refresh_vacancies", fake_refresh_vacancies
    )

    callback = FakeCallback(111, "career:refresh")
    await controller.on_career_callback(callback)

    assert any("Не получилось обновить вакансии" in reply for reply in callback.message.replies)
    assert any("boom" in reply for reply in callback.message.replies)
    assert controller._vacancy_refresh_in_progress is False


@pytest.mark.asyncio
async def test_refresh_busy_guard_blocks_concurrent_runs(monkeypatch):
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, refresh_enabled=True)
    release = asyncio.Event()

    async def slow_refresh_vacancies(*, digest_repo_path, telegram_id):
        await release.wait()
        return RefreshResult(True, "DONE. imported=0")

    monkeypatch.setattr(
        ml_technical_bot, "refresh_vacancies", slow_refresh_vacancies
    )

    first = FakeCallback(111, "career:refresh", callback_id="first")
    second = FakeCallback(111, "career:refresh", callback_id="second")

    first_task = asyncio.create_task(controller.on_career_callback(first))
    await asyncio.sleep(0)  # let the first handler grab the busy-guard
    await controller.on_career_callback(second)

    assert second.answers == ["Уже проверяю, подождите"]

    release.set()
    await first_task
    assert first.answers[0] == "Запускаю проверку"


# ---------------------------------------------------------------------------
# Application package creation (Career OS Slice D1b.1)
# ---------------------------------------------------------------------------


def _facts_bank_with_variants(tmp_path: Path, keys: list[str]) -> Path:
    path = tmp_path / "facts_bank.yaml"
    role_types = "\n".join(f"  {k}:\n    cv: CV_{k}.md" for k in keys)
    path.write_text(
        f"role_types:\n{role_types}\n"
        "facts:\n  - id: profile_core\n    tier: A\n    text: Applied AI инженер.\n",
        encoding="utf-8",
    )
    return path


async def _approved_draft(
    gateway: FakeInboxGateway, controller: MlTechnicalTelegramController, inbox_item_id: str
) -> str:
    before = set(gateway.cover_letter_drafts)
    generate = FakeCallback(
        111, _career_draft_callback(inbox_item_id), callback_id=f"gen-{uuid4().hex}"
    )
    await controller.on_career_callback(generate)
    draft_id = next(iter(set(gateway.cover_letter_drafts) - before))
    approve = FakeCallback(
        111, _career_draft_approve_callback(draft_id), callback_id=f"app-{uuid4().hex}"
    )
    await controller.on_career_callback(approve)
    return draft_id


@pytest.mark.asyncio
async def test_package_button_hidden_when_flag_off():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, draft_enabled=True, ready_queue_enabled=False)
    inbox_item_id = await _prepared_item(gateway, controller)
    draft_id = await _approved_draft(gateway, controller, inbox_item_id)

    detail = FakeCallback(111, _career_draft_approve_callback(draft_id), callback_id="app-2")
    await controller.on_career_callback(detail)

    markup = detail.message.markups[-1]
    buttons = _flat_buttons(markup) if markup is not None else []
    assert not any("Собрать пакет" in text for text, _data in buttons)


@pytest.mark.asyncio
async def test_package_button_shown_when_flag_on():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, draft_enabled=True, ready_queue_enabled=True)
    inbox_item_id = await _prepared_item(gateway, controller)
    draft_id = await _approved_draft(gateway, controller, inbox_item_id)

    detail = FakeCallback(111, _career_draft_approve_callback(draft_id), callback_id="app-2")
    await controller.on_career_callback(detail)

    buttons = _flat_buttons(detail.message.markups[-1])
    assert any("Собрать пакет" in text for text, _data in buttons)


@pytest.mark.asyncio
async def test_package_start_blocked_when_draft_not_approved():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, draft_enabled=True, ready_queue_enabled=True)
    inbox_item_id = await _prepared_item(gateway, controller)
    await controller.on_career_callback(
        FakeCallback(111, _career_draft_callback(inbox_item_id), callback_id="gen-1")
    )
    draft_id = next(iter(gateway.cover_letter_drafts))  # still status='draft'

    callback = FakeCallback(111, _career_package_start_callback(draft_id))
    await controller.on_career_callback(callback)

    assert callback.answers == ["Сначала одобрите черновик"]
    assert gateway.prepare_package_calls == []


@pytest.mark.asyncio
async def test_package_start_bounds_cv_variants_to_three(tmp_path):
    gateway = FakeInboxGateway()
    facts_path = _facts_bank_with_variants(tmp_path, ["a", "b", "c", "d"])
    controller = _controller(
        gateway, enabled=True, draft_enabled=True, ready_queue_enabled=True, facts_bank_path=facts_path
    )
    inbox_item_id = await _prepared_item(gateway, controller)
    draft_id = await _approved_draft(gateway, controller, inbox_item_id)

    callback = FakeCallback(111, _career_package_start_callback(draft_id))
    await controller.on_career_callback(callback)

    buttons = _flat_buttons(callback.message.markups[-1])
    assert len(buttons) == 3


@pytest.mark.asyncio
async def test_package_cv_selection_calls_prepare_with_exact_ids(tmp_path):
    gateway = FakeInboxGateway()
    facts_path = _facts_bank_with_variants(tmp_path, ["agents_llm"])
    controller = _controller(
        gateway, enabled=True, draft_enabled=True, ready_queue_enabled=True, facts_bank_path=facts_path
    )
    inbox_item_id = await _prepared_item(gateway, controller)
    draft_id = await _approved_draft(gateway, controller, inbox_item_id)

    callback = FakeCallback(111, _career_package_cv_callback(draft_id, "agents_llm"))
    await controller.on_career_callback(callback)

    assert gateway.prepare_package_calls == [
        {
            "inbox_item_id": inbox_item_id,
            "cover_draft_id": draft_id,
            "cv_variant_id": "agents_llm",
        }
    ]
    assert any("Пакет готов" in reply for reply in callback.message.replies)


@pytest.mark.asyncio
async def test_package_cv_repeat_click_creates_no_duplicate(tmp_path):
    gateway = FakeInboxGateway()
    facts_path = _facts_bank_with_variants(tmp_path, ["agents_llm"])
    controller = _controller(
        gateway, enabled=True, draft_enabled=True, ready_queue_enabled=True, facts_bank_path=facts_path
    )
    inbox_item_id = await _prepared_item(gateway, controller)
    draft_id = await _approved_draft(gateway, controller, inbox_item_id)

    await controller.on_career_callback(
        FakeCallback(111, _career_package_cv_callback(draft_id, "agents_llm"), callback_id="cv-1")
    )
    await controller.on_career_callback(
        FakeCallback(111, _career_package_cv_callback(draft_id, "agents_llm"), callback_id="cv-2")
    )

    assert len(gateway.application_packages) == 1


@pytest.mark.asyncio
async def test_package_flag_off_blocks_start_and_cv_actions():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, draft_enabled=True, ready_queue_enabled=False)
    inbox_item_id = await _prepared_item(gateway, controller)
    draft_id = await _approved_draft(gateway, controller, inbox_item_id)

    start = FakeCallback(111, _career_package_start_callback(draft_id))
    await controller.on_career_callback(start)
    cv = FakeCallback(111, _career_package_cv_callback(draft_id, "agents_llm"))
    await controller.on_career_callback(cv)

    assert start.answers == ["Функция выключена"]
    assert cv.answers == ["Функция выключена"]
    assert gateway.prepare_package_calls == []


@pytest.mark.asyncio
async def test_package_prepare_error_surfaces_message(tmp_path):
    gateway = FakeInboxGateway()
    facts_path = _facts_bank_with_variants(tmp_path, ["agents_llm"])
    controller = _controller(
        gateway, enabled=True, draft_enabled=True, ready_queue_enabled=True, facts_bank_path=facts_path
    )
    inbox_item_id = await _prepared_item(gateway, controller)
    draft_id = await _approved_draft(gateway, controller, inbox_item_id)
    gateway.prepare_package_error = CareerInboxError("cover draft does not belong to this inbox item")

    callback = FakeCallback(111, _career_package_cv_callback(draft_id, "agents_llm"))
    await controller.on_career_callback(callback)

    assert callback.answers == ["Ошибка"]
    assert any("cover draft does not belong" in reply for reply in callback.message.replies)


# ---------------------------------------------------------------------------
# Ready queue + bounded preview (Career OS Slice D1b.2a, read-only)
# ---------------------------------------------------------------------------


async def _ready_package(
    gateway: FakeInboxGateway,
    controller: MlTechnicalTelegramController,
    facts_path: Path,
    *,
    cv_variant_id: str = "agents_llm",
) -> str:
    inbox_item_id = await _prepared_item(gateway, controller)
    draft_id = await _approved_draft(gateway, controller, inbox_item_id)
    await controller.on_career_callback(
        FakeCallback(111, _career_package_cv_callback(draft_id, cv_variant_id))
    )
    return next(
        p["package_id"]
        for p in gateway.application_packages.values()
        if p["cover_draft_id"] == draft_id
    )


@pytest.mark.asyncio
async def test_ready_queue_hidden_and_blocked_when_flag_off():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, ready_queue_enabled=False)
    menu = FakeCallback(111, "menu:career")
    await controller.on_menu(menu)
    labels = [text for text, _data in _flat_buttons(menu.message.markups[-1])]
    assert "Готовые" not in labels

    ready = FakeCallback(111, "career:ready")
    await controller.on_career_callback(ready)
    item = FakeCallback(111, _career_package_item_callback(str(uuid4())))
    await controller.on_career_callback(item)

    assert ready.answers == ["Функция выключена"]
    assert item.answers == ["Функция выключена"]


@pytest.mark.asyncio
async def test_ready_queue_empty_state_is_safe():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, ready_queue_enabled=True)

    callback = FakeCallback(111, "career:ready")
    await controller.on_career_callback(callback)

    assert any("Готовых пакетов нет." in reply for reply in callback.message.replies)


@pytest.mark.asyncio
async def test_ready_queue_bounded_newest_first_and_excludes_non_ready(tmp_path):
    gateway = FakeInboxGateway()
    facts_path = _facts_bank_with_variants(tmp_path, ["agents_llm"])
    controller = _controller(
        gateway, enabled=True, draft_enabled=True, ready_queue_enabled=True, facts_bank_path=facts_path
    )
    package_ids = []
    for _ in range(9):
        package_ids.append(await _ready_package(gateway, controller, facts_path))
    # One package moves out of 'ready' (e.g. already submitted) - must not be listed.
    gateway.application_packages[package_ids[0]]["status"] = "submitted"

    callback = FakeCallback(111, "career:ready")
    await controller.on_career_callback(callback)

    buttons = _flat_buttons(callback.message.markups[-1])
    assert len(buttons) == 7 + 1  # 7 packages + Назад
    listed_callbacks = [data for _text, data in buttons if data != "career:back"]
    assert _career_package_item_callback(package_ids[0]) not in listed_callbacks
    # newest first: the most recently prepared package is first in the list.
    assert listed_callbacks[0] == _career_package_item_callback(package_ids[-1])


@pytest.mark.asyncio
async def test_package_preview_shows_bounded_fields_and_cv_label(tmp_path):
    gateway = FakeInboxGateway()
    facts_path = _facts_bank_with_variants(tmp_path, ["agents_llm"])
    controller = _controller(
        gateway, enabled=True, draft_enabled=True, ready_queue_enabled=True, facts_bank_path=facts_path
    )
    package_id = await _ready_package(gateway, controller, facts_path)
    gateway.application_packages[package_id]["gates_snapshot"] = {
        "legal_hire_from_rf": {"status": "pass"}
    }
    gateway.application_packages[package_id]["questions_for_recruiter"] = [
        "Доступен ли contractor?",
        "Формат интервью?",
        "Третий вопрос - не должен показаться",
    ]

    callback = FakeCallback(111, _career_package_item_callback(package_id))
    await controller.on_career_callback(callback)

    text = callback.message.replies[-1]
    assert "CV: CV_agents_llm.md" in text
    assert "legal_hire_from_rf: pass" in text
    assert text.count("Вопрос:") == 2
    assert "Третий вопрос" not in text
    buttons = _flat_buttons(callback.message.markups[-1])
    draft_id = gateway.application_packages[package_id]["cover_draft_id"]
    assert (
        "Скопировать сопровод",
        _career_draft_copy_callback(draft_id),
    ) in buttons


@pytest.mark.asyncio
async def test_package_item_fails_closed_for_unknown_or_non_ready_package():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, ready_queue_enabled=True)

    unknown = FakeCallback(111, _career_package_item_callback(str(uuid4())))
    await controller.on_career_callback(unknown)

    assert unknown.answers == ["Пакет недоступен"]


@pytest.mark.asyncio
async def test_package_item_malformed_callback_fails_closed():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, ready_queue_enabled=True)

    malformed = FakeCallback(111, "career:pkgitem:not!!valid!!base64")
    await controller.on_career_callback(malformed)

    assert malformed.answers == ["Кнопка устарела"]


# ---------------------------------------------------------------------------
# Sent-confirmation: Отправлено -> Подтвердить/Отмена -> submit (Slice D1b.2b)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_and_confirm_hidden_and_blocked_when_flag_off(tmp_path):
    gateway = FakeInboxGateway()
    facts_path = _facts_bank_with_variants(tmp_path, ["agents_llm"])
    controller = _controller(
        gateway, enabled=True, draft_enabled=True, ready_queue_enabled=True, facts_bank_path=facts_path
    )
    package_id = await _ready_package(gateway, controller, facts_path)
    controller.career_ready_queue_enabled = False

    send = FakeCallback(111, _career_package_send_callback(package_id))
    await controller.on_career_callback(send)
    confirm = FakeCallback(111, _career_package_confirm_callback(package_id, "abcdef123456"))
    await controller.on_career_callback(confirm)

    assert send.answers == ["Функция выключена"]
    assert confirm.answers == ["Функция выключена"]
    assert gateway.application_packages[package_id]["status"] == "ready"


@pytest.mark.asyncio
async def test_first_click_shows_preview_and_writes_nothing(tmp_path):
    gateway = FakeInboxGateway()
    facts_path = _facts_bank_with_variants(tmp_path, ["agents_llm"])
    controller = _controller(
        gateway, enabled=True, draft_enabled=True, ready_queue_enabled=True, facts_bank_path=facts_path
    )
    package_id = await _ready_package(gateway, controller, facts_path)
    pkg = gateway.application_packages[package_id]
    pkg["company"], pkg["role_title"] = "Acme", "ML Engineer"

    callback = FakeCallback(111, _career_package_send_callback(package_id))
    await controller.on_career_callback(callback)

    text = callback.message.replies[-1]
    assert "Acme" in text and "ML Engineer" in text
    assert pkg["package_content_hash"][:12] in text
    assert pkg["status"] == "ready"
    assert gateway.applications == {}
    buttons = [t for t, _d in _flat_buttons(callback.message.markups[-1])]
    assert buttons == ["Подтвердить, отклик уже отправлен", "Отмена"]


@pytest.mark.asyncio
async def test_cancel_writes_nothing(tmp_path):
    gateway = FakeInboxGateway()
    facts_path = _facts_bank_with_variants(tmp_path, ["agents_llm"])
    controller = _controller(
        gateway, enabled=True, draft_enabled=True, ready_queue_enabled=True, facts_bank_path=facts_path
    )
    package_id = await _ready_package(gateway, controller, facts_path)

    callback = FakeCallback(111, _career_package_cancel_callback())
    await controller.on_career_callback(callback)

    assert callback.answers == ["Отменено"]
    assert gateway.application_packages[package_id]["status"] == "ready"
    assert gateway.applications == {}


@pytest.mark.asyncio
async def test_confirm_changed_hash_blocks_submit(tmp_path):
    gateway = FakeInboxGateway()
    facts_path = _facts_bank_with_variants(tmp_path, ["agents_llm"])
    controller = _controller(
        gateway, enabled=True, draft_enabled=True, ready_queue_enabled=True, facts_bank_path=facts_path
    )
    package_id = await _ready_package(gateway, controller, facts_path)
    send = FakeCallback(111, _career_package_send_callback(package_id))
    await controller.on_career_callback(send)
    # The package content changed after the preview was shown (e.g. re-prepared).
    gateway.application_packages[package_id]["package_content_hash"] = "0" * 64

    confirm = FakeCallback(111, _career_package_confirm_callback(package_id, "f" * 12))
    await controller.on_career_callback(confirm)

    assert confirm.answers == ["Пакет изменился, откройте карточку заново"]
    assert gateway.applications == {}
    assert gateway.application_packages[package_id]["status"] == "ready"


@pytest.mark.asyncio
async def test_confirm_success_creates_one_application_and_removes_from_ready_list(tmp_path):
    gateway = FakeInboxGateway()
    facts_path = _facts_bank_with_variants(tmp_path, ["agents_llm"])
    controller = _controller(
        gateway, enabled=True, draft_enabled=True, ready_queue_enabled=True, facts_bank_path=facts_path
    )
    package_id = await _ready_package(gateway, controller, facts_path)
    pkg = gateway.application_packages[package_id]
    hash_prefix = pkg["package_content_hash"][:12]

    confirm = FakeCallback(111, _career_package_confirm_callback(package_id, hash_prefix))
    await controller.on_career_callback(confirm)

    assert confirm.answers == ["Отправлено"]
    assert len(gateway.applications) == 1
    assert pkg["status"] == "submitted"

    ready = FakeCallback(111, "career:ready")
    await controller.on_career_callback(ready)
    assert any("Готовых пакетов нет." in reply for reply in ready.message.replies)


@pytest.mark.asyncio
async def test_confirm_replay_same_callback_id_is_idempotent(tmp_path):
    gateway = FakeInboxGateway()
    facts_path = _facts_bank_with_variants(tmp_path, ["agents_llm"])
    controller = _controller(
        gateway, enabled=True, draft_enabled=True, ready_queue_enabled=True, facts_bank_path=facts_path
    )
    package_id = await _ready_package(gateway, controller, facts_path)
    pkg = gateway.application_packages[package_id]
    hash_prefix = pkg["package_content_hash"][:12]

    first = FakeCallback(111, _career_package_confirm_callback(package_id, hash_prefix), callback_id="dup-1")
    await controller.on_career_callback(first)
    second = FakeCallback(111, _career_package_confirm_callback(package_id, hash_prefix), callback_id="dup-1")
    await controller.on_career_callback(second)

    assert len(gateway.applications) == 1


@pytest.mark.asyncio
async def test_confirm_replay_with_different_update_id_creates_no_duplicate(tmp_path):
    gateway = FakeInboxGateway()
    facts_path = _facts_bank_with_variants(tmp_path, ["agents_llm"])
    controller = _controller(
        gateway, enabled=True, draft_enabled=True, ready_queue_enabled=True, facts_bank_path=facts_path
    )
    package_id = await _ready_package(gateway, controller, facts_path)
    pkg = gateway.application_packages[package_id]
    hash_prefix = pkg["package_content_hash"][:12]

    first = FakeCallback(111, _career_package_confirm_callback(package_id, hash_prefix), callback_id="first-id")
    await controller.on_career_callback(first)
    second = FakeCallback(111, _career_package_confirm_callback(package_id, hash_prefix), callback_id="second-id")
    await controller.on_career_callback(second)

    assert len(gateway.applications) == 1
    assert second.answers == ["Уже отправлено"]


@pytest.mark.asyncio
async def test_confirm_fails_closed_for_unknown_package():
    gateway = FakeInboxGateway()
    controller = _controller(gateway, enabled=True, ready_queue_enabled=True)

    confirm = FakeCallback(111, _career_package_confirm_callback(str(uuid4()), "abcdef123456"))
    await controller.on_career_callback(confirm)

    assert confirm.answers == ["Пакет недоступен"]
    assert gateway.applications == {}
