---
last_updated: 2026-04-22
status: Target architecture appendix aligned to the master project view
---

# Target Product Architecture

Canonical top-level project view:
[../MASTER_PROJECT_VIEW_2026-04-22.md](../MASTER_PROJECT_VIEW_2026-04-22.md)

EnglishFriend should converge toward a vertical career-English operating loop for Russian-speaking technical specialists.

The core idea is simple:

- voice is a delivery layer
- evidence is the control layer
- adaptive mission routing is the product moat

## One-Screen Schematic

```text
Signals In
  text + voice + vacancy + project notes + prior sessions
        |
        v
Career State Engine
  target role + baseline + current stage + blockers + readiness
        |
        v
Mission Router
  stage default + weakest-area targeting + repeat vs advance logic
        |
        v
Session Runtime
  /chat/v2 or /realtime + bounded coach behavior + STT/TTS
        |
        v
Evidence Layer
  outcome score + error patterns + weakness tags + adaptation hint
        |
        v
Memory and Artifact Layer
  learner profile + interview pack + project story pack + relevant memory
        |
        v
Next Mission + Home Snapshot
  what to do next, why, and what changed
```

## Why This Architecture

The market is commoditizing around generic `voice + memory + tutor chat`.

That means EnglishFriend should not try to win on:

- generic voice assistant quality
- generic long-term memory
- generic tutoring breadth
- user-facing agent tooling

EnglishFriend should win on a narrower loop:

`career target -> baseline -> mission -> live session -> evidence -> next mission`

This architecture is correct because it keeps three things stable:

1. Product state stays server-owned and goal-relative.
2. Voice infrastructure stays replaceable.
3. Each session contributes structured evidence, not only chat history.

## The Three Layers That Matter

### 1. Experience Layer

This is what the user sees:

- Home
- vacancy upload
- interview pack
- project story pack
- one current mission
- one active voice or text session

Rule: the product should feel like one guided path, not a toolbox.

### 2. Career-State and Adaptation Layer

This is the real moat layer.

It should own:

- target role and market context
- baseline and current stage
- session evidence
- recurring weakness patterns
- repeat vs advance routing
- mission explanations shown to the user

In the current codebase, this is centered around:

- `LearningPlanService`
- `ProgramSnapshotService`
- `learning_plan.roadmap`
- `session_evidence[]`

Rule: LLM output may inform state, but it should not directly own state transitions.

### 3. Delivery and Runtime Layer

This is important, but it is not the moat.

It includes:

- `/chat/v2`
- `/realtime`
- browser Vosk
- backend Parakeet STT
- PersonaPlex or other premium voice lanes
- TTS
- observability and smoke harnesses

Rule: this layer should be replaceable without changing the career-state engine.

## Where The Moat Comes From

The moat is not a single model. It is the compounding effect of four linked assets.

### 1. Goal-Relative Career State

The system should know:

- what job the learner wants
- what part of the path is weakest
- what task is most useful next

This is stronger than generic user memory because it is anchored to a career target.

### 2. Pedagogy For Weak Spoken English

The product should work for users who:

- hesitate
- mix Russian and English
- lose structure under pressure
- cannot yet produce clean interview answers on demand

This requires bounded prompts, guided turn design, and safe fallback paths.

### 3. Evidence-Linked Adaptation

Each session should produce reusable evidence:

- what the user handled well
- what broke again
- whether performance improved
- whether the next mission should repeat or advance

This is the layer that separates EnglishFriend from a generic `ChatGPT wrapper`.

### 4. Audience-Specific Artifact Flywheel

The product should accumulate structured artifacts for one niche:

- vacancy context
- interview packs
- project story packs
- weakness tags for Russian-speaking technical specialists
- mission designs that actually improve readiness for this audience

This becomes harder to copy over time if the product stays focused.

## What Parakeet And PersonaPlex Mean In This Architecture

These two technologies solve different problems.

### Parakeet

`Parakeet` should be treated as the mainline STT upgrade path.

Why:

- it improves transcript quality for the core product loop
- it is benchmarkable against role, project, and technical-term capture
- it helps every guided mission, not only premium realtime UX
- it reduces the biggest current trust gap: "the product works, but hears me badly"

Recommendation: connect `Parakeet` first as the default backend STT lane beside browser Vosk.

### PersonaPlex

`PersonaPlex` should be treated as a premium or advanced delivery lane.

Why:

- it can improve full-duplex feel, premium UX, and cost control on owned hardware
- it is valuable once the core loop is already stable
- it does not, by itself, solve the main moat problem

Recommendation: keep `PersonaPlex` as an optional premium runtime path on top of the same career-state engine.

### Decision Rule

If the question is "what should we connect next to strengthen the moat?", the answer is:

1. `Parakeet` first
2. evidence loop hardening second
3. `PersonaPlex` later as a premium lane

## The Road To Moat

The moat is reached by stacking a few specific advantages in order.

```text
better goal capture
  ->
better baseline and stage placement
  ->
better mission routing
  ->
better session evidence
  ->
better repeat vs advance decisions
  ->
better learner outcomes
  ->
stronger niche-specific data and artifacts
```

This is why roadmap priorities should stay narrow.

## Architecture Rules

Use these rules when deciding what to build.

- Build features that improve goal precision, pedagogy, evidence, or adaptive mission routing.
- Treat STT, TTS, transport, and realtime runtime as infrastructure, not identity.
- Keep the product surface guided and narrow.
- Prefer new evidence fields over new generic modes.
- Prefer niche artifacts over general-purpose tutor breadth.

## Anti-Goals

Do not turn EnglishFriend into:

- a general tutor
- a notebook or research workspace
- a user-facing multi-agent shell
- a broad learning OS
- a product whose value is mostly "realtime AI voice"

## Current Execution Consequence

The correct near-term sequence is:

1. stabilize the demo path
2. move core STT from browser-only toward backend `Parakeet`
3. harden evidence-driven repeat vs advance routing
4. complete the wedge with `project_story_pack`
5. move memory consolidation into a background job
6. later add richer speaking evidence such as pace, pause, and stronger pronunciation scoring

## Related Docs

- Russian business and data-flow version: [./BUSINESS_AND_DATA_FLOW_RU_2026-04-21.md](./BUSINESS_AND_DATA_FLOW_RU_2026-04-21.md)
- Current state: [../operations/CURRENT_PRODUCT_STATE.md](../operations/CURRENT_PRODUCT_STATE.md)
- Active roadmap: [../strategy/ROADMAP.md](../strategy/ROADMAP.md)
- Long-form research and strategy context: [../research/deep-research-report.md](../research/deep-research-report.md)
