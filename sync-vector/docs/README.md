## sync-vector Service Overview

Sprint 4 focuses on translating the `memories` canon in Postgres into a high-performance semantic search layer (Qdrant by default, Pinecone or pgvector fallback).

### Responsibilities

1. **CDC ingestion**: subscribe to Debezium/Kafka topic `memories_public`.
2. **Idempotent Upserts**: map each Postgres record to vector payload (embedding + metadata) and upsert into Qdrant.
3. **Deletes / Right to be forgotten**: remove points by `id` or by `user_id`.
4. **Retry & DLQ**: resilience layer for transient failures.
5. **Observability**: metrics for p95 latency, queue lag, failure counts.

### Directory layout

- `sync-vector/config/qdrant/*.json` — reference collection schemas, filters, and examples.
- `sync-vector/docs/api.md` — API documentation for upsert/delete/query usage.
- `sync-vector/docs/runbook.md` — operational procedures (deploy, rollback, troubleshooting).
- `sync-vector/docs/testing.md` — manual checklist for validating collection lifecycle and queries.
- Implementation stubs (future): `/sync-vector/src`, `/sync-vector/tests`, etc.
