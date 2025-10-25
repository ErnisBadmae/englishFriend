# Sync-Graph Testing Checklist

1. **Schema readiness**
   ```bash
   cypher-shell -u neo4j -p password -f graph/schema/constraints.cypher
   cypher-shell -u neo4j -p password -f graph/tests/schema_checks.cypher
   ```
2. **Connector flow**
   ```bash
   ./scripts/register_connector.sh cdc/connectors/graph_connector.json
   ./scripts/cdc_batch_sessions.py --events 1000
   ```
   Expectation: sync-graph logs show batches flushed, Neo4j gains corresponding nodes (validate via `match (u:User)-[:PARTICIPATED_IN]->(:Session) return count(*)`).
3. **Recommendation query**
   Run `cypher-shell -f graph/tests/query_checks.cypher` and ensure `recs` contains data.
4. **DLQ handling**
   - Stop Neo4j to force failures.
   - Produce a session event (script above).
   - Verify message lands in `graph_failures` (use `kafka-console-consumer`).
   - Restart Neo4j and execute `scripts/cdc_dlq_retry.sh graph_failures` to reprocess.
