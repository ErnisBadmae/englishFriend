from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.adapters.telegram.ml_technical_bot import MlTechnicalTelegramController
from app.services.career_ledger_service import CareerLedgerError, STATUS_APPLIED


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

    async def answer(self, text: str, **kwargs: object) -> None:
        self.replies.append(text)


class FakeCareerGateway:
    """Minimal gateway stub exercising only the career-ledger surface."""

    def __init__(self) -> None:
        self.links = {111: 11}
        self.applications: list[dict] = []
        self.used_idempotency_keys: set[str] = set()

    async def resolve_user(self, telegram_id: int):
        return self.links.get(telegram_id)

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
        del actor_id
        if not company.strip() or not role_title.strip():
            raise CareerLedgerError("company and role_title are required")
        if idempotency_key in self.used_idempotency_keys:
            existing = next(
                app
                for app in self.applications
                if app["idempotency_key"] == idempotency_key
            )
            return {"created": False, "application": existing}
        self.used_idempotency_keys.add(idempotency_key)
        application = {
            "application_id": str(uuid4()),
            "company": company,
            "role_title": role_title,
            "url": url,
            "status": STATUS_APPLIED,
            "idempotency_key": idempotency_key,
        }
        self.applications.append(application)
        return {"created": True, "application": application}

    async def applications_overview(self, user_id: int):
        del user_id
        by_status: dict[str, int] = {}
        for app in self.applications:
            by_status[app["status"]] = by_status.get(app["status"], 0) + 1
        return {
            "summary": {"total": len(self.applications), "by_status": by_status},
            "recent": list(reversed(self.applications)),
        }


def _controller(gateway: FakeCareerGateway) -> MlTechnicalTelegramController:
    return MlTechnicalTelegramController(gateway, allowed_ids=frozenset({111}))


@pytest.mark.asyncio
async def test_applied_command_creates_exactly_one_application():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    message = FakeMessage(111, "/applied Acme | ML Engineer | https://acme.example/1")

    await controller.on_applied(message)

    assert len(gateway.applications) == 1
    assert any("Acme" in reply for reply in message.replies)


@pytest.mark.asyncio
async def test_replaying_same_telegram_update_creates_no_additional_application():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    first = FakeMessage(
        111, "/applied Acme | ML Engineer | https://acme.example/1", message_id=42
    )
    replay = FakeMessage(
        111, "/applied Acme | ML Engineer | https://acme.example/1", message_id=42
    )

    await controller.on_applied(first)
    await controller.on_applied(replay)

    assert len(gateway.applications) == 1


@pytest.mark.asyncio
async def test_malformed_applied_command_returns_usage_and_writes_nothing():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    message = FakeMessage(111, "/applied only one field")

    await controller.on_applied(message)

    assert gateway.applications == []
    assert any("Формат" in reply for reply in message.replies)


@pytest.mark.asyncio
async def test_unauthorized_telegram_id_cannot_record_application():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    message = FakeMessage(999, "/applied Acme | ML Engineer | https://acme.example/1")

    await controller.on_applied(message)

    assert gateway.applications == []


@pytest.mark.asyncio
async def test_applications_command_reports_counts_and_recent_list():
    gateway = FakeCareerGateway()
    controller = _controller(gateway)
    await controller.on_applied(
        FakeMessage(111, "/applied Acme | ML Engineer | https://acme.example/1")
    )

    message = FakeMessage(111, "/applications")
    await controller.on_applications(message)

    assert any("Всего заявок: 1" in reply for reply in message.replies)
    assert any("Acme" in reply for reply in message.replies)
