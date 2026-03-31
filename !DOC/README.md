# English Friend Documentation

**Last Updated**: 2026-03-30

Welcome to the English Friend documentation. This guide will help you navigate the project documentation efficiently.

---

## Quick Start

- **New to the project?** Start with [QUICK_START.md](../QUICK_START.md) in the root directory
- **Need to understand the system?** Read [SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md)
- **Working on database?** Check [DB.md](./DB.md)
- **Session history?** See [CLAUDE_SESSION_LOG.md](./CLAUDE_SESSION_LOG.md)

---

## Documentation Structure

### Core Documentation

| File | Purpose | When to Read |
|------|---------|--------------|
| [SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md) | High-level architecture, data flow, deployment | Understanding system design |
| [DB.md](./DB.md) | Database schema, partitioning, CDC, RLS | Working with database |
| [STRATEGY.md](./STRATEGY.md) | Business strategy, market analysis, roadmap | Strategic planning |
| [strategy/PRODUCT_WEDGE_PIVOT_2026-03-30.md](./strategy/PRODUCT_WEDGE_PIVOT_2026-03-30.md) | Current strategic pivot, research summary, rationale, next execution step | Product direction and prioritization |
| [TEMPLATE.md](./TEMPLATE.md) | Documentation system template for other projects | Reusing doc system |
| [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) | How to deploy doc system to other projects | Setting up docs elsewhere |

### Implementation Guides

| File | Purpose | When to Read |
|------|---------|--------------|
| [LANGGRAPH_IMPLEMENTATION_SUMMARY.md](./LANGGRAPH_IMPLEMENTATION_SUMMARY.md) | LangGraph agent implementation | Working on agent system |
| [db-steps.md](./db-steps.md) | Database implementation roadmap | Database sprint planning |

### Research & Analysis

| File | Purpose | When to Read |
|------|---------|--------------|
| [JEPA_WORLDMODELS_VOICE_AI_ANALYSIS.md](./JEPA_WORLDMODELS_VOICE_AI_ANALYSIS.md) | Voice AI technology comparison | Evaluating voice tech stack |

### Session History

| File | Purpose | When to Read |
|------|---------|--------------|
| [CLAUDE_SESSION_LOG.md](./CLAUDE_SESSION_LOG.md) | AI agent session continuity log | Understanding recent changes |

---

## Coding Standards & Architecture

**For both Kiro and Claude Code agents:**

- **Coding Standards**: See `.kiro/steering/coding-standards.md` and `.claude/rules/coding-standards.md`
- **Architecture Guidelines**: See `.kiro/steering/architecture-guidelines.md`

These files are automatically loaded by AI agents and contain:
- Python code style (Black, isort, type hints)
- Async/await patterns
- Service layer patterns
- Database access patterns
- External service integration (Groq, edge-tts, FSRS)
- Error handling
- Testing guidelines
- API design

---

## Key Concepts

### Architecture

- **CDC-Based**: PostgreSQL → Debezium → Kafka → Sync Services (Neo4j, Qdrant)
- **Event-Driven**: All writes to PostgreSQL trigger CDC events
- **Microservices**: API server, sync-vector, sync-graph services
- **Async-First**: FastAPI, asyncpg, httpx for non-blocking I/O

### Voice Learning System

- **STT**: Vosk (browser-based, privacy-preserving)
- **LLM**: Groq llama-3.3-70b (fast, cost-effective)
- **TTS**: edge-tts (free, high quality)
- **Vocabulary**: FSRS spaced repetition system

### Learning Modes

- **ASSESSMENT**: Evaluate English level
- **MOCK_INTERVIEW**: Job interview simulation
- **VOCABULARY_DRILL**: Spaced repetition practice
- **FREE_CONVERSATION**: Open-ended chat with corrections

### Gamification

- **XP System**: Base rewards + streak bonuses
- **Streaks**: Daily check-in tracking
- **Achievements**: First session, comeback bonuses

---

## Database

### Tables

- **Core**: User, Session, Utterance
- **Extended**: Memory, LearningPlan, XPEvent, VocabularyCard
- **Dimensions**: DimEmotion, DimTopic, DimAccent, DimGoal

### Partitioning

- **Sessions**: Monthly partitions (`sessions_2025_01`, `sessions_2025_02`)
- **Utterances**: 8 hash partitions (`utterances_p0` to `utterances_p7`)
- **XP Events**: Monthly partitions (`xp_events_2025_01`)

### CDC Topics

- `memories.public.memories` → Qdrant (vector embeddings)
- `graph.public.sessions` → Neo4j (session nodes)
- `graph.public.utterances` → Neo4j (conversation edges)
- `graph.public.user_interest` → Neo4j (interest relationships)

---

## Helper Modules

To reduce code duplication, use these helper modules:

- **response_mappers.py**: API response mapping (eliminates 30% duplication)
- **query_helpers.py**: Common database queries (`get_by_id`, `get_top_by_field`)
- **logger_helpers.py**: Consistent logging (`format_user_info`, `format_data_preview`)
- **voice_helpers.py**: Voice chat logic (`handle_goal_setting`, `award_session_gamification`)

---

## Testing

- **Unit Tests**: `pytest tests/` with async support
- **Integration Tests**: `scripts/test_*.py`
- **E2E Tests**: `scripts/test_agent_e2e.py`
- **Coverage Target**: 70% minimum for business logic

---

## Monitoring

- **Prometheus**: Metrics collection
- **Grafana**: Dashboards (CDC pipeline, voice backend, English Friend)
- **Logs**: Structured logging with data flow tracking

See `monitoring/README.md` for details.

---

## Development Workflow

1. **Start services**: `docker-compose up -d`
2. **Run migrations**: Auto-applied on first postgres start
3. **Seed data**: `python scripts/seed_database.py`
4. **Run tests**: `pytest tests/`
5. **Start API**: `uvicorn main:app --reload`

---

## Common Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Run tests
pytest tests/ -v

# Manage partitions
bash scripts/manage_partitions.sh

# Load demo data
bash scripts/load_postgres_demo.sh
```

---

## Architecture Decisions

For rationale behind technology choices (Groq vs OpenAI, edge-tts vs paid TTS, Vosk vs server STT, etc.), see:

- `.kiro/steering/architecture-guidelines.md` (Architecture Decision Rationale section)
- [JEPA_WORLDMODELS_VOICE_AI_ANALYSIS.md](./JEPA_WORLDMODELS_VOICE_AI_ANALYSIS.md) (Voice AI comparison)
- [STRATEGY.md](./STRATEGY.md) (Technical stack section)

---

## Contributing

When adding new features:

1. Follow coding standards in `.kiro/steering/coding-standards.md`
2. Update relevant documentation
3. Add tests (70% coverage minimum)
4. Update [CLAUDE_SESSION_LOG.md](./CLAUDE_SESSION_LOG.md) with changes
5. Run `pytest tests/` before committing

---

## Documentation Maintenance

- **Update frequency**: After each significant feature or architectural change
- **Session log**: Update after each AI agent session
- **Quarterly review**: Review and archive old content

---

## Need Help?

- **System architecture**: [SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md)
- **Database design**: [DB.md](./DB.md)
- **Recent changes**: [CLAUDE_SESSION_LOG.md](./CLAUDE_SESSION_LOG.md)
- **Business strategy**: [STRATEGY.md](./STRATEGY.md)
- **Voice AI tech**: [JEPA_WORLDMODELS_VOICE_AI_ANALYSIS.md](./JEPA_WORLDMODELS_VOICE_AI_ANALYSIS.md)

---

**Documentation Version**: 1.0  
**Last Audit**: 2026-01-26  
**Next Review**: 2026-04-26
