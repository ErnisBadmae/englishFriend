# sync-vector Runbook

## Prerequisites

- Kafka topic `memories_public` populated by Debezium.
- Qdrant cluster reachable at `${QDRANT_URL}` (default `http://qdrant:6333`).
- Secrets stored via environment variables or Vault:
  - `QDRANT_API_KEY` (if auth enabled)
  - `KAFKA_BROKERS`, `KAFKA_SASL_*` if needed
- Utility dependencies when running scripts locally: `curl`, `jq`, `bash`.

## Deployment

1. Build container:
   ```bash
   docker build -t englishfriend/sync-vector:latest sync-vector
   ```
2. Apply migrations `005_memories_learning_plan.sql` to ensure canonical table exists.
3. Deploy via Compose/Kubernetes:
   ```bash
   docker compose up -d sync-vector
   ```
4. Verify health endpoint:
   ```bash
   curl http://localhost:8090/healthz
   ```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `QDRANT_URL` | Base URL for Qdrant | `http://qdrant:6333` |
| `QDRANT_COLLECTION` | Collection name | `user_memories` |
| `QDRANT_VECTOR_DIM` | Embedding size | `1536` |
| `KAFKA_BROKERS` | Kafka bootstrap servers | `kafka:9092` |
| `KAFKA_TOPIC` | CDC topic name | `memories_public` |
| `DLQ_TOPIC` | Dead-letter topic | `vector_failures` |
| `MAX_RETRIES` | Upsert retries before DLQ | `5` |

Configuration file template: `sync-vector/config/app.example.yaml`.

## Operational Tasks

- **Refresh Collection**: if schema changes, run `scripts/qdrant_recreate.sh`.
- **Backfill**: run `sync-vector --replay-from checkpoints/<timestamp>` to rebuild collection.
- **GDPR delete**: trigger `drop_old_sessions_partitions` + `sync-vector --delete user_id=<id>` (ensures VectorDB cleanup).

## Troubleshooting

### High DLQ rate
- Inspect `vector_failures` topic via `kafka-console-consumer`.
- Common causes: embedding length mismatch, payload validation failure, Qdrant unavailable.

### Qdrant latency spikes
- Check Qdrant logs (`docker compose logs qdrant`).
- Ensure `hnsw_config` and `quantization_config` match `!DOC/DB.md:298`.
- Consider increasing `optimizers_config.default_segment_number`.

### Kafka lag
- Inspect `sync_vector_queue_lag` metric.
- Scale consumer replicas or increase `max_poll_records`.

### Deletion not propagating
- Confirm CDC event for delete (Debezium tombstone).
- Use `qdrant delete points` with `filter` fallback.

### pgvector fallback
- Ensure Postgres `vector` extension installed (`000_init` already includes optional comment).
- Run `alter table memories add column embedding vector(1536)` if not present (migration handles conditional add).
- Use `memories_vec_search.sql` example query for debugging.
