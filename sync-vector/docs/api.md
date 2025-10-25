# VectorDB Contracts

This document complements `!DOC/DB.md §3` with concrete API payloads and environment conventions.

## Collections

### Qdrant — `user_memories`

- Vector size: `1536` (OpenAI `text-embedding-3-large`). Make configurable via `QDRANT_VECTOR_DIM`.
- Distance: `Cosine`.
- Payload schema:
  - `user_id` (`int64`, required)
  - `kind` (`string`, enum of `episodic|semantic|persona|skill`)
  - `salience` (`float`)
  - `created_at`, `last_refreshed` (`int64` epoch seconds)
  - `emotion_code` (`string|null`)
  - `topic_ids` (`string[]`)
  - `source_session`, `source_utterance` (`string uuid|null`)

### Pinecone (alternative)

- Index name: `englishfriend-memories`.
- Pod type: `p2.x1` (or serverless equivalent) with `cosine` metric.
- Namespace: `user_{user_id}` (preferred) or global namespace + `user_id` metadata filter.

### pgvector fallback

- Column `memories.embedding vector(1536)` in Postgres (already covered in migrations).
- Query example:

```sql
select id, content, salience
from memories
where user_id = $1 and kind = any('{episodic,semantic}')
order by embedding <=> $2
limit 12;
```

## CDC Event Contract

`sync-vector` consumes events with payload:

```json
{
  "id": "uuid",
  "user_id": 123,
  "kind": "episodic",
  "content": "You love minimalist design.",
  "meta": {"emotion": "joy", "topic_ids": ["<uuid>"]},
  "salience": 0.7,
  "embedding": [ ...1536 floats ... ],
  "last_refreshed": "2025-01-10T12:00:00Z",
  "created_at": "2025-01-09T19:00:00Z",
  "op": "c|u|d"
}
```

- For delete events (`op = d`) we only require `id`; optionally include `user_id` for fallback filtering.
- Embeddings are produced upstream (Realtime pipeline) and stored in Postgres as canonical reference.

## Upsert Flow

1. Convert ISO timestamps to epoch seconds.
2. Validate embedding length matches `QDRANT_VECTOR_DIM`.
3. Upsert via `/collections/{collection}/points` REST API or gRPC equivalent.
4. On success, commit Kafka offset. On failure, push to DLQ (`vector_failures` topic) with reason.

## Deletion Flow

- Single point delete:

```json
{
  "points": ["UUID-TO-DELETE"]
}
```

- Delete by filter (e.g., GDPR request):

```json
{
  "filter": {
    "must": [
      {"key": "user_id", "match": {"value": 123}}
    ]
  }
}
```

## Observability

Expose Prometheus metrics:

- `sync_vector_upsert_latency_ms` (histogram)
- `sync_vector_queue_lag` (gauge)
- `sync_vector_failures_total{reason="qdrant"}` (counter)
- `sync_vector_last_success_timestamp` (gauge)

Grafana dashboards should include:

- Upsert p50/p95 vs SLA (150 ms)
- DLQ backlog
- Qdrant collection size and memory usage (via Qdrant monitoring endpoint)
