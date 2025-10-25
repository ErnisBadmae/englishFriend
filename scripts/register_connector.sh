#!/usr/bin/env bash
set -euo pipefail

CONNECTOR_FILE=${1:?"path to connector json"}
CONNECT_URL=${CONNECT_URL:-http://localhost:8083/connectors}

if [ ! -f "$CONNECTOR_FILE" ]; then
  echo "Connector file not found: $CONNECTOR_FILE" >&2
  exit 1
fi

echo "Registering connector from $CONNECTOR_FILE ..."
response=$(curl -s -o /tmp/connector_resp.json -w "%{http_code}" -X POST \
  -H "Content-Type: application/json" \
  --data "@${CONNECTOR_FILE}" \
  "$CONNECT_URL")

cat /tmp/connector_resp.json

if [ "$response" -ge 200 ] && [ "$response" -lt 300 ]; then
  echo "Connector registered successfully."
else
  echo "Failed with status $response" >&2
  exit 1
fi
