from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.adapters.telegram.ml_technical_bot import (
    MlTechnicalTelegramController,
    _item_callback,
)
from app.data.ml_technical_questions import (
    get_ml_technical_question,
    public_question_view,
)
from app.services.ml_technical_service import (
    MlTechnicalConflictError,
    select_daily_queue,
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
    ) -> None:
        self.chat = FakeChat(telegram_id, chat_type)
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
        # A real callback belongs to the human actor while callback.message was
        # authored by the bot. Authorization must use callback.from_user.
        self.message.from_user = SimpleNamespace(id=999_999)
        self.from_user = SimpleNamespace(id=telegram_id)
        self.data = data
        self.id = callback_id
        self.answers: list[str] = []

    async def answer(self, text: str = "", **_kwargs: object) -> None:
        self.answers.append(text)


def _snapshot(question_ids: list[str], *, mode: str = "daily") -> dict:
    session_id = str(uuid4())
    items = [
        {
            "item_id": str(uuid4()),
            "position": position,
            "question": public_question_view(get_ml_technical_question(question_id)),
            "status": "pending",
        }
        for position, question_id in enumerate(question_ids, start=1)
    ]
    return {
        "session_id": session_id,
        "mode": mode,
        "topic_id": None,
        "practice_date": date.today().isoformat(),
        "status": "active",
        "total_items": len(items),
        "completed_items": 0,
        "current_item": items[0] if items else None,
        "_items": items,
    }


class FakeGateway:
    def __init__(self) -> None:
        self.links = {111: 11}
        self.session: dict | None = None
        self.daily_by_date: dict[date, dict] = {}
        self.history: list[dict] = []
        self.source_events: set[str] = set()
        self.submit_kinds: list[str] = []
        self.needs_review = False

    async def resolve_user(self, telegram_id: int):
        return self.links.get(telegram_id)

    async def start_daily(self, user_id: int, *, practice_date: date, seed: str):
        del user_id, seed
        if practice_date not in self.daily_by_date:
            self.daily_by_date[practice_date] = _snapshot(
                [f"mltech_{index:03d}" for index in range(1, 6)]
            )
        self.session = self.daily_by_date[practice_date]
        return self._public_snapshot()

    async def start_topic(self, user_id: int, *, topic_id: str, seed: str):
        del user_id, seed
        if self.session and self.session["status"] == "active":
            raise MlTechnicalConflictError("active")
        question_ids = [
            qid
            for qid in (f"mltech_{index:03d}" for index in range(1, 16))
            if get_ml_technical_question(qid)["topic_id"] == topic_id
        ][:5]
        self.session = _snapshot(question_ids, mode="topic")
        self.session["topic_id"] = topic_id
        return self._public_snapshot()

    async def active(self, user_id: int):
        del user_id
        if self.session is None or self.session["status"] != "active":
            return None
        return self._public_snapshot()

    async def progress(self, user_id: int):
        del user_id
        return {
            "passed": sum(
                1 for item in self.history if item["review"]["score_percent"] >= 70
            ),
            "total_questions": 15,
            "due_for_repetition": 0,
            "needs_review": sum(
                1 for item in self.history if item["review"]["status"] == "needs_review"
            ),
            "topics": [
                {
                    "topic_id": "dl_training",
                    "total_questions": 5,
                    "average_latest_score_percent": 50.0,
                }
            ],
        }

    async def skip(self, user_id: int, *, session_id: str, item_id: str):
        del user_id
        if self.session is None or self.session["session_id"] != session_id:
            return {"changed": False, "session": self._public_snapshot()}
        current = self.session.get("current_item")
        if current is None or current["item_id"] != item_id:
            return {"changed": False, "session": self._public_snapshot()}
        current["status"] = "skipped"
        self._advance()
        return {"changed": True, "session": self._public_snapshot()}

    async def cancel(self, user_id: int):
        del user_id
        if self.session is None or self.session["status"] != "active":
            return {"cancelled": False, "session_id": None}
        self.session["status"] = "cancelled"
        return {"cancelled": True, "session_id": self.session["session_id"]}

    async def submit(
        self,
        user_id: int,
        *,
        session_id: str,
        question_id: str,
        answer_text: str,
        answer_kind: str,
        source_event_id: str,
    ):
        del user_id, answer_text
        if source_event_id in self.source_events:
            raise MlTechnicalConflictError("duplicate")
        if self.session is None or self.session["session_id"] != session_id:
            raise MlTechnicalConflictError("stale")
        current = self.session.get("current_item")
        if current is None or current["question"]["id"] != question_id:
            raise MlTechnicalConflictError("stale")
        self.source_events.add(source_event_id)
        self.submit_kinds.append(answer_kind)
        review = {
            "status": "needs_review" if self.needs_review else "graded",
            "score_percent": None if self.needs_review else 0.0,
            "feedback": None if self.needs_review else "Нужно повторить тему.",
        }
        self.history.append(
            {
                "question_id": question_id,
                "answer_kind": answer_kind,
                "source_channel": "telegram",
                "source_event_id": source_event_id,
                "review": review,
            }
        )
        current["status"] = "answered"
        self._advance()
        return {
            "review": review,
            "reference_explanation_ru": "Эталонный разбор",
        }

    def _advance(self) -> None:
        pending = next(
            (item for item in self.session["_items"] if item["status"] == "pending"),
            None,
        )
        self.session["current_item"] = pending
        self.session["completed_items"] = sum(
            1
            for item in self.session["_items"]
            if item["status"] in {"answered", "skipped"}
        )
        if pending is None:
            self.session["status"] = "completed"

    def _public_snapshot(self) -> dict:
        if self.session is None:
            return None
        return {
            key: deepcopy(value)
            for key, value in self.session.items()
            if key != "_items"
        }


def _controller(gateway: FakeGateway, allowed=frozenset({111})):
    return MlTechnicalTelegramController(gateway, allowed_ids=allowed)


def test_daily_policy_is_priority_ordered_deterministic_and_unique():
    now = datetime.now(timezone.utc)
    attempts = [
        {
            "question_id": "mltech_001",
            "answered_at": (now - timedelta(days=5)).isoformat(),
            "review": {"status": "graded", "score_percent": 100},
        },
        {
            "question_id": "mltech_002",
            "answered_at": (now - timedelta(hours=1)).isoformat(),
            "review": {"status": "graded", "score_percent": 20},
        },
    ]

    first = select_daily_queue(attempts, session_seed="11:2026-07-21", limit=5)
    second = select_daily_queue(attempts, session_seed="11:2026-07-21", limit=5)

    assert first == second
    assert first[:2] == ["mltech_001", "mltech_002"]
    assert len(first) == len(set(first)) == 5


@pytest.mark.asyncio
async def test_private_and_allowlist_guard_exposes_unknown_id_without_writes():
    gateway = FakeGateway()
    controller = _controller(gateway)

    group = FakeMessage(111, chat_type="group")
    await controller.on_start(group)
    unknown = FakeMessage(999)
    await controller.on_start(unknown)

    assert "только в личном" in group.replies[0].lower()
    assert "999" in unknown.replies[0]
    assert gateway.session is None


@pytest.mark.asyncio
async def test_allowlisted_but_unlinked_user_cannot_write():
    gateway = FakeGateway()
    controller = _controller(gateway, allowed=frozenset({222}))
    message = FakeMessage(222)

    await controller.on_today(message)

    assert "не связан" in message.replies[0].lower()
    assert gateway.session is None


@pytest.mark.asyncio
async def test_today_is_idempotent_and_limited_to_five():
    gateway = FakeGateway()
    controller = _controller(gateway)
    first = FakeMessage(111)
    second = FakeMessage(111)

    await controller.on_today(first)
    first_id = gateway.session["session_id"]
    await controller.on_today(second)

    assert gateway.session["session_id"] == first_id
    assert gateway.session["total_items"] == 5
    assert len(gateway.daily_by_date) == 1


@pytest.mark.asyncio
async def test_cancelled_daily_is_not_resumed_or_shown_again():
    gateway = FakeGateway()
    controller = _controller(gateway)
    await controller.on_today(FakeMessage(111))
    cancelled_session_id = gateway.session["session_id"]
    await controller.on_cancel(FakeMessage(111))

    repeated = FakeMessage(111)
    await controller.on_today(repeated)

    assert gateway.session["session_id"] == cancelled_session_id
    assert gateway.session["status"] == "cancelled"
    assert any("не возобновляется" in reply for reply in repeated.replies)
    assert all("Вопрос 1/" not in reply for reply in repeated.replies)


@pytest.mark.asyncio
async def test_restart_recovers_pending_item_from_gateway_state():
    gateway = FakeGateway()
    await _controller(gateway).on_today(FakeMessage(111))
    recovered_controller = _controller(gateway)

    answer = FakeMessage(111, "мой ответ", message_id=22)
    await recovered_controller.on_text(answer)

    assert len(gateway.history) == 1
    assert gateway.session["current_item"]["position"] == 2


@pytest.mark.asyncio
async def test_duplicate_message_creates_one_attempt():
    gateway = FakeGateway()
    controller = _controller(gateway)
    await controller.on_today(FakeMessage(111))
    duplicate = FakeMessage(111, "ответ", message_id=44)

    await controller.on_text(duplicate)
    await controller.on_text(duplicate)

    assert len(gateway.history) == 1
    assert len(gateway.source_events) == 1


@pytest.mark.asyncio
async def test_unknown_slash_command_never_becomes_an_answer():
    gateway = FakeGateway()
    controller = _controller(gateway)
    await controller.on_today(FakeMessage(111))
    typo = FakeMessage(111, "/progess", message_id=45)

    await controller.on_text(typo)

    assert gateway.history == []
    assert gateway.session["current_item"]["position"] == 1
    assert any("Неизвестная команда" in reply for reply in typo.replies)


@pytest.mark.asyncio
async def test_skip_and_cancel_are_idempotent_for_stale_actions():
    gateway = FakeGateway()
    controller = _controller(gateway)
    await controller.on_today(FakeMessage(111))
    old = deepcopy(gateway.session["current_item"])
    callback_data = _item_callback("sk", gateway.session["session_id"], old["item_id"])

    first = FakeCallback(111, callback_data)
    stale = FakeCallback(111, callback_data, callback_id="cb-2")
    await controller.on_skip_callback(first)
    await controller.on_skip_callback(stale)
    cancel = FakeMessage(111)
    await controller.on_cancel(cancel)
    await controller.on_cancel(cancel)

    assert first.answers == ["Пропущено"]
    assert stale.answers == ["Уже обработано"]
    assert any("Нет активной" in reply for reply in cancel.replies)


class BlockingGateway(FakeGateway):
    def __init__(self) -> None:
        super().__init__()
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def submit(self, *args, **kwargs):
        self.entered.set()
        await self.release.wait()
        return await super().submit(*args, **kwargs)


@pytest.mark.asyncio
async def test_reference_is_not_sent_before_attempt_persists():
    gateway = BlockingGateway()
    controller = _controller(gateway)
    await controller.on_today(FakeMessage(111))
    answer = FakeMessage(111, "ответ", message_id=55)

    task = asyncio.create_task(controller.on_text(answer))
    await gateway.entered.wait()
    assert all("Эталонный" not in reply for reply in answer.replies)
    assert gateway.history == []
    gateway.release.set()
    await task

    assert len(gateway.history) == 1
    assert any("Эталонный разбор" in reply for reply in answer.replies)


@pytest.mark.asyncio
async def test_dont_know_uses_first_class_kind_and_reveals_after_write():
    gateway = FakeGateway()
    controller = _controller(gateway)
    await controller.on_today(FakeMessage(111))
    current = gateway.session["current_item"]
    callback = FakeCallback(
        111,
        _item_callback("dk", gateway.session["session_id"], current["item_id"]),
    )

    await controller.on_dont_know(callback)

    assert gateway.submit_kinds == ["dont_know"]
    assert gateway.history[0]["review"]["score_percent"] == 0.0
    assert any("Эталонный разбор" in reply for reply in callback.message.replies)


@pytest.mark.asyncio
async def test_qwen_failure_is_rendered_as_needs_review():
    gateway = FakeGateway()
    gateway.needs_review = True
    controller = _controller(gateway)
    await controller.on_today(FakeMessage(111))
    answer = FakeMessage(111, "ответ", message_id=66)

    await controller.on_text(answer)

    assert gateway.history[0]["review"]["status"] == "needs_review"
    assert any("ожидает ручной проверки" in reply for reply in answer.replies)


@pytest.mark.asyncio
async def test_telegram_attempt_is_visible_through_shared_history_and_progress():
    gateway = FakeGateway()
    controller = _controller(gateway)
    await controller.on_today(FakeMessage(111))
    await controller.on_text(FakeMessage(111, "ответ", message_id=77))

    # The fake's history represents the same service read surface used by MCP.
    mcp_history = list(gateway.history)
    shared_progress = await gateway.progress(11)

    assert mcp_history[0]["source_channel"] == "telegram"
    assert mcp_history[0]["source_event_id"] == "message:111:77"
    assert shared_progress["total_questions"] == 15
