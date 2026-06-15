# English Friend Documentation

Last updated: 2026-06-12

Token discipline: load by tier, never scan this directory wholesale.
`archive/` is history — never auto-load it.

## Tier 0 — every session (short, living)

| File | Purpose |
| --- | --- |
| [operations/CURRENT_PRODUCT_STATE.md](./operations/CURRENT_PRODUCT_STATE.md) | Now/next, known issues, last update. THE resume point |

## Tier 1 — when planning or designing (canonical, living)

| File | Purpose |
| --- | --- |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Global architecture: system map, layers, invariants |
| [strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md](./strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md) | Active workplan, product gates, anti-roadmap |
| [strategy/MOAT_AND_METRICS_DOCTRINE_2026-06-11.md](./strategy/MOAT_AND_METRICS_DOCTRINE_2026-06-11.md) | Moat thesis, invariants, L1/L2/L3 metrics |
| [architecture/SELF_DOGFOOD_TARGET_ARCHITECTURE_2026-05-25.md](./architecture/SELF_DOGFOOD_TARGET_ARCHITECTURE_2026-05-25.md) | Target domain core + verification gates |
| [operations/SELF_DOGFOOD_30_DAY_PLAN_2026-05-25.md](./operations/SELF_DOGFOOD_30_DAY_PLAN_2026-05-25.md) | Dogfood execution protocol |

## Tier 2 — on demand (task-specific)

| File | When |
| --- | --- |
| [strategy/ROADMAP.md](./strategy/ROADMAP.md) | Delivery planning |
| [architecture/DATA_FLOW_TRUTH_STATE_2026-04-21.md](./architecture/DATA_FLOW_TRUTH_STATE_2026-04-21.md) | Sync/async contours, CDC (verify against code — dated) |
| [operations/PRODUCT_SYNTHETIC_EVAL_RUNBOOK.md](./operations/PRODUCT_SYNTHETIC_EVAL_RUNBOOK.md) | Running product evals |
| [operations/STT_BENCHMARK_RUNBOOK.md](./operations/STT_BENCHMARK_RUNBOOK.md) | STT benchmark only |
| [operations/VOICE_OBSERVABILITY_RUNBOOK.md](./operations/VOICE_OBSERVABILITY_RUNBOOK.md) | Voice telemetry debugging |
| [operations/DISCOVERY_PHASE0_RUNBOOK.md](./operations/DISCOVERY_PHASE0_RUNBOOK.md) + templates | Discovery calls |
| [research/deep-research-report.md](./research/deep-research-report.md) | Long-form vision (strategic decisions only) |
| [GLOSSARY.md](./GLOSSARY.md) | Term definitions (also educational source) |

Local (per-subsystem) architecture docs live next to code:
`app/agent/README.md`, `app/services/conversation_runtime/README.md`,
`db/README.md`. See ARCHITECTURE.md → Local Architecture Docs.

## Rules

- One source of truth per concern; appendices must not compete with ARCHITECTURE.md.
- Living docs carry `Last updated` and a one-line reason.
- Superseded/historical material goes to `archive/` via `git mv` (history preserved), and inbound links are fixed in the same commit.
- Derived/educational docs are generated FROM Tier 1 + local READMEs; do not fork their content by hand.
