# Current Product State

Last updated: 2026-04-10
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
2. System builds a draft career goal from weak signals.
3. User confirms or lightly corrects the draft.
4. System runs a quick baseline assessment.
5. System compiles a 90-day draft program.
6. Home shows target, baseline, current stage, and today's mission.
7. Session produces evidence.
8. Next mission adapts from that evidence.

## What Works Now
- Program snapshot API aggregates goal, assessment, program, mission, interview, pronunciation, vocabulary, and evidence.
- Interview loop works end-to-end: run, save, results screen, adaptive next mission.
- Pronunciation evidence layer exists through provider abstraction with current heuristic text-backed implementation.
- Guided sessions now save generic session evidence, not only interview outcomes.
- Internal coach behavior now supports md-driven skill manifests with safe Python fallback, so prompt/policy iteration is less hardcoded without turning the product into a general assistant.
- The product can now accept a pasted vacancy, sharpen career context, build an interview pack, and store a paid-beta intent signal without adding a separate platform layer.
- Onboarding now uses code-owned prompt logic for the main flow instead of depending on DB prompt templates.
- Draft goal state is routing-ready for baseline and first program steps.
- Home is simplified around target, baseline, mission, and stage instead of a large dashboard.
- Setup and assessment sessions now support transcript review before send, so weak browser STT is less destructive in the first-run flow.
- Setup and assessment now use a persistent voice+text composer with helper chips and manual send, so poor STT no longer forces a fragile modal review step.
- Session end now persists a strong draft goal, not only an explicitly confirmed goal.
- Graph/session init now treats `draft` as setup-complete enough to move into baseline routing.
- Experimental modular voice runtime now exists behind `REALTIME_RUNTIME_ENABLED` at `/api/v1/voice/realtime` with explicit transport, STT, turn detection, TTS, and controller boundaries.
- The new runtime keeps the current text protocol and LangGraph brain, so the stack can benchmark new voice paths without rewriting product state logic.
- Shared `voice_session` lifecycle now powers both `/chat/v2` and `/realtime`, so user bootstrap and post-session persistence are no longer duplicated across the two main voice paths.
- Foundation and grammar missions now run through a stricter guided voice flow on `/chat/v2`, so weak STT no longer auto-sends noisy turns into a free-form tutor loop.
- Learning turns for early foundation work now stay anchored to current work -> recent ML project -> next step, with deterministic clarifications instead of semantic guessing.
- Primary frontend voice sessions now pass explicit mission metadata from `ProgramSnapshot.mission` into backend init, so `/chat/v2` and `/realtime` do not rely only on roadmap inference for early mission anchoring.
- `llama_cpp` / Qwen compatibility is now hardened in the adapter layer: empty final content no longer silently propagates, and `final-only` mode is the default contract for the CPU endpoint.
- Voice bootstrap now assembles a compact `LearnerProfileSummary` plus mission-scoped memory context from roadmap, evidence, and stored memories, so prompt memory is less raw and more stable across sessions.
- Memory persistence now does a lightweight self-healing pass before save: relative dates are normalized, exact duplicates are dropped, and semantic conflicts are surfaced for profile-level resolution instead of silently bloating prompt context.
- Mainline voice paths now emit a shared observability envelope across backend layers, including `runtime`, `session_id`, `turn_id`, `phase`, and `mode`.
- Frontend dev voice sessions now expose a local debug panel with event capture and JSON export, so browser STT, websocket flow, and session handoff can be correlated with backend logs.
- `/chat/v2` and `/realtime` now enrich websocket payloads with optional runtime metadata, so both paths can be compared through the same smoke harness.
- Mainline voice paths now carry an explicit `stt_provider` label through session init, websocket payloads, and observability, so smoke runs and benchmark reports can be grouped by STT lane instead of only by transport source.
- A product-oriented STT benchmark layer now exists: frontend debug exports keep full sent transcripts in dev mode, and `scripts/run_stt_benchmark.py` can score live smoke artifacts or multi-provider case files against role/project/technical-term expectations.

## Known Issues
- Full-stack observability is now wired for the mainline voice paths, but it still needs live validation to prove that each failure mode is diagnosable in one pass.
- Live onboarding and foundation voice still need manual smoke testing after the latest explicit mission-contract wiring.
- Old users with stale data can surface edge cases; snapshot fallback has been hardened, but more live verification is needed.
- Frontend bundle is still too large and warns on build.
- Langfuse is configured in code but disabled locally unless credentials are set.
- Some old docs are noisy or outdated; use this file as the active continuity source.
- Browser Vosk is still weak on broken English; the product now has a stronger typed fallback, but STT quality itself is unchanged.
- `/chat/v2` still contains the older large endpoint implementation; the new modular runtime is additive for now and has not yet replaced that path.
- Legacy and premium voice paths are not fully aligned yet; `/chat-legacy` and `/chat/plex` still use older init patterns outside the shared mission-contract path.
- Live retest on the real `llama_cpp` endpoint is still needed after the new Qwen compatibility pass.
- Memory consolidation is still request-time only; there is no background job yet for periodic profile refresh or deep contradiction cleanup.
- Cloud LLM resilience is still thin; the practical path today is mostly `Groq -> llama.cpp`.
- The vocabulary scheduling layer still runs on the current Python FSRS path and has not yet been reviewed against Rust-backed alternatives.
- The dev debug panel is local-only; frontend debug events are not yet persisted or queryable from the backend.
- The benchmark layer is artifact-first for now; it can score browser/live exports and structured case files, but first-class server adapters for `faster-whisper` and `Parakeet-TDT` are not wired yet.
- Strategic risk: product breadth can still drift toward a generic tutor / learning workspace if new features are not filtered through the career-loop moat.

## Next Step
- Run the instrumented 3-session live smoke set on the current stack using `VOICE_OBSERVABILITY_RUNBOOK.md`.
- For each run, collect:
  - frontend debug JSON export
  - backend logs by `session_id`
  - `/metrics` snapshot before and after
- Use the new shared `runtime/session_id/turn_id` contract to identify whether the next real bottleneck is STT, pedagogy, LLM fallback, memory, or persistence.
- Keep the roadmap filtered by moat:
  - prioritize features that improve goal precision, pedagogy, evidence, or next-mission adaptation
  - deprioritize features that only add generic tutor breadth
- Then start the STT benchmark track:
  - collect the first benchmark-ready artifacts with `STT_BENCHMARK_RUNBOOK.md`
  - compare current browser Vosk first
  - then add backend `faster-whisper`
  - then add backend `Parakeet-TDT`
  - then add browser-side `Whisper-small/WebGPU`
- Keep `Cerebras` as the near-term resilience sidecar and keep FSRS review as a parallel, lower-priority track.
- Keep `deep-research-report.md` as the broader architecture map, but treat this file as the current execution source of truth.

## Last Update
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
