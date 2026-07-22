# ML technical Telegram v0.2.1

The bot is a private adapter over `MlTechnicalService` and
`CareerLedgerService`. PostgreSQL owns the practice session, queue, attempts,
progress and the career ledger; restarting the bot loses no practice or
career state.

## Career menu (v0.2.1)

Home menu adds `Карьера`, opening a submenu with `Записать отправленный
отклик`, `Мои отклики`, `Назад`.

- Adding an application (menu button or `/applied` with no payload) records a
  30-minute pending intent in PostgreSQL and prompts for
  `Компания | Роль | Ссылка`. Correct routing does not depend on
  `ForceReply`, `reply_to_message`, hidden markers, or process memory.
  `/applied Компания | Роль | Ссылка` remains supported.
- Pending career input is routed to `CareerLedgerService` before the ML answer
  handler, even when an ML session is active. A structurally valid direct
  `Компания | Роль | vacancy URL` message also works without opening the menu. A message that
  merely looks like a vacancy link (`hh.ru/vacancy/`, `linkedin.com/jobs/`,
  Greenhouse or Lever job URLs) but is not a reply to the career prompt is
  never graded as an ML answer.
- `Мои отклики` (menu button or `/applications`) shows counts with Russian
  status labels and up to 10 recent applications as inline buttons.
  Selecting one shows company/role/URL/status/next action and only the
  transitions allowed by `ALLOWED_TRANSITIONS`. Status buttons call
  `CareerLedgerService.append_application_event`, are owner-originated, and
  are idempotent on the Telegram callback id.
- `Задать следующее действие` stores a restart-safe pending intent with the
  owner-scoped application id and prompts for `Действие | ГГГГ-ММ-ДД`
  (date optional). The next message is routed to
  `CareerLedgerService.set_next_action`, which locks the row, updates
  `next_action`/`next_action_due_date`, and appends one idempotent `note`
  event. Invalid dates fail closed and repeat the prompt.
- No model or MCP write path can change status or owner facts; the career
  ledger only records what the owner explicitly reports in Telegram.

## Prerequisites

1. Apply migrations `012_ml_technical_practice.sql` through
   `017_career_telegram_pending_inputs.sql` during the documented storage cutover.
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
7. Record a real application with
   `/applied Company | Role | URL`, then confirm it appears once in
   `/applications`.
8. Tap `Карьера -> Записать отправленный отклик`, send a valid
   `Компания | Роль | Ссылка`, confirm it is recorded once; reply with a
   missing field and confirm the prompt repeats without writing.
9. While an ML question is active, reply to the career prompt; confirm the
   reply is recorded as an application and never graded as an ML answer.
   Send a naked `hh.ru/vacancy/...` link as a plain message; confirm it is
   never graded and the bot points to the career menu instead.
10. Open an application from `Мои отклики`, apply an allowed status
    transition, then retry the same button tap; confirm the status changes
    once and the retry is a no-op.
11. Tap `Задать следующее действие`, reply with `Действие | 2026-08-01`;
    confirm the application shows the new next action. Retry with an
    invalid date and confirm nothing is written.

## Stop and rollback

Stop the bot process first. Migration `017` adds only the owner-scoped,
short-lived `career_telegram_pending_inputs` table. If rollback is required,
drop that table only after stopping the bot and confirming no pending career
input must be preserved. Do not roll back migrations `012`-`016` through this
runbook.
