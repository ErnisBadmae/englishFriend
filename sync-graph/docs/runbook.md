# Sync-Graph Runbook

## Deploy
1. Ensure Kafka, Debezium, Neo4j running (`docker-compose.cdc.yml`).
2. Register connectors (`memories-connector`, `graph-connector`).
3. Start service: `docker compose -f docker-compose.cdc.yml up -d sync-graph`.
4. Verify health: `curl http://localhost:8091/health`.

## Operations
- **Backfill**: replay Kafka topic with `kafka-consumer-groups --reset-offsets --to-earliest`.
- **DLQ**: inspect `graph_failures` topic; requeue via `scripts/cdc_dlq_retry.sh graph_failures`.
- **Scaling**: increase consumer instances and configure `assignor: cooperative-sticky` in config.

## Metrics
`/metrics` (Prometheus format) exposes `sync_graph_batch_duration_ms`, `sync_graph_dlq_total`, `sync_graph_last_success_timestamp`.

## Troubleshooting
- Missing nodes: check Debezium status (`curl :8083/connectors/graph-connector/status`).
- Sessions topic empty: rerun `db/migrations/postgres/007_publications.sql` so `graph_publication` is recreated with `publish_via_partition_root = true`, delete/recreate the `graph-connector`, then replay a write into `sessions` and verify `graph.public.sessions` via `kafka-console-consumer`.
- Constraint errors: ensure `graph/schema/constraints.cypher` applied.
- Performance: reduce batch size or tune Neo4j memory.
