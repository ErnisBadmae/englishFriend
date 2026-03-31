---
last_updated: 2026-03-30
status: active
---

# Product Wedge Pivot - 2026-03-30

## Summary

EnglishFriend should not compete as a generic "AI that talks to you in English".
That category is now directly attacked by ChatGPT Voice, ChatGPT Memory, ChatGPT Study Mode, Claude mobile voice mode, Duolingo Video Call, Speak, Praktika, and Langua-like products.

The product decision made on 2026-03-30 is to focus the first durable wedge on:

- **Audience**: Russian-speaking IT professionals
- **Outcome**: international work readiness and interview/workplace English
- **Surface**: Telegram Mini App
- **Model**: B2C first

The moat is not voice itself. The moat is a product loop:

`assessment -> program -> mission -> live session -> evidence -> next mission`

## Independent Findings

### 1. Voice + memory alone is no longer enough

Large frontier assistants already cover:

- realtime or near-realtime voice interaction
- saved memory / cross-session personalization
- generic tutoring / explanation workflows
- broad multimodal flexibility

That means EnglishFriend loses if it is perceived as a flexible chatbot with voice.

### 2. The repo already had strong backend pieces, but weak product packaging

At the time of analysis, the repository already contained:

- voice websocket flows
- learning plan service
- assessment flow
- vocabulary spaced repetition via FSRS
- memory pipeline
- gamification services

But the user-visible loop was incomplete:

- frontend was effectively a single voice surface
- the Mini App did not expose a clear "what should I do today?" experience
- progress lived in backend structures more than in the product
- frontend build was broken

### 3. Neo4j / CDC / infra sophistication are not the first product moat

The architecture is technically ambitious, but the user does not buy:

- Kafka
- CDC
- Neo4j
- graph sync

The user buys:

- "I know my current level"
- "I know what to practice today"
- "I can see what got better"
- "This product helps me pass interviews and speak better at work"

## Why This Direction Was Chosen

### We explicitly rejected "AI mentor for everyone"

Reason:

- broad B2C English is too crowded
- generic conversational AI is already commoditized
- product positioning becomes weak and price pressure grows

### We explicitly chose the IT-career wedge

Reason:

- sharper pain than general fluency
- clearer willingness to pay
- easier to create differentiated scenario packs
- easier to measure progress in meaningful ways
- better fit with the current goal templates already present in the codebase

### We explicitly prioritized the product shell before advanced features

Reason:

- backend strengths were invisible to users
- the Mini App needed a coherent home/progress/review experience
- without a product shell, any new AI sophistication is hard to validate

## Product Decisions

### Primary Differentiators

EnglishFriend v1 should differentiate through:

1. **Structured program state**
   - goal
   - current level
   - mission for today
   - visible next step

2. **Persistent evidence**
   - recent sessions
   - recurring errors
   - due vocabulary
   - milestone progress

3. **Career-specific scenarios**
   - mock interviews
   - project walkthroughs
   - workplace communication

4. **Russian-speaker-aware correction**
   - recurring grammar/preposition/article patterns
   - personalized error loop instead of one-off corrections

### Explicit Deprioritization

The following items were intentionally deprioritized for this stage:

- complex reporting before the core loop is visible
- notifications as a primary retention lever
- graph-first product features
- emotional intelligence as a headline feature
- infra optimization as a product substitute

## Implemented On 2026-03-30

### Backend

- added `GET /api/v1/programs/{user_id}/snapshot`
- added vocabulary REST endpoints:
  - `GET /api/v1/vocabulary/{user_id}/stats`
  - `GET /api/v1/vocabulary/{user_id}/due`
  - `POST /api/v1/vocabulary/{user_id}/review`
- introduced `ProgramSnapshotService` to aggregate:
  - goal
  - latest assessment
  - mission recommendation
  - XP and streak
  - due vocabulary preview
  - top error patterns
  - milestones
  - recent session summaries

### Frontend

- replaced the single-screen Mini App flow with:
  - `Home`
  - `Session`
  - `Review`
  - `Progress`
- resolved Telegram user identity into internal user identity before calling product APIs
- surfaced the assistant greeting in the session UI
- fixed the frontend build issue around Piper CDN imports

### Runtime Resilience

- made prompt/template infra degrade safely when optional prompt models or Jinja2 are unavailable
- fixed model package import behavior so the server can import in a partial environment

## What This Unlocks

The project now has a visible product shell:

- a user can open the app and see a mission
- a user can see due review work
- a user can see progress state
- backend learning state is now visible without digging into internal tables

This is the minimum base needed to justify the next strategic implementation step.

## Next Build Step

The next high-value implementation step is:

## Career Interview Loop

Build a dedicated outcome loop for interview/workplace readiness:

- scenario selection
- interview session run
- structured scoring
- session outcome record
- historical comparison over time

Reason:

- it is the clearest product wedge against generic voice chat
- it aligns with the chosen IT-career segment
- it produces stronger retention and payment reasons than a generic dashboard

## Research Inputs Used

The following external references informed this pivot:

- OpenAI Memory FAQ
- OpenAI ChatGPT release notes
- Anthropic Claude mobile voice mode help article
- Speak official product site
- Praktika official product site
- Langua / LanguaTalk AI tutor product pages
- Duolingo Video Call announcement

These references were used to answer one specific question:

**"Can general frontier assistants or large language-learning products replicate a generic voice tutor?"**

Answer: yes.

Therefore the product must win on workflow, evidence, positioning, and domain-specific outcomes rather than on raw conversational ability alone.
