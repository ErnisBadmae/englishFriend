---
last_updated: 2026-04-22
---

# Roadmap

This roadmap is an execution appendix to:
[../MASTER_PROJECT_VIEW_2026-04-22.md](../MASTER_PROJECT_VIEW_2026-04-22.md)

This is the active delivery roadmap for the current wedge.

North star:

`career state -> evidence -> adaptive missions`

Supporting architectural map:
[../architecture/TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md](../architecture/TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md)

## Intended Outcome

Over the next 6-8 weeks, EnglishFriend should become:

- demo-stable on the main guided path
- stronger on real weak-English speech input
- better at routing the next mission from actual session evidence
- more complete on the wedge through vacancy + interview + project story artifacts

This cycle is not about becoming a broader tutor.
It is about making the current moat legible and repeatable.

## Architectural Thesis

The product should be built as:

- a vertical career-English coach externally
- a bounded coach runtime internally
- a career-state and evidence engine at the center
- a replaceable voice and STT layer underneath

Decision rule:

- `Parakeet` is the next mainline STT bet
- `PersonaPlex` remains a premium or advanced delivery lane
- the moat comes from state, pedagogy, evidence, and adaptation, not from a voice stack alone

## Track 1: Demo Readiness

Timeline: Weeks 1-2

Goal: remove the remaining blockers that make live product demos fragile.

Scope:

- harden post-session gamification so `xp_events` writes do not fail on missing monthly partitions
- harden post-session memory extraction so transient provider connection failures do not poison the whole run
- verify main frontend browser behavior for first greeting audio, farewell audio, and redirect timing

Acceptance:

- no `xp_events` partition failure on the mainline session end path
- no fatal post-session failure from one transient memory extraction error
- one real browser smoke pass for `workplace`, `interview`, and `project`

## Track 2: Backend STT With Parakeet

Timeline: Weeks 2-4

Goal: improve the weakest part of the current loop, speech recognition under broken English.

Scope:

- keep browser Vosk as fallback
- add backend `ParakeetSTTProvider`
- expose a backend transcription lane through `/api/v1/voice/transcribe`
- let the frontend switch between browser STT and backend STT without changing product state logic
- benchmark capture quality on role, project, and technical-term signals

Acceptance:

- `Parakeet` beats browser Vosk on product metrics, not only generic WER
- p50 latency remains acceptable for guided sessions
- the default STT choice can be justified from live benchmark evidence

## Track 3: Evidence Loop Hardening

Timeline: Weeks 3-6

Goal: make the next mission depend on actual repeated weakness or improvement.

Scope:

- extend `session_evidence` with richer fields such as `outcome_score`, `weakness_tags`, `improvement_tags`, and `adaptation_hint`
- route missions by `repeat` vs `advance`, not only by stage default
- keep weakest-area routing for interview readiness
- expose `adaptation_reason` in the Home mission card so the user sees why this mission is next

Acceptance:

- repeated weakness leads to a narrower repeat drill
- visible improvement advances the learner to the next step
- fallback stays stable when evidence is weak or mixed

## Track 4: Wedge Completion Through Project Story Pack

Timeline: Weeks 4-8

Goal: move from a 3/5 wedge to a more complete career loop.

Scope:

- capture raw `project_notes`
- generate `project_story_pack`
- surface it in the snapshot and Home
- feed weak spots from the project story back into session evidence and mission routing

Acceptance:

- vacancy upload, interview pack, project notes, and project story pack work as one guided path
- weak project storytelling produces future targeted missions

## What We Are Explicitly Not Doing

Do not spend this cycle on:

- generic tutor flows
- notebook or research workspace surfaces
- user-facing multi-agent tooling
- a full realtime stack rewrite
- FSRS as the headline feature
- graph or vector infrastructure productization as a user-facing bet

## Verification Gates

Use these gates to keep the roadmap honest.

- browser smoke: one real guided run for `workplace`, `interview`, and `project`
- STT benchmark: compare browser Vosk vs backend `Parakeet` on role/project/technical-term capture
- backend tests: repeat vs advance routing, session evidence, XP writes, and voice/session contracts stay green
- frontend build: Home and voice session flows compile with the new mission and STT paths

## Exit Criteria For This Cycle

This roadmap is successful when:

- the main demo path is stable enough to show repeatedly
- users can feel the STT improvement in real sessions
- next missions are visibly tied to prior weakness or improvement
- the wedge is clearer than "AI voice tutor" and closer to "career-English operating loop"

For current operational status, see [../operations/CURRENT_PRODUCT_STATE.md](../operations/CURRENT_PRODUCT_STATE.md).

Если коротко про следующий шаг: сначала live browser smoke и benchmark browser Vosk vs  
 backend Parakeet, потом background memory consolidation и richer speaking evidence (pace/
pause, позже pronunciation/audio scoring). Именно эта последовательность усиливает moat, а
не уводит продукт в generic tutor breadth.
