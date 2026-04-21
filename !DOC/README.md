# English Friend Documentation

**Last Updated**: 2026-04-21

Welcome to the English Friend documentation. This guide will help you navigate the project documentation efficiently.

---

## Quick Start

- **New to the project?** Start with [QUICK_START.md](../QUICK_START.md) in the root directory
- **Need the current product status and next step?** Read [operations/CURRENT_PRODUCT_STATE.md](./operations/CURRENT_PRODUCT_STATE.md)
- **Need the current hot-path vs async truth-state?** Read [architecture/DATA_FLOW_TRUTH_STATE_2026-04-21.md](./architecture/DATA_FLOW_TRUTH_STATE_2026-04-21.md)
- **Need the target architecture and moat map?** Read [architecture/TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md](./architecture/TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md)
- **Need a Russian business/data-flow schematic?** Read [architecture/BUSINESS_AND_DATA_FLOW_RU_2026-04-21.md](./architecture/BUSINESS_AND_DATA_FLOW_RU_2026-04-21.md)
- **Need the active execution roadmap?** Read [strategy/ROADMAP.md](./strategy/ROADMAP.md)
- **Need the current long-form product and architecture vision?** Read [research/deep-research-report.md](./research/deep-research-report.md)
- **Need the moat, anti-roadmap, and strategic boundaries?** Read [research/deep-research-report.md](./research/deep-research-report.md)
- **Need to understand the system?** Read [SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md)
- **Working on database?** Check [DB.md](./DB.md)
- **Legacy session history?** See [CLAUDE_SESSION_LOG.md](./CLAUDE_SESSION_LOG.md)

---

## Documentation Structure

### Core Documentation

| File | Purpose | When to Read |
|------|---------|--------------|
| [SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md) | High-level architecture, data flow, deployment | Understanding system design |
| [DB.md](./DB.md) | Database schema, partitioning, CDC, RLS | Working with database |
| [STRATEGY.md](./STRATEGY.md) | Business strategy, market analysis, roadmap | Strategic planning |
| [architecture/DATA_FLOW_TRUTH_STATE_2026-04-21.md](./architecture/DATA_FLOW_TRUTH_STATE_2026-04-21.md) | Current code truth-state: hot path, async contour, and storage roles | Aligning docs to the real implementation |
| [architecture/TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md](./architecture/TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md) | Target product architecture, moat logic, and the Parakeet vs PersonaPlex decision | Aligning on north star and system shape |
| [architecture/BUSINESS_AND_DATA_FLOW_RU_2026-04-21.md](./architecture/BUSINESS_AND_DATA_FLOW_RU_2026-04-21.md) | Russian visual explanation of user problem, product business logic, data flow, and moat | Aligning the team on the product loop in Russian |
| [strategy/ROADMAP.md](./strategy/ROADMAP.md) | Active 6-8 week delivery roadmap for demo readiness, STT, evidence loop, and wedge completion | Planning the current execution cycle |
| [strategy/PRODUCT_WEDGE_PIVOT_2026-03-30.md](./strategy/PRODUCT_WEDGE_PIVOT_2026-03-30.md) | Current strategic pivot, research summary, rationale, next execution step | Product direction and prioritization |
| [strategy/HYBRID_COACH_AGENT_STRATEGY_2026-04-02.md](./strategy/HYBRID_COACH_AGENT_STRATEGY_2026-04-02.md) | Why EnglishFriend should stay a vertical coach while adopting internal agent patterns | Current product/architecture strategy |
| [research/deep-research-report.md](./research/deep-research-report.md) | Canonical long-form product and architecture vision, including moat and anti-roadmap | Current north star, moat, and architectural direction |
| [operations/CURRENT_PRODUCT_STATE.md](./operations/CURRENT_PRODUCT_STATE.md) | Active source of truth for current wedge, current flow, known issues, and next step | Resuming active product work |
| [CLAUDE_SESSION_LOG.md](./CLAUDE_SESSION_LOG.md) | Legacy detailed session history | Historical continuity only |
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
| [operations/CURRENT_PRODUCT_STATE.md](./operations/CURRENT_PRODUCT_STATE.md) | Short current-state report for Codex and Claude Code | Every active work session |
| [CLAUDE_SESSION_LOG.md](./CLAUDE_SESSION_LOG.md) | Legacy AI agent session continuity log | Only if older history is needed |

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
- **Async Replication Layer**: CDC and sync services support enrichment and projections rather than canonical bootstrap
- **Microservices**: API server, sync-vector, sync-graph services
- **Async-First**: FastAPI, asyncpg, httpx for non-blocking I/O
- **Product Loop First**: career state -> mission -> session -> evidence -> next mission
- **Replaceable Voice Layer**: browser Vosk and backend Parakeet can change without changing the career-state engine

Important:
- for the current code truth-state, treat PostgreSQL as the canonical hot path
- treat Qdrant as best-effort retrieval enrichment
- treat Neo4j, Kafka, and Debezium as async/materialization infrastructure rather than bootstrap dependencies
- see [architecture/DATA_FLOW_TRUTH_STATE_2026-04-21.md](./architecture/DATA_FLOW_TRUTH_STATE_2026-04-21.md)

### Voice Learning System

- **STT**: browser Vosk today, backend Parakeet lane now available for benchmark and rollout
- **LLM**: Groq llama-3.3-70b (fast, cost-effective)
- **TTS**: edge-tts (free, high quality)
- **Vocabulary**: FSRS spaced repetition system
- **Premium Runtime**: PersonaPlex remains an optional advanced voice lane, not the core moat

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

### CDC / Materialization Topics

These are infrastructure topics and projections, not the session bootstrap source of truth.

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
4. Update [operations/CURRENT_PRODUCT_STATE.md](./operations/CURRENT_PRODUCT_STATE.md) with short current-state changes
5. Run `pytest tests/` before committing

---

## Documentation Maintenance

- **Update frequency**: After each significant feature or architectural change
- **Current product state**: Update after each significant AI agent session
- **Legacy session log**: Do not extend unless older historical continuity truly needs it
- **Quarterly review**: Review and archive old content

---

## Need Help?

- **System architecture**: [SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md)
- **Database design**: [DB.md](./DB.md)
- **Recent changes**: [operations/CURRENT_PRODUCT_STATE.md](./operations/CURRENT_PRODUCT_STATE.md)
- **Target architecture**: [architecture/TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md](./architecture/TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md)
- **Active roadmap**: [strategy/ROADMAP.md](./strategy/ROADMAP.md)
- **Business strategy**: [STRATEGY.md](./STRATEGY.md)
- **Voice AI tech**: [JEPA_WORLDMODELS_VOICE_AI_ANALYSIS.md](./JEPA_WORLDMODELS_VOICE_AI_ANALYSIS.md)

---

**Documentation Version**: 1.0  
**Last Audit**: 2026-04-21  
**Next Review**: 2026-05-21
