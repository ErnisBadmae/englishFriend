# ML progress review MCP runbook

## Boundary

Migration `015_ml_progress_reviews.sql` adds append-only senior analysis over
the existing PostgreSQL ML practice evidence. It does not change attempts,
scores, sessions or question lifecycle state. Qdrant and Neo4j are not in this
write path.

`get_ml_progress_review_context` is read-only. It returns a bounded canonical
snapshot and `context_hash`. `append_ml_progress_review` recomputes that
snapshot in its database transaction and rejects a stale hash.

`get_career_brief` reads only the YAML fence between
`career-brief:start` / `career-brief:end` in the root `PERSONAL_STRATEGY.md`.
It does not copy or edit strategy data.

## Clone verification

Apply twice to a disposable database:

```powershell
docker cp db\migrations\postgres\015_ml_progress_reviews.sql english_friend_postgres:/tmp/015_ml_progress_reviews.sql
docker exec english_friend_postgres psql -U postgres -d englishfriend_slicea_20260721 -v ON_ERROR_STOP=1 -f /tmp/015_ml_progress_reviews.sql
docker exec english_friend_postgres psql -U postgres -d englishfriend_slicea_20260721 -v ON_ERROR_STOP=1 -f /tmp/015_ml_progress_reviews.sql
```

Run focused unit and real PostgreSQL checks:

```powershell
$env:ML_TECHNICAL_PG_TEST_URL='postgresql+asyncpg://postgres:postgres@localhost:5432/englishfriend_slicea_20260721'
venv\Scripts\python.exe -m pytest tests\test_ml_progress_review.py -q
```

Expected: a second migration is a no-op, stable context calls return the same
hash, changed evidence is rejected as stale, and database UPDATE/DELETE of a
stored review fails.

## Live cutover

Do not apply `015` before `014` is accepted live. Then:

1. Take a fresh PostgreSQL backup.
2. Stop API/MCP writers for the short migration window.
3. Apply `015_ml_progress_reviews.sql` with `ON_ERROR_STOP=1`.
4. Verify table, indexes, RLS policy and append-only trigger.
5. Keep appends disabled and restart the normal API.
6. Read `get_career_brief` and `get_ml_progress_review_context` once.
7. Enable appends only for a controlled senior review run.

Verification query:

```sql
select count(*) from ml_progress_reviews;
select indexname from pg_indexes
where tablename = 'ml_progress_reviews' order by indexname;
select tgname from pg_trigger
where tgrelid = 'ml_progress_reviews'::regclass and not tgisinternal;
```

## Capability flag

Default and normal runtime:

```text
ML_PROGRESS_REVIEW_APPEND_ENABLED=false
```

Set it to `true` only for the MCP process allowed to append the reviewed
artifact. A `reviewer_id` argument is provenance, not authorization. Restart
that MCP process after changing the setting, append against the exact context
hash, then disable the flag again.

## Failure handling

- Stale hash: read a fresh context and rerun analysis. Never override it.
- Missing/duplicate strategy markers or invalid YAML: repair the canonical
  strategy document; do not add a fallback copy.
- Model failure or invalid structured output: append nothing.
- Migration failure: leave appends disabled and restore/repair before restart.
