# Career Cover Letter Draft v0 (implementation task)

Status: BLOCKED until (a) Ernis ratifies `career/CAREER_COVER_LETTER_DRAFT_SPEC.md`
and (b) Slice B import task is accepted (needs `prepare` cards to attach a draft to).
Executor: Claude Code / Sonnet
Spec anchor: `career/CAREER_COVER_LETTER_DRAFT_SPEC.md`
Repository: `englishFriend`

Do NOT start this task before both preconditions hold. It intentionally lifts part
of a former cockpit Non-goal, so it must ride on a ratified spec, not a silent edit.

## Central invariant (repeat from spec section 2)

The LLM is an untrusted drafter. No concrete claim about the owner (number, company,
date, technology, metric, role) may appear in the draft unless it traces to
`career/facts_bank.yaml` (+ chosen CV variant). Untraceable concrete claims are
FLAGGED in a grounding report, never silently kept. `owner_approved` is not a send.

## Invariants

- PostgreSQL canonical; draft versions are immutable/append-only.
- Grounding source is `career/facts_bank.yaml` + selected CV; the bot reads these,
  never mutates them.
- Reuse the existing LLM provider adapter (untrusted extractor pattern already in
  `career_inbox_service.py`); no new provider framework.
- No auto-apply, no auto-send, no scheduler, no MCP write, no Qdrant/Neo4j.
- No-LLM path fully works: on empty facts bank / timeout / bad schema, offer the
  manual skeleton, generate nothing.
- Feature flag default OFF, separate from the inbox flag.
- Draft attaches only to an inbox item whose owner_verdict is `prepare`.
- Tests synthetic, no network, no private text in Git.

## Slice 1 - model + service (do first)

Allowed files:

- `app/models/career.py`
- `app/services/career_inbox_service.py` (extend; keep it narrow)
- `db/migrations/postgres/019_career_cover_letter_draft.sql`
- `db/README.md`
- `tests/test_career_inbox_service.py`

Add a cover-letter-draft entity (spec section 4) and owner-only service methods:
generate-draft (calls LLM as untrusted drafter, returns body + grounding report),
approve, reject, list versions. Implement the grounding report: match concrete
tokens (numbers, org names, tech, years) in the draft against facts_bank/CV; list
used facts and flag sentences with unmatched concrete claims. Do not apply the
migration to the live DB; do not commit.

Acceptance for Slice 1:

- a draft asserting a number absent from facts_bank flags that sentence;
- empty/broken facts bank or LLM timeout yields no draft and a manual-path signal;
- approve sets `owner_approved`, creates no application, sends nothing;
- versions immutable; generate is idempotent to replay;
- facts_bank and CV files are byte-identical before/after generation;
- focused service tests pass on an isolated PostgreSQL test DB.

Stop after Slice 1; report.

## Slice 2 - Telegram UX (after Slice 1 accepted)

Allowed files:

- `app/adapters/telegram/ml_technical_bot.py`
- `tests/test_career_inbox_bot.py`
- `!DOC/operations/CURRENT_PRODUCT_STATE.md` (short update)

Add `Черновик сопровода` on a `prepare` card (spec section 6): show draft + short
grounding report; buttons `Одобрить черновик`, `Отклонить`, `Скопировать` (display
only), `Обновить факты вручную` (routes to manual input, never auto-edits facts
bank). `Одобрить` records `owner_approved` and sends nothing.

Acceptance for Slice 2:

- `Черновик сопровода` appears only after `Готовить`;
- approve records state, sends nothing, creates no application;
- Telegram replay creates no duplicate version/approve;
- stale callback fail-closed;
- no LLM path still lets the owner proceed manually;
- focused bot tests pass.

Stop after Slice 2. Do not restart the live bot, migrate live data, or commit.
Report files, design, test command, result.

## Verification command

```powershell
venv\Scripts\python.exe -m pytest tests\test_career_inbox_service.py tests\test_career_inbox_bot.py -q
```
