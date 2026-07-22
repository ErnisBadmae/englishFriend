# Career Telegram pending input v0.2.1

## Observed defect

Telegram `ForceReply` does not reliably provide `message.reply_to_message` in the
owner's client. The zero-width marker appended to the prompt is also rendered as
visible `career_add`. A valid line such as
`Company | AI Engineer | https://hh.ru/vacancy/42` therefore reaches the vacancy
link guard instead of the career handler.

This is a design defect, not invalid owner input.

## Invariants

- PostgreSQL is canonical for pending input; no in-memory FSM.
- `ForceReply` is only a convenience. Correct routing must not depend on Telegram
  reply metadata.
- Remove all user-visible and hidden career markers.
- Routing order is: command -> active pending career intent -> structurally valid
  direct career payload -> vacancy-link guard -> active ML answer -> help.
- Career input must never reach ML grading.
- Invalid input while an intent is active explains the exact format and keeps the
  intent active.
- Successful input clears the intent.
- An explicit cancel/back/start path clears the intent so technical practice is
  not trapped.
- Pending intents expire after 30 minutes.
- Owner isolation is mandatory.
- No auto-apply, vacancy fetch, CV/letter generation, MCP write path, Qdrant, or
  Neo4j work.

## Slice A - PostgreSQL state (do this first)

Before editing, query the existing `graphify-out/graph.json` for the path between
Telegram controller, career service, PostgreSQL, pending input, and application.

Allowed files:

- `app/models/career.py`
- `app/services/career_ledger_service.py`
- `db/migrations/postgres/017_career_telegram_pending_inputs.sql`
- `db/README.md`
- `tests/test_career_ledger_service.py`

Add one typed row per user, for intents `career_add` and
`career_next_action`. Store the application id only for the latter. Provide narrow
service methods to set/upsert, read active, clear, and discard expired intent.
Use existing service/session conventions and RLS style. Do not apply the migration
to the live database and do not commit.

Acceptance for Slice A:

- migration is idempotent and owner-isolated;
- replacing one intent with another works;
- active intent survives a new DB session;
- expired intent is not returned;
- another user cannot read or clear it;
- application id, when present, belongs to the same user;
- focused service tests pass on an explicitly supplied isolated PostgreSQL test DB.

Stop after Slice A and report files, design, test command, and result.

## Slice B - Telegram integration (only after Slice A is accepted)

Allowed files:

- `app/adapters/telegram/ml_technical_bot.py`
- `tests/test_career_ledger_bot.py`
- `!DOC/operations/ML_TECHNICAL_TELEGRAM_RUNBOOK.md`
- `!DOC/operations/CURRENT_PRODUCT_STATE.md`

Extend the existing gateway with the narrow pending-intent operations. Button
`career:add` and `/applied` without arguments set `career_add`; next-action button
sets `career_next_action` with its application id. Send clean prompts, optionally
with `ForceReply`, but never inspect `reply_to_message` for correctness.

Also accept a stateless direct payload only when it has exactly three non-empty
pipe-separated fields and the third field is a recognized vacancy URL. This
fallback must run before the vacancy-link guard. Plain technical answers and bare
vacancy links keep their existing behavior.

Add a visible Cancel button/callback or an equally explicit existing path that
clears pending input. `/start` should clear stale pending input.

Acceptance for Slice B:

- the exact owner input `Напоправку|AI Engineer|https://spb.hh.ru/vacancy/135445141`
  records an application after pressing Add even with no `reply_to_message`;
- the same valid three-field payload is recognized without pending state;
- `AI Engineer / AI-разработчик https://spb.hh.ru/vacancy/135445141`
  gets a precise format hint while pending and remains pending;
- bare vacancy URL outside pending never reaches ML grading;
- valid ML answer is still graded outside pending;
- restart is simulated by a new controller/gateway instance and pending input is
  still routed;
- next-action flow follows the same rules;
- cancellation clears pending;
- all focused bot tests pass.

Stop after Slice B. Do not restart the live bot, migrate live data, or commit.
