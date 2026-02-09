# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

English Friend is a multi-layered language learning system built on microservices architecture. The system uses different database types for specialized tasks:
- **PostgreSQL**: Primary relational database for users, sessions, utterances, memories
- **Kafka + Debezium**: CDC (Change Data Capture) layer for event streaming
- **Neo4j**: Graph database for relationships (user interests, topics, emotions)
- **Qdrant**: Vector database for semantic search on memories

The application is a FastAPI-based service with Python backend and SQLAlchemy ORM.

## Architecture

### Data Flow
```
User → PostgreSQL → Debezium → Kafka → [sync-vector → Qdrant]
                                      → [sync-graph → Neo4j]
```

### Key Components
1. **FastAPI Application** (`app/`): Main API service with routers for users, sessions, utterances, memories
2. **LangGraph Agent** (`app/agent/`): State machine for pedagogical conversations
3. **PersonaPlex Provider** (`app/services/ai/personaplex_provider.py`): Full-duplex speech-to-speech via NVIDIA Moshi 7B
4. **Database Migrations** (`db/migrations/postgres/`): Flyway-compatible SQL migrations
5. **CDC Layer** (`cdc/`): Debezium connectors and Kafka topic definitions
6. **Sync Services**:
   - `sync-vector/`: Syncs memories from Kafka to Qdrant
   - `sync-graph/`: Syncs sessions/utterances from Kafka to Neo4j
7. **Graph Layer** (`graph/`): Neo4j schema, queries, and Cypher scripts

### Database Features
- **Partitioning**: `sessions` (by month), `utterances` (by hash), `xp_events` (by date)
- **Row-Level Security (RLS)**: User data isolation at PostgreSQL level
- **Materialized Views**: For analytics queries

### LangGraph Agent Architecture (NEW)

The conversational AI is implemented as a LangGraph state machine with explicit phases and pedagogical logging.

**Conversation Flow**:
```
START → GOAL_DISCOVERY (with confirmation) → INTEREST_PROBE → ASSESSMENT
  → PROGRAM_BUILD → LEARNING_SESSION (turn_processor loop) → SESSION_END
```

**Key Nodes** (`app/agent/nodes/`):
- `start.py`: Routes new vs returning users
- `goal_discovery.py`: LLM-based goal extraction with user confirmation
- `interest_probe.py`: Discovers user interests for personalization
- `assessment.py`: 3-question CEFR level evaluation
- `program_build.py`: Generates personalized learning roadmap
- `mode_router.py`: Selects learning mode (mock_interview, vocab_drill, etc.)
- `turn_processor.py`: Handles conversation turns with Socratic recast
- `session_end.py`: Session termination and persistence

**API Endpoints**:
- `/api/v1/voice/chat`: Legacy endpoint (redirects to v2)
- `/api/v1/voice/chat/v2`: LangGraph-based endpoint (Vosk + Groq + edge-tts)
- `/api/v1/voice/chat/plex`: PersonaPlex full-duplex speech-to-speech (recommended)

**Logging**: All pedagogical decisions logged with `[PEDAGOGY]` prefix via `app/services/pedagogy_logger.py`

**State**: `AgentState` (TypedDict) flows through nodes, loaded from PostgreSQL at session start

### PersonaPlex Integration

Full-duplex speech-to-speech provider using NVIDIA Moshi 7B, self-hosted on Linux server (RTX 5060 Ti 16GB VRAM, INT8 quantization).

**Architecture**:
```
Student audio → EnglishFriend → PersonaPlex (ws://192.168.0.88:8998/api/chat)
Student audio ← EnglishFriend ← PersonaPlex
                     ↕
              LangGraph Agent (pedagogy, memories, vocabulary)
```

**Key Principle**: PersonaPlex = voice (blackbox), EnglishFriend = brain (we control)
- PersonaPlex follows our `system_prompt` for generation
- We build the prompt from user context (goals, memories, vocabulary, interests)
- We analyze transcripts for errors, vocabulary, progress
- We update the prompt dynamically when mode/phase changes

**Advantages over Vosk+Groq+edge-tts**:
- Latency: 200-400ms vs 800-1200ms (3-4x faster)
- Full-duplex: student can interrupt mentor
- Neural voice quality: 16 built-in personas
- Cost: $0 (self-hosted) vs ~$0.002/reply (Groq)

**Fallback**: If PersonaPlex is unavailable, `/chat/plex` automatically falls back to `/chat/v2`

**Configuration** (`.env`):
```bash
PERSONAPLEX_ENABLED=true
PERSONAPLEX_HOST=192.168.0.88
PERSONAPLEX_PORT=8998
PERSONAPLEX_DEFAULT_VOICE=NATM0
PERSONAPLEX_QUANTIZATION=int8
```

**Key Files**:
- `app/services/ai/personaplex_provider.py`: WebSocket client (`PersonaPlexProvider`)
- `app/services/ai/personaplex_health.py`: Health check with TTL cache
- `app/core/config.py`: PersonaPlex settings block
- `app/api/voice.py`: `/chat/plex` endpoint + `_build_personaplex_system_prompt()`
- `docker-compose.personaplex.yml`: Docker Compose for Linux GPU server

## Development Commands

### Environment Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Start PostgreSQL only
docker compose up -d postgres

# Start full CDC stack (Postgres + Kafka + Debezium + Neo4j + Qdrant)
docker compose -f docker-compose.cdc.yml up -d
```

### Running the Application
```bash
# Start FastAPI application
python main.py

# Or using Makefile
make start

# Application runs on http://localhost:8000
# API docs: http://localhost:8000/docs
```

### PersonaPlex Setup (Linux GPU Server)
```bash
# Deploy PersonaPlex on Linux server (RTX 5060 Ti)
scp docker-compose.personaplex.yml nero@192.168.0.88:~/personaplex/
ssh nero@192.168.0.88 "cd ~/personaplex && docker compose up -d"

# Verify health
curl http://192.168.0.88:8998/health

# Enable in .env on Windows laptop
PERSONAPLEX_ENABLED=true
PERSONAPLEX_HOST=192.168.0.88
```

### Database Management
```bash
# Run migrations manually (in order)
psql $DATABASE_URL -f db/migrations/postgres/000_init.sql
psql $DATABASE_URL -f db/migrations/postgres/001_reference_tables.sql
psql $DATABASE_URL -f db/migrations/postgres/002_users.sql
# ... etc

# Load reference data (emotions, topics, accents)
psql $DATABASE_URL -f db/seed/001_reference_seed.sql

# Test database connection
make test-db
```

### Testing
```bash
# Run all tests
pytest

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# PostgreSQL tests (using pgTAP)
docker compose exec postgres psql -U postgres -d englishfriend_dev -f db/tests/010_users_channel_identity.sql

# Neo4j graph tests
docker compose exec neo4j cypher-shell -u neo4j -p password -f graph/tests/schema_checks.cypher

# Sync-vector tests
pytest sync-vector/tests/test_unit.py -v
pytest sync-vector/tests/test_integration.py -v

# Sync-graph tests
pytest sync-graph/tests/test_transform.py

# LangGraph Agent tests
pytest tests/agent/ -v

# PersonaPlex tests
pytest tests/test_personaplex.py -v
```

### Code Quality
```bash
# Lint code
make lint
# Or: flake8 app/ tests/ && mypy app/

# Format code
make format
# Or: black app/ tests/ && isort app/ tests/
```

### Partition Management
```bash
# Manage partitions (create future, drop old)
./scripts/manage_partitions.sh

# See db/PARTITION_MANAGEMENT.md for details
```

### CDC & Sync Operations
```bash
# Register Debezium connectors
./scripts/register_connector.sh cdc/connectors/memories_connector.json
./scripts/register_connector.sh cdc/connectors/graph_connector.json

# Generate test data for CDC
python scripts/cdc_batch_sessions.py --events 100

# Trigger manual memory insert for testing
./scripts/cdc_insert_memory.sh

# Retry failed messages from DLQ
./scripts/cdc_dlq_retry.sh vector_failures
./scripts/cdc_dlq_retry.sh graph_failures
```

### Demo Data Loading
```bash
# Load all demo data
docker compose -f docker-compose.cdc.yml up load-postgres-demo load-neo4j-demo load-qdrant-demo
```

## Project Structure

```
englishFriend/
├── app/
│   ├── agent/            # LangGraph state machine (NEW)
│   │   ├── nodes/        # Conversation flow nodes
│   │   ├── state.py      # AgentState TypedDict
│   │   └── graph.py      # State machine assembly
│   ├── api/              # FastAPI routers (users, sessions, utterances, etc.)
│   ├── core/             # Config and database initialization
│   ├── models/           # SQLAlchemy ORM models
│   ├── schemas/          # Pydantic schemas
│   └── services/         # Business logic (including pedagogy_logger.py)
│       └── ai/           # AI providers (LLM, TTS, PersonaPlex)
├── db/
│   ├── migrations/postgres/  # SQL migrations (ordered 000-007)
│   ├── seed/                 # Reference data seeds
│   └── tests/                # pgTAP test suites
├── cdc/
│   └── connectors/       # Debezium connector JSON configs
├── sync-vector/          # Kafka → Qdrant sync service
│   ├── src/main.py
│   ├── config/
│   └── tests/
├── sync-graph/           # Kafka → Neo4j sync service
│   ├── sync_graph/
│   ├── config/
│   └── tests/
├── graph/
│   ├── schema/           # Neo4j constraints and indexes
│   ├── queries/          # Saved Cypher queries
│   └── tests/            # Cypher validation scripts
├── scripts/              # Utility scripts for CDC, partitions, demo data
└── tests/                # Main application tests
```

## Key Files

- `main.py`: FastAPI application entry point
- `app/core/database.py`: Database connection and initialization
- `app/core/config.py`: Settings (including PersonaPlex config)
- `app/core/metrics.py`: Prometheus metrics (voice, agent, PersonaPlex)
- `app/models/core_tables.py`: Core SQLAlchemy models (users, sessions, utterances)
- `app/models/extended_tables.py`: Extended models (memories, learning_plan, xp_events)
- `app/api/voice.py`: WebSocket endpoints (`/chat`, `/chat/v2`, `/chat/plex`)
- `app/services/ai/personaplex_provider.py`: PersonaPlex WebSocket client
- `app/services/ai/personaplex_health.py`: PersonaPlex health check with cache
- `app/services/ai/base.py`: AIProvider base class (with `update_persona()`)
- `app/services/data_flow_logger.py`: Data flow logger (includes PersonaPlex events)
- `Makefile`: Development shortcuts
- `pyproject.toml`: Black, isort, mypy configuration
- `pytest.ini`: Pytest configuration

## Database Models

### Core Tables (in `app/models/core_tables.py`)
- `User`: User profiles with channel_id/identity
- `Session`: Learning sessions (partitioned by month)
- `Utterance`: User/AI messages in sessions (partitioned by hash)
- `Correction`: Feedback on pronunciation/grammar

### Extended Tables (in `app/models/extended_tables.py`)
- `Memory`: User memories for semantic search
- `UserInterest`: Topic interests with salience scores
- `LearningPlan`: Personalized learning goals
- `XPEvent`: Experience points tracking (partitioned by date)
- `EmotionalLog`: Emotional state tracking

### Dimension Tables (in `app/models/enums_and_dimensions.py`)
- `DimEmotion`: Emotion reference (happy, sad, frustrated, etc.)
- `DimTopic`: Topic reference (technology, sports, movies, etc.)
- `DimAccent`: Accent reference (american, british, australian, etc.)

## Docker Compose Configurations

- `docker-compose.yml`: PostgreSQL only
- `docker-compose.cdc.yml`: Full CDC stack (Postgres + Kafka + Debezium + Neo4j + Qdrant + sync services)
- `docker-compose.vector.yml`: Vector stack (Postgres + Kafka + Qdrant + sync-vector)
- `docker-compose.graph.yml`: Graph stack (Postgres + Kafka + Neo4j + sync-graph)
- `docker-compose.partitions.yml`: Partition management cron job
- `docker-compose.personaplex.yml`: PersonaPlex on Linux GPU server (NVIDIA Moshi 7B, INT8)

## Important Patterns

### Migration Ordering
Migrations in `db/migrations/postgres/` must be run in order:
1. `000_init.sql` / `000_wal_level.sql`: Initialize and set WAL level
2. `001_reference_tables.sql`: Dimension tables
3. `002_users.sql`: User management with RLS
4. `003_sessions_utterances.sql`: Sessions and utterances with partitions
5. `004_partition_management.sql`: Partition helper functions
6. `005_memories_learning_plan.sql`: Memory and learning features
7. `006_materialized_views.sql`: Analytics views
8. `007_publications.sql`: CDC publications for Debezium

### Partitioning Strategy
- Sessions: Monthly partitions (e.g., `sessions_2025_10`)
- Utterances: Hash partitions (e.g., `utterances_p0` to `utterances_p7`)
- XP Events: Monthly partitions (e.g., `xp_events_2025_10`)

Use `scripts/manage_partitions.sh` to maintain partitions automatically.

### CDC Topics
- `memories.public.memories` → sync-vector → Qdrant
- `graph.public.sessions` → sync-graph → Neo4j
- `graph.public.utterances` → sync-graph → Neo4j
- `graph.public.corrections` → sync-graph → Neo4j
- `graph.public.user_interest` → sync-graph → Neo4j

### Neo4j Graph Schema
Nodes: `User`, `Session`, `Topic`, `Emotion`, `Utterance`
Relationships: `PARTICIPATED_IN`, `INTEREST_IN`, `EXPRESSES`, `RELATED_TO`

## Testing Strategy

1. **Unit Tests**: Fast, no external dependencies
2. **Integration Tests**: Require Docker containers (Postgres, Qdrant, Neo4j)
3. **Database Tests**: pgTAP for PostgreSQL, Cypher for Neo4j
4. **CDC Tests**: Generate events with `cdc_batch_sessions.py`, verify sync

## Observability & Logging

### Log Levels Strategy

| Level | Что логируем | Пример |
|-------|-------------|--------|
| DEBUG | Детали для отладки | State dumps, raw responses |
| INFO | Бизнес-события | router → onboarding, LLM=1123ms |
| WARNING | Recoverable issues | Parse failed, using fallback |
| ERROR | Критические ошибки | WebSocketDisconnect |

### Log Format

Логи форматируются с Request ID для корреляции:

```
HH:MM:SS [request_id] LEVEL [logger] message
22:16:31 [a1b2c3d4] INFO  [app.agent] router → onboarding (new_user)
22:16:32 [a1b2c3d4] INFO  [app.agent] onboarding LLM=1123ms action=ask_goal
```

### Где смотреть логи

**Console (development):**
```bash
python main.py
# Логи идут в stdout с Request ID
```

**Langfuse (LLM tracing):**
1. Настроить в `.env`:
   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-xxx
   LANGFUSE_SECRET_KEY=sk-lf-xxx
   LANGFUSE_HOST=https://cloud.langfuse.com
   ```
2. Открыть https://cloud.langfuse.com
3. Видны traces: prompts, responses, tokens, latency

### Silenced Loggers

Следующие loggers установлены на WARNING для снижения шума:
- `sqlalchemy.engine` - SQL queries (echo=False в database.py)
- `httpx`, `httpcore` - HTTP client internals
- `websockets`, `asyncio` - WebSocket/async internals
- `langgraph`, `langchain`, `langchain_core` - LangGraph/LangChain internals
- `groq`, `openai` - LLM provider logs
- `langfuse` - Observability client logs
- `urllib3` - HTTP connection logs

### Как включить verbose логи

```bash
# В .env:
DEBUG=true  # Включает DEBUG level для app.agent

# Или в коде:
import logging
logging.getLogger("app.agent").setLevel(logging.DEBUG)
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)  # SQL queries
```

### Request ID

Каждый HTTP запрос получает уникальный ID (8 символов):
- Виден в логах: `[a1b2c3d4]`
- Виден в response headers: `X-Request-ID: a1b2c3d4`
- Используется для корреляции в Langfuse

### Prometheus Metrics

Доступны на `/metrics`:
- `voice_sessions_active` - Активные WebSocket сессии
- `voice_llm_latency_seconds` - Latency LLM запросов
- `voice_tts_latency_seconds` - Latency TTS синтеза
- `voice_errors_total` - Счётчик ошибок по stage
- `personaplex_connections_active` - Активные PersonaPlex соединения
- `personaplex_latency_seconds` - Latency PersonaPlex по операциям (connect, audio_in, audio_out)
- `personaplex_sessions_total` - Счётчик PersonaPlex сессий по статусу
- `personaplex_turns_total` - Счётчик conversation turns по mode/phase
- `personaplex_pedagogical_events` - Педагогические события (error_detected, vocabulary_used, memory_extracted)
- `personaplex_errors_total` - Ошибки PersonaPlex по типу
- `personaplex_fallback_total` - Количество fallback на legacy стек

## Health Check Endpoints

- FastAPI: `http://localhost:8000/health`
- sync-vector: `http://localhost:8090/health`
- sync-graph: `http://localhost:8091/health`
- Qdrant: `http://localhost:6333/health`
- Neo4j: `http://localhost:7474`
- PersonaPlex: `http://192.168.0.88:8998/health` (Linux GPU server)

## Running Single Tests

To run a specific test file:
```bash
pytest tests/test_specific_file.py -v

# With specific marker
pytest -m unit tests/test_specific_file.py

# Specific test function
pytest tests/test_specific_file.py::test_function_name
```

For sync services, use their own test directories:
```bash
pytest sync-vector/tests/test_unit.py::test_specific
pytest sync-graph/tests/test_transform.py::TestEventMapping
```

## Common Issues

1. **Partition Management**: Partitions must be created before inserting data. Use `scripts/manage_partitions.sh` or the partition functions in migration `004`.

2. **CDC Lag**: Monitor Kafka consumer lag if sync services fall behind. Check DLQ topics for failed messages.

3. **RLS Policies**: When testing, set `application.user_id` session variable or queries will return empty results due to RLS.

4. **Connection Strings**: Default database is `englishfriend_dev` in Docker, `english_friend` in some configs. Check your environment.

## Documentation References

- **Session Progress Log**: `!DOC/CLAUDE_SESSION_LOG.md` ← **READ THIS FIRST** for context between sessions
- System Overview: `SYSTEM_OVERVIEW.md`
- Database: `db/README.md`, `db/PARTITION_MANAGEMENT.md`, `db/CI_INTEGRATION.md`
- CDC: `cdc/README.md`
- Graph Layer: `graph/README.md`, `graph/docs/RUNBOOK.md`
- Sync Vector: `sync-vector/README.md`, `sync-vector/docs/`
- Sync Graph: `sync-graph/README.md`, `sync-graph/docs/`

## Session Continuity

При начале новой сессии:
1. Читай `!DOC/CLAUDE_SESSION_LOG.md` для контекста
2. В конце сессии обновляй этот файл с прогрессом

Формат записи:
```markdown
### YYYY-MM-DD - Краткое описание
**Агент**: Claude Model
**Задача**: Что делали
**Что сделано**: Список изменений
**Результат**: Итог
```
