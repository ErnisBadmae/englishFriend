# Sonnet task: Career Ledger v0

Status: approved implementation task  
Owner: Ernis  
Architect and acceptance owner: Codex  
Executor: Sonnet

## Outcome

Add a small career execution ledger to EnglishFriend so the owner can record
manual applications from Telegram and senior models can read a bounded funnel
snapshot through MCP.

This is not an auto-apply system and not a general personal-management platform.
The human strategy in `C:/Users/badmaev_es/develop/PERSONAL_STRATEGY.md` remains
canonical and read-only.

## Mandatory first action

Before reading implementation files, run from the EnglishFriend root:

```powershell
graphify query "career vacancy application evidence postgres telegram mcp progress" --budget 3500
```

Use the graph result to identify the existing service, PostgreSQL, Telegram and
MCP seams. In the final report, state which graph nodes guided the implementation.
Do not rebuild Graphify and do not broadly rescan the repository.

Then read only:

- `AGENTS.md`
- `CLAUDE.md`
- `!DOC/architecture/CAREER_PRACTICE_CONTROL_PLANE.md`
- `!DOC/operations/CURRENT_PRODUCT_STATE.md`
- the existing `ml_technical` models/service/Telegram adapter/MCP server and
  their focused tests
- `db/README.md` and migration `015_ml_progress_reviews.sql`

## Product boundary

The service may:

- persist vacancy snapshots and owner-confirmed application events;
- show the owner a compact Telegram summary;
- expose a bounded, hash-stamped read context through MCP;
- preserve exact evidence and append-only history.

The service must not:

- send an application, message a recruiter or open an external form;
- generate or choose a cover letter or CV;
- change `PERSONAL_STRATEGY.md` or copy the full strategy into PostgreSQL;
- let an LLM change application status or owner facts;
- use Qdrant, Neo4j, CDC or a new service/process;
- implement vacancy fetching or Qwen triage in this slice;
- parse `career/PIPELINE_2026-07.md` as a database source;
- modify `telegram-digest`, `egeMentor`, `expert-agent` or root strategy files;
- apply migrations to the live database;
- commit or push.

## Required vertical slice

### 1. Additive PostgreSQL migration

Create the next idempotent migration after `015` with three owner-scoped tables.
Follow existing UUID, timestamp, index, foreign-key and RLS conventions.

`career_vacancy_snapshots`

- immutable snapshot identity;
- `user_id`;
- source and optional external id;
- company, role title, optional URL;
- optional bounded raw description;
- deterministic content hash;
- creation timestamp;
- an idempotency constraint that prevents the same user/source/content snapshot
  from being inserted twice.

`career_applications`

- `user_id` and exact vacancy snapshot id;
- current status derived only through the service transition policy;
- owner-confirmed application timestamp;
- optional resume reference and hash;
- optional cover-letter reference and hash;
- next action and optional due date;
- created/updated timestamps;
- at most one active application for the same user and vacancy snapshot.

`career_application_events`

- append-only event history for one application and user;
- event type, timestamp, actor type/id and bounded JSON metadata;
- no update or delete path in application code.

Use a conservative initial status set sufficient for the existing funnel:
`applied`, `screening`, `technical`, `rejected`, `offer`, `withdrawn`.
The initial record operation creates `applied` plus the first event atomically.
Define and test an explicit transition map. Invalid transitions fail closed.

### 2. Application service

Create a focused service, not a generic repository framework.

Required operations:

- `record_manual_application(...)`: atomically create/reuse an immutable vacancy
  snapshot, create the application, and append its first event;
- idempotent retry using a caller-provided event/idempotency key;
- `append_application_event(...)`: owner-originated allowed transition only;
- `list_applications(...)`: bounded recent list;
- `get_pipeline_summary(...)`: counts by status plus nearest actions;
- `get_review_context(...)`: bounded facts and stable SHA-256 context hash for MCP.

The service must enforce user isolation. It must not accept model conclusions as
facts. Prefer existing canonical JSON/hash helpers if they fit without coupling
the two domains; otherwise add a small local helper rather than a framework.

### 3. Private Telegram commands

Extend the existing private allowlisted bot without creating another bot or a
second in-memory state machine.

Commands:

- `/applied Company | Role | URL`
- `/applications`

`/applied` is an explicit owner action. Validate the three fields, trim and bound
their lengths, derive an idempotency key from the Telegram update id, record the
application and return a compact confirmation. A repeated update must not create
a duplicate application/event.

`/applications` returns total counts by status and a bounded recent list.

Do not add LLM extraction in v0. Do not interpret arbitrary forwarded messages.
If `/applied` is malformed, return one short usage example. Existing ML drill
message routing must remain unchanged.

All human-facing Russian text follows the root writing convention: ordinary
ASCII `-`, concise wording and no decorative English terminology.

### 4. MCP read boundary

Extend the existing project-specific MCP server with read-only tools:

- `get_career_pipeline_summary`
- `get_career_pipeline_review_context`

Resolve by `user_id` or `telegram_id` using the existing helper. Return bounded
PostgreSQL facts and a context hash. Do not add an MCP write tool for application
status, applications, strategy or external actions.

Keep the existing `get_career_brief` behavior unchanged. A senior model is
expected to read the brief and the pipeline context separately and reason over
both; it cannot write either source.

### 5. Tests and documentation

Add focused tests for:

- migration shape/idempotency using the repository's established pattern;
- atomic first application event;
- duplicate Telegram update/event idempotency;
- user isolation;
- allowed and forbidden status transitions;
- bounded fields and context;
- stable context hash and hash change after a new event;
- Telegram authorization and existing ML drill routing regression;
- MCP tools are read-only and return the same service truth.

Update:

- `!DOC/architecture/CAREER_PRACTICE_CONTROL_PLANE.md` with the implemented slice;
- `!DOC/operations/CURRENT_PRODUCT_STATE.md` with current state only, including
  that Telegram ML polling is now live and the prior "missing token/ID" blocker
  is stale;
- a short migration/runbook note if the existing database documentation requires it.

Run focused tests and a compile/import check. Do not run the full suite unless
focused tests expose a broad regression. Do not mutate the live database.

## Acceptance gates

1. One `/applied` command creates exactly one snapshot, application and first
   event in a test database.
2. Replaying the same Telegram update creates no additional rows.
3. `/applications` and MCP read the same counts from the same service.
4. An external model has no write path to owner application facts.
5. Existing ML Telegram drill tests remain green.
6. No Qdrant, Neo4j, new process, vacancy fetcher, letter generator or auto-send
   is introduced.
7. The final report includes changed files, tests, unresolved risks and the exact
   live migration command as a recommendation only. It must not execute it.

## Stop conditions

Stop and report instead of expanding scope if:

- current schema conventions make the three-table slice unsafe without a broad
  migration framework change;
- existing Telegram routing cannot add the two commands without changing ML
  answer semantics;
- a required fact is missing and guessing would alter user-visible behavior;
- unrelated dirty worktree changes appear.

