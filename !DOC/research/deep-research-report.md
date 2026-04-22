# EnglishFriend Vision and Architecture - 2026-04-10

Status: Canonical long-form product and architecture vision  
Operational source of truth: [../operations/CURRENT_PRODUCT_STATE.md](../operations/CURRENT_PRODUCT_STATE.md)

## How To Use This Document

Use this file when you need the current long-form answer to:

- what EnglishFriend is building
- what architecture we are intentionally converging toward
- what we refuse to turn the product into
- what the near-term execution order should be

Do not use this file for day-to-day continuity updates.  
Those belong in [../operations/CURRENT_PRODUCT_STATE.md](../operations/CURRENT_PRODUCT_STATE.md).

## Executive Summary

EnglishFriend should stay a vertical career-English coach for Russian-speaking ML/AI and adjacent IT specialists preparing for international work.

The correct architecture is:

- product identity: vertical coach
- runtime style: bounded coach with agentic internals
- memory style: DB-first hybrid memory, not filesystem memory as the source of truth
- voice strategy: improve observability and STT quality first, not rewrite around a new realtime framework immediately

The product moat is not "AI that can talk" and not "agent with tools".  
The moat is a measurable career loop:

`goal brief -> baseline -> program -> mission -> live session -> evidence -> next mission`

As of 2026-04-10, the backend already owns the critical control plane:

- product state and mission routing
- shared voice session lifecycle
- explicit mission contract for primary voice sessions
- Qwen `final-only` compatibility safeguards
- compact learner profile plus mission-scoped memory

The next architecture work should prioritize:

1. observability across every live voice layer
2. repeatable live smoke scenarios
3. STT benchmark and replacement path, including browser-side candidates
4. resilience sidecars that improve reliability without stealing focus
5. pronunciation upgrade after STT evidence
6. only then a decision on `Pipecat` or `LiveKit Agents`

## Product Position

### What EnglishFriend Is

EnglishFriend is:

- a career-English coach
- optimized for Russian-speaking technical specialists
- focused on interviews, project walkthroughs, and workplace communication
- built around one guided path instead of a toolbox of unrelated modes
- designed to produce evidence, not just conversation

### What EnglishFriend Is Not

EnglishFriend is not:

- a general-purpose assistant
- a generic voice tutor
- a user-facing skill marketplace
- an "agent console" product
- a realtime voice product whose main value is the conversation itself

### Core Product Promise

The product promise should remain:

- understand the user's real career target
- estimate readiness relative to that target
- route the next useful mission
- collect evidence from real sessions
- adapt the next step from that evidence

This is the real product loop.  
Voice, memory, and agent patterns only matter if they make this loop more reliable.

## Moat

EnglishFriend's moat is not a generic AI tutoring stack.

The moat should be defined as:

- a vertical career-English operating loop
- for Russian-speaking IT/ML specialists
- with weak-to-mid spoken English
- targeting international jobs, interviews, project walkthroughs, and workplace communication

The real moat is:

`career target -> baseline -> mission -> live session -> evidence -> next mission`

This moat has four parts:

### 1. Career-State Precision

The system should understand:

- target role
- target market or company context
- current stage of readiness
- blockers relative to that target

This is stronger than generic "user profile" memory because it is goal-relative.

### 2. Pedagogy Under Weak Spoken English

The system should coach people who:

- speak imperfectly
- hesitate
- mix languages
- lose structure under pressure

This is not solved by better LLMs alone.  
It requires stage-aware, low-pressure, deterministic coaching design.

### 3. Evidence-Driven Adaptation

The product should not only remember facts.  
It should accumulate evidence about:

- what the learner can already say
- what still breaks under pressure
- which mission improved what
- what next step is actually justified

This is stronger than generic memory because it changes program routing.

### 4. Audience-Specific Data Flywheel

If EnglishFriend keeps focus, it can accumulate the hardest-to-copy layer:

- recurring patterns of Russian-speaker mistakes
- accent and STT failure modes
- interview and project-story bottlenecks for ML/IT specialists
- mission designs that actually move readiness for this audience

This is the long-term moat.  
Voice stack, agent shell, and generic RAG are not.

## Anti-Roadmap

To protect the moat, EnglishFriend should explicitly avoid several tempting expansions.

### What We Are Not Building

We are not building:

- a general AI tutor for every subject
- a notebook-centric learning OS
- a research workspace
- a generic upload-anything RAG tutor
- a user-facing multi-agent platform
- a plugin or skill marketplace
- a voice assistant whose main value is realtime conversation itself

### What We Refuse To Treat As Moat

These are useful infrastructure layers, but not defensible product identity:

- voice transport and realtime runtime
- multi-agent orchestration itself
- document upload and retrieval
- long-context memory by itself
- generic knowledge graphs
- generic tutor chat quality

### Product Drift Risks

The biggest strategic risks are:

- breadth drift toward a "learning platform"
- agent theater instead of measurable learner progress
- over-investment in voice polish before pedagogy and STT quality
- memory accumulation without evidence-linked adaptation

If a feature improves only breadth and not the career loop, it should be deprioritized.

## Current Architecture As Of 2026-04-10

### What Is Already Real In Code

The current codebase already has the right structural pieces:

- a product-state engine centered on `learning_plan.roadmap`
- `ProgramSnapshot` as the main user-facing aggregation layer
- shared voice bootstrap and persistence for `/chat/v2` and `/realtime`
- explicit mission metadata wiring from snapshot to voice session init
- a modular experimental voice runtime behind `REALTIME_RUNTIME_ENABLED`
- bounded LangGraph coaching logic for onboarding, learning, and session end
- Qwen `llama_cpp` compatibility with `final-only` behavior
- a DB-first hybrid memory layer with:
  - raw stored memories
  - compact learner profile summary
  - mission-scoped memory context
  - lightweight request-time self-healing

### What Is Still Weak

The current weak points are mostly architectural and product-execution related, not "missing one better model":

- browser Vosk is still the main STT bottleneck
- live voice debugging is not yet layered enough
- `/chat/v2` still carries legacy endpoint complexity
- legacy and premium voice paths are not yet fully aligned
- memory consolidation is still request-time only, not periodic
- pronunciation remains heuristic and transcript-based
- cloud LLM resilience is still narrow and effectively centered on `Groq -> llama.cpp`
- the FSRS layer still uses the current Python scheduler line and has not been deliberately re-evaluated for newer or Rust-backed paths
- product discipline still has to be actively protected against horizontal tutor/platform drift

## Four-Layer Model

EnglishFriend should be reasoned about as four layers.

### 1. Voice and Transport Layer

This layer includes:

- WebSocket transport
- STT
- turn detection
- interruption handling
- TTS
- optional future WebRTC runtime

Rule:

- treat this as replaceable infrastructure
- do not confuse transport quality with product differentiation

### 2. Coach Runtime Layer

This layer includes:

- bounded session agent
- stage-aware pedagogy
- mission scaffolding
- lexical rescue
- low-signal and fallback behavior

Rule:

- one session should stay inside one mission boundary
- the runtime is a coach, not an open-ended autonomous assistant

### 3. Product State Layer

This layer includes:

- goal brief
- baseline and proficiency profile
- program plan
- mission selection
- interview pack
- evidence and progress state

Rule:

- this remains the source of truth for product behavior
- LLM output must not directly own state transitions

### 4. Memory and Control Plane Layer

This layer includes:

- compact learner profile
- mission memory context
- internal skill manifests
- guardrails and write gating
- evaluation and observability hooks

Rule:

- memory and skills should reinforce product routing and pedagogy
- they must not become a second product state system

## Pedagogy Is The Product Core

The main product differentiator is not the presence of voice.  
It is the quality of pedagogical control under weak spoken English.

### Desired Pedagogical Behavior

Early career missions should feel:

- simple
- staged
- confidence-building
- corrective without being overwhelming

That means:

- short scaffolded questions first
- deterministic ladders for early `project_walkthrough`, `hr_intro`, and `workplace_update`
- lexical rescue when the user does not understand a word
- lower pressure before STAR, architecture trade-offs, or deeper project framing

### Why This Matters

Without this layer, better STT or better TTS only creates a smoother version of the wrong coach.

The product should sound less like:

- a generic interviewer
- a smart explainer
- a broad assistant

and more like:

- a focused speaking coach who knows what the user is trying to achieve next

## Memory Architecture

The correct memory architecture is hybrid and DB-first.

### 1. Raw Session Memory

This is the storage layer:

- transcripts and conversation history
- extracted memories
- Qdrant semantic retrieval
- learning plan state
- evidence and interview history

This layer is raw input, not the thing we should inject directly into every prompt.

### 2. Learner Profile Summary

This is the compact stable layer.

It should contain only durable, prompt-worthy facts such as:

- target role and market
- current level and confidence
- current stage
- active mission family
- current blockers
- recurring error patterns
- most relevant work/project context
- latest evidence summary

This is our analogue to compact memory, but it is server-owned and derived from product state plus memory, not stored as a root markdown file.

### 3. Mission-Scoped Memory

This is the session layer.

Each voice session should receive:

- explicit mission contract
- learner profile summary
- only a few relevant memories
- only the evidence and context needed for that mission

This keeps context bounded and reduces drift.

### 4. Self-Healing

The current minimum self-healing should do:

- relative date normalization
- duplicate dropping
- surfacing memory conflicts before they pollute compact profile context

The later, stronger version should add:

- periodic consolidation job
- contradiction resolution by recency and confirmation strength
- profile refresh after important product events

### What We Borrow From Claude-Code-Like Patterns

Useful patterns:

- compact memory entrypoint
- bounded context per task
- pruning and consolidation
- strict distinction between durable memory and transient logs

What we do not borrow:

- filesystem memory as primary source of truth
- user-facing agent console
- open-ended tool-use identity as the product

## Voice Architecture And Decision Tree

### Current Voice Position

Right now the correct approach is:

- keep the modular runtime work
- keep the shared session lifecycle
- keep mission contract as the source of truth for primary sessions
- stop treating a new voice framework as the immediate solution

The next issue is not "which framework is coolest".  
The next issue is "can we diagnose the live pipeline precisely enough to make the right replacement".

### Decision Tree

#### Step 1: Observability First

Before changing the runtime, instrument the live path end to end:

- transport
- STT
- turn detection
- bootstrap
- pedagogy/runtime
- LLM
- TTS
- memory retrieval and persistence
- session completion and evidence writes

The goal is to make every live failure attributable to a layer.

#### Step 2: Live Smoke Harness

Keep a stable 3-session smoke set:

1. first-run goal and baseline
2. noisy foundation mission
3. clean foundation mission

Each run should capture:

- transcript
- frontend console
- backend logs
- metrics snapshot

#### Step 3: STT Benchmark Before Runtime Rewrite

Compare:

- current browser Vosk
- backend `faster-whisper`
- backend `Parakeet-TDT`
- browser-side `Whisper-small` / WebGPU via Transformers.js

Evaluate them against product signals:

- target-role capture
- recent-project capture
- fallback frequency
- noisy-turn recovery
- latency to final transcript
- technical term accuracy
- device stability and bundle/runtime impact for browser-side options

#### Step 4: Pronunciation Upgrade

After STT, the next practical upgrade is pronunciation:

- replace or augment heuristic pronunciation with a stronger provider
- keep it tightly connected to evidence and coaching, not as a separate toy metric
- favor phoneme-level or alignment-based scoring over another transcript heuristic

#### Step 5: Runtime Choice Only After Evidence

Only after instrumented live data and STT results should we decide:

- `Pipecat` if we want pipeline-first composition and modular voice orchestration
- `LiveKit Agents` if we want a stronger WebRTC/runtime substrate and built-in room semantics

The runtime decision should be justified by measured UX gain, not architectural aesthetics.

## Near-Term Plan

The near-term sequence should be explicit.

### Critical Path

#### 1. Observability Pass

Add per-turn, per-layer visibility for live sessions.

Success means:

- every problematic live turn can be traced to a layer
- logs, metrics, and traces agree on the same request and session identifiers

#### 2. Live Retest

Run the 3 live scenarios again on the current stack.

Success means:

- no mission drift
- no empty assistant turns
- correct setup handoff
- stable bounded coaching under noisy speech

#### 3. STT Benchmark And Replacement Track

Prototype backend STT while keeping the product loop unchanged.

Current recommendation:

- first backend candidate: `faster-whisper`
- second benchmark candidate: `Parakeet-TDT`
- third benchmark candidate: browser-side `Whisper-small/WebGPU`

This is still a benchmark, not a commitment to ship browser Whisper as the default fallback.

### Parallel Sidecars

#### 4. LLM Resilience Track

Add a cloud fallback lane that improves reliability without changing the product loop.

Current recommendation:

- keep the mainline provider logic stable
- explicitly evaluate `Cerebras` as a low-effort cloud fallback
- converge toward `Groq -> Cerebras -> llama.cpp` instead of relying on only one cloud fast path plus CPU fallback

#### 5. FSRS Layer Review

Revisit the vocabulary scheduling layer deliberately instead of assuming the current Python path is already optimal.

Current recommendation:

- keep the existing FSRS flow unchanged until the review is done
- compare the current `py-fsrs` line with a Rust-backed path such as `fsrs-rs-python`
- decide from product needs: short-interval quality, per-user tuning cost, and operational simplicity

### After STT Evidence

#### 6. Pronunciation Track

Upgrade pronunciation after the STT path is more reliable.

Current recommendation:

- move from transcript-only heuristic scoring toward an audio-backed phoneme/alignment family
- inspect `ai-pronunciation-trainer` or an equivalent open phoneme scorer first
- treat this as a candidate family, not yet as a locked dependency

#### 7. Runtime PoC

Do not start here.  
Do this only if the earlier steps show that transport/runtime, not pedagogy or STT, is the next true bottleneck.

## Cost Model

The voice stack should be judged not only by quality but by maintenance shape.

### Browser Compute

- low server cost
- good resilience when backend capacity is weak
- higher device variability
- bundle and runtime constraints matter

### Server-Side Self-Hosted

- predictable product control
- lower marginal inference cost on owned hardware
- higher operations and deployment burden
- debugging and scaling are our problem

### Cloud Inference

- easiest resilience and fastest iteration
- external latency and limits still matter
- costs can spike if a fallback path becomes the main path

Rule:

- use the cheapest layer that still protects the learning loop
- do not choose a stack only because it is architecturally elegant

## Competitive Landscape

EnglishFriend still has a differentiated wedge, but the surrounding landscape matters.

### DeepTutor Teardown

`DeepTutor` is a useful warning signal, not a product template for EnglishFriend.

As of April 2026, DeepTutor presents a broad "AI-powered personalized learning assistant" with:

- multi-agent problem solving
- knowledge base and document Q&A
- guided learning
- exam-style practice generation
- deep research
- notebook and persistent learning artifacts

This confirms that horizontal tutoring breadth is becoming easier to assemble.

What that means for EnglishFriend:

- if we stay vertical, DeepTutor is not the same product
- if we copy that width, we lose our wedge and become easier to compare against broader platforms

What we can borrow:

- cleaner capability boundaries
- stronger persistence and artifacts
- better learning profile consolidation

What we should not borrow:

- all-in-one learning workspace identity
- document/RAG-first product framing
- broad research or notebook surface as the core product

This is exactly why EnglishFriend should stay a vertical career-English coach.

### Voice Infrastructure

- `Pipecat` matters as a modular pipeline reference
- `LiveKit Agents` matters as a WebRTC/runtime reference

### Interview And Speaking Products

- interview simulators matter as UX references for guided question flow
- generic speaking apps matter mainly as latency and polish baselines, not as product identity models

### Learning Architecture References

- adaptive learning and multi-agent tutor systems are useful as internal architecture references
- they are not a reason to turn EnglishFriend into a user-facing agent platform

### External Signals That Matter

- `DeepTutor` updates in April 2026 reinforce that horizontal tutoring stacks are commoditizing quickly.
- OpenAI's Praktika case study from January 22, 2026 reinforces that measurable adaptation and progress-linked coaching matter more than raw agent breadth.
- Hugging Face `Transformers.js v4` from February 9, 2026 reinforces that browser-side WebGPU speech tooling is now serious enough to benchmark, but still remains infrastructure rather than moat.

## Technology Watchlist

These are worth monitoring, but none of them should displace the near-term critical path.

- browser-side ASR on WebGPU, especially `Whisper-small`
- `Pipecat`
- `LiveKit Agents`
- `Sesame CSM` and related speech-native OSS
- emotion-aware voice systems such as `Hume EVI`
- Rust-backed FSRS optimization paths
- stronger open pronunciation scorers based on phoneme alignment

## Long-Term Direction

The long-term goal is not "be the best assistant with voice".  
The long-term goal is:

- best voice-first career-English coach for Russian-speaking technical specialists

That requires:

- stronger mission design
- stronger evidence loop
- more accurate speech understanding
- better memory consolidation
- reliable near-realtime conversation when it measurably helps the learning loop

The architecture should continue moving toward:

- bounded coach runtime
- replaceable voice infrastructure
- code-owned pedagogy and state transitions
- memory as a compact control plane
- emotion-aware coaching as a later watchlist direction, only if it improves frustration handling or confidence-sensitive coaching in a measurable way

## Decision Rules

Use these rules when deciding what to build next.

### Build It If

It makes EnglishFriend better at:

- sharpening a career goal
- assessing readiness
- routing a mission
- coaching one high-value speaking task
- producing useful evidence
- adapting the next step
- strengthening the vertical career-English loop for Russian-speaking IT/ML specialists

### Do Not Prioritize It If

It mostly improves:

- generic assistant breadth
- agent theater
- plugin surface area
- multimodal novelty without impact on the learning loop
- realtime polish without evidence that it fixes a product bottleneck
- general tutoring breadth without improving career-state, pedagogy, evidence, or adaptation

## Related Documents

- Short strategic manifesto: [../strategy/HYBRID_COACH_AGENT_STRATEGY_2026-04-02.md](../strategy/HYBRID_COACH_AGENT_STRATEGY_2026-04-02.md)
- Operational continuity and latest status: [../operations/CURRENT_PRODUCT_STATE.md](../operations/CURRENT_PRODUCT_STATE.md)
- Technical history and older strategy comparisons: [../strategy/TECHNICAL_STRATEGY.md](../strategy/TECHNICAL_STRATEGY.md), [../STRATEGY.md](../STRATEGY.md)
- External references:
  - DeepTutor repo: https://github.com/HKUDS/DeepTutor
  - Praktika case study: https://openai.com/index/praktika/
  - Transformers.js v4: https://huggingface.co/blog/transformersjs-v4
