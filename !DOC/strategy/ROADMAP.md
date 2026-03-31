---
last_updated: 2026-03-30
---

# Roadmap

> Strategic update on 2026-03-30:
> the execution order in this file is no longer the primary product roadmap.
> See [PRODUCT_WEDGE_PIVOT_2026-03-30.md](./PRODUCT_WEDGE_PIVOT_2026-03-30.md) for the current wedge, rationale, and next build step.

**Summary**: EnglishFriend MVP is ~95% complete with PersonaPlex (full-duplex, 200-400ms, $0) already integrated. The roadmap focuses on launch validation (Phase 1.5), monetization with self-hosted advantage (Phase 2), and scaling to B2B/mobile (Phase 3).

## Phase 1: MVP (Status: ~95% Complete)

**Goal**: Working Free Tier with AI mentor

**Completed**:
- ✅ Vosk STT — working (browser WASM, 48kHz→16kHz resampling)
- ✅ Groq LLM — configured (llama-3.3-70b-versatile)
- ✅ edge-tts — working (en-US-AndrewNeural)
- ✅ Agent V2 (LangGraph) — 4-node state machine, tests pass (7/7)
- ✅ PersonaPlex integration — full-duplex via NVIDIA Moshi 7B, 200-400ms latency, fallback to legacy stack
- ✅ Gamification — XP system, streaks implemented
- ✅ Prometheus + Grafana — metrics for voice, agent, PersonaPlex
- ✅ PostgreSQL + CDC (Debezium → Kafka) — working
- ✅ Neo4j + Qdrant — infrastructure deployed
- ✅ FSRS vocabulary service — code exists (not yet integrated into dialogue)

**Remaining**:
- 🔄 Telegram Mini App frontend — verify/finalize
- 🔄 Basic analytics (retention, session duration dashboards)
- 🔄 Stabilization and bug fixes
- 🔄 End-to-end testing of full user journey

---

## Phase 1.5: Launch & Validate (2-4 weeks)

**Goal**: Get first 100 users, validate product-market fit

**Tasks**:

1. **Closed Beta (week 1-2)**:
   - 20-50 testers from target audience (Russian-speaking devs)
   - Source: personal contacts, developer Telegram chats
   - Fix critical bugs from feedback

2. **Soft Launch (week 3-4)**:
   - Open to 200-500 users
   - Habr article: "Как мы сделали AI-репетитора с задержкой 200ms"
   - Telegram channel for the project
   - Partnerships with 2-3 IT Telegram channels

3. **Prepare for scale**:
   - Referral mechanics (invite friend → +30 min free)
   - Product Hunt / Hacker News launch prep
   - Collect and analyze user feedback

**Success Metrics**:
- 100 active users
- 7-day retention >30%
- Average session >10 minutes
- 80% of beta testers complete 3+ sessions

---

## Phase 2: Premium Launch (2-3 months after Phase 1.5)

**Goal**: Monetization through Pro Tier ($12.99/month)

**Tasks**:

1. **Pro Tier Features**:
   - PersonaPlex as premium voice stack (already integrated, full-duplex, $0 COGS)
   - Free Tier: Vosk + Groq + edge-tts (30 min/day limit)
   - Pro Tier: PersonaPlex unlimited + advanced features

2. **FSRS Vocabulary in Dialogue**:
   - Connect existing FSRS code into turn_processor
   - Organic word repetition during conversations
   - Post-session vocabulary report (new words + errors)

3. **RAG via Qdrant**:
   - Infrastructure ready (Qdrant deployed, CDC syncing memories)
   - Connect semantic search into prompt building
   - AI remembers past sessions, goals, interests

4. **Payment System**:
   - Stripe integration
   - Free Tier limitations enforcement (30 min/day)
   - 7-day free trial for Pro

5. **Post-Session Feedback**:
   - Error summary (grammar, pronunciation patterns)
   - New vocabulary list with FSRS scheduling
   - Progress tracking dashboard

**Success Metrics**:
- 500 registered users
- 5-10% free → paid conversion
- MRR $500+
- Churn rate <15%/month

---

## Phase 3: Scale (6+ months after Phase 2)

**Goal**: Growth and diversification

**Tasks**:

1. **B2B / Corporate Licenses**:
   - Team Tier: $99/month for up to 10 people
   - Admin dashboard with team progress
   - Custom scenarios (business English, technical interviews)

2. **Mobile Application**:
   - React Native app
   - Offline vocabulary review (FSRS cards)
   - Push notifications for spaced repetition

3. **Language Expansion**:
   - Additional L1 support (Spanish-speaking, Arabic-speaking learners)
   - Localized error databases per L1
   - Multi-language system prompts

4. **Group Mode**:
   - 2-3 students + AI mentor conversation
   - Peer practice with AI moderation
   - Competition/collaboration mechanics

5. **Advanced Analytics**:
   - Weak point detection (grammar, vocabulary, pronunciation)
   - Automatic material recommendations
   - Progress export (PDF/Excel)

6. **Emotional Intelligence**:
   - Frustration detection → task simplification
   - Boredom detection → topic switch
   - Leverage PersonaPlex prosody data

**Success Metrics**:
- 1000+ paying users (Pro + Team)
- MRR $10K+
- B2B contracts signed
- NPS >50

---

## Success Metrics Summary

| Phase | Users | Retention | Revenue |
|-------|-------|-----------|---------|
| 1.5 (Launch) | 100 active | 30% 7-day | — |
| 2 (Premium) | 500 registered, 25-50 pro | — | MRR $500+ |
| 3 (Scale) | 1000+ paying | — | MRR $10K+ |

---

*For business context, see [Business Strategy](./BUSINESS_STRATEGY.md)*
*For technical details, see [Technical Strategy](./TECHNICAL_STRATEGY.md)*
