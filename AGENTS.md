# AGENTS.md

Compact bootstrap memory for Codex and other terminal agents.

Portfolio bootstrap: for strategic or cross-repository context, read
`../PERSONAL_STRATEGY.md`, `../AGENT_OPERATING_MODEL.md`, and `../PORTFOLIO_CONTEXT.md`. Do not copy the full
portfolio process here; this repository's local docs remain canonical for product work.

## Project Summary

English Friend is a FastAPI-based career English coach. The product is for Russian-speaking ML/AI and adjacent IT specialists and should stay focused on:
- `interviews`
- `workplace_communication`
- `project_walkthrough`

Product rule: guided coach flow, not a generic assistant or toolbox.

## Architecture Defaults

- `app/` is the main backend/runtime surface.
- PostgreSQL is canonical for product/session state.
- Qdrant is retrieval enrichment only.
- Neo4j is a derived graph layer, not bootstrap truth.
- Frontend should render backend truth-state rather than invent parallel product logic.

## Repo Map

- `app/`: APIs, agent runtime, services, routing
- `tests/`: regression coverage
- `frontend/`: UI
- `db/`: migrations
- `cdc/`, `sync-vector/`, `sync-graph/`, `graph/`: event and derived-data layers
- `scripts/`: eval and maintenance
- `!DOC/operations/CURRENT_PRODUCT_STATE.md`: short continuity file

## Agent Rules

- Read only the files needed for the task.
- Prefer targeted search over broad repo sweeps.
- Keep docs short; do not append long session narratives to continuity files.
- If product behavior changes, update `!DOC/operations/CURRENT_PRODUCT_STATE.md` with current state only.
- Use subsystem docs and READMEs on demand instead of loading long global docs at startup.

## Useful References

- `QUICK_START.md`
- `app/agent/README.md`
- `!DOC/MASTER_PROJECT_VIEW_2026-04-22.md`
- `!DOC/research/deep-research-report.md`
