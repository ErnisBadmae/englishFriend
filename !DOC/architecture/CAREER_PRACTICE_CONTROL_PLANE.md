# Career Practice Control Plane

Status: accepted implementation direction
Date: 2026-07-21

## Outcome

EnglishFriend owns the founder's career-practice state. Telegram, web and MCP are adapters over one application service and one PostgreSQL truth.

The first supported domain is Russian ML/DL interview practice. Career strategy, vacancies and English practice may join the same control plane later, but are not part of the Telegram v0 runtime.

## Storage roles

- PostgreSQL is canonical for questions, sessions, attempts, reviews and progress.
- Qdrant may later index question meaning, source material and similar mistakes. It cannot decide progress or question status.
- Neo4j may later derive a graph of skills, questions, mistakes and vacancies. It cannot receive canonical writes from Telegram or MCP.
- Existing `LearningPlan.roadmap.ml_technical` becomes a read-only migration archive after the evidence migration.

## Channel invariant

```text
Telegram -----\
Web ----------- application service ----- PostgreSQL
MCP ----------/             |
                              +-- optional derived Qdrant / Neo4j projections
```

No adapter owns a second queue, score or progress model. A reference answer is never returned before an attempt is persisted.

## Delivery slices

### Slice A: durable practice evidence

Create four append-oriented tables.

#### `ml_technical_sessions`

- `id UUID PRIMARY KEY`
- `user_id BIGINT NOT NULL REFERENCES users(id)`
- `mode TEXT NOT NULL`: `topic` or `daily`
- `channel TEXT NOT NULL`: `web`, `telegram` or `mcp`
- `topic_id TEXT NULL`: required for `topic`, null for cross-topic `daily`
- `session_seed TEXT NULL`
- `practice_date DATE NULL`: required for `daily`
- `status TEXT NOT NULL`: `active`, `completed` or `cancelled`
- `created_at TIMESTAMPTZ NOT NULL`
- `closed_at TIMESTAMPTZ NULL`
- `UNIQUE(id, user_id)`
- partial unique `(user_id, practice_date)` where `mode = 'daily'`
- checks constrain `mode`, `channel`, `status`, and require `practice_date` only for `daily`

#### `ml_technical_session_items`

- `id UUID PRIMARY KEY`
- `user_id BIGINT NOT NULL`
- `session_id UUID NOT NULL`
- `question_id TEXT NOT NULL`
- `position INTEGER NOT NULL`
- `status TEXT NOT NULL`: `pending`, `answered` or `skipped`
- `created_at TIMESTAMPTZ NOT NULL`
- `updated_at TIMESTAMPTZ NOT NULL`
- composite FK `(session_id, user_id)`
- `UNIQUE(session_id, question_id)`
- `UNIQUE(session_id, position)`
- a check constrains `status` to `pending`, `answered` or `skipped`

#### `ml_technical_attempts`

- `id UUID PRIMARY KEY`
- `user_id BIGINT NOT NULL`
- `session_id UUID NOT NULL`
- `question_id TEXT NOT NULL`
- `topic_id TEXT NOT NULL`
- `answer_kind TEXT NOT NULL`: `normal` or `dont_know`
- `answer_language TEXT NOT NULL`
- `raw_answer TEXT NOT NULL`
- `source_channel TEXT NOT NULL`
- `source_event_id TEXT NULL`
- `answered_at TIMESTAMPTZ NOT NULL`
- `provenance_id TEXT NULL`
- `review JSONB NOT NULL`
- composite FK `(session_id, user_id)`
- `UNIQUE(session_id, question_id)`
- partial unique `(source_channel, source_event_id)` where `source_event_id IS NOT NULL`
- duplicate insertion uses `ON CONFLICT DO NOTHING RETURNING id`; an empty result becomes a typed, controlled duplicate outcome rather than an unhandled database error

#### `ml_technical_external_reviews`

- `id UUID PRIMARY KEY`
- `user_id BIGINT NOT NULL`
- `attempt_id UUID NOT NULL`
- `reviewer TEXT NOT NULL`
- `verdict TEXT NOT NULL`
- `notes TEXT NULL`
- `created_at TIMESTAMPTZ NOT NULL`
- composite FK `(attempt_id, user_id)`

All tables receive user and time indexes plus the same RLS isolation rule used by `learning_plan`.

Migration `012` is additive and idempotent. A fail-fast preflight uses `jsonb_typeof` to require an object section and array-valued `sessions`, `attempts` and `external_reviews`; malformed rows abort the migration instead of being skipped. It backfills the existing session, item, attempt and external-review rows with their original identifiers and timestamps, and never deletes the old JSONB. A second run must create no duplicates. Current live baseline before migration: user `11`, 2 sessions, 6 attempts and 0 external reviews.

Cutover is an operational transaction, not an implicit dual-read window: take a database snapshot, stop old API/MCP writers, run migration `012`, compare counts and progress, start the table-backed code, then run read-only smoke. If verification fails, do not accept new writes on either implementation.

After cutover the service reads and writes only the new tables. There is no permanent dual-write or dual-read.

`dont_know` is a first-class attempt. It does not call the LLM, receives deterministic 0%, records all rubric points as missing and reveals the reference only after persistence.

### Slice B: private Telegram v0

Create a separate long-polling process. It talks directly to the same application service and PostgreSQL. It does not require the web frontend or FastAPI process.

Commands:

- `/start`: show the menu, do not start a session.
- `/today`: return the same idempotent five-question daily session for a user and Moscow date.
- `/slice`: choose a non-empty topic and start at most five questions.
- `/progress`: show total progress, due repetitions, pending reviews and three weakest non-empty topics.
- `/skip`: mark the current item skipped without an attempt or error.
- `/cancel`: persistently cancel the active session.

The `Не знаю - показать разбор` callback submits `answer_kind=dont_know` through the service.

Daily order is a pure deterministic policy:

```text
due repetitions -> latest failures -> unseen -> remaining questions
```

A session and its current item are recovered from PostgreSQL after every process restart. Python dictionaries cannot be the source of active-session state. A text answer is routed only to the next `pending` item of the user's active Telegram session. `/skip` and `dont_know` use conditional state transitions from `pending`; zero affected rows are an idempotent stale outcome. Callback data carries session and item identifiers, and the service rejects an item that is no longer pending. `source_event_id` prevents duplicate Telegram updates from creating a second attempt.

Access rules:

- private chats only;
- allowlist from `ML_TECHNICAL_TELEGRAM_ALLOWED_IDS`;
- resolve an existing user by the real Telegram ID;
- never auto-create a user;
- an unknown `/start` may return its Telegram ID for manual linking;
- repeated Telegram updates and stale callbacks are idempotent.

The bot runs as a separate Compose service with `restart: unless-stopped`. Token and allowlist stay in environment variables. Proxy configuration reuses the existing project proxy setting or `HTTPS_PROXY`.

### Slice C1: versioned question bank and curator MCP

Create immutable `ml_question_revisions` and append-only `ml_question_reviews`.

An approved question is never edited. A correction creates a new revision and retires the previous approved revision in one transaction. Attempts bind to an exact question revision.

Question provenance contains:

- source kind and safe label;
- optional public URI;
- private source fingerprint, never a private URL in public output;
- derivation kind;
- publication scope;
- license or consent note;
- model and prompt versions when applicable;
- idempotency key and content hash.

MCP read tools:

- `get_ml_question_bank_coverage`
- `list_ml_question_drafts`
- `get_ml_question_revision`
- `get_career_brief`

MCP write tools:

- `create_ml_question_draft`
- `validate_ml_question_draft`
- `append_ml_question_qa_review`
- `approve_ml_question`
- `retire_ml_question`

Creating a draft never approves it. Approval and retirement require an explicit admin configuration flag. Stale content hashes, missing provenance, invalid schemas, model timeouts and source/IP uncertainty all fail closed to `draft`.

The 15 checked-in questions become approved revision 1 through an idempotent backfill. Runtime switches to the database only after a shadow comparison of all public fields, order and topic coverage.

### Slice C2: senior progress analysis

Only after C1 is live, add read-only `get_ml_progress_review_context` and append-only `ml_progress_reviews` / `append_ml_progress_review`. A progress review references an immutable context hash and existing evidence; it can recommend a drill but cannot alter attempts, scores or question status.

## Career brief boundary

The human strategy document remains canonical. A small versioned machine-readable brief will expose only targets, constraints, current focus, skill gaps and nearest outcomes. MCP reads it and returns its SHA-256; it cannot edit it. Free-form strategy prose is not copied into several databases.

## Content growth

Do not generate 45 questions in one unreviewed batch. Grow from 15 to 60 through three approved batches:

1. Add 15 questions driven by current vacancies: recsys/ranking, A/B tests, classical ML and LLM evaluation.
2. After at least 30 real attempts, add 15 questions for observed gaps.
3. Add the last 15 from actual interview evidence and vacancy changes.

Every batch passes `draft -> deterministic validation -> senior technical review -> owner approval`.

## Acceptance gates

### Slice A

- Existing 2 sessions and 6 attempts survive migration with identical progress.
- Reapplying migration creates no duplicates.
- Concurrent different answers both persist.
- Concurrent duplicate answer produces one attempt and a controlled conflict.
- External MCP review cannot overwrite an attempt.
- Existing API and MCP response shapes remain compatible.
- Existing focused ML and interview tests stay green.

### Slice B

- Unauthorized and unlinked chats cannot write.
- `/today` is idempotent for a date.
- Restart between question and answer preserves the session.
- Repeated update, `/skip`, `/cancel` and stale callback are idempotent.
- `dont_know` bypasses Qwen and does not leak the reference before persistence.
- Qwen failure becomes `needs_review`.
- Web, Telegram and MCP show the same progress.

### Slice C

- Draft lifecycle, immutable revisions, retirement and content-hash conflicts are tested.
- Private provenance never appears in public views.
- An old attempt always resolves its original rubric revision.
- Progress reviews are append-only and cannot change scores.
- Backfill and shadow comparison of the first 15 questions are idempotent.

## Career ledger v0 (implemented slice)

A small, separate execution ledger sits beside the interview-practice tables.
It does not replace or extend Slice A-C; it owns three additive tables so the
founder can record manual applications from Telegram and a senior model can
read a bounded funnel snapshot through MCP.

`career_vacancy_snapshots` (immutable, content-hashed), `career_applications`
(current status only; history lives in events) and `career_application_events`
(append-only, DB-trigger enforced). Migration `016_career_ledger.sql` is
additive and was applied to the live development database on 2026-07-22 after
a fresh backup and PostgreSQL-backed integration tests.

`CareerLedgerService` (`app/services/career_ledger_service.py`) is the only
write path: `record_manual_application` atomically creates/reuses a snapshot,
creates the application and its first event, and is idempotent on a
caller-provided key. `append_application_event` allows only owner-originated,
explicitly mapped status transitions (`applied -> screening/technical/
rejected/withdrawn`, `screening -> technical/rejected/withdrawn`,
`technical -> offer/rejected/withdrawn`, `offer -> withdrawn`); everything
else fails closed. Status transitions lock the application row before deriving
the next event, so concurrent retries cannot branch from a stale status.

Telegram (`/applied Company | Role | URL`, `/applications`) is the only
write-capable channel, added to the existing private ML-technical bot and
dispatcher - no second bot, no second in-memory state machine. `/applied`
derives its idempotency key from the chat id and Telegram message id, so a
replayed update creates no duplicate rows.

MCP exposes two read-only tools on the existing `ml_technical` server:
`get_career_pipeline_summary` and `get_career_pipeline_review_context`
(bounded facts plus a stable SHA-256 context hash). There is no MCP write
tool for application status, applications, vacancies or strategy; a model can
read `get_career_brief` and the pipeline context but cannot write either.

Not in this slice: vacancy fetching, Qwen triage, cover letter/CV generation,
auto-apply, and no Qdrant/Neo4j/CDC involvement.

## Stop conditions

- Do not modify egeMentor or its data.
- Do not connect Qdrant or Neo4j to the request-time write path.
- Do not create a second career strategy source of truth.
- Do not start Slice C until Slice A has passed migration and live read verification.
- Do not start mass question generation until the draft-approve path is live.
