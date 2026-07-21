# ML technical Telegram v0

The bot is a private adapter over `MlTechnicalService`. PostgreSQL owns the
session, queue, attempts and progress; restarting the bot loses no practice
state.

## Prerequisites

1. Apply migrations `012_ml_technical_practice.sql`, then
   `013_ml_technical_telegram.sql` during the documented storage cutover.
2. Install `requirements.txt`.
3. Create a bot with BotFather and set:

```env
ML_TECHNICAL_TELEGRAM_BOT_TOKEN=<token>
ML_TECHNICAL_TELEGRAM_ALLOWED_IDS=<real Telegram user ID>
ML_TECHNICAL_TELEGRAM_TIMEZONE=Europe/Moscow
```

The allowed Telegram ID must already exist in `users.telegram_id`. The bot
never creates or links a user. An unauthorized `/start` prints the caller's ID
so it can be linked manually.

## Read-only smoke

```powershell
venv\Scripts\python.exe scripts\ml_technical_bot_runtime_smoke.py
```

The smoke calls Telegram `getMe`, connects to PostgreSQL and verifies every
allowed ID is linked. It does not send a message or create a session.

## Run

```powershell
venv\Scripts\python.exe -m app.adapters.telegram.ml_technical_bot
```

An empty token stops startup. Use one long-running process and configure
`HTTPS_PROXY` or the existing `PROXY_URL` when Telegram is unavailable
directly.

## Manual acceptance

1. `/start` shows the menu but does not start a session.
2. `/today` twice returns the same session and at most five questions.
3. Restart the process after receiving a question; the next text answer must
   continue that pending database item.
4. Tap `Не знаю - показать разбор`; verify the saved attempt is 0% and the
   reference appears only after it is saved.
5. Retry an old button and duplicate message; neither creates another attempt.
6. Compare `/progress`, the web view and MCP history for the same user.

## Stop and rollback

Stop the bot process first. No Telegram-specific data store exists. Migration
`013` adds only indexes; if rollback is required, drop
`ml_technical_sessions_one_active_telegram_key` and
`ml_technical_session_items_pending_position_idx` after confirming no bot
writer is running. Do not roll back migration `012` through this runbook.
