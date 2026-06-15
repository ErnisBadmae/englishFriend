---
last_updated: 2026-02-12
---

# Business Strategy

**Summary**: EnglishFriend targets Russian-speaking English learners with a freemium Telegram-based AI mentor. Our competitive advantage: self-hosted full-duplex voice (200ms latency, 90%+ margin), specialization on Russian speaker errors (W/V, TH, articles), goal-driven learning, and FSRS spaced repetition. We compete against TalkPal ($5-15/mo), Speak.com ($20/mo), Gliglish ($29/mo), and Duolingo Max ($30/mo) with a $12.99/mo Pro tier backed by self-hosted economics.

## Market Analysis

### Top Competitors and Technologies

#### 1. **Speak.com** ($1B valuation, $162M raised)
- **Technology**: OpenAI GPT-4 + proprietary ML scaffolding
- **Focus**: Conversational practice without live tutors
- **Price**: ~$19.50/month ($235/year)
- **Strengths**:
  - 1 billion+ sentences spoken
  - Custom GPT-4 model for Japanese (2.8x faster)
  - Open-ended conversations with feedback
- **Weakness**: Expensive, English-only for learners

#### 2. **ELSA Speak** (Pronunciation focus)
- **Technology**: Proprietary STT + phonetic analysis
- **Focus**: Pronunciation, intonation, rhythm
- **Price**: $12-15/month ($70-100/year)
- **Strengths**:
  - 8000+ lessons
  - Visual "mouth shape" guidance
  - Accent-based learning paths (American, British, Australian)
  - Specific phoneme detection
- **Weakness**: No free conversations, only exercises

#### 3. **TalkPal** (57 languages, fastest-growing)
- **Technology**: GPT-4 powered voice + text conversations
- **Focus**: Role-play scenarios (restaurant, travel, doctor, job interview)
- **Price**: $5.99/month (Basic), $9.99/month (Premium), $15.99/month (Premium+)
- **Free Tier**: 10 minutes/day, limited features
- **Strengths**:
  - 57 languages (broadest coverage)
  - Role-play scenarios with AI characters
  - Grammar/vocabulary explanations after each response
  - Affordable entry price ($5.99)
- **Weakness**:
  - API-dependent (OpenAI) — margin ~70%
  - No full-duplex (turn-based only, 500-800ms latency)
  - Generic corrections (not L1-specific)
  - Free tier very limited (10 min)

#### 4. **Langua** (LanguaTalk)
- **Technology**: AI voices cloned from real native speakers
- **Focus**: Natural conversations
- **Strengths**: Most natural voices
- **Weakness**: Less structured learning

#### 5. **Heylama**
- **Technology**: Custom role-play + vocabulary
- **Focus**: Personalization
- **Strengths**: Users create their own scenarios
- **Weakness**: Requires self-organization

### Key Insights for EnglishFriend

#### What Makes Leaders Successful:
1. **Speak.com**: "Holy grail" = understanding tone, pronunciation, intent + instant natural response
2. **ELSA**: Systematic approach: word → sentence → combinations → context
3. **Common**: AI personalization, instant feedback, adaptive difficulty

#### Our Unique Niche:

| Factor | Competitors | EnglishFriend |
|--------|-------------|---------------|
| **Target Audience** | Everyone | Russian speakers |
| **Error Specificity** | General | W/V, TH, articles, schwa |
| **Support Language** | English | Russian + English |
| **Price** | $10-20/month | Freemium (Telegram) |
| **Platform** | Mobile apps | Telegram Mini App |

### Typical Russian Speaker Errors:

| Category | Error | Examples |
|----------|-------|----------|
| **Consonants** | W→V | "where"→"vere", "water"→"vater" |
| **Consonants** | TH→S/Z/F/D | "think"→"sink", "the"→"zee" |
| **Consonants** | Devoicing | "bad"→"bat" |
| **Vowels** | Long/short | "ship"="sheep" |
| **Vowels** | Schwa | "today" /tuːˈdeɪ/ instead of /təˈdeɪ/ |
| **Intonation** | Flat | Questions without rising tone |
| **Stress** | Incorrect | Stress on articles, prepositions |

## Pricing on the Market

| App | Month | Year | Model |
|-----|-------|------|-------|
| TalkPal Basic | $5.99 | $72 | Voice + text, 57 langs |
| TalkPal Premium | $9.99 | $120 | Unlimited + advanced |
| ELSA Speak | $12-15 | $70-100 | Pronunciation focus |
| Speak.com | ~$19.50 | $235 | Conversations |
| Gliglish | $29 | ~$348 | Premium voice AI |
| Duolingo Max | ~$30 | $168 | Gamification + AI |
| **EnglishFriend Free** | **$0** | **$0** | **30 min/day, Telegram** |
| **EnglishFriend Pro** | **$12.99** | **~$156** | **Full-duplex, unlimited** |

### ⚠️ Important Update: Duolingo Video Call (September 2024)

Duolingo launched AI Video Call with character Lily:
- **Technology**: OpenAI-powered, adaptive difficulty
- **Features**: Remembers past conversations, adapts to level
- **Languages**: EN, ES, FR, DE, IT, PT, JP, KO
- **Price**: Duolingo Max only ($30/month)

**Our Advantage over Duolingo:**
- Specialization on Russian speakers (typical errors W/V, TH, articles)
- Goal-based learning (ML interview prep, IELTS, etc.)
- FSRS spaced repetition integrated into dialogue
- Cheaper: $10-30/month vs $30/month
- Open-source self-hosting possibility

### Gliglish - Scientifically Proven, Premium Pricing

- **Price**: $29/month (single tier, no free plan — only trial)
- **Technology**: OpenAI GPT-4 + Whisper STT + proprietary TTS
- **Strengths**: Scientifically validated (+75% speaking improvement, Gualán & Ramírez 2024)
- **Weakness**: Expensive ($29/mo), API-dependent, no free tier, generic (not L1-specific)

Gualán & Ramírez (2024) study: **+75% improvement** in speaking scores
- Pre-test: 4.69 → Post-test: 8.24
- Especially improved fluency (pace, pauses, hesitation)

**Conclusion**: Voice AI for language learning works. The question is differentiation.

**Our niche**: Between free Duolingo (low quality) and expensive Gliglish/Cambly ($29-40/mo). We provide full-duplex dialogue quality at $12.99/mo + Russian speaker specialization + goal-based approach.

## Unit Economics (Updated February 2026)

### Game Changer: Self-Hosted PersonaPlex

PersonaPlex (NVIDIA Moshi 7B on RTX 5060 Ti) is already integrated, replacing the need for Deepgram + ElevenLabs + OpenAI Realtime. This fundamentally changes our economics.

### Free Tier ($0)

| Component | Cost |
|-----------|------|
| Vosk STT | $0 (browser WASM) |
| Groq LLM | ~$0.001/request |
| edge-tts | $0 |
| **Per hour** | **~$0.10-0.50** |
| **Per user/month** | **~$1.50-7.50** |

### Pro Tier ($12.99/month)

| Component | Cost |
|-----------|------|
| PersonaPlex (self-hosted) | $0 marginal |
| GPU server amortized | ~$0.25-1/user/month |
| **Gross margin** | **$11.99-12.74 (92-98%)** |

### Team Tier ($99/month, up to 10)

| Metric | Value |
|--------|-------|
| COGS | ~$2.50-10/month |
| **Gross margin** | **$89-96.50 (90-97%)** |

### Competitor Margin Comparison

| | EnglishFriend | TalkPal | Gliglish | SPEAK |
|---|---|---|---|---|
| Price | $12.99 | $9.99 | $29 | ~$20 |
| COGS/user | ~$1 | ~$2-3 | ~$3-5 | ~$3-5 |
| **Margin** | **92%** | ~70% | ~83% | ~75% |
| Stack | Self-hosted | API | API | API |

**Break-even**: ~300 active free users + 20 pro subscribers

> For detailed analysis, see [Unit Economics](./UNIT_ECONOMICS.md)

## Competitive Advantages (What Sets Us Apart)

### 1. **Full-Duplex Voice with Self-Hosted Economics**
- **Difference**: All competitors use turn-based API calls (500ms+ latency)
- **Ours**: PersonaPlex (Moshi 7B) gives full-duplex at 200-400ms, self-hosted at $0 marginal cost
- **Result**: 90%+ margins vs 70-80% at competitors; user can interrupt AI naturally

### 2. **Specialization on Russian-Speaking Students**
- **Difference**: Prompts account for typical Russian speaker errors (articles, "most of people", th-sounds)
- **Ours**: Knowledge base of interferences (Russian influence on English)
- **Implementation**: System prompts with built-in correction rules for Russian students

### 3. **SRS + RAG Integration in Voice Format**
- **Difference**: Anki - cards without context, ChatGPT - no repetition
- **Ours**: AI automatically creates cards from conversation and organically returns to difficult words in future sessions
- **Example**: Student forgot word "resilience" → AI adds to SRS → in 3 days asks in dialogue "How would you describe resilience?"

### 4. **Emotional Intelligence (Ultra Tier)**
- **Difference**: Competitors ignore emotions
- **Ours**: Frustration detection → task simplification, boredom detection → switch to interesting topic
- **Technology**: Hume AI EVI or OpenAI Realtime with prosody analysis

### 5. **Progressive Data Model**
- **Difference**: Most EdTech don't store detailed history
- **Ours**: PostgreSQL with partitioning + Neo4j (interest graph) + Qdrant (semantic memory search)
- **Result**: AI remembers student loves technology and Marvel → adapts examples

## Critical Risks and Mitigation

### Risk 1: Low Free → Paid Conversion

**Mitigation**:
- Limit Free Tier to 30 min/day (create "hunger" for product)
- Trial Pro: 7 days free PersonaPlex to demonstrate quality difference
- Gamification: "Unlock unlimited full-duplex practice for $12.99"
- Full-duplex experience creates clear quality gap vs free tier

### Risk 2: GPU Server Scaling

**Mitigation**:
- Single RTX 5060 Ti handles ~200 concurrent users
- At 500+ concurrent: add second GPU server (~$50/month)
- Fallback to Vosk+Groq+edge-tts stack if PersonaPlex unavailable (already implemented)

### Risk 3: Competitor Price War

**Mitigation**:
- Self-hosted economics allow us to match any price while staying profitable
- TalkPal at $5.99 has ~70% margin; we can go to $7.99 and still have 85%+ margin
- Focus on quality differentiator (full-duplex) rather than price alone

---

*For technical implementation details, see [Technical Strategy](./TECHNICAL_STRATEGY.md)*
*For timeline and milestones, see [Roadmap](./ROADMAP.md)*
*For detailed unit economics, see [Unit Economics](./UNIT_ECONOMICS.md)*
*For go-to-market plan, see [Go-to-Market](./GO_TO_MARKET.md)*
*For voice AI technology research, see [Voice AI Technologies](../research/VOICE_AI_TECHNOLOGIES.md)*
