# EnglishFriend Vision and Architecture - 2026-04-10

Status: Canonical long-form product and architecture vision  
Operational source of truth: [../operations/CURRENT_PRODUCT_STATE.md](../operations/CURRENT_PRODUCT_STATE.md)

## Executive Summary

Vertical career-English coach for Russian-speaking ML/AI/IT specialists. Architecture: bounded coach with agentic internals, DB-first hybrid memory, improve STT quality before rewriting voice runtime. Moat: career loop (goal -> baseline -> program -> mission -> session -> evidence -> next mission).

Current backend owns: product state, mission routing, shared voice session lifecycle, mission contract, Qwen final-only safeguards, learner profile + mission memory.

Near-term priorities: 1) observability 2) smoke scenarios 3) STT benchmark 4) resilience sidecars 5) pronunciation upgrade 6) then Pipecat vs LiveKit decision.

## Product Position

## Product Identity

A career-English coach for Russian-speaking IT/ML specialists preparing for international work.

What it is: interviews, project walkthroughs, workplace communication; one guided path; evidence-driven.
What it is not: general assistant, generic voice tutor, skill marketplace, agent console, realtime-conversation product.

Product loop: goal brief -> baseline -> program -> mission -> live session -> evidence -> next mission.
Voice, memory, and agent patterns only matter if they make this loop more reliable.

## Moat

Not generic AI tutoring. The moat is a vertical career-English operating loop for Russian-speaking IT/ML specialists with weak-to-mid spoken English, targeting international jobs and interviews.

Four parts:

1. **Career-State Precision** — goal-relative understanding of target role, market, readiness stage, blockers. Stronger than generic user profiles.
2. **Pedagogy Under Weak Spoken English** — stage-aware, low-pressure, deterministic coaching for people who hesitate, mix languages, lose structure under pressure. Not solvable by better LLMs alone.
3. **Evidence-Driven Adaptation** — accumulate evidence about what the learner can say, what breaks under pressure, which mission improved what, what next step is justified. Changes program routing.
4. **Audience-Specific Data Flywheel** — recurring Russian-speaker mistake patterns, accent/STT failure modes, interview bottlenecks for ML/IT, mission designs that move readiness. The long-term moat. Voice stack, agent shell, generic RAG are not.

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

1. **Voice/Transport** — WebSocket, STT, turn detection, interruption handling, TTS, future WebRTC. Replaceable infrastructure; not product differentiation.
2. **Coach Runtime** — bounded session agent, stage-aware pedagogy, mission scaffolding, lexical rescue, fallback. One session = one mission. Not open-ended assistant.
3. **Product State** — goal brief, baseline, program plan, mission selection, interview pack, evidence. Source of truth. LLM output must not own state transitions.
4. **Memory/Control Plane** — learner profile, mission memory, skill manifests, guardrails, eval hooks. Reinforce routing/pedagogy, not second product state.

Borrow from Claude-Code patterns: compact memory, bounded context, pruning, durable vs transient. Do not borrow: filesystem memory as primary truth, user-facing agent console, open-ended tool-use identity.

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

Hybrid, DB-first.

1. **Raw Session Memory** — transcripts, extracted memories, Qdrant retrieval, learning plan state, evidence. Raw input, not injected directly into prompts.
2. **Learner Profile Summary** — durable, prompt-worthy facts: target role/market, level, stage, active mission, blockers, error patterns, project context, latest evidence. Server-owned, derived from product state + memory.
3. **Mission-Scoped Memory** — per-session: explicit mission contract, profile summary, few relevant memories, evidence for that mission. Bounded context reduces drift.
4. **Self-Healing** — current: date normalization, duplicate dropping, conflict surfacing. Later: periodic consolidation, contradiction resolution, profile refresh on product events.

## Voice Architecture: Decision Tree

Keep modular runtime, shared session lifecycle, mission contract as truth. Next issue: diagnose live pipeline precisely.

1. **Observability** — instrument transport, STT, turn detection, bootstrap, pedagogy, LLM, TTS, memory, session completion. Every failure attributable to a layer.
2. **Live Smoke Harness** — 3-session set: first-run goal, noisy foundation, clean foundation. Capture transcript, console, logs, metrics.
3. **STT Benchmark** — compare browser Vosk, backend faster-whisper, Parakeet-TDT, browser Whisper-small/WebGPU. Evaluate: target-role capture, fallback freq, latency, technical term accuracy, device stability.
4. **Pronunciation** — after STT: replace heuristic with phoneme/alignment-based scoring connected to evidence.
5. **Runtime Choice** — only after evidence: Pipecat (pipeline-first) vs LiveKit Agents (WebRTC substrate). Justified by measured UX gain, not aesthetics.

## Near-Term Plan

Critical path: 1) Observability pass (per-layer visibility) → 2) Live retest (3 scenarios, no drift) → 3) STT benchmark (faster-whisper, Parakeet-TDT, Whisper-small/WebGPU).

Sidecars (parallel): 4) LLM resilience (Groq → Cerebras → llama.cpp) → 5) FSRS review (py-fsrs vs fsrs-rs-python) → 6) Pronunciation (phoneme/alignment family) → 7) Runtime PoC (only if earlier steps show transport/runtime is bottleneck).

## Cost Model

Browser: low server cost, good resilience, higher device variability. Server-side: predictable control, lower marginal cost, higher ops burden. Cloud: easy resilience, fastest iteration, cost spikes possible.

Rule: use cheapest layer protecting the learning loop. Not architectural elegance.

## Competitive Landscape

DeepTutor (broad multi-agent tutoring) confirms horizontal breadth is commoditizing. Borrow: cleaner boundaries, stronger persistence. Avoid: all-in-one learning workspace identity.

Voice infra: Pipecat (pipeline ref), LiveKit Agents (WebRTC ref). Interview simulators: UX reference for guided flows. Adaptive learning/multi-agent tutors: internal architecture refs only.

Key signals: DeepTutor updates (horizontal tutoring commoditizing), OpenAI Praktika (measurable adaptation > agent breadth), Transformers.js v4 (browser WebGPU speech serious enough to benchmark, but infrastructure not moat).

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

- Current strategy and moat: [../strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md](../strategy/TEXT_FIRST_MOAT_WORKPLAN_2026-05-20.md), [../strategy/MOAT_AND_METRICS_DOCTRINE_2026-06-11.md](../strategy/MOAT_AND_METRICS_DOCTRINE_2026-06-11.md)
- Operational continuity and latest status: [../operations/CURRENT_PRODUCT_STATE.md](../operations/CURRENT_PRODUCT_STATE.md)
- Older strategy comparisons (archived): [../archive/strategy/](../archive/strategy/), [../archive/STRATEGY.md](../archive/STRATEGY.md)
- External references:
  - DeepTutor repo: https://github.com/HKUDS/DeepTutor
  - Praktika case study: https://openai.com/index/praktika/
  - Transformers.js v4: https://huggingface.co/blog/transformersjs-v4
