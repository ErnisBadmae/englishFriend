# English Friend Documentation

**Last Updated**: 2026-05-25

This directory contains the product, architecture, operations, and implementation documentation for English Friend.

---

## Quick Start

- **Need one canonical view of the whole project?** Read [MASTER_PROJECT_VIEW_2026-04-22.md](./MASTER_PROJECT_VIEW_2026-04-22.md)
- **Need the current product status and the immediate next step?** Read [operations/CURRENT_PRODUCT_STATE.md](./operations/CURRENT_PRODUCT_STATE.md)
- **Need the active text-first workplan for Codex/Claude Code?** Read [strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md](./strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md)
- **Need the self-dogfood architecture for the founder job-search loop?** Read [architecture/SELF_DOGFOOD_TARGET_ARCHITECTURE_2026-05-25.md](./architecture/SELF_DOGFOOD_TARGET_ARCHITECTURE_2026-05-25.md)
- **Need the local 30-day execution plan?** Read [operations/SELF_DOGFOOD_30_DAY_PLAN_2026-05-25.md](./operations/SELF_DOGFOOD_30_DAY_PLAN_2026-05-25.md)
- **Need the current hot-path vs async truth-state?** Read [architecture/DATA_FLOW_TRUTH_STATE_2026-04-21.md](./architecture/DATA_FLOW_TRUTH_STATE_2026-04-21.md)
- **Need the target architecture and moat map?** Read [architecture/TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md](./architecture/TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md)
- **Need a Russian business/data-flow schematic?** Read [architecture/BUSINESS_AND_DATA_FLOW_RU_2026-04-21.md](./architecture/BUSINESS_AND_DATA_FLOW_RU_2026-04-21.md)
- **Need the active delivery roadmap?** Read [strategy/ROADMAP.md](./strategy/ROADMAP.md)
- **Need the long-form strategic vision?** Read [research/deep-research-report.md](./research/deep-research-report.md)
- **Need the system overview?** Read [SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md)
- **Need the database model?** Read [DB.md](./DB.md)
- **Need the root project bootstrap guide?** Read [../QUICK_START.md](../QUICK_START.md)

---

## Canonical Reading Order

1. [MASTER_PROJECT_VIEW_2026-04-22.md](./MASTER_PROJECT_VIEW_2026-04-22.md)
2. [operations/CURRENT_PRODUCT_STATE.md](./operations/CURRENT_PRODUCT_STATE.md)
3. Appendices as needed:
   - [architecture/DATA_FLOW_TRUTH_STATE_2026-04-21.md](./architecture/DATA_FLOW_TRUTH_STATE_2026-04-21.md)
   - [architecture/TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md](./architecture/TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md)
   - [architecture/BUSINESS_AND_DATA_FLOW_RU_2026-04-21.md](./architecture/BUSINESS_AND_DATA_FLOW_RU_2026-04-21.md)
   - [strategy/ROADMAP.md](./strategy/ROADMAP.md)

---

## Core Documents

| File | Purpose | When to Read |
| --- | --- | --- |
| [MASTER_PROJECT_VIEW_2026-04-22.md](./MASTER_PROJECT_VIEW_2026-04-22.md) | Canonical project view: product thesis, moat, architecture, execution rules, horizons | First read when you need the whole project |
| [operations/CURRENT_PRODUCT_STATE.md](./operations/CURRENT_PRODUCT_STATE.md) | Current wedge status, known issues, live blockers, next operational step | Resuming active work |
| [strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md](./strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md) | Active text-first moat plan, task queue, product gates, and voice deferral rules | Planning current work across Codex and Claude Code |
| [architecture/SELF_DOGFOOD_TARGET_ARCHITECTURE_2026-05-25.md](./architecture/SELF_DOGFOOD_TARGET_ARCHITECTURE_2026-05-25.md) | Clean architecture target for the founder's real job-search preparation loop | Designing domain boundaries and implementation slices |
| [operations/SELF_DOGFOOD_30_DAY_PLAN_2026-05-25.md](./operations/SELF_DOGFOOD_30_DAY_PLAN_2026-05-25.md) | Step-by-step local dogfood plan with verification gates | Executing daily job-search preparation work |
| [architecture/DATA_FLOW_TRUTH_STATE_2026-04-21.md](./architecture/DATA_FLOW_TRUTH_STATE_2026-04-21.md) | Current code truth-state for sync and async contours | Verifying what the code actually does |
| [architecture/TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md](./architecture/TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md) | Target architecture appendix: north star, moat map, stack direction | Deep architecture work |
| [architecture/BUSINESS_AND_DATA_FLOW_RU_2026-04-21.md](./architecture/BUSINESS_AND_DATA_FLOW_RU_2026-04-21.md) | Russian schematic of business logic and data movement | Product explanation in Russian |
| [strategy/ROADMAP.md](./strategy/ROADMAP.md) | Active 6-8 week execution roadmap | Planning current delivery |
| [research/deep-research-report.md](./research/deep-research-report.md) | Long-form strategic product and moat vision | Strategic decisions |
| [SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md) | High-level technical system overview | General system orientation |
| [DB.md](./DB.md) | Database schema, partitioning, CDC, storage responsibilities | DB and storage work |

---

## Supporting Documents

| File | Purpose |
| --- | --- |
| [STRATEGY.md](./STRATEGY.md) | Higher-level business strategy and market framing |
| [strategy/PRODUCT_WEDGE_PIVOT_2026-03-30.md](./strategy/PRODUCT_WEDGE_PIVOT_2026-03-30.md) | Current wedge pivot and rationale |
| [strategy/HYBRID_COACH_AGENT_STRATEGY_2026-04-02.md](./strategy/HYBRID_COACH_AGENT_STRATEGY_2026-04-02.md) | Why the product stays a vertical coach and not a generic agent shell |
| [JEPA_WORLDMODELS_VOICE_AI_ANALYSIS.md](./JEPA_WORLDMODELS_VOICE_AI_ANALYSIS.md) | Voice AI technology comparison |
| [LANGGRAPH_IMPLEMENTATION_SUMMARY.md](./LANGGRAPH_IMPLEMENTATION_SUMMARY.md) | Agent/runtime implementation notes |
| [CLAUDE_SESSION_LOG.md](./CLAUDE_SESSION_LOG.md) | Legacy historical continuity log |
| [TEMPLATE.md](./TEMPLATE.md) | Reusable documentation system template |
| [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) | How to reuse this doc system elsewhere |

---

## Architecture Summary

- **Canonical state for the product loop**: PostgreSQL
- **Fast hot path**: session bootstrap and current mission logic should rely on PostgreSQL first
- **Retrieval enrichment**: Qdrant is best-effort and should not be a hard dependency for session start
- **Async materialization**: Kafka, Debezium, and Neo4j support projections, sync, and longer-horizon intelligence
- **Product loop first**: career state -> mission -> session -> evidence -> next mission
- **Voice layer is replaceable**: browser Vosk, backend Parakeet, and future premium runtime can evolve without changing the core career-state engine

For the authoritative truth-state, see [architecture/DATA_FLOW_TRUTH_STATE_2026-04-21.md](./architecture/DATA_FLOW_TRUTH_STATE_2026-04-21.md).

---

## Development References

- **Coding standards**: `.kiro/steering/coding-standards.md` and `.claude/rules/coding-standards.md`
- **Architecture guidelines**: `.kiro/steering/architecture-guidelines.md`
- **Current state handoff**: [operations/CURRENT_PRODUCT_STATE.md](./operations/CURRENT_PRODUCT_STATE.md)

Common commands:

```bash
docker-compose up -d
docker-compose logs -f api
pytest tests/ -v
bash scripts/manage_partitions.sh
bash scripts/load_postgres_demo.sh
```

---

## Documentation Rules

- Update the master view when the product thesis, architecture direction, or strategic boundaries change
- Update current product state after meaningful implementation or live verification
- Keep appendices aligned with the master view rather than letting them drift into competing sources of truth
- Do not append working notes or long analysis dumps into this README; use dedicated strategy or architecture documents instead

---

**Documentation Version**: 1.0  
**Last Audit**: 2026-04-22  
**Next Review**: 2026-05-22
