---
last_updated: 2025-01-31
---

# Roadmap

**Summary**: Three-phase development plan: MVP Launch (1-2 months) validates Free Tier with first 100 users, Premium Launch (3-4 months) introduces monetization with Deepgram/ElevenLabs stack, Ultra Tier & Scale (6+ months) adds OpenAI Realtime or Moshi self-hosted for premium experience.

## Phase 1: MVP Launch (1-2 months)

**Goal**: Launch Free Tier for first users

**Tasks**:
1. ✅ Fix Vosk STT (already done)
2. 🔄 Resolve LLM issue (configure Groq API or fix vLLM connection)
3. Optimize prompts for Russian-speaking students:
   - Add typical error database to system prompt
   - Implement Socratic questioning to stimulate speech
   - Configure correction levels (A1: soft → C2: strict)
4. Implement basic analytics:
   - Practice time tracking
   - Dialogue history in PostgreSQL
   - Simple progress dashboard
5. Improve UX:
   - Speech activity visualization (Lottie animations)
   - Latency indicator for quality monitoring
   - Emergency stop button (if AI "talks nonsense")

**Success Metrics**:
- 100 active Free Tier users
- Average session >10 minutes
- 7-day retention >30%

---

## Phase 2: Premium Launch (3-4 months)

**Goal**: Monetization through Premium Tier

**Tasks**:

1. Integrate Deepgram Nova-3:
   - STT switcher: Vosk (Free) / Deepgram (Premium)
   - WebSocket streaming for Deepgram
   - Keyword boosting for specialized vocabulary

2. Integrate ElevenLabs Flash v2.5:
   - Professional voice with low latency (75ms)
   - Voice choice: British/American accent

3. Implement RAG:
   - Vectorize learning history (Qdrant already in stack)
   - Search relevant fragments from past sessions
   - Prompt engineering for contextual responses

4. Implement SRS (Spaced Repetition):
   - FSRS algorithm for interval calculation
   - Automatic new word extraction from transcripts (GPT-4o)
   - Organic repetition integration into dialogue

5. Subscription system:
   - Stripe integration
   - Free Tier limitations (30 min/day)
   - Unlimited for Premium

**Success Metrics**:
- 5-10% Free → Premium conversion
- LTV (Lifetime Value) >$50 per user
- Churn rate <15% per month

---

## Phase 3: Ultra Tier & Scale (6+ months)

**Goal**: Differentiation through exclusive features

**Tasks**:

1. Migrate to OpenAI Realtime API (Ultra Tier):
   - Complete WebSocket logic rework
   - Server VAD with configurable parameters (silence_duration, eagerness)
   - Implement barge-in (interruptions)
   - Context summarization for long sessions (>30 min)

2. Emotional Intelligence:
   - Integrate Hume AI EVI or use Realtime API with prosody analysis
   - Adaptive prompts based on emotional state
   - Log emotions to EmotionalLog table (already in DB)

3. Personalization:
   - 4-5 mentor types (strict professor, friendly tutor, native slang speaker)
   - PVC (Professional Voice Cloning) from ElevenLabs for unique voices
   - Thematic scenarios (business English, travel, IELTS prep)

4. Advanced Analytics:
   - Weak point detection (grammar, vocabulary, pronunciation)
   - Automatic material recommendations
   - Progress export to PDF/Excel

5. Scale Infrastructure:
   - Transition to LiveKit Agents for orchestration (if Realtime API doesn't handle)
   - Prompt caching (80% savings on input tokens)
   - Adaptive TTS quality (cheap TTS for routine phrases, premium for reading)

**Success Metrics**:
- 1000+ paying users (Premium + Ultra)
- Ultra Tier >15% of Premium base
- NPS (Net Promoter Score) >50

---

## Alternative: Moshi Self-Hosted (Phase 3+)

**When to Consider**:
- >1000 paying users
- OpenAI Realtime costs >$5000/month
- Have DevOps for GPU infrastructure

**Advantages**:
- Cost: $0.02/min vs $0.30/min OpenAI
- Latency: 160-200ms (better than Realtime)
- Full data control
- Can fine-tune on education content

**Requirements**:
- GPU infrastructure (L4/A100)
- DevOps team
- Moshi stable API (v1.0+)

---

## Next Steps (Immediately After Vosk MVP)

1. **Complete Free Tier MVP** (priority #1):
   - Resolve LLM connection issue (Groq API setup)
   - Optimize system prompts for Russian speakers
   - Add basic analytics (table already exists in PostgreSQL)

2. **Prepare Premium Infrastructure**:
   - Create architecture with STT/TTS provider switching
   - Integrate Stripe for subscriptions
   - Implement role-based limitations (Free vs Premium)

3. **Research Competitive Advantages**:
   - Collect database of typical Russian speaker errors (from forums, textbooks)
   - Design SRS integration algorithm into dialogue
   - Create emotional detection prototype (Hume AI trial)

4. **Create Reference Note from Neural Network Analysis**:
   - Save document with detailed recommendations on VAD, latency, prompts
   - Use as checklist when developing Premium/Ultra

---

*For business context, see [Business Strategy](./BUSINESS_STRATEGY.md)*  
*For technical details, see [Technical Strategy](./TECHNICAL_STRATEGY.md)*
