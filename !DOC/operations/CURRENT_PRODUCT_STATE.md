# Current Product State

Last updated: 2026-04-21
Status: Active source of truth for product progress and agent continuity

Canonical long-form vision and architecture:
[../research/deep-research-report.md](../research/deep-research-report.md)

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
3. System runs a lightweight baseline and sets the first stage.
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

## Known Issues
- Old users with stale roadmap state can still surface edge cases; more live verification is needed against non-fresh accounts.
- Browser Vosk is still weak on broken English; the backend Parakeet lane exists, but live benchmark and rollout tuning are still pending.
- Browser-level verification is still needed for the main frontend path: first greeting audio, farewell audio before redirect, and clean post-session logs from a real browser run.
- Memory consolidation is still request-time only; there is no background job yet for periodic profile refresh or contradiction cleanup.
- Pace and pause evidence are still missing, and pronunciation is still mostly transcript-backed rather than audio-native.
- `/chat/v2` still contains the older large endpoint implementation; the modular runtime is additive for now, not yet the mainline path.
- Full `pytest tests -q` still has unrelated legacy failures outside the current wedge work; targeted product-track tests are green.

## Next Step
- Run one real browser smoke pass for `workplace`, `interview`, and `project`, then mark greeting/farewell/redirect as live-verified.
- Benchmark browser Vosk against backend Parakeet on role capture, project capture, technical terms, and guided-session latency; then choose the mainline STT lane from evidence.
- Move memory consolidation from request-time only toward a background job.
- Add richer speaking evidence next: pace, pause patterns, and later audio-backed pronunciation scoring.
- Keep roadmap decisions filtered by the moat: career state, weak-English pedagogy, structured evidence, and adaptive next-mission routing.
- Keep PersonaPlex as a premium or advanced delivery lane, not as the primary moat bet for the next cycle.

## Last Update
### 2026-04-21
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
