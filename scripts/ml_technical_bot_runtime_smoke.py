"""Read-only Telegram ML bot smoke: getMe, DB and allowlist linkage."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.adapters.telegram.ml_technical_bot import DbTelegramPracticeGateway
from app.core.config import settings
from app.core.database import get_async_session


async def run() -> int:
    if not settings.ml_technical_telegram_bot_token:
        print("FAIL: ML_TECHNICAL_TELEGRAM_BOT_TOKEN is empty")
        return 2
    allowed_ids = settings.ml_technical_telegram_allowed_id_set
    if not allowed_ids:
        print("FAIL: ML_TECHNICAL_TELEGRAM_ALLOWED_IDS is empty")
        return 2

    session_factory = get_async_session()
    required_indexes = {
        "ml_technical_sessions_one_active_telegram_key",
        "ml_technical_session_items_pending_position_idx",
    }
    async with session_factory() as db:
        found_indexes = set(
            (
                await db.scalars(
                    text(
                        "select indexname from pg_indexes "
                        "where schemaname = current_schema() and indexname in "
                        "('ml_technical_sessions_one_active_telegram_key', "
                        "'ml_technical_session_items_pending_position_idx')"
                    )
                )
            ).all()
        )
    missing_indexes = required_indexes - found_indexes
    if missing_indexes:
        print(
            "FAIL: migration 013 indexes missing: " + ", ".join(sorted(missing_indexes))
        )
        return 1

    try:
        from aiogram import Bot
        from aiogram.client.session.aiohttp import AiohttpSession
    except ImportError:
        print("FAIL: aiogram is not installed")
        return 2

    proxy = settings.proxy_url or os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    bot_session = AiohttpSession(proxy=proxy) if proxy else None
    bot = Bot(token=settings.ml_technical_telegram_bot_token, session=bot_session)
    try:
        identity = await bot.get_me()
    finally:
        await bot.session.close()

    gateway = DbTelegramPracticeGateway(session_factory)
    unlinked = [
        telegram_id
        for telegram_id in sorted(allowed_ids)
        if await gateway.resolve_user(telegram_id) is None
    ]
    if unlinked:
        print(
            "FAIL: allowed Telegram IDs are not linked in users: "
            + ", ".join(map(str, unlinked))
        )
        return 1

    print(
        f"OK: bot=@{identity.username or identity.id}, DB reachable, "
        f"{len(allowed_ids)} allowed ID(s) linked; no messages sent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
