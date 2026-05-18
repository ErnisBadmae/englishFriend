---
description: Scoped backend/runtime guidance for Python product code
paths:
  - app/**/*.py
  - tests/**/*.py
  - scripts/**/*.py
  - main.py
last_updated: 2026-05-05
---

# Backend Python Guidance

- Treat PostgreSQL as the canonical product/session state source.
- Keep Qdrant as retrieval enrichment only; do not move bootstrap truth into vector retrieval.
- Keep Neo4j and other derived stores outside request-time bootstrap logic.
- Prefer explicit service-layer and routing behavior over broad magic/fallback logic.
- When changing routing or onboarding, preserve `primary_context`, scope-gate behavior, and mission determinism.
- When changing session or evidence flow, verify both persistence and product-facing snapshot behavior.
