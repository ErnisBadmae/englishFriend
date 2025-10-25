# CDC & Synchronization (Sprint 6)

This folder contains Debezium connector definitions, Kafka topic layout, and validation scripts for synchronizing Postgres → Kafka → sync-vector / sync-graph.

## Components

1. **Debezium Connect** (`docker-compose.cdc.yml`) — streams logical replication slots from Postgres.
2. **Kafka Topics**
   - `memories_public` → consumed by `sync-vector` (DLQ: `vector_failures`).
   - `sessions_public`, `utterances_public`, `corrections_public`, `user_interest_public` → consumed by `sync-graph` (DLQ: `graph_failures`).
3. **Services**
   - `sync-vector` (already implemented in Sprint 4).
   - `sync-graph` (new skeleton service with batching + MERGE pipeline).
4. **Neo4j / Qdrant** — targets for vector/graph storage.
5. **Scripts** *(require `psql`, Kafka CLI, and `psycopg2-binary` if running Python helpers)*
   - `register_connector.sh` — register Debezium connectors.
   - `cdc_insert_memory.sh` — insert sample record to trigger CDC.
   - `cdc_batch_sessions.py` — push synthetic batch of session/utterance events for benchmarking.
   - `cdc_dlq_retry.sh` — re-enqueue DLQ payloads for retry testing.

## Connectors

Connector definitions live in `cdc/connectors/*.json`.
- `memories_connector.json` — captures `public.memories` for sync-vector.
- `graph_connector.json` — captures `public.sessions`, `public.utterances`, `public.corrections`, `public.user_interest` for sync-graph.

Register via:
```bash
./scripts/register_connector.sh cdc/connectors/memories_connector.json
./scripts/register_connector.sh cdc/connectors/graph_connector.json
```

## Testing scenarios

1. **Memories upsert/delete** — run `scripts/cdc_insert_memory.sh` to insert/update/delete, then verify in Qdrant via `sync-vector/docs/testing.md` checklist.
2. **Graph batch** — run `python3 scripts/cdc_batch_sessions.py --events 1000` to publish 1k synthetic utterances and confirm Neo4j ingests them (use `graph/tests/query_checks.cypher`).
3. **DLQ retry** — run `scripts/cdc_dlq_retry.sh vector_failures` (or `graph_failures`) after intentionally causing an error; confirms messages can be reprocessed.

Refer to `sync-graph/docs/testing.md` for detailed validation steps.
