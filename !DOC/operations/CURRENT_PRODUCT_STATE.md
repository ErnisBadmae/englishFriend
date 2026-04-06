# Current Product State

Last updated: 2026-04-06
Status: Active source of truth for product progress and agent continuity

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
- Foundation and grammar missions now run through a stricter guided voice flow on `/chat/v2`, so weak STT no longer auto-sends noisy turns into a free-form tutor loop.
- Learning turns for early foundation work now stay anchored to current work -> recent ML project -> next step, with deterministic clarifications instead of semantic guessing.

## Known Issues
- Live onboarding and foundation voice still need manual smoke testing after the latest mission-anchored turn policy changes.
- Old users with stale data can surface edge cases; snapshot fallback has been hardened, but more live verification is needed.
- Frontend bundle is still too large and warns on build.
- Langfuse is configured in code but disabled locally unless credentials are set.
- Some old docs are noisy or outdated; use this file as the active continuity source.
- Browser Vosk is still weak on broken English; the product now has a stronger typed fallback, but STT quality itself is unchanged.
- `/chat/v2` still contains the older large endpoint implementation; the new modular runtime is additive for now and has not yet replaced that path.
- Foundation mission context is currently inferred from roadmap/program state in backend init; explicit session-contract wiring is still optional, not mandatory.

## Next Step
- Run a live smoke test for the stricter foundation path on `/chat/v2`:
  - start `Run a foundation speaking drill`
  - say a noisy or partial answer
  - verify transcript stays in composer and does not auto-send
  - send one short cleaned answer
  - verify the coach stays on current work / recent project / next step instead of inventing a new topic
- If that path feels reliable, continue with vacancy -> interview pack -> mission -> paid-intent loop and collect 3-5 real session transcripts.
- Then enable `REALTIME_RUNTIME_ENABLED=true` locally and smoke-test `/api/v1/voice/realtime` against the same frontend protocol before wiring any new STT/TTS provider.

## Last Update
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
