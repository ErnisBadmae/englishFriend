# Career Inbox import identity preservation corrective v0

Status: approved for bounded implementation (owner: Ernis, 2026-08-05)
Executor: Claude Code / Sonnet
Repository: `englishFriend`
Outcome: Career OS vacancy intake remains usable after owner verdicts

## Problem and observed evidence

A live refresh on 2026-08-05 produced 13 `outreach` candidates, but only 2 had
never been imported. Eleven were repeat imports of already seen vacancies. The
problem is reproducible after the owner sets a verdict such as `applied`,
`prepare`, `skip`, or `false_positive`.

The current write path explains the symptom:

- `CareerInboxService.import_snapshot` creates the stable import identity
  `telegram_digest:{external_id}:{content_hash}` and stores it in
  `career_inbox_items.idempotency_key`;
- `CareerInboxService.set_verdict` later replaces that value with a Telegram
  callback idempotency key;
- `CareerInboxService.confirm_applied` replaces it again with the application
  callback key;
- the next import can no longer find the original stable key and inserts a new
  row, even though the unique index itself works as designed.

Use only synthetic vacancy data in tests and reports. Do not copy live vacancy
text or private Telegram content into Git.

## Product outcome and budget

After the fix, repeatedly refreshing vacancies must not recreate an already
imported snapshot merely because the owner acted on it. This unblocks normal use
of the bot and makes queue-quality metrics meaningful again.

- Price of inaction: the inbox fills with old cards, owner time is wasted, and
  source precision/recall measurements become unreliable.
- Time cap: 2 hours.
- Scope cap: one service plus focused regression tests; target under 150 changed
  lines total and under 30 production lines.
- Stop if a migration, a new table/column, or changes to Telegram bot routing,
  `CareerLedgerService`, or `telegram-digest` appear necessary.

## Authority and identity invariant

`CareerInboxItem.idempotency_key` is the immutable creation/import identity of
the inbox row. Once the row exists, later owner commands must not overwrite it.

Command replay safety remains local to each command:

- `set_verdict` is an idempotent state assignment. Repeating the same normalized
  verdict and reason on the same row is a no-op with `created=False`; a genuine
  state change returns `created=True`.
- `confirm_applied` is protected by the existing `owner_verdict` /
  `linked_application_id` state and the existing idempotent ledger event path.
- A callback idempotency key may be validated and passed to the ledger where the
  ledger owns it, but it must not replace the inbox row's creation identity.

The import contract remains unchanged:

- same `(user_id, external_id, content_hash)` -> the existing row;
- changed `content_hash` for the same `external_id` -> a new immutable snapshot;
- owner verdict, reason, and linked application survive an identical re-import;
- no import creates an application or performs an external action.

## Required implementation

1. Preserve the inbox row's creation/import `idempotency_key` in
   `set_verdict` and `confirm_applied`.
2. Keep the existing public method signatures and response shape.
3. Make repeated assignment of the same verdict/reason an explicit no-op without
   relying on replacing the row's creation key.
4. Do not add a second idempotency framework, action log, repository abstraction,
   model hook, or database migration.
5. Add a short code comment only where needed to prevent a future regression in
   the meaning of the field.

## Mandatory regression cases

Add PostgreSQL-backed tests using synthetic data:

1. `import_snapshot` -> `set_verdict(skip)` -> identical `import_snapshot`:
   second import reports `created=False`; exactly one row exists for the
   import identity; the verdict remains `skip`.
2. `import_snapshot` -> `set_verdict(prepare)` -> `confirm_applied` -> identical
   `import_snapshot`: second import reports `created=False`; exactly one inbox
   row and one linked application exist; the `applied` state is retained.
3. Repeating the same verdict and reason is a no-op; changing the verdict remains
   a real state change.
4. Existing changed-content behavior stays green: a different `content_hash`
   creates a new immutable version and latest-only surfacing still works.

If inexpensive within the cap, add one manual-lead regression proving that its
creation key also survives an owner verdict. This is optional; the four cases
above are the acceptance gate.

## Allowed files

- `app/services/career_inbox_service.py`
- `tests/test_career_inbox_import.py`
- `tests/test_career_inbox_service.py` only if needed for verdict-state coverage
- `!DOC/operations/CURRENT_PRODUCT_STATE.md` only after tests pass, as a short
  current-state update

The worktree already contains unrelated owner/agent changes. Preserve them. Do
not edit, restore, stage, or commit unrelated files. If an allowed source file
changes concurrently, stop and report the overlap.

## Verification

Run the focused tests first:

```powershell
venv\Scripts\python.exe -m pytest tests\test_career_inbox_import.py tests\test_career_inbox_service.py -q
```

Then run the broader career slice if the local test database is available:

```powershell
venv\Scripts\python.exe -m pytest tests\test_career_inbox_service.py tests\test_career_inbox_import.py tests\test_career_inbox_bot.py tests\test_career_ledger_service.py tests\test_vacancy_refresh_service.py -q
```

Do not weaken, skip, or replace PostgreSQL-backed regression tests with mocks.
If unrelated dirty-worktree tests fail, report the exact failures and still show
the focused result.

## Non-goals

- no cleanup, merge, deletion, or mutation of existing live duplicate rows;
- no live database write or migration;
- no bot restart or deployment;
- no change to exporter ranking, gates, Qwen prompt, source configuration, or
  vacancy identity contract;
- no scheduler, auto-apply, cover generation, or new UX;
- no attempt to infer one canonical row among existing live duplicates.

## Rollout and handoff

Stop after the implementation and tests. Do not commit. Report:

1. root cause and exact invariant restored;
2. changed files and line counts;
3. focused and broader test commands/results;
4. whether existing live duplicates still require a separate owner-approved
   repair decision;
5. `READY_FOR_CODEX_ACCEPTANCE`.

Live data cleanup, bot restart, and another vacancy refresh require a separate
owner decision after Codex accepts this corrective slice.
