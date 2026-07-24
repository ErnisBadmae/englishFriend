# Career Inbox batch paste v0

Status: approved for bounded implementation (owner: Ernis, 2026-07-24)
Executor: Claude Code / Sonnet
Spec anchor: `career/CAREER_TELEGRAM_COCKPIT_SPEC.md` sections 6-7, 9 (Slice A bug fix)
Repository: `englishFriend`

## Observed defect

Owner pastes several recruiter messages as ONE text (numbered `1. ... 2. ... 3. ...`
or blank-line separated). Result: only the last lead survives.

Root cause (verified in code):

- `_handle_manual_lead_paste` (`app/adapters/telegram/ml_technical_bot.py:1400`)
  stores a single pending payload `{raw_text, suggestion}` per user.
- `suggest_manual_lead` runs one LLM call over the whole blob and extracts one
  company only.
- Pending intent is one-per-user, so a second paste overwrites the first.

This is a design defect in the paste handler, not invalid owner input, and not a
gap in `CareerInboxService` (its `confirm_manual_lead` is already correct and
idempotent).

## Invariants (must not regress)

- PostgreSQL stays canonical; pending state remains one typed row per user
  (no in-memory FSM, no second pending table).
- LLM remains an untrusted extractor: nothing becomes canonical without the owner
  pressing Подтвердить for THAT lead. Each lead is confirmed individually.
- `is_grounded` evidence rule and all `CareerInboxService` contracts are unchanged.
- No auto-apply, no vacancy fetch, no CV/cover-letter generation, no MCP write, no
  Qdrant/Neo4j.
- A single-message paste (one segment) behaves exactly as today - zero regression.
- Owner isolation and the 30-minute pending expiry from
  `SONNET_CAREER_PENDING_INPUT_V021_TASK.md` still hold.
- No migration: the pending payload is JSON; only its shape changes.

## Slice 1 - deterministic segmenter (do this first, pure function)

Allowed files:

- `app/services/career_inbox_service.py`
- `tests/test_career_inbox_service.py`

Add one pure, deterministic function, e.g. `split_pasted_leads(raw_text) -> list[str]`:

- Primary split: lines beginning with `N.` or `N)` (leading number markers).
- Fallback split: blank-line separated blocks when no numbering is present.
- One segment when neither pattern matches (identity case).
- Trim empties; cap at a bounded `MAX_PASTED_LEADS` (e.g. 10) to stay bounded;
  drop the overflow and let the handler tell the owner N were kept.
- No LLM, no network. Whitespace/marker handling reuses existing normalization
  helpers where natural; do not add a new abstraction layer.

Acceptance for Slice 1:

- numbered blob of 3 → 3 segments in order;
- blank-line blob of 3 → 3 segments;
- single message → exactly 1 segment (identity);
- >MAX blob → capped to MAX, deterministic;
- pure/deterministic: same input, same output, no I/O.

Stop after Slice 1 and report.

## Slice 2 - queued preview/confirm in the bot (after Slice 1 accepted)

Allowed files:

- `app/adapters/telegram/ml_technical_bot.py`
- `tests/test_career_inbox_bot.py` (or the existing career bot test module)
- `!DOC/operations/CURRENT_PRODUCT_STATE.md` (short update only)

Change the paste handler to build a QUEUE, keeping one pending row:

- On paste: `split_pasted_leads`, run `suggest_manual_lead` per segment, store
  payload `{"queue": [{raw_text, suggestion}, ...], "index": 0}` in the single
  pending intent.
- Show preview for `queue[index]` with a position marker (`Лид 1 из 3`) and the
  existing Подтвердить / Отмена markup; add a Пропустить-this-lead affordance so a
  bad segment does not block the rest.
- On Подтвердить: confirm `queue[index]` via the unchanged
  `confirm_manual_lead`; use a per-segment idempotency key (callback id + index,
  or a uuid minted per segment and kept in the payload) so replay is still safe;
  advance `index`; show the next preview, or a done summary and clear the intent
  when the queue is exhausted.
- Отмена clears the whole queue as today.

Acceptance for Slice 2:

- pasting the real 3-message blob (Миролла / стартап / Премьер Консалт) yields 3
  separate previews and, after 3 confirms, 3 inbox items;
- a single-message paste still yields one preview and one item;
- Telegram update replay on one confirm does not create a duplicate item;
- Пропустить skips only the current lead and advances;
- stale/expired pending answers safe-closed as today;
- career input never reaches ML grading;
- all focused career bot + service tests pass.

Stop after Slice 2. Do not restart the live bot, do not migrate live data, do not
commit. Report files, design, `pytest` command, and result.

## Verification command

```powershell
venv\Scripts\python.exe -m pytest tests\test_career_inbox_service.py tests\test_career_inbox_bot.py -q
```
