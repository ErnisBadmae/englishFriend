# EnglishFriend — Global Architecture

## Summary
Career-English coach for Russian-speaking ML/SWE engineers preparing for Western
interviews. Text-first guided coach loop on a single LangGraph workflow engine;
PostgreSQL is the only product truth; the LLM is a swappable commodity port.
This is the live global map; subsystem details live in local READMEs next to code.

## System Map (runtime path)

```
frontend (React, composer/typed input; voice opt-in)
   └─ WS /api/v1/voice/chat/v2          app/api/voice.py (transport endpoint)
        └─ ConversationController        app/services/conversation_runtime/
           (transport-neutral, text_only explicit; STT/TTS are opt-in adapters)
             └─ run_agent_turn_v2        app/agent/graph_v2.py  ← THE engine
                  router → onboarding → learning → session_end
                     │           │            │
                     │           │            └─ missions/contracts.py (MissionContract)
                     │           └─ onboarding_{patterns,text,assessment,goal_brief}.py
                     └─ control flow only (no product decisions)
             └─ Session{Bootstrap,Persistence}Service  app/services/voice_session/
Product brain (delivery-independent):
   services/routing/        goal/career routing (lexical + LLM classifier + arbiter)
   program_snapshot_service recommend_next_mission ← single owner of "next mission"
   learning_plan_service    persistence of plan/evidence (Postgres)
```

## Layers & Boundaries

| Layer | Owns | Must NOT own |
| --- | --- | --- |
| `app/api/` | transport, (de)serialization, client contract (e.g. `stt_provider→text_only`) | product decisions |
| `app/services/conversation_runtime/` | turn loop, transcript/feedback/completion events | mission selection, career state, evidence rules |
| `app/agent/` (graph_v2 + nodes_v2) | conversation phases, when to call which service | persistence details, transport |
| `app/services/` (routing, missions, snapshot, learning_plan) | product truth: goal brief, mission selection, evidence, progression | transport, prompt-UI concerns |
| DB (Postgres) | canonical state | — |
| Qdrant / Neo4j / Kafka-CDC | derived enrichment only | anything required to pick the next mission |

Three "routing" concerns are distinct by design (do not merge):
`nodes_v2/router.py` = graph control flow; `agent/intent_policy/` = per-turn
shadow telemetry (never drives behavior); `services/routing/` = authoritative
goal/career routing feeding `recommend_next_mission`.

## Invariants (violations = bugs)

1. One engine: `graph_v2` only. No parallel conversation brains.
2. PostgreSQL first: session bootstrap and next-mission need no derived store.
3. Text-first: text is the default modality; audio is an opt-in adapter
   (`text_only` flag set at the API boundary, never inferred in the runtime).
4. `AgentState` schema is honest: every written key is declared
   (guard: `tests/test_agent_state_schema.py`).
5. LLM is a port (`get_llm_provider`, OpenAI-compatible); nodes never bind to a
   specific model. Provenance (`model_id` + `prompt_version`) must be stamped
   on evidence/feedback (doctrine requirement, being rolled out).
6. `primary_context` and `goal_brief` are server-owned routing truth; frontend
   renders state, never invents it.

## Domain Core (target, per self-dogfood architecture)

`CareerProfile → VacancyContext → InterviewPack → MissionPlan → Evidence →
ProgressSnapshot` — typed objects, delivery- and model-independent. Today most
of this lives as dicts inside `program_snapshot_service` / `learning_plan_service`;
typing them by vertical slices is the active architecture work (see doctrine).

## Local Architecture Docs

- `app/agent/README.md` — engine, nodes, state, how to add behavior
- `app/services/conversation_runtime/README.md` — runtime loop and adapters
- `db/README.md` — schema, migrations
- gaps (write when next touched): services/routing, program_snapshot, frontend

## Related Documentation

- **Why / strategy**: [strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md](./strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md), [strategy/MOAT_AND_METRICS_DOCTRINE_2026-06-11.md](./strategy/MOAT_AND_METRICS_DOCTRINE_2026-06-11.md)
- **Target domain core**: [architecture/SELF_DOGFOOD_TARGET_ARCHITECTURE_2026-05-25.md](./architecture/SELF_DOGFOOD_TARGET_ARCHITECTURE_2026-05-25.md)
- **Sync/async data contours**: [architecture/DATA_FLOW_TRUTH_STATE_2026-04-21.md](./architecture/DATA_FLOW_TRUTH_STATE_2026-04-21.md)
- **Now / next**: [operations/CURRENT_PRODUCT_STATE.md](./operations/CURRENT_PRODUCT_STATE.md)

## Last Updated
2026-06-12: created as the live global map after the delivery-layer cleanup
(single engine, conversation_runtime rename, onboarding split, state guard).
