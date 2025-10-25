#!/bin/sh
set -euo pipefail

CONNECT_URL="${CONNECT_URL:-http://debezium:8083}"
MEMORIES_FILE="${MEMORIES_FILE:-/app/cdc/connectors/memories_connector.json}"
GRAPH_FILE="${GRAPH_FILE:-/app/cdc/connectors/graph_connector.json}"
WAIT_TIME="${WAIT_TIME:-30}"
RETRIES="${RETRIES:-10}"

echo "Waiting for Debezium at ${CONNECT_URL} ..."
for i in $(seq 1 "$RETRIES"); do
  if curl -s "${CONNECT_URL}/connectors" >/dev/null 2>&1; then
    READY=1
    break
  fi
  echo "Attempt ${i}/${RETRIES}: Debezium not ready yet, sleeping ${WAIT_TIME}s"
  sleep "$WAIT_TIME"
done

if [ "${READY:-0}" -ne 1 ]; then
  echo "Debezium not reachable at ${CONNECT_URL}, aborting."
  exit 1
fi

register_connector() {
  local file=$1
  if [ ! -f "$file" ]; then
    echo "Connector file not found: $file"
    return 1
  fi
  echo "Registering connector from $file"
  curl -sS -X POST \
    -H "Content-Type: application/json" \
    --data @"$file" \
    "${CONNECT_URL}/connectors" || echo "Failed to register connector from $file"
}

register_connector "$MEMORIES_FILE"
register_connector "$GRAPH_FILE"

echo "Connectors registration completed."
