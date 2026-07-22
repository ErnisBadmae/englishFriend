# Sonnet task: Career Telegram menu v0.2

## Mandatory first action

Use the existing graph before reading implementation files:

```powershell
graphify query "telegram career application button callback controller handler menu message postgresql service status" --budget 3500
```

Then inspect only the files needed for this bounded slice.

## User-visible problem

`/applied` without arguments loops on a syntax hint. A vacancy URL sent as a
plain message while an ML question is active is graded as the technical
answer. The owner wants a clear nested Telegram menu and status management.

## Outcome

Extend the existing private `ml_technical` bot. Do not create a second bot,
service, database or in-memory FSM.

Home menu:

- `Сегодня`
- `Срез по теме`
- `Прогресс ML/DL`
- `Карьера`

Career menu:

- `Записать отправленный отклик`
- `Мои отклики`
- `Назад`

## Required behaviour

### Adding an application

1. `Карьера -> Записать отправленный отклик` sends a `ForceReply` prompt for:
   `Компания | Роль | Ссылка`.
2. `/applied` with no payload opens the same prompt instead of repeating only
   the syntax error.
3. `/applied Компания | Роль | Ссылка` remains backward compatible.
4. A reply to the bot's stable career-add prompt is routed to Career Ledger
   before the ML answer handler, including when an ML session is active.
5. Invalid input explains which field is missing and repeats the prompt.
6. A message that contains a recognizable vacancy URL (`hh.ru/vacancy/`,
   `linkedin.com/jobs/`, Greenhouse or Lever job URL) but is not a reply to the
   career prompt must never be graded as an ML answer. Return a safe prompt to
   use `Карьера -> Записать отправленный отклик`.

Use reply-to-message markers or another restart-safe Telegram-native envelope.
Do not use process memory as canonical pending state. Keep the visible prompt
clean; implementation markers may be compact.

### Listing and status

1. `Мои отклики` shows counts with Russian status labels and at most 10 recent
   applications as inline buttons.
2. Selecting an application shows company, role, URL, status, and current next
   action/date if present.
3. Show only status transitions allowed by `ALLOWED_TRANSITIONS`.
4. A status callback calls `CareerLedgerService.append_application_event`, is
   owner-originated and idempotent on Telegram callback id.
5. Do not permit a model/MCP write path.

### Nearest action

1. Application details include `Задать следующее действие`.
2. The button sends a restart-safe `ForceReply` prompt for
   `Действие | ГГГГ-ММ-ДД`; date may be empty.
3. Add a service method that locks the application row, updates
   `next_action`/`next_action_due_date`, and appends an idempotent `note` event.
4. The reply envelope must identify the application without relying on process
   memory. Invalid dates fail closed and repeat the prompt.

No new database table is expected: migration 016 already contains the current
fields and `note` event type. If you believe a migration is necessary, stop
and report instead of creating it.

## Telegram routing invariant

Order every text message through this decision:

```text
command -> career ForceReply envelope -> vacancy-link guard
        -> active ML answer -> no-active-session help
```

A career message must never reach local Qwen grading.

## Tests

Add or extend focused tests for:

- home and career menu buttons;
- `/applied` without payload produces `ForceReply`;
- valid reply records exactly one application;
- invalid reply does not write and is re-prompted;
- career reply during active ML session never calls ML `submit`;
- naked HH/LinkedIn/Greenhouse/Lever vacancy link never calls ML `submit`;
- list -> application details -> allowed transition;
- forbidden/stale transition fails closed;
- status callback replay is idempotent;
- next-action reply updates fields and appends one note event;
- invalid date does not write;
- existing ML Telegram tests remain green.

Run PostgreSQL integration tests when `ML_TECHNICAL_PG_TEST_URL` is available;
otherwise report them as skipped rather than claiming they passed.

## Allowed files

- `app/adapters/telegram/ml_technical_bot.py`
- `app/services/career_ledger_service.py`
- `tests/test_career_ledger_bot.py`
- `tests/test_career_ledger_service.py`
- `tests/test_ml_technical_bot.py` only if compatibility requires it
- `!DOC/operations/ML_TECHNICAL_TELEGRAM_RUNBOOK.md`
- `!DOC/operations/CURRENT_PRODUCT_STATE.md`

## Stop conditions

- No auto-apply and no HTTP/browser submission to HH or other job boards.
- No cover-letter or CV generation.
- No Qdrant, Neo4j, CDC or microservice split.
- No new bot and no in-memory FSM.
- No MCP write tools.
- Do not apply migrations, restart processes, commit or push.
- Preserve unrelated dirty-worktree changes.

Report changed files, test commands and any unresolved ambiguity, then stop.
