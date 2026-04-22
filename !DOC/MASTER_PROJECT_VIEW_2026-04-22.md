---
last_updated: 2026-04-22
status: Canonical master view of product, architecture, and execution
---

# EnglishFriend Master Project View

This is the single top-level document for the project.

Use it when you need one coherent answer to:

- what EnglishFriend is
- where the moat comes from
- how the product loop works
- what architecture we are converging toward
- how current execution should be prioritized

Operational continuity still lives in:
[operations/CURRENT_PRODUCT_STATE.md](./operations/CURRENT_PRODUCT_STATE.md)

## Product Thesis

EnglishFriend is a vertical career-English coach for Russian-speaking ML/AI and adjacent IT specialists.

It is not:

- a generic tutor
- a notebook workspace
- a user-facing agent shell
- a voice product whose value is mainly realtime conversation

The user problem is not “I do not know English” in the abstract.
The real problem is:

- I have a career target
- my spoken English collapses under pressure
- I fail interviews, project walkthroughs, or workplace communication because I sound less clear than I actually am

## Moat

The moat is:

`career state -> evidence -> adaptive missions`

Not:

- voice alone
- long-term memory alone
- agents alone
- graph/vector infra alone

The moat compounds through four assets:

1. Goal-relative career state
2. Pedagogy for weak spoken English
3. Evidence-driven adaptation
4. Audience-specific artifact flywheel

## Canonical Product Loop

```text
Signals In
  text + voice + vacancy + project notes + prior sessions
        |
        v
Career State Engine
  target role + baseline + stage + blockers + readiness
        |
        v
Mission Router
  first useful mission + repeat vs advance + adaptation reason
        |
        v
Session Runtime
  bounded guided session via text/voice
        |
        v
Evidence Layer
  outcome_score + weakness_tags + error_patterns + adaptation_hint
        |
        v
Artifacts + Memory
  learner profile + interview pack + project story pack + relevant memory
        |
        v
Program Snapshot
  what changed, what is next, and why
```

Canonical rules:

- `primary_context` is the source of truth for the first useful mission
- transcript alone is not progress
- progress appears only when transcript is turned into structured evidence
- voice is a delivery layer; evidence is the control layer

First useful mission contract:

- `interviews` -> `foundation_speaking_drill`
- `workplace_communication` -> `stakeholder_explanation_drill`
- `project_walkthrough` -> `technical_project_walkthrough`

Secondary contexts can shape wording and later routing, but not override the first mission.

## Architecture

The system should be understood as three layers.

### 1. Experience Layer

What the user sees:

- Home
- current mission
- vacancy upload
- interview pack
- project story pack
- one active voice/text session

Rule: the product should feel like one guided path, not a toolbox.

### 2. Career-State and Adaptation Layer

This is the moat layer.

It owns:

- goal brief
- baseline / assessment
- program stage
- session evidence
- repeat vs advance logic
- mission explanations shown to the user

Rule: LLM output may inform state, but must not directly own state transitions.

### 3. Delivery and Runtime Layer

This is infrastructure.

It includes:

- `/chat/v2`
- `/realtime`
- browser Vosk
- backend Parakeet
- PersonaPlex premium lane
- TTS
- observability
- smoke/eval harnesses

Rule: runtime should be replaceable without rewriting the career-state engine.

## Data Truth-State

Current system truth-state:

- PostgreSQL = canonical product-state store
- Qdrant = best-effort retrieval enrichment
- Neo4j / Kafka / Debezium = async materialization contour

This means:

- bootstrap and mainline product behavior must work from PostgreSQL
- vector/graph layers may enrich, but must not block core product behavior

## Voice Strategy

Mainline decision:

- Parakeet is the next STT bet for the core moat loop
- PersonaPlex is a premium or advanced delivery lane, not the main moat bet

Decision order:

1. Parakeet
2. Evidence loop hardening
3. PersonaPlex later

## Execution Rules

The project should operate with explicit quality gates.

Release and quality rules:

- `mainline synthetic eval` is a release gate
- `expanded synthetic eval` is a regression radar, not a release blocker
- browser smoke is a milestone gate for voice UX
- STT benchmark is a gate for changing the mainline STT lane
- targeted backend tests gate routing/state changes

Decision rules:

- if a feature does not improve career state, pedagogy, evidence, or adaptive routing, it is not core priority
- if an infrastructure upgrade does not improve the product loop, it is secondary
- if routing changes, rerun synthetic eval
- if runtime changes, rerun browser smoke and session-end checks

Canonical development cadence:

1. Truth-state through eval
2. Routing/state fixes
3. Browser smoke
4. STT/runtime upgrades
5. Richer evidence
6. Premium voice sophistication later

## Near-Term Horizon (6-8 Weeks)

The current cycle should focus on:

- routing cleanup and product-loop integrity
- demo stability
- Parakeet validation
- evidence loop hardening
- wedge completion through vacancy + interview + project story artifacts

## Strategic Horizon (6-12 Months)

The strategic goal is not product breadth.

It is:

- a stronger career-state engine
- stronger evidence and adaptation
- richer speaking evidence
- better switching cost through state + artifacts + repeated outcomes

## Canonical Doc Topology

This file is the top-level project definition.

Other documents should play supporting roles:

- `operations/CURRENT_PRODUCT_STATE.md`
  - operational truth
- `architecture/TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md`
  - target architecture appendix
- `architecture/BUSINESS_AND_DATA_FLOW_RU_2026-04-21.md`
  - Russian schematic appendix
- `strategy/ROADMAP.md`
  - current delivery roadmap appendix
- `research/deep-research-report.md`
  - long-form research and vision appendix

Rule:

- appendices may deepen or operationalize this view
- they must not define a conflicting product thesis or execution order

## One-Sentence Project Definition

EnglishFriend is a vertical career-English operating loop:

`capture target -> run bounded mission -> extract evidence -> adapt next mission`

That loop, not generic voice chat, is the product.
