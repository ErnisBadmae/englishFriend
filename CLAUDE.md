# CLAUDE.md

This file is the compact bootstrap memory for Claude Code in this repository.

Load only what is needed for the current task. Do not re-scan large docs by default.

Portfolio bootstrap: for strategic or cross-repository context, read
`../PERSONAL_STRATEGY.md`, `../AGENT_OPERATING_MODEL.md`, and `../PORTFOLIO_CONTEXT.md`. Keep product execution
anchored in this repository's local docs.

## Project In One Screen

English Friend is a career-focused English coaching product for Russian-speaking ML/AI and adjacent IT specialists.

Core product shape:
- one guided coach path, not a generic assistant
- primary tracks: `interviews`, `workplace_communication`, `project_walkthrough`
- backend is the product truth; frontend should render backend state, not invent parallel logic

Main runtime:
- FastAPI backend in `app/`
- PostgreSQL is canonical for product/session state
- Qdrant is retrieval enrichment, not bootstrap truth
- Neo4j is outside the request-time bootstrap path

## Repo Map

- `app/`: FastAPI app, agent runtime, services, routing, APIs
- `tests/`: unit and integration tests
- `frontend/`: product UI
- `db/`: migrations and database assets
- `cdc/`, `sync-vector/`, `sync-graph/`, `graph/`: event and derived-data layers
- `scripts/`: eval, smoke, and maintenance scripts
- `!DOC/operations/CURRENT_PRODUCT_STATE.md`: short operational continuity
- `QUICK_START.md`: local setup and runbook

## Working Rules

- Prefer narrow, product-aligned changes over broad framework churn.
- Keep `primary_context` and mission selection consistent with backend routing truth.
- Do not introduce a second product truth-state in docs or frontend-only state.
- Update `!DOC/operations/CURRENT_PRODUCT_STATE.md` only after meaningful product or architecture changes, and keep it short.
- Use existing tests or targeted regressions when changing routing, onboarding, snapshot, or session persistence behavior.

## Read On Demand

Only open these when relevant:
- `!DOC/operations/CURRENT_PRODUCT_STATE.md` for current operational state
- `!DOC/ARCHITECTURE.md` for the global system map and invariants
- `QUICK_START.md` for environment and commands
- `.claude/rules/*.md` for scoped rules
- `app/agent/README.md`, `app/services/conversation_runtime/README.md`, `db/README.md` for subsystem details

Canonical long-form references (load only for strategic decisions):
- `!DOC/strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md`
- `!DOC/strategy/MOAT_AND_METRICS_DOCTRINE_2026-06-11.md`
- `!DOC/research/deep-research-report.md`

`!DOC/README.md` is the tiered index; `!DOC/archive/` is history — never auto-load it.

## Common Commands

```bash
pytest -q
pytest tests/test_learning_node.py -q
venv\Scripts\python.exe scripts/test_voice_backend.py
```

## Continuity

When resuming work:
1. Read `!DOC/operations/CURRENT_PRODUCT_STATE.md`.
2. Read only the subsystem files you are touching.
3. Avoid loading long-form architecture or research docs unless the task actually depends on them.
