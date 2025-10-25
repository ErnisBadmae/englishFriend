#!/usr/bin/env bash
set -euo pipefail

TOPIC=${1:?"DLQ topic (vector_failures|graph_failures)"}
BROKER=${BROKER:-localhost:9092}

if ! command -v kafka-console-consumer >/dev/null 2>&1; then
  echo "kafka-console-consumer not found (install Kafka CLI)" >&2
  exit 1
fi
if ! command -v kafka-console-producer >/dev/null 2>&1; then
  echo "kafka-console-producer not found" >&2
  exit 1
fi

echo "Draining $TOPIC and requeueing to retry topic..."
kafka-console-consumer --bootstrap-server "$BROKER" --topic "$TOPIC" --from-beginning --max-messages 10 |
while read -r line; do
  echo "Requeueing: $line"
  echo "$line" | kafka-console-producer --bootstrap-server "$BROKER" --topic ${TOPIC/_failures/_retry}
done
