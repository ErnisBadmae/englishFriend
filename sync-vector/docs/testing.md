# Vector Layer Testing Plan

Because Sprint 4 deliverables are mostly infrastructure artifacts, validation is performed manually (pre-implementation) using the following checklist.

## 1. Local Qdrant bring-up

```bash
docker run --rm -p 6333:6333 qdrant/qdrant:latest
export QDRANT_URL=http://localhost:6333
```

## 2. Apply schema

```bash
./scripts/qdrant_recreate.sh
```

Expected: script prints `status: "ok"` for delete/create.

## 3. Seed sample point

```bash
curl -s -X POST "$QDRANT_URL/collections/user_memories/points" \
  -H "Content-Type: application/json" \
  -d @<(cat <<'JSON'
{
  "points": [{
    "id": "11111111-1111-1111-1111-111111111111",
    "vector": [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1,
      0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18, 0.19, 0.2],
    "payload": {
      "user_id": 123,
      "kind": "episodic",
      "salience": 0.7,
      "created_at": 1730000000,
      "last_refreshed": 1730000500,
      "emotion_code": "joy",
      "topic_ids": ["22222222-2222-2222-2222-222222222222"]
    }
  }]
}
JSON
)
```

## 4. Query verification

```bash
curl -s -X POST "$QDRANT_URL/collections/user_memories/points/search" \
  -H "Content-Type: application/json" \
  -d '{"vector":[0.01,0.02,0.03,0.04,0.05,0.06,0.07,0.08,0.09,0.1,
       0.11,0.12,0.13,0.14,0.15,0.16,0.17,0.18,0.19,0.2],
       "limit":5,
       "filter":{"must":[{"key":"user_id","match":{"value":123}}]},
       "with_payload":true}'
```

Should return the point above with payload values intact.

## 5. Delete test

```bash
curl -s -X POST "$QDRANT_URL/collections/user_memories/points/delete" \
  -H "Content-Type: application/json" \
  -d '{"points":["11111111-1111-1111-1111-111111111111"]}'
```

Follow with a search; response should have empty `result`.

## 6. CDC replay dry run

1. Produce a mock Kafka message (example JSON in `sync-vector/docs/api.md`).
2. Use local consumer stub (future step) or `kcat` to ensure payload fields match schema.

Document results in run log before merging Sprint 4 deliverables.
