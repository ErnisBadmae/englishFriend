#!/usr/bin/env bash
set -euo pipefail

QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
COLLECTION="${QDRANT_COLLECTION:-user_memories}"
SCHEMA_FILE="${SCHEMA_FILE:-sync-vector/config/qdrant/collection_user_memories.json}"

if [ ! -f "$SCHEMA_FILE" ]; then
  echo "Schema file not found: $SCHEMA_FILE" >&2
  exit 1
fi

echo "Deleting collection $COLLECTION (if exists)..."
curl -s -X DELETE "$QDRANT_URL/collections/$COLLECTION" | jq '.status? // .result?'

echo "Creating collection $COLLECTION..."
curl -s -X PUT "$QDRANT_URL/collections/$COLLECTION" \
  -H "Content-Type: application/json" \
  --data-binary "@${SCHEMA_FILE}" | jq '.status? // .result?'

echo "Done."
