# ML Question Bank Cutover

Migration `014_ml_question_bank.sql` is required before starting code that
imports the new ORM schema. Do not point the new code at a database that has
only migrations 012-013.

## 1. Rehearse on a disposable clone

Stop ML practice writers, take a restorable snapshot, and restore it into a
disposable database. Apply the migration there first:

```bash
psql "$CLONE_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f db/migrations/postgres/014_ml_question_bank.sql
psql "$CLONE_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f db/migrations/postgres/014_ml_question_bank.sql
```

The second application is the idempotency check. Both commands must finish
without an error.

## 2. Verify the clone

```sql
select status, count(*)
from ml_question_revisions
group by status
order by status;

select review_kind, verdict, count(*)
from ml_question_reviews
group by review_kind, verdict
order by review_kind, verdict;

select count(*) as unbound_items
from ml_technical_session_items
where question_revision_id is null;

select count(*) as unbound_attempts
from ml_technical_attempts
where question_revision_id is null;

select question_key, count(*)
from ml_question_revisions
where status = 'approved'
group by question_key
having count(*) <> 1;
```

Expected baseline after backfill:

- 15 approved question revisions
- 15 PASS schema reviews
- 15 PASS technical reviews
- 15 PASS source/IP reviews
- zero unbound session items and attempts
- zero rows from the final duplicate-approved query

Run one existing Telegram session and one web topic session against the clone.
Confirm that each stored attempt has the same `question_revision_id` as its
session item and that recent-attempt output resolves its rubric from that exact
revision.

### Exact public shadow comparison

Before cutover, save the public question list from the checked-in pack as
`questions-static.json`. Against the migrated clone, save
`MlQuestionBankService.list_approved_questions()` after applying
`public_question_view` as `questions-postgres.json`. Compare the following
ordered projection, with no set conversion and no sorting in the comparison:

```text
id, topic_id, question_ru, difficulty, tags
```

The PostgreSQL service order must be the same stable `question_key` ascending
order used by the static baseline. `question_revision_id` is an additive field
and is checked separately: it must be a non-empty UUID for every PostgreSQL
row. Fail the cutover on the first differing public field or position.

Also compare topic coverage exactly, including zero-count topics:

```text
topic_id -> ordered question ids -> count
```

The baseline cutover must have 15 rows in both snapshots, the same ordered IDs,
and the same per-topic ordered IDs and counts. A matching total with a moved,
missing or extra topic is a failure, not a warning.

## 3. Apply in the cutover window

1. Keep API, Telegram and MCP writers stopped.
2. Take and verify a fresh PostgreSQL snapshot.
3. Apply migration 014 with `ON_ERROR_STOP=1`.
4. Run all verification queries from step 2.
5. Start the table-backed code only after the checks pass.

Keep these settings false for the first read-only smoke:

```env
ML_QUESTION_CURATOR_ENABLED=false
ML_QUESTION_ADMIN_ENABLED=false
```

Enable the curator flag only for a controlled draft/review run. The admin flag
is separate and is required only for approve/retire operations.

## 4. Recovery

Migration 014 intentionally has no destructive down migration. If verification
fails, keep writers stopped and restore the pre-cutover snapshot. Do not remove
revision foreign keys or rewrite question rows manually on the live database.
