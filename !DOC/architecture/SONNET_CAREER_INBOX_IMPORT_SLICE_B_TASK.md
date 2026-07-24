# Career Inbox vacancy import (Slice B) v0

Status: approved for bounded implementation (owner: Ernis, 2026-07-24)
Executor: Claude Code / Sonnet
Spec anchor: `career/CAREER_TELEGRAM_COCKPIT_SPEC.md` sections 4-6, 11 (Slice B), 13, 16
Repositories: `telegram-digest`, then `englishFriend`

## Goal

Deliver "подгрузка подходящих вакансий" = Slice B of the cockpit spec: import the
top-7 already-triaged vacancy cards from `telegram-digest` into the EnglishFriend
inbox so the owner gives verdicts in one place. Owner still applies manually.

Relevance is NOT re-computed here. It is decided upstream by telegram-digest's
existing LLM triage + final authority gates (routes `apply_candidate`, `outreach`).
Do NOT build a second matcher/ranker in EnglishFriend - if relevance is weak, that
is telegram-digest gate tuning, out of scope for this task.

## What already exists (do not rebuild)

- `CareerInboxService.import_snapshot` - idempotent import, new content_hash =
  new immutable snapshot, latest-only surfacing. Correct; reuse as-is.
- `validate_import_envelope` - strict schema check. Reuse as-is.
- Bot `Входящие` already lists inbox items via `list_inbox_items`. Imported items
  surface there once import runs.

Missing = the exporter (telegram-digest side) and the import CLI (englishFriend
side) that connects a JSONL file to `import_snapshot`.

## Invariants

- No shared DB, shared package, HTTP service, or broker between repos. Transfer is
  ONE JSONL file passed by an explicit CLI command (spec section 11 Slice B).
- Exporter is deterministic and read-only: no fetch, no Qwen, no retriage. Same
  data in → byte-identical export out.
- Envelope obeys spec section 5: `schema_version==1`; only final authority gates;
  no `raw_text`; no `model_status`/`model_claims`/`fit`/`hard_fail_reasons` as
  facts; bounded grounded `evidence_excerpt`; ≤2 `questions_for_recruiter`;
  default limit 7.
- EnglishFriend runtime never reads telegram-digest files directly; only the CLI,
  invoked by the owner, touches the JSONL.
- Import stays idempotent: re-importing the same file creates no duplicates and no
  stale overwrite. Changed content_hash adds a new snapshot, never mutates an
  existing application.
- No auto-apply, no auto-send, no scheduler. Feature flag default OFF.
- Private recruiter/vacancy text never enters Git fixtures, logs, or reports; tests
  use synthetic data with no network calls.

## Slice B1 - telegram-digest exporter (do first)

Repository: `telegram-digest`. Allowed files:

- one new narrow exporter module + its focused tests;
- a README section for the manual export command;
- existing vacancy files only if a minimal clean helper is unavoidable.

Emit JSONL, one envelope per line, only for routes `apply_candidate` and
`outreach`, default top-7, passing `validate_import_envelope`'s schema. Determinism
and schema/size/privacy tests are the acceptance bar. No fetch/Qwen triggered.

Stop after B1; report the export command and a synthetic sample line.

## Slice B2 - EnglishFriend import CLI (after B1 accepted)

Repository: `englishFriend`. Allowed files:

- one new narrow import CLI/script under `scripts/` (or the existing career CLI
  entrypoint) that reads the JSONL, validates each line with
  `validate_import_envelope`, and calls `CareerInboxService.import_snapshot`;
- `tests/test_career_inbox_service.py` or a focused import test module;
- `!DOC/operations/CURRENT_PRODUCT_STATE.md` (short update only).

No new provider framework, no new service abstraction - wire the existing service.
A malformed line is rejected with a clear error and does not abort the whole batch
unless the owner asked for strict mode; default is skip-and-report.

Acceptance for B2:

- importing a synthetic 7-line file creates 7 inbox items surfaced in `Входящие`;
- re-importing the same file creates 0 new items (idempotent);
- a changed content_hash for one external_id adds a new snapshot; `list_inbox_items`
  shows only the newest; the older row remains for audit;
- an envelope with `raw_text` or a bad gate set is rejected by validation;
- no network calls in tests; all focused tests pass.

Stop after B2. Per spec section 11, do NOT enable the Telegram feature flag until a
repeated import has proven no duplicates and no stale overwrite. Do not migrate live
data, do not commit. Report files, design, test command, result.

## Verification command

```powershell
venv\Scripts\python.exe -m pytest tests\test_career_inbox_service.py -q
```
telegram-digest:
```powershell
venv\Scripts\python.exe -m pytest tests -p no:cacheprovider -q
```
