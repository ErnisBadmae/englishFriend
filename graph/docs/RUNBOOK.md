# Graph Layer Runbook

## Overview

Sprint 5 delivers the Neo4j graph layer to capture conversational context, interests, and emotional memory. Components:
- Neo4j instance (via docker-compose.graph.yml).
- Schema constraints (`graph/schema/constraints.cypher`).
- Reference seed (`graph/schema/reference_seed.cypher`).
- Ingest MERGE scripts (`graph/schema/ingest.cypher`).
- Saved queries (`graph/queries/*.cypher`).

## Setup

1. **Start services**
   ```bash
docker compose -f docker-compose.graph.yml up -d neo4j
docker compose logs -f neo4j
```

2. **Apply constraints**
   ```bash
cypher-shell -a neo4j://localhost:7687 -u neo4j -p password \
  -f graph/schema/constraints.cypher
```

3. **Seed reference data**
   ```bash
cypher-shell -a neo4j://localhost:7687 -u neo4j -p password \
  -f graph/schema/reference_seed.cypher
```

4. **Smoke test**
   ```bash
cypher-shell -a neo4j://localhost:7687 -u neo4j -p password \
  -f graph/queries/recommend_topics.cypher --param userId=123
```

## CDC / sync-graph

- Source topics: `sessions_public`, `utterances_public`, `corrections_public`, `user_interest_public`.
- `sync-graph` worker consumes events, batches 500–1000, and executes MERGE statements from `graph/schema/ingest.cypher`.
- Use `apoc.periodic.iterate` for batch performance when running manual backfills.

## Testing

### Automated schema tests

`graph/tests/schema_checks.cypher` ensures constraints exist.

Run:
```bash
cypher-shell -a neo4j://localhost:7687 -u neo4j -p password \
  -f graph/tests/schema_checks.cypher
```

### Query checks

Use `graph/tests/query_checks.cypher` to verify sample recommendation/emotion queries return expected shapes.

## Troubleshooting

- **Constraint violations**: Inspect payloads; ensure `id` uniqueness before MERGE.
- **Missing nodes**: Confirm reference seed applied and CDC topics contain data.
- **Performance issues**: Check Neo4j logs, ensure `dbms.memory.heap.max_size` is tuned, and relationships have proper indexes.
- **Rollback**: Use `MATCH (n) DETACH DELETE n` cautiously in non-prod; for prod, rely on backups/snapshots.

## Operations checklist

- [ ] Constraints applied.
- [ ] Reference data seeded.
- [ ] `sync-graph` connected to Kafka.
- [ ] Monitoring (Neo4j metrics endpoint) hooked into Grafana.
- [ ] Backups scheduled (Neo4j `neo4j-admin backup`).
