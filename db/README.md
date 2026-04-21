## Postgres Data Layer

This directory contains migrations, seeds, and tests for the English Friend data layer (Sprints 1‑3).

### Layout

- `migrations/postgres` — ordered SQL migrations (Flyway-compatible) to bootstrap Postgres.
- `seed` — deterministic inserts for reference tables (`dim_emotion`, `dim_topic`, `dim_accent`).
- `tests` — pgTAP suites and helper scripts to validate constraints, partitions, and RLS.

### Running locally

```bash
docker compose up -d postgres
psql $DATABASE_URL -f db/migrations/postgres/000_init.sql
psql $DATABASE_URL -f db/migrations/postgres/001_reference_tables.sql
psql $DATABASE_URL -f db/migrations/postgres/002_users.sql
psql $DATABASE_URL -f db/migrations/postgres/003_sessions_utterances.sql
psql $DATABASE_URL -f db/migrations/postgres/004_partition_management.sql
psql $DATABASE_URL -f db/migrations/postgres/005_memories_learning_plan.sql
psql $DATABASE_URL -f db/migrations/postgres/006_materialized_views.sql
psql $DATABASE_URL -f db/migrations/postgres/010_streaks_gamification.sql
psql $DATABASE_URL -f db/seed/001_reference_seed.sql
bash scripts/manage_partitions.sh create 3
bash scripts/manage_partitions.sh verify
pg_prove db/tests/010_users_channel_identity.sql
pg_prove db/tests/020_sessions_utterances.sql
pg_prove db/tests/030_partition_management.sql
pg_prove db/tests/040_memories_learning_plan.sql
pg_prove db/tests/050_mv_weekly_summary.sql
```

> Adjust connection variables to point at your local Postgres instance. The migrations are idempotent and may be re-applied safely in dev. Tests rely on pgTAP being installed in the target database.
>
> `005_memories_learning_plan.sql` still carries a historical sample `xp_events_2025_10` partition for schema/tests. For fresh local/dev bootstrap, always run `bash scripts/manage_partitions.sh create 3` after migrations so the current-month `xp_events` partition exists before the first `session_complete` insert.

### Current-Month Partition Verification

Use the helper after bootstrap or before a live `/chat/v2` smoke:

```bash
bash scripts/manage_partitions.sh verify
```

For an explicit SQL check against the active month:

```sql
WITH expected AS (
  SELECT
    'xp_events_' || to_char(date_trunc('month', current_date), 'YYYY_MM') AS xp_partition
)
SELECT xp_partition, to_regclass('public.' || xp_partition) AS partition_regclass
FROM expected;
```
