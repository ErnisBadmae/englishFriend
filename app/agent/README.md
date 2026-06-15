# Agent Engine (graph_v2) — Local Architecture

## Summary
The single conversational engine: a 4-node LangGraph workflow
(`router → onboarding → learning → session_end`). LLM-driven inside nodes,
deterministic at the edges. There is no v1 graph and no parallel engine.

## Graph

```
START → router ─→ onboarding ─→ (wait | learning | session_end)
              ├─→ learning   ─→ (wait | session_end)
              └─→ session_end → END
```

- Entry/turn API: `graph_v2.initialize_session_v2`, `graph_v2.run_agent_turn_v2`.
- "wait" = route to END with `needs_user_input=True`; next user message re-enters via router.
- Graph-level errors emit a mission-safe recovery response and stamp
  `fallback_reason/fallback_stage` telemetry on state.

## Modules

| File | Role |
| --- | --- |
| `graph_v2.py` | graph wiring, session init, turn loop, fallback annotation |
| `nodes_v2/router.py` | control flow only: who handles this turn (no product decisions) |
| `nodes_v2/onboarding.py` | orchestration: node + action dispatch + prompt + mission handoff |
| `nodes_v2/onboarding_goal_brief.py` | goal-brief inference, scope gate, merge, routing arbiter calls |
| `nodes_v2/onboarding_assessment.py` | CEFR baseline subsystem (prompts, scoring, completion) |
| `nodes_v2/onboarding_text.py` | stateless text helpers (STT-noise normalization, signal matching) |
| `nodes_v2/onboarding_patterns.py` | pure data: pattern tables, baseline prompts, token sets |
| `nodes_v2/learning.py` | learning session turns; `MissionContract` slot flow for missions |
| `nodes_v2/session_end.py` | farewell, completion signals, XP |
| `state.py` | `AgentState` TypedDict — the honest schema (see guard below) |
| `intent_policy/` | per-turn intent classification — SHADOW telemetry only, never drives behavior |
| `guardrails.py`, `response_parser.py`, `recovery.py` | LLM output validation, parsing, safe fallbacks |

Layering inside onboarding is acyclic:
`patterns ← text ← assessment ← goal_brief ← onboarding(node)`.

## State Rules

- `AgentState` is `total=False`; **every key the agent writes must be declared**
  in `state.py`. Guard: `tests/test_agent_state_schema.py` scans for
  `state["..."] =` and fails on undeclared keys.
- Product truth (goal_brief, mission_*, evidence inputs) is server-owned;
  nodes mutate state, services decide products
  (`recommend_next_mission` in `program_snapshot_service` owns "next mission").
- LLM access only via `get_llm_provider()` (model-agnostic port).

## Extending

1. Put product logic in a service (or an `onboarding_*` leaf), not in the node body.
2. Declare any new state key in `state.py` (the guard will catch you).
3. New node: define `async def my_node(state) -> state` + `route_after_my_node`,
   wire in `graph_v2.create_agent_graph_v2`, export via `nodes_v2/__init__.py`.
4. Tests live flat in `tests/` (e.g. `tests/test_onboarding_node.py`). For
   end-to-end turn tests use the `deterministic_routing` fixture — the
   TurnAnalyzer and shadow classifier make live LLM calls and will flake
   assertions otherwise.

## Testing

```bash
pytest tests/test_onboarding_node.py tests/test_learning_node.py \
       tests/test_session_end_node.py tests/test_agent_state_schema.py -q
pytest tests/test_conversation_runtime.py -q   # runtime integration
```

## Related Documentation

- **Implements**: [!DOC/ARCHITECTURE.md](../../!DOC/ARCHITECTURE.md) — global map and invariants
- **Depends-On**: [app/services/conversation_runtime/README.md](../services/conversation_runtime/README.md) — the loop that drives turns
- **Related-To**: `app/services/routing/` and `app/services/missions/` package docstrings — authoritative routing and mission contracts

## Last Updated
2026-06-12: rewritten for graph_v2 reality (v1 graph removed; onboarding split
into focused modules; state guard added). Previous version described the
deleted 11-node v1 graph.
