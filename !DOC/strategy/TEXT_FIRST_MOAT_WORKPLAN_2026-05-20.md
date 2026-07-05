# Text-First Moat Workplan
Last updated: 2026-05-20
Status: active planning anchor for Codex and Claude Code
This document is the shared working plan for the current EnglishFriend cycle.
It overrides voice-first experimentation unless the user explicitly changes the priority.
## 2026-05-25 Execution Update
The current validation mode is self-dogfood.
The founder will use EnglishFriend to prepare for a real job-search goal:
`first remote hard-currency job in ML/AI/SWE-adjacent work`
The active implementation path is now:
`CareerProfile -> VacancyContext -> Mission -> text session -> Evidence -> Next Mission`
Detailed documents:
- [../architecture/SELF_DOGFOOD_TARGET_ARCHITECTURE_2026-05-25.md](../architecture/SELF_DOGFOOD_TARGET_ARCHITECTURE_2026-05-25.md)
- [../operations/SELF_DOGFOOD_30_DAY_PLAN_2026-05-25.md](../operations/SELF_DOGFOOD_30_DAY_PLAN_2026-05-25.md)
This does not change the voice decision. Voice remains deferred until the text loop produces useful evidence and a clear need for speaking pressure.
## Decision
EnglishFriend should first reach an acceptable product level in text mode.
Voice remains strategically important, but it is not the current moat. The moat has to come from the business loop:
- a narrow learner segment: Russian-speaking ML/SWE and adjacent IT specialists
- a narrow job-to-be-done: interview preparation in English
- a guided coach flow, not a generic assistant
- persistent evidence about the learner's real gaps
- missions that build from session to session
- feedback that is specific enough to feel better than ChatGPT with a generic prompt
The current priority is therefore:
1. Make the text-first interview loop useful enough that a real user wants `session 2`.
2. Make the session-to-session evidence loop reliable and visible.
3. Use voice only as an opt-in delivery layer until the business loop is validated.
4. Build voice benchmarks before deeper provider integration.
## Why Voice Is Deferred
Realtime voice can make the product feel premium, but it can also hide weak product logic.
If the core loop is weak, better TTS only makes a smoother demo. It does not create retention.
If the core loop is strong, voice can amplify it with emotional presence, speaking pressure, and lower friction.
The current risk is not "we do not have a good enough voice model." The current risk is:
- the product may still feel like a generic English chatbot
- missions may not yet feel inevitable or personally relevant
- feedback may not yet be sharper than what a user can get from ChatGPT
- evidence persistence may not yet create a clear reason to return
- the user may not understand why the next session matters
Voice provider work starts only after the text loop passes the gates below.
## Product Thesis
The product is not a general English tutor.
The product is a career-English coach for interview performance, where the learner needs to:
- answer "tell me about yourself" clearly
- explain projects and tradeoffs in English
- survive behavioral and technical follow-ups
- reduce common Russian-speaker errors only when they affect interview performance
- build repeatable answer patterns across sessions
The strongest product shape is not "chat with a tutor." It is:
`goal -> baseline answer -> targeted mission -> correction -> evidence -> next mission`
Every feature should strengthen that loop.
## Current Wedge
Active wedge:
- `ML/SWE interview prep`
Allowed supporting contexts:
- `project_walkthrough` only as an interview artifact
- `workplace_communication` only if it supports interview readiness in this cycle
Out of scope for this cycle:
- broad workplace English
- general speaking club
- grammar drills as standalone product
- vocabulary toolbox
- open-ended AI companion
- provider-driven voice experiments
## Moat Hypothesis
The moat is not infrastructure, TTS latency, or graph/vector sophistication.
The moat should be:
- `learner evidence`: the system remembers what the learner actually said, not just what topic they selected
- `mission progression`: the next task follows from observed gaps, not from a static lesson list
- `career specificity`: feedback is grounded in ML/SWE interview situations
- `Russian-speaker diagnosis`: corrections focus on the mistakes this audience actually makes
- `coach constraints`: short turns, one task at a time, clear pressure, no generic assistant sprawl
- `return reason`: the user sees why session 2 will be better than starting over elsewhere
If a change does not improve one of these, it is probably polish or scope drift.
## Product Gates
### Gate 1: Text Session 1 Works
The user can complete a text-first session from onboarding to first useful mission.
Acceptance criteria:
- goal or interview intent is captured
- primary context remains `interviews`
- first mission is specific, not generic
- assistant responses stay short and coach-like
- there is no generic fallback leak
- the user receives a useful correction or sharper answer
- session completes cleanly
### Gate 2: Evidence Creates Session 2
The system stores enough evidence to make the next session feel continuous.
Acceptance criteria:
- baseline answer or key user answer is persisted
- corrections and weak spots are tied to session evidence
- next mission is derived from evidence
- home or session summary makes the next task clear
- replay by `session_id` shows the path from input to next mission
### Gate 3: Human Signal Exists
At least one real user shows return intent.
Acceptance criteria:
- user completes `session 1`
- user returns to `session 2` within 7 days or explicitly schedules it
- user says why the next mission is relevant
- at least one cold or weak-tie user is included before calling the signal strong
### Gate 4: Voice Benchmark Before Voice Integration
Only after the previous gates does voice provider work become a candidate.
Acceptance criteria:
- current text baseline has a report
- current voice baseline has a report
- candidate provider is compared on the same scenarios
- result includes latency, cost, product correctness, and human audio ratings
- integration is justified by product impact, not novelty
## Workstreams
### 1. Text-First Product Loop
Goal: make typed/composer sessions the default path for validation.
Work items:
- make the interview flow coherent without relying on STT/TTS
- keep responses short, guided, and mission-bound
- improve answer correction quality
- make next mission explicit after each session
- remove any user-facing ambiguity between chat, lesson, mission, and interview prep
Done when:
- a pilot can use text mode without the operator explaining the product
- session output is specific enough to discuss in a debrief
- product evals cover the main interview path
### 2. Evidence and Continuity
Goal: make the data loop the product's memory moat.
Work items:
- verify memory/evidence persistence on real DB
- ensure `next_mission_choice` reflects observed learner gaps
- make session replay reliable by `session_id`
- align program snapshot, session evidence, and mission state
- prevent duplicate or stale completion signals
Done when:
- a session can be replayed end-to-end
- session 2 uses session 1 evidence without manual intervention
- a failed session can be diagnosed from artifacts, not guesswork
### 3. Product Evals
Goal: keep the product from regressing while we tune behavior.
Work items:
- keep `scripts/run_product_synthetic_eval.py` as the main text/product gate
- add or refine scenarios around interview self-intro and project explanation
- treat eval failures as product regressions unless clearly flaky
- keep STT benchmark separate from product benchmark
Done when:
- text-first core scenarios pass
- failures point to specific product contracts
- evals do not require voice to validate the product loop
### 4. Discovery and Pilots
Goal: collect real signal before expanding scope.
Work items:
- run discovery calls before adding large features
- use the current templates in `!DOC/operations`
- classify failures consistently
- track whether users need speaking pressure, answer structure, or both
Failure classes:
- weak mission relevance
- generic coaching
- bad answer correction
- unclear next step
- runtime failure
- voice/STT friction
Done when:
- there are enough notes to choose `go / narrow / pivot / kill`
- at least one user has a credible session 2 signal
### 5. Voice Benchmark, Parked Until Gates
Goal: prepare a measured path for Inworld/OpenAI/Hume/PersonaPlex without letting voice drive the roadmap.
Work items:
- define a small voice model benchmark after text gates are passed
- compare provider bundles, not isolated marketing claims
- measure product correctness, latency, cost, and human audio quality
- include Russian/English mixed scenarios
Candidate bundles later:
- current baseline: `chat_v2 + current STT + edge-tts`
- text control: composer input, no audio dependency
- OpenAI Realtime
- Hume EVI
- Inworld Realtime API
- Inworld TTS-only
- PersonaPlex
Voice benchmark non-goals for now:
- no deep Inworld integration during text-loop hardening
- no provider shootout before baseline reports
- no voice-first redesign
- no voice moat claim without retention or human-rating evidence
## Immediate Task Board
Use this list as the default next-work queue unless the user gives a newer instruction.
### Now
- Apply and verify the `memory_kind` enum migration on the real dev database.
- Run the text-first product synthetic eval for interview scenarios.
- Verify that composer/typed flow can complete onboarding -> mission -> evidence -> next mission.
- Inspect one replay bundle by `session_id` after a live or synthetic session.
- Tighten the session 2 continuity path if replay shows stale or missing evidence.
### Next
- Add a focused product eval for `interview_self_intro_gap` if current coverage is not enough.
- Add a focused product eval for `project_tradeoff_story` as an interview-supporting artifact.
- Improve assistant correction quality where the eval or pilot replay shows generic feedback.
- Update pilot debrief template with failure classification if missing.
- Record one baseline report for the current text-first flow.
### Later
- Define `VOICE_MODEL_BENCHMARK_PLAN.md` only after text gates are stable.
- Implement a voice benchmark runner only after the plan has stable scenarios.

## Anti-Roadmap: Do not work on generic tutor, vocab drill, grammar rescue, broad workplace/project, voice as mainline, detached leaderboards, graph expansion, or new UI without session support.
