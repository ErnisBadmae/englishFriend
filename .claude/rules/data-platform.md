---
description: Scoped guidance for database, CDC, and derived-data layers
paths:
  - db/**
  - cdc/**
  - sync-vector/**
  - sync-graph/**
  - graph/**
  - docker-compose*.yml
last_updated: 2026-05-05
---

# Data Platform Guidance

- Preserve PostgreSQL as the canonical write path for product state.
- Treat Kafka, Qdrant, and Neo4j as downstream or enrichment layers unless a task explicitly changes that contract.
- Keep request-time dependencies on CDC or sync layers out of the main product path.
- Document any contract change that affects bootstrap truth, event ordering, or recovery behavior.
