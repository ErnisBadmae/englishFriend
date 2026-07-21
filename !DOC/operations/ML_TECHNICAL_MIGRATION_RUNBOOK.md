# ML Technical Migration Runbook

Manual cutover for Slice A durable `ml_technical` practice evidence.

Do not run this while old API/MCP writers are accepting answers.

## 1. Capture Preflight State

Record counts and progress from the current JSONB-backed production state:

```sql
select
  user_id,
  jsonb_array_length(roadmap->'ml_technical'->'sessions') as sessions,
  jsonb_array_length(roadmap->'ml_technical'->'attempts') as attempts,
  jsonb_array_length(roadmap->'ml_technical'->'external_reviews') as external_reviews
from learning_plan
where roadmap ? 'ml_technical';
```

Capture current API/MCP progress output for the founder account before cutover.

## 2. Snapshot

Take a restorable PostgreSQL snapshot:

```bash
pg_dump "$DATABASE_URL" --format=custom --no-owner --file ml_technical_precutover.dump
pg_restore --list ml_technical_precutover.dump > ml_technical_precutover.list
```

Before the production window, rehearse the restore into a disposable database.
Set the standard `PGHOST`, `PGPORT`, `PGUSER` and `PGPASSWORD` variables first:

```bash
dropdb --if-exists --force englishfriend_restore_check
createdb --template=template0 englishfriend_restore_check
pg_restore --exit-on-error --single-transaction --no-owner \
  --dbname=englishfriend_restore_check ml_technical_precutover.dump
psql --dbname=englishfriend_restore_check -c "select count(*) from learning_plan where roadmap ? 'ml_technical';"
dropdb --force englishfriend_restore_check
```

Do not start the cutover unless the rehearsal restore and verification query succeed.

## 3. Stop Writers

Stop old API and MCP writers before applying `012_ml_technical_practice.sql`.
Read-only inspection is allowed; answer submission and external review writes are not.

## 4. Apply Migration

Apply the additive migration once:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/postgres/012_ml_technical_practice.sql
```

If preflight fails, do not edit live JSONB in place during the cutover window.
Restore service availability on the old code path, inspect the malformed row offline,
and schedule a new cutover.

## 5. Verify Baseline

For the latest cloned preflight captured on 2026-07-21, verify user `11` has:

- 3 `ml_technical_sessions`
- 6 `ml_technical_attempts`
- 0 `ml_technical_external_reviews`

Two sessions are complete (1/1 and 5/5 answered). The third remains active
(0/2 answered). The captured preflight immediately before the real cutover is
authoritative if activity changes these numbers again.

These are live verification expectations only; do not hard-code them into migration logic.

Also verify:

```sql
select count(*) from ml_technical_session_items where user_id = 11;
select session_id, count(*) from ml_technical_attempts where user_id = 11 group by session_id;
```

Reapply the migration to confirm idempotency and verify counts do not change.

## 6. Start Table-Backed Code

Start the API/MCP code that reads and writes only `ml_technical_*` tables.

## 7. Compare Read Shapes

Compare post-cutover API/MCP output against the preflight captures:

- total progress
- per-topic progress
- recent attempts shape
- reference/rubric fields
- external review shape

No reference answer should appear before an attempt row exists.

## 8. Restore If Needed

If any count, progress value or response shape differs unexpectedly:

1. Stop API/MCP writers again.
2. Confirm `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD` and `TARGET_DB` identify
   the intended database. Keep writers stopped for the entire restore.
3. Recreate the target and restore the exact snapshot:

   ```bash
   dropdb --force "$TARGET_DB"
   createdb --template=template0 "$TARGET_DB"
   pg_restore --exit-on-error --single-transaction --no-owner \
     --dbname="$TARGET_DB" ml_technical_precutover.dump
   ```

4. Run the preflight count query from step 1 against the restored database and
   compare the saved API/MCP progress output.
5. Restart the old JSONB-backed code path only after restore verification.
6. Investigate on a cloned database before retrying cutover.
