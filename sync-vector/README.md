# Sync-Vector Service

Sprint 4 Vector Layer implementation for the English Friend project. This service provides CDC (Change Data Capture) to Qdrant vector database synchronization for the `memories` table.

## Overview

The sync-vector service translates PostgreSQL `memories` records into high-performance semantic search vectors stored in Qdrant. It handles:

- **CDC ingestion**: Subscribes to Debezium/Kafka topic `memories_public`
- **Idempotent Upserts**: Maps Postgres records to vector payloads and upserts to Qdrant
- **Deletes & Right to be forgotten**: Removes points by `id` or `user_id`
- **Retry & DLQ**: Resilience layer for transient failures
- **Observability**: Metrics for p95 latency, queue lag, failure counts

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Virtual environment (recommended)

### Local Development

1. **Activate virtual environment:**
   ```bash
   source .venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r sync-vector/requirements.txt
   ```

3. **Start Qdrant:**
   ```bash
   docker run --rm -d --name qdrant-test -p 6333:6333 qdrant/qdrant:latest
   ```

4. **Run automated tests:**
   ```bash
   # Manual validation checklist
   python3 sync-vector/tests/test_manual_checklist.py
   
   # Unit tests
   python3 -m pytest sync-vector/tests/test_unit.py -v
   
   # Integration tests (requires Docker)
   python3 -m pytest sync-vector/tests/test_integration.py -v
   ```

### Docker Deployment

1. **Start the complete stack:**
   ```bash
   docker-compose -f docker-compose.vector.yml up -d
   ```

2. **Check service health:**
   ```bash
   curl http://localhost:8090/health  # sync-vector service
   curl http://localhost:6333/health  # Qdrant
   ```

## Configuration

### Environment Variables

- `CONFIG_PATH`: Path to configuration file (default: `sync-vector/config/app.yaml`)
- `QDRANT_URL`: Qdrant instance URL
- `KAFKA_BROKERS`: Comma-separated list of Kafka brokers

### Configuration File

See `sync-vector/config/app.example.yaml` for the complete configuration schema.

Key sections:
- **kafka**: Broker settings, topic names, consumer group
- **qdrant**: Vector database connection and collection settings
- **ingest**: Retry logic and backoff configuration
- **observability**: Metrics port and logging level

## API Documentation

### Collection Schema

The service uses the `user_memories` collection with the following schema:

```json
{
  "name": "user_memories",
  "vectors": {
    "size": 1536,
    "distance": "Cosine"
  },
  "payload_schema": {
    "user_id": {"type": "integer"},
    "kind": {"type": "keyword"},
    "salience": {"type": "float"},
    "created_at": {"type": "integer"},
    "last_refreshed": {"type": "integer"},
    "emotion_code": {"type": "keyword"},
    "topic_ids": {"type": "keyword"},
    "source_session": {"type": "uuid"},
    "source_utterance": {"type": "uuid"}
  }
}
```

### Vector Operations

- **Upsert**: Insert or update memory vectors
- **Search**: Semantic similarity search with filters
- **Delete**: Remove vectors by ID or user_id
- **Batch Operations**: Efficient bulk processing

## Testing

### Manual Validation Checklist

The service includes an automated version of the manual testing checklist:

```bash
python3 sync-vector/tests/test_manual_checklist.py
```

This validates:
1. ✅ Local Qdrant bring-up
2. ✅ Schema application
3. ✅ Sample point insertion
4. ✅ Query verification
5. ✅ Delete operations
6. ✅ CDC replay dry run

### Test Suite

- **Unit Tests**: `sync-vector/tests/test_unit.py` - Component testing without external dependencies
- **Integration Tests**: `sync-vector/tests/test_integration.py` - Full pipeline testing with disposable Qdrant instances
- **Manual Checklist**: `sync-vector/tests/test_manual_checklist.py` - Automated validation of manual testing steps

## Monitoring & Observability

### Health Checks

- **Service Health**: `GET /health` - Returns service status
- **Qdrant Health**: `GET http://qdrant:6333/health` - Vector database status
- **Kafka Health**: Consumer lag and connection status

### Metrics

- **Processing Rate**: Messages processed per second
- **Queue Lag**: Kafka consumer lag
- **Error Rate**: Failed operations percentage
- **Latency**: P95 processing time

## Troubleshooting

### Common Issues

1. **Qdrant Connection Failed**
   - Check if Qdrant is running: `curl http://localhost:6333/health`
   - Verify network connectivity and firewall settings

2. **Kafka Consumer Lag**
   - Monitor consumer group status
   - Check for processing errors in logs
   - Scale consumer instances if needed

3. **Vector Dimension Mismatch**
   - Ensure all vectors are 1536-dimensional
   - Check embedding model consistency

### Logs

```bash
# Service logs
docker logs sync-vector

# Qdrant logs
docker logs qdrant

# Kafka logs
docker logs kafka
```

## Development

### Project Structure

```
sync-vector/
├── src/
│   └── main.py              # Main service implementation
├── tests/
│   ├── test_unit.py        # Unit tests
│   ├── test_integration.py # Integration tests
│   └── test_manual_checklist.py # Automated manual validation
├── config/
│   ├── app.example.yaml # Configuration template
│   └── qdrant/
│       └── collection_user_memories.json # Collection schema
├── docs/
│   ├── README.md           # This file
│   ├── api.md              # API documentation
│   ├── runbook.md          # Operational procedures
│   └── testing.md          # Manual testing checklist
├── requirements.txt        # Python dependencies
└── Dockerfile             # Container definition
```

### Adding New Features

1. **Update Configuration**: Modify `config/app.example.yaml`
2. **Add Tests**: Create test cases in `tests/`
3. **Update Documentation**: Keep `docs/` in sync
4. **Run Validation**: Execute all test suites

## Next Steps

- [ ] Implement Kafka consumer with proper error handling
- [ ] Add Prometheus metrics endpoint
- [ ] Create Kubernetes deployment manifests
- [ ] Set up CI/CD pipeline with automated testing
- [ ] Implement vector embedding generation pipeline
