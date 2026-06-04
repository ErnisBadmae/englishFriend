# Self-Dogfood Target Architecture

Last updated: 2026-05-25
Status: active architecture target for the personal job-search preparation loop

## Purpose

This document defines the target architecture for using EnglishFriend as a real preparation system for the founder's own job search.

The goal is not to add a separate personal-product branch. The goal is to sharpen the main product loop through a real, high-pressure use case:

`prepare for the first remote hard-currency job in ML/AI/SWE-adjacent work`

This architecture should guide implementation until the self-dogfood loop is usable end to end.

## Product Loop

The target loop is:

```text
CareerProfile
  -> VacancyContext
  -> InterviewPack
  -> MissionPlan
  -> Text Session
  -> Evidence
  -> Updated InterviewPack
  -> Next Mission
```

Voice is still a delivery layer. The current product should work in text mode first.

## Clean Architecture Rule

The domain core must not depend on delivery mechanisms.

Inner layers:

- `CareerProfile`
- `VacancyContext`
- `InterviewPack`
- `MissionPlan`
- `Evidence`
- `ProgressSnapshot`

Outer layers:

- FastAPI endpoints
- WebSocket runtime
- STT/TTS providers
- frontend components
- scripts and operators
- external LLM providers

Practical rule: if a decision affects what the learner should practice next, it belongs closer to the domain core. If it affects how text or audio is transported, it belongs outside.

## Domain Concepts

### CareerProfile

Represents the candidate's job-search state.

It should eventually include:

- target role: ML engineer, AI engineer, LLM engineer, backend/ML-adjacent engineer
- target market: remote, international, hard-currency compensation
- current level and constraints
- strongest projects
- weak areas for interviews
- language constraints for Russian-speaking candidate
- current CV and portfolio links when available

Verification question:

`Can the system explain who this candidate is and what job they are preparing for without reading chat history?`

### VacancyContext

Represents one or more real vacancies.

It should include:

- raw vacancy text
- company and role title when known
- required skills
- repeated requirements across vacancies
- interview risks for the candidate
- vocabulary and answer patterns needed for this vacancy

Verification question:

`Can the system turn a vacancy into a concrete interview-prep mission?`

### InterviewPack

Represents reusable job-search artifacts.

It should include:

- self-introduction
- background story
- project walkthroughs
- tradeoff stories
- STAR stories
- recruiter-screen answers
- weak-answer backlog
- improved answer versions

Verification question:

`Can the candidate reuse the output outside the app in a real recruiter screen or interview?`

### MissionPlan

Represents what to practice next and why.

It should include:

- current mission
- reason for the mission
- success signal
- linked evidence
- repeat or advance decision
- expected artifact update

Verification question:

`Does the next mission clearly follow from the candidate's actual evidence?`

### Evidence

Represents what the candidate actually did in a session.

It should include:

- raw answer
- corrected answer
- gap tags
- language issues that matter for interview performance
- content issues such as vague impact, weak structure, missing tradeoff
- readiness signal
- next-action hint

Verification question:

`Can replay show why the system chose the next mission?`

### ProgressSnapshot

Represents the user-facing state.

It should answer:

- what I am preparing for
- what I practiced last
- what improved
- what is still weak
- what I should do next
- why this matters for my job search

Verification question:

`Can the candidate open the app tomorrow and immediately know what to do next?`

## Target Data Ownership

PostgreSQL remains canonical for product state.

Canonical state:

- career profile
- vacancy-derived context
- interview pack artifacts
- mission state
- session evidence
- progress snapshot

Derived or optional state:

- Qdrant retrieval enrichment
- Neo4j graph/materialized insights
- cached LLM summaries
- voice-specific telemetry

Rule: no derived store should be required to decide the next mission.

## Session Runtime Responsibility

The session runtime should do only three things:

- receive user input
- call the coach/agent with server-owned context
- emit transcript, feedback, and completion events

The runtime should not own:

- career state transitions
- next mission selection
- interview pack updates
- long-term evidence rules

If current code mixes these concerns, refactor only when it blocks the self-dogfood loop.

## First End-to-End Slice

The first slice should prove:

```text
Manual CareerProfile
  -> pasted VacancyContext
  -> generated Mission
  -> text session
  -> evidence saved
  -> next mission visible
```

No voice work is required for this slice.

No automatic vacancy scraping is required for this slice.

No new graph/vector architecture is required for this slice.

## Verification Gates

### Gate A: Profile Exists

Pass criteria:

- system has a stable candidate profile
- profile includes target role and job-search constraints
- profile can be loaded during session bootstrap

### Gate B: Vacancy Becomes Mission

Pass criteria:

- pasted vacancy creates or informs a mission
- mission is interview-prep specific
- mission has reason and success signal
- mission is not a generic English task

### Gate C: Session Produces Useful Evidence

Pass criteria:

- user answer is preserved
- correction is specific
- evidence includes weakness tags
- evidence can update interview pack or next mission

### Gate D: Session 2 Is Obvious

Pass criteria:

- next mission is visible
- next mission references prior evidence
- user can understand why the next task matters
- replay by `session_id` explains the transition

## Architecture Non-Goals

Do not prioritize:

- voice provider integration
- multi-provider voice benchmark
- UI redesign
- vacancy scraping
- public multi-user onboarding
- generalized coaching framework
- broad workplace English
- graph-driven routing
- new storage layer for product truth

## Implementation Bias

Prefer small vertical changes over broad refactors.

Good changes:

- add a minimal domain object if it clarifies ownership
- add a script or endpoint that supports self-dogfood verification
- improve evidence extraction for interview answers
- make next mission traceable
- add an eval scenario around a real job-search step

Risky changes:

- extracting a reusable framework before the self-dogfood loop works
- adding voice APIs before text evidence is useful
- rewriting runtime code without a failing gate
- creating generic abstractions for future users before the founder path works

## Relationship To Existing Documents

This document narrows the existing target architecture for the current real use case.

Use it together with:

- [TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md](./TARGET_PRODUCT_ARCHITECTURE_2026-04-21.md)
- [DATA_FLOW_TRUTH_STATE_2026-04-21.md](./DATA_FLOW_TRUTH_STATE_2026-04-21.md)
- [../strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md](../strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md)
- [../operations/SELF_DOGFOOD_30_DAY_PLAN_2026-05-25.md](../operations/SELF_DOGFOOD_30_DAY_PLAN_2026-05-25.md)
