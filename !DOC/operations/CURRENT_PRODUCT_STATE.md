# Current Product State

Last updated: 2026-04-01
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
- Onboarding now uses code-owned prompt logic for the main flow instead of depending on DB prompt templates.
- Draft goal state is routing-ready for baseline and first program steps.
- Home is simplified around target, baseline, mission, and stage instead of a large dashboard.
- Setup and assessment sessions now support transcript review before send, so weak browser STT is less destructive in the first-run flow.
- Session end now persists a strong draft goal, not only an explicitly confirmed goal.
- Graph/session init now treats `draft` as setup-complete enough to move into baseline routing.

## Known Issues
- Live onboarding still needs manual smoke testing after the latest draft-goal and transcript-review changes.
- Old users with stale data can surface edge cases; snapshot fallback has been hardened, but more live verification is needed.
- Frontend bundle is still too large and warns on build.
- Langfuse is configured in code but disabled locally unless credentials are set.
- Some old docs are noisy or outdated; use this file as the active continuity source.
- Baseline quality still depends on prompt behavior; the flow is now shorter, but real live wording still needs verification with weak-English users.

## Next Step
- Run a live smoke test for the main path:
  - noisy goal
  - transcript review appears before send in setup/assessment
  - draft target shown
  - short baseline starts with one question, not a mini-exam
  - first mission appears
- If onboarding still sounds generic, inspect runtime prompt path before changing product logic again.
- If the flow is clearer but STT is still too weak, compare transcript-review UX against a typed fallback before touching the ASR stack.

## Last Update
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
