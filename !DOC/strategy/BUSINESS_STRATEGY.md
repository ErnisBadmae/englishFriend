---
last_updated: 2025-01-31
---

# Business Strategy

**Summary**: EnglishFriend targets Russian-speaking English learners with a freemium Telegram-based AI mentor. Our competitive advantage lies in specialization on typical Russian speaker errors (W/V, TH, articles), goal-driven learning (ML interviews, IELTS), and integrated spaced repetition. We compete against Speak.com ($20/mo), ELSA ($12/mo), and Duolingo Max ($30/mo) with a more affordable $10-30/mo pricing model.

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

#### 3. **TalkPal** (50+ languages)
- **Technology**: Voice + text conversations
- **Focus**: Role-play scenarios (restaurant, travel, doctor)
- **Price**: Unknown (free tier + premium)
- **Strengths**: Many languages, practical scenarios
- **Weakness**: Basic feedback

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
| ELSA Speak | $12-15 | $70-100 | Pronunciation focus |
| Speak.com | ~$19.50 | $235 | Conversations |
| Kippy | ~$6.70 | $80 | Budget |
| Duolingo+ | ~$7 | $84 | Gamification |
| **EnglishFriend** | $0 (free) | $5-10? | Telegram, Russians |

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

### Gliglish - Scientifically Proven Effectiveness

Gualán & Ramírez (2024) study: **+75% improvement** in speaking scores
- Pre-test: 4.69 → Post-test: 8.24
- Especially improved fluency (pace, pauses, hesitation)

**Conclusion**: Voice AI for language learning works. The question is differentiation.

**Our niche**: Between free Duolingo (low quality) and expensive Cambly (live people). We provide live dialogue quality at subscription price + Russian speaker specialization + goal-based approach.

## Unit Economics (Updated January 2026)

### ⚡ Important Change: OpenAI Realtime API Price Reduction

In December 2024 OpenAI reduced prices:
- **Input audio**: -60% (was $0.06/min → ~$0.024/min)
- **Output audio**: -87.5% (was $0.24/min → ~$0.03/min)

**New Ultra Tier Calculation:**
- 10 min dialogue: ~$0.54 (was $3.00)
- Hour of practice: ~$3.24 (was $18.00)

### Premium Tier ($9.99/month)

**Assumptions**:
- Average user: 10 hours/month practice
- Operating cost: $3/hour (Deepgram + GPT-4o-mini + ElevenLabs)
- Total COGS (Cost of Goods Sold): $30/month
- **Margin**: -$20.01 😱 (UNPROFITABLE at small scale!)

**Optimization**:
1. Prompt caching: -80% on input tokens → $2/hour
2. Mixed TTS: OpenAI (cheap) for simple phrases, ElevenLabs for complex → $1.5/hour
3. Total: $1.5/hour × 10 hours = $15/month
4. **Margin**: -$5.01 (still negative, but tolerable for attracting Ultra)

### Ultra Tier ($29.99/month) - OpenAI Realtime

**Updated Assumptions** (after price reduction):
- Average user: 15 hours/month (more engaged)
- Operating cost: ~$3.24/hour (after price reduction)
- Total COGS: ~$48.60/month
- **Margin**: -$18.61 (still negative, but better than was -$0.01 at 15 hours)

### 🆕 Ultra Tier Alternative: Moshi Self-Hosted

**Calculation for self-hosted Moshi:**
- GPU cost: L4 instance ~$0.50/hour (with shared usage)
- Per user with 10 concurrent users: ~$0.05/hour
- 15 hours/month × $0.05 = **$0.75/month**
- **Margin**: +$29.24 🎉

**Trade-offs Moshi vs OpenAI Realtime:**

| Factor | OpenAI Realtime | Moshi Self-Hosted |
|--------|-----------------|-------------------|
| Latency | 200-300ms | 160-200ms ✅ |
| Quality | Best-in-class | Very good |
| Cost/hour | $3.24 | $0.05 ✅ |
| Setup complexity | Low ✅ | High |
| Maintenance | None ✅ | DevOps required |

**Conclusion (Updated)**:
- Premium Tier - loss leader for attraction
- Ultra Tier with OpenAI Realtime - for MVP and validation (easier to launch)
- Ultra Tier with Moshi - for scale (after 1000+ users)
- B2B tier: $99/month for corporate license with Moshi self-hosted = 95%+ margin

## Competitive Advantages (What Sets Us Apart)

### 1. **Hybrid Architecture with Tier Choice**
- **Difference**: Most competitors use only one technology
- **Ours**: Freemium model allows free trial, then upgrade as you progress
- **Example**: Duolingo uses only text, HelloTalk - only peer-to-peer, we - adaptive AI with tier choice

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

### Risk 1: High Operating Cost

**Mitigation**:
- Aggressive prompt caching
- Hybrid TTS model
- Self-hosted vLLM for Premium (instead of GPT-4o-mini) → $0.50/hour instead of $2

### Risk 2: OpenAI Realtime API May Change Pricing

**Mitigation**:
- Keep ready alternative on LiveKit + Pipecat (open source)
- Monitor Anthropic Claude Voice (announced for 2025)

### Risk 3: Low Free → Paid Conversion

**Mitigation**:
- Limit Free Tier to 30 min/day (create "hunger" for product)
- Trial Premium: 7 days free to demonstrate quality
- Gamification: "Unlock unlimited practice for $9.99"

---

*For technical implementation details, see [Technical Strategy](./TECHNICAL_STRATEGY.md)*  
*For timeline and milestones, see [Roadmap](./ROADMAP.md)*  
*For voice AI technology research, see [Voice AI Technologies](../research/VOICE_AI_TECHNOLOGIES.md)*
