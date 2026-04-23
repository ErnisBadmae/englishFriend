# Current Product State

Last updated: 2026-04-22
Status: Active source of truth for product progress and agent continuity

Canonical long-form vision and architecture:
[../research/deep-research-report.md](../research/deep-research-report.md)

Canonical master project view:
[../MASTER_PROJECT_VIEW_2026-04-22.md](../MASTER_PROJECT_VIEW_2026-04-22.md)

## Reporting Rule
This file is the single place for short progress reports from Codex and Claude Code.

Update only these sections:
- `Current Wedge`
- `Golden Path`
- `What Works Now`
- `Known Issues`
- `Next Step`
- `Last Update`

Keep updates short:
- 3-7 bullets max
- no long narratives
- no duplicate history
- only current state, blockers, and next move

Do not create a new session log if this file is enough.

## Current Wedge
- Product: career English coach, not generic AI tutor
- Strategic frame: hybrid coach + agent internally, but still a vertical coach product externally
- Primary audience: Russian-speaking ML/AI and adjacent IT specialists
- Core outcome: prepare for international jobs, interviews, project walkthroughs, and workplace communication
- Main UX principle: one guided path, not a toolbox of disconnected modes
- Moat candidate: goal-relative career state + pedagogy for weak spoken English + evidence-driven next-mission adaptation

## Golden Path
1. Noisy user intent comes in through text or voice.
2. System builds and confirms a target career direction.
3. System starts with the first useful mission and can infer the first working baseline from that real answer.
4. User adds high-signal artifacts such as vacancy context and project notes.
5. Home shows target, stage, mission, and supporting artifacts.
6. Guided session runs through the bounded coach flow.
7. Session produces structured evidence, not only transcript history.
8. Next mission adapts from repeated weakness, improvement, and career context.

## What Works Now
- `ProgramSnapshot` now aggregates target state, baseline, mission, interview artifacts, project story artifacts, and evidence in one product-facing response.
- Shared `voice_session` lifecycle powers `/chat/v2` and `/realtime`, and the frontend passes explicit mission metadata into backend session init.
- Session bootstrap is now explicitly documented as PostgreSQL-canonical, with Qdrant used only as best-effort retrieval enrichment and Neo4j kept outside the bootstrap path.
- Session end now persists richer `session_evidence`, including `outcome_score`, `weakness_tags`, `improvement_tags`, `adaptation_hint`, and mission-linked context.
- `recommend_next_mission()` now supports `repeat` vs `advance` logic and exposes `adaptation_reason`, `evidence_source`, and `repeat_vs_advance` to the frontend.
- The wedge now includes vacancy upload, interview pack generation, paid-intent capture, project notes, and `project_story_pack`.
- Post-session hardening is in place: XP writes ensure the monthly `xp_events` partition before insert, memory extraction retries once before soft-failing, and vector sync is scheduled out-of-band after PostgreSQL commit instead of blocking request-time persistence.
- Backend STT now has a real upgrade lane through `ParakeetSTTProvider` and `POST /api/v1/voice/transcribe`, while browser Vosk remains the current fallback/default path.
- Live synthetic product eval now exists through `scripts/run_product_synthetic_eval.py`: the service can be measured on `first useful mission -> embedded baseline -> evidence -> ready snapshot` without waiting for full browser voice polish.
- Live synthetic eval now has `mainline` and `expanded` scenario sets, so the product can be measured both on canonical flows and on more varied user shapes.
- Canonical routing policy (`app/services/routing/goal_routing.py`) is the single source of truth for `primary_context`, `recommended_track_id`, and `first_mission_task_type`; onboarding, snapshot, and mission selection all read from the same profile.
- Runtime recovery is mission-safe: `app/agent/recovery.py` returns a drill-pinned next-utterance instead of the legacy `I'm having trouble` generic fallback; synthetic eval now enforces that via `no_generic_fallback_leak`.
- Synthetic eval now separates routing vs runtime checks, and mainline is a blocking release gate while expanded is advisory-only.
- Routing correction is now explicit rather than accidental: once the draft is routing-ready, keyword drift stays blocked, but a clear user correction can intentionally rewrite the draft and require reconfirmation.
- Active voice mainline is now `v2`-only: `/chat`, `/chat/v2`, `/realtime`, and shared bootstrap/runtime no longer branch back into the legacy graph on the request path.
- `chat_v2` now treats websocket `session_complete` as a post-persistence signal, so live eval can read snapshot immediately after completion without racing the evidence write path.
- Local/team LLM truth-state is now explicit: mainline chat/runtime should use `vllm` via `http://192.168.0.18:8000/v1` with `token-abc123`, and `scripts/test_voice_backend.py` is the first-line connectivity smoke.
- Live `mainline synthetic eval` is verified green again on a real local API: `workplace`, `interview`, and `project` all pass with `100%`.

## Routing Invariants
- `primary_context` is the source of truth for the first useful mission. `domain` and secondary contexts never override it.
- Once `goal_brief.status` is `draft` or `confirmed`, `primary_context` is sticky: only an explicit user correction can change it.
- Context scoring is cumulative across the onboarding transcript, not just the latest reply.
- Mapping table (enforced by `GoalRoutingProfile` and by `tests/test_goal_routing.py::test_track_and_first_mission_always_consistent`):

| `primary_context`         | `recommended_track_id`   | `first_mission_task_type`        |
|---------------------------|--------------------------|----------------------------------|
| `interviews`              | `hr_intro`               | `foundation_speaking_drill`      |
| `workplace_communication` | `workplace_communication`| `stakeholder_explanation_drill`  |
| `project_walkthrough`     | `project_walkthrough`    | `technical_project_walkthrough`  |

## Known Issues
- Old users with stale roadmap state can still surface edge cases; more live verification is needed against non-fresh accounts.
- Browser Vosk is still weak on broken English; the backend Parakeet lane exists, but live benchmark and rollout tuning are still pending.
- Browser-level verification is still needed for the main frontend path: first greeting audio, farewell audio before redirect, and clean post-session logs from a real browser run.
- Memory consolidation is still request-time only; there is no background job yet for periodic profile refresh or contradiction cleanup.
- Pace and pause evidence are still missing, and pronunciation is still mostly transcript-backed rather than audio-native.
- `/chat/v2` still contains the older large endpoint implementation; the modular runtime is additive for now, not yet the mainline path.
- Full `pytest tests -q` still has unrelated legacy failures outside the current wedge work; targeted product-track tests are green.
- Explicit goal correction is now supported only inside the onboarding correction lane; a broader post-handoff goal-edit UX does not exist yet.
- Split truth-state (llama_cpp vs intended vllm) is still an open infrastructure consistency task; product evals are passing but the backend may not be using the canonical vllm endpoint in all runs.

## Next Step
- Restart FastAPI and run live synthetic eval in three tiers: `mainline`, `expanded`, then `live_tester` as advisory/stress.
- Run `scripts/run_routing_classifier_eval.py --scenario-set expanded --classifier-source llm --arbiter-mode shadow` to collect an offline classifier disagreement report before any `gate` rollout.
- Do NOT add a new LLM layer yet; in-session intent is the next candidate only if live evidence shows bounded fast rules miss important cases.
- Do NOT touch voice architecture in this cycle; PersonaPlex stays as premium/advanced lane.
- Resolve split truth-state: llama_cpp vs vllm as a separate infra task, not blocking product.
- Run one real browser smoke pass for `workplace`, `interview`, and `project`, then mark greeting/farewell/redirect as live-verified.
- Benchmark browser Vosk vs backend Parakeet from evidence; then choose the mainline STT lane.

## Last Update
### 2026-04-23 (offline classifier eval)
- Added `scripts/run_routing_classifier_eval.py`, an offline lexical/classifier/arbiter eval that compares expected primary context, lexical routing, classifier output, and `shadow/gate/mainline` arbiter decisions without opening the live websocket.
- Default rollout remains `career_routing_classifier_mode=shadow`; the new runner is measurement infrastructure, not a product behavior change.
- Added `tests/test_routing_classifier_eval_script.py` to pin scenario tier resolution, deterministic fixture classification, gate/shadow arbitration, and summary metrics.
- Verification: classifier eval tests `10 passed`; deterministic expanded fixture dry-run saved `!DOC/research/data/routing_eval/offline-fixture-expanded.json` with `6/6` arbiter matches.

### 2026-04-23 (routing architecture hardening)
- Added canonical goal-brief context normalization, so LLM/free-text labels like `job interview` are coerced to supported enums or rejected before they reach routing/snapshot state.
- Made goal routing negation-aware and tolerant of a small set of common STT/noisy-English spellings, without moving the classifier out of `shadow`.
- Hardened onboarding with cumulative short-answer inference, adjacent IT-role recognition, explicit safe force-routing after repeated low-signal goal turns, and no scenario-specific production branches.
- Split synthetic eval tiers back into `mainline`, compact `expanded`, and large `live_tester` stress/advisory.
- Verification: targeted routing/onboarding/provider/eval suite `97 passed`; product-track downstream suite `92 passed`; changed modules compile.

### 2026-04-22 (goal_brief contract canonicalization)
- Added `app/services/goal_brief_contract.py` — canonical two-level contract: `routing-ready` (handoff to first mission) and `full profile` (enrichment); `target_market` no longer blocks first-mission handoff.
- Migrated onboarding, `learning_plan_service`, `program_snapshot_service` to read from the shared contract; `missing_fields`, setup progress, draft/confirmed semantics, and routing gate are now in sync.
- Added `tests/test_goal_brief_contract.py`; full suite: `84 passed`.
- Live expanded synthetic eval: `6/6 PASS, 100%`; `project_tradeoff_story` green.
- Next: live disagreement report for routing classifier (shadow run) before deciding gate scope.

### 2026-04-22 (stabilization pass)
- Added an explicit correction lane in onboarding: routing stays sticky against drift, but a clear user correction can now rewrite `main_contexts`, `target_role`, `domain`, and re-open draft confirmation.
- `GoalRoutingProfile.decision_source` now distinguishes `explicit_user_correction` from ordinary sticky draft routing.
- `scripts/run_product_synthetic_eval.py` now treats only blocking scenarios as release gates; `expanded` edge cases stay advisory unless the user explicitly runs a single scenario.
- Active voice request paths now stay on `v2` only, and shared bootstrap/runtime no longer fall back to the legacy graph in mainline execution.
- Local run truth-state was clarified: canonical Windows API launch is `venv\\Scripts\\python.exe main.py`, and product synthetic eval should use softer timeouts against remote/corporate LLM backends.
- Fixed the completion contract in `chat_v2`: websocket `session_complete` is now emitted after post-session persistence, not before it.
- Repointed the active local/team vLLM truth-state from the stale `192.168.0.27` host to `http://192.168.0.18:8000/v1`, updated `.env` / `.env.example` / docs / tests, and added explicit connectivity smoke through `scripts/test_voice_backend.py`.
- Re-ran live `mainline synthetic eval` after the fix on a real local API and confirmed `PASS 3/3`, `average_score=100.0`, `pass_rate=100.0%`.

### 2026-04-21 (routing policy + mission-safe recovery)
- Added `app/services/routing/goal_routing.py` as the canonical policy for `primary_context → recommended_track_id → first_mission_task_type`. Onboarding, `ProgramSnapshotService`, and first-mission selection now read from the same `GoalRoutingProfile`.
- Context scoring is now cumulative across the onboarding transcript, and `primary_context` is sticky after `goal_setup_complete=True`; LLM-extracted goal-brief updates are filtered once routing is locked in.
- Removed the `domain`-first branch and the `and not has_project_context` guard from `_build_first_useful_mission_without_assessment`, so secondary signals can no longer override the first useful mission.
- Added `app/agent/recovery.py::build_mission_safe_recovery` and routed both the onboarding LLM-error path and the outer graph-level catch through it; replaced the legacy `I'm having trouble` fallbacks.
- `scripts/run_product_synthetic_eval.py` now categorizes checks (`routing_check` vs `runtime_check`), adds a `no_generic_fallback_leak` scan of assistant transcripts, and treats mainline as blocking while expanded is advisory-only.
- Verification:
  - `py -m pytest tests/test_goal_routing.py tests/test_agent_error_recovery.py -q`
  - `20 passed`

### 2026-04-22
- Added `!DOC/MASTER_PROJECT_VIEW_2026-04-22.md` as the new top-level project view that connects product thesis, moat, target architecture, execution rules, and dual-horizon planning in one place.
- Repositioned docs around explicit roles:
  - master view = canonical project definition
  - `CURRENT_PRODUCT_STATE.md` = operational truth
  - target architecture / roadmap / RU business flow = appendices
- Updated `!DOC/README.md` so the reading order starts from the master view instead of forcing the team to reconstruct the project from several parallel docs.

### 2026-04-21
- Ran live synthetic eval against a real local API + PostgreSQL and saved two reports:
  - `product-synthetic-baseline-report.json`
  - `product-synthetic-expanded-report.json`
- Mainline baseline result:
  - `workplace_first_value` PASS
  - `project_first_value` PASS
  - `interview_first_value` FAIL because persisted `latest_evidence.task_type` is `technical_project_walkthrough`, not `foundation_speaking_drill`
- Expanded result exposed two more product weaknesses:
  - `workplace_status_update` drifts from workplace communication into project walkthrough
  - `project_tradeoff_story` hit one unstable assistant recovery turn
- Updated `run_product_synthetic_eval.py` so live eval matches truth-state completion: explicit `session_complete` or a real farewell transcript with `phase=session_end`.
- Added extra synthetic scenarios and rewrote `PRODUCT_SYNTHETIC_EVAL_RUNBOOK.md` with clean commands for `mainline` and `expanded`.
- Verification:
  - `python -m pytest tests/test_product_synthetic_eval_script.py -q`
  - `10 passed`
  - `python scripts/run_product_synthetic_eval.py --base-url http://127.0.0.1:8000 --output product-synthetic-baseline-report.json`
  - `python scripts/run_product_synthetic_eval.py --base-url http://127.0.0.1:8000 --scenario-set expanded --output product-synthetic-expanded-report.json`

### 2026-04-21
- Added `scripts/run_product_synthetic_eval.py` plus `PRODUCT_SYNTHETIC_EVAL_RUNBOOK.md` as a live product-first eval loop for the mainline `chat_v2` path.
- The synthetic eval uses canonical `composer` scenarios to score business behavior rather than STT quality: handoff into `first useful mission`, `embedded_first_mission` baseline persistence, `session_evidence`, and `ready_for_program` snapshot state.
- Updated `VOICE_OBSERVABILITY_RUNBOOK.md` so the first-run smoke reflects the new `goal -> first useful mission -> session_complete` contract instead of the old baseline-first path.
- Verification:
  - `python -m py_compile scripts/run_product_synthetic_eval.py`
  - `python -m pytest tests/test_product_synthetic_eval_script.py tests/test_agent_e2e_script.py -q`
  - `27 passed`

### 2026-04-21 (later)
- Switched the main onboarding contract from `baseline-first` to `first-useful-mission-first`: a routing-ready draft goal now hands off straight into a real guided mission instead of blocking on a standalone assessment.
- `ProgramSnapshot`, Home, and Progress now use `needs_first_mission`, and the UI explains that the working baseline can be inferred from the first real mission.
- Added `assessment.source` with `explicit_assessment` vs `embedded_first_mission`, so the product can distinguish a manual baseline from one captured during a real mission.
- Shared voice-session persistence now captures embedded baseline only when it is genuinely new, then writes it as `embedded_first_mission` and passes that source into `session_evidence`.
- Onboarding/router runtime now resumes learning after the first-mission handoff instead of bouncing back into assessment-only logic.
- Verification:
  - `python -m pytest tests/test_program_snapshot_service.py tests/test_learning_plan_service.py tests/test_onboarding_node.py tests/test_voice_session_services.py -q`
  - `73 passed`
  - `python -m py_compile app/agent/state.py app/agent/graph_v2.py app/agent/nodes_v2/router.py app/agent/nodes_v2/onboarding.py app/services/voice_session/service.py app/api/voice_helpers.py app/services/learning_plan_service.py app/api/programs.py`
  - `npm.cmd run build` in `frontend` passed

### 2026-04-21 (earlier)
- Added a short truth-state architecture doc that separates the real hot path from the async/materialization contour: PostgreSQL is canonical, Qdrant is best-effort retrieval, and Neo4j is async-only for now.
- Moved memory-to-Qdrant sync out of the request path: memory persistence now commits to PostgreSQL first and schedules vector sync as best-effort background work.
- Added a server-side guard in the XP write path so monthly `xp_events` partitions are ensured before insert instead of relying only on ops scripts.
- Hardened post-session memory extraction with one retry and a soft-failure outcome, so transient provider connection errors do not poison the whole persistence path.
- Extended `session_evidence` and mission routing: the product now records richer weakness/improvement signals and can route `repeat` vs `advance` with a visible `adaptation_reason`.
- Completed the next wedge layer with `project_notes` and `project_story_pack`, and added a backend Parakeet transcription lane behind `POST /api/v1/voice/transcribe`.
- Verification:
  - `python -m pytest tests/test_learning_plan_service.py tests/test_program_snapshot_service.py tests/test_xp_service.py tests/test_rag_pipeline.py tests/test_voice_runtime.py tests/test_voice_helpers.py tests/test_voice_session_services.py tests/e2e/test_business_flow.py::test_gamification -q`
  - `116 passed`
  - `python -m py_compile app/services/gamification/xp_service.py app/services/ai/memory_pipeline.py app/services/learning_plan_service.py app/services/program_snapshot_service.py app/services/voice_runtime/stt.py app/api/career.py app/api/voice.py`
  - `npm.cmd run build` in `frontend` passed
  - `python -m pytest tests -q` still shows unrelated legacy failures outside the current wedge track

### 2026-04-14
- Locked the first main-loop mission contract around `main_contexts[0]` for fresh users: workplace-first now routes to `stakeholder_explanation_drill`, interview-first to `foundation_speaking_drill`, and project-first to `technical_project_walkthrough`.
- Expanded the live `/chat/v2` smoke harness into a 3-scenario routing suite and verified all 3 scenarios against a fresh backend: workplace, interview, and project.
- Validated runtime hardening live on the composer lane: Windows-safe logging no longer throws `UnicodeEncodeError`, first-turn onboarding survives transient LLM connection glitches, and TTS now soft-degrades instead of turning the session into a failure.
- Remaining live blockers from the same run are now explicit: local `xp_events` partition failures and post-session memory extraction `Connection error`.
- Verification:
  - `venv\Scripts\python.exe -m pytest tests/test_agent_e2e_script.py tests/test_learning_plan_service.py tests/test_interview_service.py tests/test_program_snapshot_service.py tests/test_voice_runtime.py -q`
  - `81 passed`
  - `venv\Scripts\python.exe -c "import main; print('main import ok')"` passed
  - `venv\Scripts\python.exe scripts/test_agent_e2e.py --base-url http://127.0.0.1:8012 --scenario-set routing` passed

### 2026-04-13
- Saved two meaningful commits for continuity:
  - `18183b9 feat(agent): выделить intent layer и трассировку voice-сессий`
  - `3f39998 fix(voice): дождаться farewell и изолировать post-session ошибки`
- Added frontend handoff hardening for the main voice path: explicit audio unlock on start, completion flow via `session_complete -> end -> session_end farewell`, and redirect only after farewell playback or socket-close fallback.
- Added backend hardening for session finalization: stale vLLM alias fallback to the canonical model, deterministic `session_end` fallback flags, split TTS synthesis vs audio-delivery logging, and safer post-session rollback behavior around gamification failures.
- Updated ops/docs continuity for local recovery: `QUICK_START.md` now points to the canonical vLLM model, `db/README.md` includes the gamification migration, and `scripts/manage_partitions.sh` now manages `xp_events` partitions too.
- Verification:
  - `venv\Scripts\python.exe -m pytest tests/test_llm_provider.py tests/test_session_end_node.py tests/test_voice_helpers.py tests/test_voice_session_services.py tests/test_voice_runtime.py tests/test_voice_observability.py -q`
  - `48 passed`
  - `venv\Scripts\python.exe -c "import main; print('main import ok')"` passed
  - `npm.cmd run build` in `frontend` passed
### 2026-04-10
- Added a product-oriented STT benchmark layer: explicit `stt_provider` metadata now flows through the main voice paths, dev debug exports retain full sent text, and `scripts/run_stt_benchmark.py` can score live smoke artifacts or structured multi-provider cases.
- Added `!DOC/operations/STT_BENCHMARK_RUNBOOK.md` to lock the benchmark contract, expected inputs, and acceptance criteria around role/project/technical-term capture rather than generic WER.
- Locked the moat framing in the canonical strategy docs: EnglishFriend should compete as a vertical career-English operating loop, not as a generic AI tutor or learning OS.
- Added an explicit anti-roadmap to guard against DeepTutor-like breadth drift: no general tutor platform, no notebook/research workspace core, no user-facing multi-agent shell.
- Recorded the strategic implication of recent external signals: horizontal tutoring stacks are commoditizing, so moat must come from career-state precision, pedagogy, evidence, and audience-specific adaptation.
- No code changes in this update; this was a strategy/documentation lock to guide the next implementation passes.
### 2026-04-09
- Added the observability-first instrumentation pass for `/chat/v2` and `/realtime`: shared backend voice envelopes, stage metrics, websocket metadata enrichment, and a dev-only frontend debug panel/export flow.
- Added an operational runbook for instrumented live smoke capture in `!DOC/operations/VOICE_OBSERVABILITY_RUNBOOK.md`.
- Added regression coverage for observability helpers and updated runtime/session tests for `runtime`, `turn_id`, and enriched payloads.
- Verification:
  - pending targeted `pytest`, backend import check, and frontend build after the observability pass
### 2026-04-09
- Added a DB-first hybrid memory layer with compact `LearnerProfileSummary`, mission-scoped memory context, and bootstrap wiring into `/chat/v2` and `/realtime`.
- Added lightweight memory self-healing in the persistence path: relative-date normalization, duplicate dropping, and conflict surfacing before save.
- Added regression coverage for learner profile assembly, mission memory rendering, memory consolidation contracts, and updated bootstrap tests.
- Verification:
  - `venv\Scripts\python.exe -m pytest tests/test_memory_contracts.py tests/test_learner_profile_service.py tests/test_voice_session_services.py tests/test_voice_runtime.py tests/test_rag_pipeline.py -q`
  - `25 passed`
  - `venv\Scripts\python.exe -c "import main; print('main import ok')"` passed
### 2026-04-06
- Added `llama_cpp` final-only compatibility mode with typed empty-content errors, one compat retry for reasoning-only responses, and safe fallbacks in onboarding, learning, session_end, memory extraction, and post-session analysis.
- Added config/docs contract for `LLAMA_CPP_RESPONSE_MODE` and `LLAMA_CPP_EXTRA_BODY_JSON`.
- Added regression coverage for llama.cpp compat retry, raw-mode behavior, empty-content node fallbacks, and post-session/memory safety.
### 2026-04-06
- Extracted a shared `voice_session` bootstrap/persistence layer and wired it into both `/chat/v2` and `/realtime`.
- Added explicit mission-contract wiring from `ProgramSnapshot.mission` through frontend websocket query into backend session init for the main voice paths.
- Added regression coverage for explicit mission precedence over roadmap fallback and for realtime controller pass-through of mission metadata.
- Verification:
  - `venv\Scripts\python.exe -m pytest tests/test_learning_node.py tests/test_voice_runtime.py tests/test_voice_session_services.py tests/test_voice_helpers.py -q`
  - `27 passed`
  - `venv\Scripts\python.exe -c "import main; print('main import ok')"` passed
### 2026-04-06
- Stabilized early foundation voice turns: `/chat/v2` now treats `foundation_speaking_drill` and `grammar_rescue` as mission-anchored guided sessions instead of generic free conversation.
- Added low-signal handling that keeps the coach on one anchor question, asks for one shorter answer, then falls back to typed/composer input if STT stays noisy.
- Added stricter frontend review mode for foundation and grammar missions, plus mission-specific helper chips in the composer.
- Added LLM safety handling for empty final `content`, so the coach falls back to a mission-anchored clarification instead of silently drifting.
- Added unit tests for mission opener, noisy-transcript handling, empty-content fallback, and anchor progression.
- Verification:
  - `venv\Scripts\python.exe -m pytest tests/test_learning_node.py tests/test_onboarding_node.py tests/test_voice_runtime.py tests/test_llm_provider.py -q`
  - `40 passed`
  - `npm.cmd run build` in `frontend` passed
### 2026-04-06 (earlier)
- Added `app/services/voice_runtime/` as a new modular runtime package with explicit `TransportAdapter`, `STTProvider`, `TurnDetector`, `TTSProvider`, and `VoiceSessionController`.
- Added feature flag `REALTIME_RUNTIME_ENABLED` and a new experimental endpoint `/api/v1/voice/realtime`.
- Kept the current text protocol and LangGraph brain, so the new runtime can benchmark alternate voice stacks without changing the product-state engine.
- Added an internal tool-registry entry for the modular runtime boundary.
- Added unit tests covering turn detection, passthrough STT, TTS adapter delegation, and controller handling for text turns and explicit session end.
- Verification:
  - `venv\Scripts\python.exe -m pytest tests/test_voice_runtime.py tests/test_voice_helpers.py -q`
  - `17 passed`
  - `venv\Scripts\python.exe -c "import main; print('main import ok')"` passed
### 2026-04-01
- Switched onboarding to a hard guided, code-owned flow for the main product path.
- Added noisy-speech ML/AI career goal inference and `draft | confirmed` goal state.
- Changed routing so a draft goal is enough to move into baseline assessment.
- Updated roadmap and snapshot semantics to treat `draft` as routing-ready.
- Updated Home and Progress to display draft target state and setup CTA more clearly.
- Fixed snapshot crash for older users by returning a default program shell when `program_plan` is missing.
- Simplified bottom navigation so early users do not see a toolbox before baseline/program readiness.
- Added transcript review before send for setup and assessment sessions in `VoiceChatV2`.
- Rebuilt `Progress` into a proof screen: target, readiness, improvements, blockers, latest evidence.
- Added session-end persistence for routing-ready `draft` goals, so Home no longer collapses back to an empty setup state after one useful onboarding session.
- Shortened baseline prompts to one-question-at-a-time wording for weak-English first-run users.
- Declared this file the single active continuity source; `CLAUDE_SESSION_LOG.md` is now legacy history.
- Verification:
  - `python -m pytest tests/test_learning_plan_service.py tests/test_onboarding_node.py tests/test_program_snapshot_service.py tests/test_voice_helpers.py -q`
  - `38 passed`
  - `python -c "import main; print('main import ok')"` passed
### 2026-04-02
- Locked strategy: do not pivot to a general assistant; keep EnglishFriend as a vertical career-English coach and use agent patterns only internally.
- Added an internal markdown skill registry for coach modes and career-loop skills.
- Wired `build_mode_prompt()` and session greetings to md-backed skill manifests with safe fallback to existing Python prompts.
- Added a minimal internal tool registry to name current speech, learning, evaluation, and state boundaries.
- This is internal control-plane infrastructure only; the product still presents one vertical coach path, not a general agent UI.
- Added vacancy-driven career context and interview-pack generation to the roadmap/snapshot loop.
- Added a paid-intent write path so the product can record willingness-to-pay before billing exists.
- Home now exposes vacancy paste, interview pack, and paid beta CTA directly in the main loop.
- Onboarding now records real turns/history, runs a deterministic one-question-at-a-time baseline, and can finish with a provisional assessment instead of looping forever.
- Session end now persists provisional baseline confidence/status, and snapshot/Home expose setup progress plus draft/provisional state instead of collapsing to an empty dashboard.
- Guided first-run now uses a persistent composer, `Type instead`, helper chips, and slower silence timing instead of modal transcript review.
- Home early states now focus on `Target`, `What happens next`, and `Next step`, with vacancy and heavier cards hidden until the program is ready.
- Verification:
  - `npm run build` passed
