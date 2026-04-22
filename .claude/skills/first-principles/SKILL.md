---
name: 'First Principles Analysis'
description: "Deconstruct problems to fundamental truths and rebuild solutions from scratch. Use when conventional solutions feel wrong, costs seem fixed, you hear 'that's how it's done,' or need breakthrough rather than incremental improvement."
---

# First Principles Analysis

## Overview

Break problems down to their fundamental truths, question every assumption, and rebuild solutions unconstrained by convention.

Work through six phases, but within each phase, have a natural dialogue. Ask one question at a time, follow interesting threads, and don't rush to the next phase until the current one feels complete.

## When to Use This

- Existing solutions feel like cargo cult or "we've always done it this way"
- You hear "that's impossible" or "too expensive"
- Industry conventions don't make logical sense
- Need breakthrough rather than incremental improvement
- Something feels like inherited constraint vs actual constraint

---

## The Process

### Phase 1: Define the Problem

Don't skip this. Most failed analyses come from solving the wrong problem.

Start by understanding what we're actually trying to achieve. Ask questions like:

- What's the core problem in your own words?
- What would success look like concretely?
- Why does this problem exist?
- What prompted this now?

Stay here until the problem is crystal clear. If it feels fuzzy, keep asking.

### Phase 2: Surface Assumptions

Now list everything we're assuming - especially the "obvious" stuff that nobody questions.

Explore together:

- What do we assume to be true about this problem?
- What's "just how it's done" in this space?
- What would someone with zero context find strange?
- What constraints do we take for granted?

Present assumptions back conversationally: "So we're assuming X, Y, and Z - does that capture it, or is there more?"

### Phase 3: Question Each Assumption

This is the core of first principles. Take each assumption and interrogate it.

For each one, explore:

- Is this actually true? What's the evidence?
- Why do we believe this? Where did it come from?
- What if the opposite were true?
- Is this physics/logic, or just convention?

Have a genuine dialogue here. Some assumptions will survive scrutiny (those are fundamentals). Others will crumble (those were conventions masquerading as constraints).

Flag each as: **Fundamental** (keep) or **Convention** (question further)

### Phase 4: Identify Fundamentals

After the questioning, take stock of what remains. These are your building blocks.

Reflect together:

- What constraints are actually real?
- What requirements are truly non-negotiable?
- What's left when we strip away the conventions?

Present: "Here's what I see as the irreducible fundamentals: [list]. Does this feel right?"

Don't proceed until there's agreement on the foundation.

### Phase 5: Rebuild From Scratch

Now the creative part. Forget how it's currently done. Using ONLY the fundamentals, explore what's possible.

Guide the exploration:

- If we were starting fresh today, what would we build?
- How do completely different domains solve similar problems?
- What becomes possible now that we've dropped [convention]?

Propose 2-3 radically different approaches. Lead with your recommendation and reasoning, but present alternatives. Discuss trade-offs conversationally.

### Phase 6: Validate

Before committing, stress-test the new approach.

Explore:

- Does this actually solve the core problem from Phase 1?
- What new assumptions have we introduced?
- What could go wrong?
- Is this actually implementable?

Be willing to loop back if something doesn't hold up.

---

## Socratic Toolkit

Keep these in your back pocket for any phase:

| When you need to... | Ask...                                                     |
| ------------------- | ---------------------------------------------------------- |
| Clarify             | "What do you mean by...?" / "Can you give an example?"     |
| Challenge           | "What if that weren't true?" / "Who says?"                 |
| Probe evidence      | "How do we know?" / "Are there counterexamples?"           |
| Shift perspective   | "How would an outsider see this?" / "What's the opposite?" |
| Test consequences   | "What happens if...?" / "What could go wrong?"             |

---

## After the Analysis

**Document it:**

- Write to `docs/plans/YYYY-MM-DD-<topic>-first-principles.md`
- Capture: problem, assumptions challenged, fundamentals, new approach
- Commit to git

**If implementing:**

- Create plan from the new mental model
- Watch for old assumptions creeping back in during implementation

---

## Key Principles

- **Question everything** - Especially the "obvious"
- **One question at a time** - Depth over breadth
- **Follow threads** - If something's interesting, explore it
- **Seek fundamentals** - Physics, logic, true requirements
- **Ignore convention** - "How it's done" isn't a reason
- **Validate rigorously** - New ideas need scrutiny too

---

## Domain Context: English Friend Project

When applying first principles to this codebase, consider these specific contexts:

### Core Problem
Help users improve English through **conversational practice** with optimal learning modes, vocabulary retention (FSRS), and gamification.

### Fundamental Constraints (Physics/Logic)

**True constraints** (cannot be changed):
- Voice latency **must be < 3s** (speech → text → LLM → TTS → audio)
- FSRS scheduling **requires user feedback** (Rating: Again/Hard/Good/Easy)
- Conversation context **limited by LLM tokens** (llama-3.3-70b: 128k, but costly)
- Browser STT **requires user permission** (getUserMedia API)
- Database writes **trigger CDC events** (Debezium automatically emits to Kafka)

**Assumed constraints** (question these):
- "Need Vosk in browser" → Why not Whisper on server? Trade-off: privacy vs latency
- "Limit to 20 messages history" → Why not 50? Trade-off: context vs token cost
- "Groq for LLM" → Why not OpenAI? Trade-off: cost vs reliability
- "edge-tts for voice" → Why not ElevenLabs? Trade-off: free vs quality
- "FSRS for vocabulary" → Why not Anki algorithm? Trade-off: science vs simplicity
- "CDC with Kafka" → Why not direct Neo4j writes? Trade-off: reliability vs complexity

### Common Conventions to Question

When working on English Friend, apply first principles to:

**"Conversation history must be limited to 20 messages"**
- Question: Why 20? Could be 10? Could be 50?
- Trade-offs: Token cost vs context quality vs response latency
- First principles: What's the minimum context needed for coherent conversation?

**"WebSocket for voice chat"**
- Question: Why not HTTP/2 + SSE? Why not REST polling?
- Fundamentals: Bidirectional real-time communication (text in, audio out)
- Challenge: Can we use streaming HTTP responses instead?

**"Auto-select learning mode"**
- First principles: What are we **actually** optimizing for?
  - User engagement (fun mode)?
  - Learning effectiveness (assessment first)?
  - Vocabulary retention (drill due cards)?
- Challenge: Should users manually choose mode every time?

**"RAG memory extraction every 5 turns"**
- Fundamentals: Extract facts from conversation for personalization
- Question: Why 5 turns? Why not every turn? Why not at session end only?
- Trade-off: Freshness vs LLM API costs

**"Gamification with XP/streaks"**
- First principles: What **actually** motivates language learners?
  - Extrinsic rewards (points, badges)?
  - Intrinsic motivation (progress, mastery)?
  - Social proof (leaderboards)?
- Challenge: Do XP points correlate with learning outcomes?

### First Principles Examples

**Example 1: "Why Groq instead of OpenAI?"**
- Break down: User speaks → STT → LLM generates → TTS → Audio response
- Fundamentals: Need fast inference for voice (< 2s response time)
- Options:
  1. OpenAI GPT-4 (high quality, $15/1M tokens, 5-10s latency)
  2. Groq llama-3.3-70b (good quality, $0.59/1M, < 2s latency)
  3. Local LLM (free, requires GPU, maintenance overhead)
- Decision factors: Voice UX requires low latency + cost matters at scale → Groq wins
- Challenge: What if Groq rate limits? (Answer: fallback to GPT-4o-mini)

**Example 2: "Should we use Vosk in browser or Whisper on server?"**
- Fundamentals: Convert speech to text
- Question assumptions:
  - "Privacy is critical" → Does user care if audio leaves device?
  - "Latency matters" → How much does network round-trip add?
  - "Accuracy vs cost" → Is Vosk good enough, or need Whisper quality?
- Options:
  1. Vosk in browser (privacy, no cost, ~85% accuracy, no latency)
  2. Whisper on server (better accuracy, uses Groq token quota, +500ms latency)
- Validate: Test with users - do they notice accuracy difference?

**Example 3: "Why limit conversation history to 20 messages?"**
- Fundamentals: LLM needs context to generate coherent responses
- Question: Why 20?
  - Cost: 20 messages ≈ 2000 tokens input, 250 tokens output = $0.001/turn
  - Context: Is 20 messages enough for coherent conversation?
  - Memory: More history = more LLM processing time
- Alternatives:
  1. 10 messages (save 50% cost, risk losing context)
  2. 50 messages (5x cost, better context)
  3. Summarize old messages (complexity, may lose nuance)
- Validate: A/B test - does 20 vs 50 messages improve conversation quality?

### When to Use First Principles in English Friend

**Use when:**
- Learning mode selection feels arbitrary
- Voice latency too high (> 3s response time)
- Gamification not motivating users
- Database partitions causing issues
- Debating technologies (Groq vs OpenAI, Vosk vs Whisper, FSRS vs custom SRS)

**Don't use when:**
- Simple bug fixes (missing await, typo, import error)
- Routine refactoring (renaming, extracting functions)
- Following established patterns (async/await, CDC, helper modules)
- Clear requirements (user explicitly asks for feature)

### Questions to Ask About English Friend Architecture

**"Why WebSocket for voice chat?"**
- Fundamental: Bidirectional real-time communication needed?
- Challenge: Could HTTP/2 + SSE work? Could REST polling suffice?
- Validate: Does WebSocket reduce latency vs alternatives?

**"Why FSRS instead of simpler SRS?"**
- Fundamental: Need optimal spaced repetition intervals
- Challenge: Does FSRS complexity improve retention vs simple algorithm?
- Validate: Do FSRS intervals lead to better long-term retention?

**"Why CDC with Kafka instead of direct writes?"**
- Fundamental: Need to sync PostgreSQL → Neo4j + Qdrant
- Challenge: Could API write directly to Neo4j/Qdrant?
- Answer: Reliability (retries), decoupling (add consumers without API changes)
- Validate: Does CDC complexity outweigh benefits?

**"Why separate sync services?"**
- Fundamental: Neo4j and Qdrant need different data transformations
- Challenge: Could one sync service handle both?
- Answer: Separation allows independent scaling and failure isolation
- Validate: Do we actually scale them differently in practice?

---

**Remember:** First principles thinking is about stripping away assumptions and rebuilding from **fundamental truths**. For English Friend, those truths are: voice latency matters (< 3s), LLM tokens cost money, users need motivation (gamification), vocabulary requires spaced repetition (FSRS), conversation needs context. Everything else is negotiable.
