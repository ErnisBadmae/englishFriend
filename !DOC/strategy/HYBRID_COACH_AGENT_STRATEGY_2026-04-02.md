---
last_updated: 2026-04-02
status: active
---

# Hybrid Coach+Agent Strategy - 2026-04-02

## Summary

EnglishFriend should continue evolving on top of the current architecture.
The product should **not** pivot into a general-purpose assistant in the style of OpenClaw, ChatGPT, Claude, or Gemini.

The correct direction is:

- **external product identity**: vertical career-English coach
- **internal architecture style**: hybrid coach + agent
- **scope of agent behavior**: career loop only
- **markdown-driven config**: internal only, not user-facing navigation

In other words:

`keep the product vertical, make the internals more agentic`

## Strategic Decision

### What We Keep

We keep the core product loop as the center of gravity:

`goal brief -> baseline -> program -> mission -> live session -> evidence -> next mission`

We keep the current architectural strengths:

- LangGraph orchestration
- structured product state
- voice session runtime
- interview loop
- evidence loop
- adaptive next-mission routing

### What We Reject

We explicitly reject a rewrite into:

- a generic AI assistant
- a general plugin platform
- a user-facing skill marketplace
- an “agent console” product
- a voice assistant whose main value is realtime conversation itself

## Why Not OpenClaw As Product Identity

OpenClaw-like patterns are useful internally, but the product identity is wrong for EnglishFriend.

Reason:

- OpenClaw-style products compete horizontally
- big frontier assistants already dominate generic tool use, memory, and flexible voice interaction
- a general assistant framing would erase the current wedge
- it would make EnglishFriend easier to compare directly with products that have more scale, infra, and distribution

So the right move is:

- borrow the internal patterns
- reject the external identity

## What Big Players Already Commoditize

Large players increasingly cover:

- general tutoring
- voice conversation
- persistent memory
- multimodal interaction
- broad assistant workflows

This means EnglishFriend should not try to win on:

- “AI that talks to you”
- “AI agent with tools”
- “voice-first assistant”
- “markdown-configured automation”

Those are implementation layers, not the product moat.

## Real Moat

The product moat should remain:

1. **goal precision**
   - understand the learner’s real career target
2. **goal-relative baseline**
   - assess current ability relative to that target
3. **career-specific program**
   - sequence what to train next
4. **evidence loop**
   - show what improved and what still blocks the goal
5. **domain context**
   - interviews, project walkthroughs, workplace communication
6. **Russian-speaker-aware coaching**
   - recurring error patterns and correction strategy

## Product Identity

EnglishFriend should be positioned as:

**career English coach for Russian-speaking ML/AI/IT specialists targeting international work**

Not:

- AI tutor for everyone
- voice chat companion
- productivity assistant
- general career bot

## Architecture Direction

The architecture should be treated as 3 layers.

### 1. Conversation Runtime

This is infrastructure.

Includes:

- Vosk and transcript-review flow
- PersonaPlex
- websocket chat endpoints
- TTS / STT / transport details

Rule:
- improve reliability and replaceability
- do not confuse this layer with the product itself

### 2. Product State Engine

This is the core.

Includes:

- goal brief
- proficiency profile
- program plan
- mission routing
- interview results
- session evidence
- next-step adaptation

Rule:
- this remains the main product logic and source of truth

### 3. Internal Skill Layer

This is the control plane for coach behavior.

Includes:

- markdown-backed skill manifests
- mode instructions
- career-loop skills
- tool boundaries / registries

Rule:
- internal only
- not a user-facing agent console
- not a second source of truth for learner state

## What Agentic Skills Are Worth Building

Only build skills that deepen the career-learning loop.

High-value internal skills:

- vacancy analysis
- resume gap analysis
- project story extractor
- interview pack builder
- follow-up planner
- career-context memory

Low-value / deprioritized:

- generic browsing assistant
- wide productivity tooling
- arbitrary external tool integrations
- broad life-assistant capabilities

## Markdown Strategy

Markdown should be used as:

- internal instruction manifests
- skill descriptions
- prompt/policy control plane

Markdown should not be used as:

- user-facing navigation
- product state storage
- a replacement for backend business logic

## Vosk / PersonaPlex Position

These stay in the stack, but as infrastructure.

### Vosk

- keep as cheap/default path
- continue transcript review for setup and baseline
- do not build the entire strategy around browser STT

### PersonaPlex

- keep as experimental or premium runtime path
- useful for voice polish and latency experiments
- not the core moat

## What To Build Next

The next product work should keep strengthening the vertical loop, not broadening the platform.

Priority order:

1. make first-run onboarding and baseline crystal clear
2. make Home show one obvious next action
3. let vacancy/resume inputs sharpen the goal brief
4. deepen interview and project-story coaching
5. improve evidence and evals

## What Not To Build Next

Do not prioritize:

- full OpenClaw-style rewrite
- multi-channel platform expansion
- user-facing skill browser
- generic assistant UI
- platform complexity without clear product gain

## Decision Rule Going Forward

For every new idea, ask:

**Does this make EnglishFriend a better career-English coach for international ML/AI/IT roles?**

If the answer is no, it should not be a near-term priority.

