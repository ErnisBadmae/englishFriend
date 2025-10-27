# Sync-Graph Service

Bridge between Postgres CDC events and Neo4j graph layer. Consumes Debezium topics (`sessions_public`, `utterances_public`, `corrections_public`, `user_interest_public`) and executes Cypher MERGE batches defined in `graph/schema/ingest.cypher`.

## Features
- Kafka consumer with batching (default 500 events).
- Event router that maps table names to Cypher parameter payloads.
- DLQ publisher (`graph_failures`) with retry CLI.
- Health + metrics endpoint (`:8091/health`).

## Quick start
```bash
pip install -r sync-graph/requirements.txt
PYTHONPATH=. python -m sync_graph.main --config sync-graph/config/app.example.yaml
```

For containerized setup see `docker-compose.cdc.yml`.

## Tests
- `pytest sync-graph/tests/test_transform.py` — unit tests for event → Cypher param mapping.
- `pytest sync-graph/tests/test_batch_metrics.py` — ensures batching/resets.

Integration tests rely on running Neo4j locally and executing `graph/tests/query_checks.cypher` after injecting sample events via `scripts/cdc_batch_sessions.py`.
