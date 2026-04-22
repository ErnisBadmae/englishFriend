---
last_updated: 2025-01-31
---

# Technical Strategy

**Summary**: EnglishFriend uses a multi-tier architecture: Free Tier (Vosk + Groq + edge-tts, browser-based), Premium Tier (Deepgram + GPT-4o + ElevenLabs, ~$3/hour), and Ultra Tier (OpenAI Realtime or Moshi self-hosted, <500ms latency). We prioritize clean LLM abstraction, modular voice providers, and hybrid storage (PostgreSQL + Neo4j + Qdrant) for scalability.

## Current Architecture (MVP - 90% Ready)

### Free Tier - Vosk Stack

```
Browser (Vosk WASM STT) → WebSocket → FastAPI → vLLM/Groq LLM → edge-tts TTS → Browser
                                         ↓
                                    PostgreSQL (history, progress)
```

**Status**: ✅ Vosk STT successfully working after fixing sample rate resampling (48kHz→16kHz)

**Advantages**:
- Completely free STT (works offline in browser)
- Speech data privacy (recognition locally)
- Low operating cost (~$0.10-0.50/hour using Groq/vLLM)
- Already working prototype with database

**Disadvantages**:
- High latency (800-1200ms end-to-end) due to cascade architecture
- Loss of prosodic information (only text passed between components)
- Vosk WER ~10-15% (worse than premium solutions)
- No emotion and intonation analysis
- Basic pronunciation correction (only through text analysis)

## LLM Architecture Audit (January 2026)

### Overall Rating: 7/10

### ✅ What's Done RIGHT:

#### 1. Clean LLM Provider Abstraction

**File:** `app/services/ai/llm_provider.py`

```python
class LLMProvider(ABC):
    async def generate(...) -> str
    async def generate_stream(...) -> AsyncIterator[str]
```

- Three implementations: VLLMProvider, GroqProvider, OpenAIProvider
- Factory function `get_llm_provider()` with caching
- Centralized config through `settings`

#### 2. Separate Voice Provider Abstraction

**File:** `app/services/ai/base.py`

```python
class AIProvider(ABC):
    async def connect(session) -> None
    async def send_audio(chunk) -> None
    async def receive() -> AsyncIterator[dict]
    async def disconnect() -> None
```

- Three implementations: HumeEVIProvider, OpenAIRealtimeProvider, WhisperPipelineProvider
- Correct separation: text (LLMProvider) vs audio (AIProvider)

#### 3. TTS Service

**File:** `app/services/ai/tts_service.py`

- Clean abstraction with edge-tts
- Voice mapping (american_female, british_male, etc.)
- Singleton pattern

#### 4. Centralized Configuration

**File:** `app/core/config.py`

- All API keys and parameters in one place
- Pydantic Settings with .env support
- Typing through Literal["vllm", "groq", "openai"]

## Multi-Tier Subscription Model

### 🆓 **FREE TIER** (current architecture)

**Technologies**: Vosk + Groq/vLLM + edge-tts  
**Operating Cost**: ~$0.10-0.50/hour  
**User Price**: Free

**Limitations**:
- Response delay: 800-1200ms
- Basic grammar correction (text only)
- Limited session history (7 days)
- Medium quality synthetic voice (edge-tts)
- 30 minutes practice per day

**Target Audience**: Beginner students (A1-B1), trying the product

---

### 💎 **PREMIUM TIER** (cascade architecture, premium components)

**Technologies**: Deepgram Nova-3 + GPT-4o-mini + ElevenLabs Flash  
**Operating Cost**: ~$2-4/hour  
**User Price**: $9.99/month

**Improvements**:
- Response delay: 400-600ms (2x faster)
- STT accuracy: WER 5.8% (Deepgram vs 10-15% Vosk)
- Natural voice with emotions (ElevenLabs Flash, 75ms latency)
- Unlimited practice
- Long-term memory (RAG): AI remembers learning history
- Automatic SRS card creation for word repetition
- Advanced grammar correction through GPT-4o-mini

**Target Audience**: Serious students (B1-C1), willing to pay for quality

---

### 🚀 **ULTRA TIER** (native S2S architecture)

**Technologies**: OpenAI Realtime API (GPT-4o Realtime) + optionally ElevenLabs PVC  
**Operating Cost**: ~$1.35-3/hour (optimized Realtime API)  
**User Price**: $29.99/month

**Unique Capabilities**:
- ⚡ **Minimal latency**: <300-500ms (natural dialogue)
- 🎭 **Prosody analysis**: Correction of intonation, accent, emotional coloring
- 🧠 **Empathy**: AI "hears" student frustration/joy and adapts approach
- 🎙️ **Natural interruptions**: Student can interrupt AI like in live conversation (barge-in)
- 📚 **Advanced RAG**: Integration with student's learning materials (PDF, articles)
- 🔄 **Smart SRS**: FSRS algorithm for optimal repetition intervals
- 🎨 **Personalization**: Choice of mentor personality (strict British, friendly American, etc.)
- 📊 **Detailed analytics**: Progress reports, weak points, topic statistics

**Target Audience**: Professionals (C1-C2), corporate clients, IELTS/TOEFL preparation

## Technology Stack Comparison (by Tiers)

| Component | Free Tier | Premium Tier (Option A) | Premium Tier (Option B) | Ultra Tier |
|-----------|-----------|-------------------------|-------------------------|------------|
| **Stack** | Vosk + Groq + edge-tts | Deepgram + GPT-4o + EL | **Pipecat + Ultravox** ⭐ | OpenAI Realtime / Moshi |
| **STT** | Vosk (browser WASM) | Deepgram Nova-3 | Ultravox (native audio) | Realtime (native) / Moshi |
| **LLM** | Groq/vLLM (free) | GPT-4o-mini | Ultravox (built-in) | GPT-4o Realtime / Moshi |
| **TTS** | edge-tts | ElevenLabs Flash | ElevenLabs / Cartesia | Realtime API / Moshi |
| **VAD** | Browser (basic) | Deepgram endpointing | Pipecat VAD | Server VAD (OpenAI) |
| **Latency** | 800-1200ms | 400-600ms | **400-600ms** | <500ms |
| **Cost/hour** | $0.10-0.50 | $2-4 | **~$3** | $1.35-3 |
| **Subscription** | Free | $9.99/mo | $9.99/mo | $29.99/mo |
| **Recommendation** | ✅ MVP NOW | Backup option | **⭐ Recommended** | After 1000+ users |

## Advanced Technologies Research

### OpenAI Realtime API
- **Latency**: ~500ms TTFB, target 800ms voice-to-voice
- **Architecture**: Speech-to-speech in one model (not STT→LLM→TTS chain)
- **Advantages**: Hears emotions, filters noise, interruptions (barge-in)
- **Connection**: WebRTC (browser), WebSocket (server), SIP (telephony)

### Hume AI EVI (Empathic Voice Interface)
- **Uniqueness**: First AI with emotional intelligence
- **Functions**:
  - Responds to expression (understands tone)
  - Always interruptible (can be interrupted)
  - Aligned with well-being (optimized for user happiness)
  - End-of-turn detection by voice tone
- **Value for learning**: Frustration detection → task simplification

### Moshi (Kyutai) - Open Source Voice AI ⭐ NEW 2025

- **What is it**: First open-source full-duplex voice AI from French lab Kyutai
- **GitHub**: https://github.com/kyutai-labs/moshi
- **License**: Apache 2.0 (code), CC-BY 4.0 (model weights)

**Technical Characteristics**:
- **Latency**: 160-200ms (best in class!)
- **Model**: 7B parameters, Helium base model
- **Architecture**: Two-stream audio (user + AI simultaneously)
- **Codec**: Mimi (300x compression)
- **Emotions**: 92 different intonations and styles

**Advantages for EnglishFriend**:
- Self-hosted = full data control
- Cost ~$0.02/min (GPU only) vs $0.30/min OpenAI
- Can fine-tune on education content
- Works on consumer GPU (RTX 3090, L4)

**Recommendation**: Consider as alternative for Ultra Tier for self-hosted deployment.

### LiveKit Agents - Orchestration Layer

- **What is it**: Open-source framework for voice agent orchestration
- **Role**: Connects STT + LLM + TTS into unified pipeline
- **Integrations**: Deepgram, ElevenLabs, OpenAI, Cartesia
- **Advantages**:
  - WebRTC out of the box
  - Turn detection and interruption handling
  - Self-hostable
- **Cost**: Open-source (MIT license)

**Application**: Intermediate option between current stack and OpenAI Realtime.

### Pipecat + Ultravox - Recommended Intermediate Option ⭐ NEW

**Pipecat** (https://github.com/pipecat-ai/pipecat):
- Open-source voice AI framework from Daily.co
- Modular architecture: plug any STT/LLM/TTS
- Built-in interruption handling and VAD
- WebSocket and WebRTC support
- Active community, good documentation

**Ultravox** (https://ultravox.ai):
- Speech-native LLM (understands audio directly, without separate STT step)
- Multimodal: text + audio in one model
- ~$0.05/min (comparable to OpenAI Realtime)
- API available, no self-hosting needed

**Advantages of Pipecat + Ultravox**:
- No separate STT step → less latency
- Ultravox "hears" intonation (prosody not lost)
- Pipecat gives WebRTC out of the box
- Easier integration than raw OpenAI Realtime
- Good middle-ground between Vosk and OpenAI Realtime

**Cost**: ~$0.05/min = $3/hour  
**Latency**: ~400-600ms

**Recommendation**: Consider as main option for Premium Tier instead of Deepgram+GPT-4o+ElevenLabs.

## Architecture Analysis: Vosk vs Moshi (January 2026)

### KEY CONCLUSION: DO NOT CHANGE architecture now

### Why "Vosk vs Moshi" comparison is incorrect

| Vosk | Moshi |
|------|-------|
| STT (Speech-to-Text) | End-to-end Speech-to-Speech |
| Only recognizes speech | Replaces **ENTIRE pipeline** (STT + LLM + TTS) |
| WASM in browser, free | GPU server, $100-200/month |
| Offline, private | Requires network |

**"Changing Vosk to Moshi" = complete architecture rebuild**, not replacing one component.

### Why Moshi has no wide adoption

1. **Very new** - open-source weights from February 2025 (~11 months)
2. **GPU requirements** - RTX 4090 / A100 / L4 mandatory
3. **No commercial support** - only research lab (Kyutai)
4. **No SDK** - need to write WebSocket, audio processing yourself
5. **English only** - no multi-language
6. **No function calling** - can't integrate with RAG/memory

### Risks of switching to Moshi for Free Tier

| Risk | Severity |
|------|----------|
| Loss of Free Tier freeness | CRITICAL |
| Loss of offline work (privacy) | HIGH |
| GPU infrastructure ($5000+/month at scale) | HIGH |
| No RAG/memory integration | HIGH |
| Loss of flexibility in LLM/TTS choice | MEDIUM |

### When to switch to Moshi

| Condition | Status |
|-----------|--------|
| >1000 paying users | ❌ Not met |
| OpenAI Realtime costs >$5000/month | ❌ Not relevant |
| Moshi has stable API (v1.0+) | ❌ Not met |
| Have DevOps for GPU | ❌ Not met |

**Answer: Consider Moshi in 12+ months** for Ultra Tier as OpenAI Realtime alternative.

### Stack Selection Strategy by Phases

```
NOW (MVP):
  ✅ Vosk + Groq + edge-tts
  ✅ Validate product-market fit
  ✅ Find first 100 users

+3-4 months (Premium validation):
  □ Assess demand for premium features
  □ Prototype Pipecat + Ultravox OR Deepgram stack
  □ A/B test latency improvements

+6-12 months (Scale decision):
  □ If >1000 paying users: implement Ultra tier
  □ Choice between OpenAI Realtime vs Moshi
  □ Evaluate self-hosting economics
```

## TTS Research: Coqui TTS vs Piper TTS (January 2026)

### Coqui TTS - Analysis Results

**What is it**: Open-source TTS on PyTorch, created by former Mozilla TTS developers.

**Status**: ⚠️ Coqui company closed in December 2023, services shut down in 2024. Code maintained by community (Idiap Research Institute).

**Key Characteristics**:
- XTTS-v2: 17 languages, voice cloning from 6 sec audio
- Latency: ~150-200ms on GPU
- **NO browser/WASM version** - server-only solution
- License: Apache 2.0, but XTTS-v2 - non-commercial license

**Conclusion**: Coqui TTS **not suitable** for our browser architecture. Blogger probably used it on server.

### Piper TTS - BROWSER ALTERNATIVE ✅

**What is it**: Fast local neural TTS from rhasspy (Home Assistant).

**Key Advantage**: Has WASM version for browser!

**npm package**: `@mintplex-labs/piper-tts-web`

```typescript
import * as tts from '@mintplex-labs/piper-tts-web';

const wav = await tts.predict({
  text: 'Hello, I am your English mentor!',
  voiceId: 'en_US-hfc_female-medium'
});

const audio = new Audio();
audio.src = URL.createObjectURL(wav);
audio.play();
```

**Piper TTS Characteristics**:
- Model size: ~100MB (medium quality)
- 904+ voices, including English (British, American)
- Quality: x_low / low / medium / high
- 100% browser, works offline
- Models cached in Origin Private File System

### TTS Solutions Comparison for Free Tier

| Solution | Local | Size | Latency | Quality | Offline |
|----------|-------|------|---------|---------|---------|
| **edge-tts** (current) | ❌ MS Server | 0 | ~200-500ms | Good | ❌ |
| **Piper TTS WASM** | ✅ Browser | ~100MB | ~100-300ms | Medium | ✅ |
| **Web Speech API** | ✅ Browser | 0 | ~50ms | Low | ✅ |

### Recommendation

**For MVP**: Keep edge-tts (works, free, good quality)

**For "fully local" mode**: Add Piper TTS as option
- Plus: Vosk STT + Piper TTS = fully offline (except LLM)
- Minus: +100MB model download

**Links**:
- [Piper TTS Web](https://github.com/Mintplex-Labs/piper-tts-web)
- [Piper voices](https://rhasspy.github.io/piper-samples/)
- [Coqui TTS (archive)](https://github.com/coqui-ai/TTS)

## Pedagogical Architecture

### ✅ IMPLEMENTED: Pedagogical AI Mentor Architecture

#### Original Problem

Current agent - just chatbot without pedagogy:
- Doesn't adapt to user goals (ML Interview → ignored)
- No assessment (level evaluation)
- No learning structure
- FSRS exists in code but **NOT connected**
- LearningPlan table **empty**

#### Solution: Learning Modes + Goal-Driven Learning

See [LangGraph Agent Implementation](../implementations/LANGGRAPH_AGENT.md) for details.

## Research Directions (Not for MVP)

### Multi-Agent + ML Scoring

From interview at AI-psychologist company:
- **LangGraph** for parallel sub-agent orchestration
- **Gradient Boosting** for scoring/ranking agent responses
- High latency (~2-3s), but significantly higher quality

**Applicability to EnglishFriend**:
- ✅ Background processing (post-session analysis)
- ❌ Real-time voice chat (latency critical)

See [research notes](../research/) for details.

### LLM-JEPA

**What is it**: JEPA-based fine-tuning for LLM  
**Paper**: https://arxiv.org/abs/2509.14252  
**Repo**: https://github.com/galilai-group/llm-jepa

**Advantages**:
- Resistance to overfitting (critical with small education datasets)
- Better than standard training objectives on GSM8K, Spider, etc.
- Works with Llama3, Gemma2, OpenELM

**Potential Application**: Fine-tune models on education dialogues, specialization on Russian speaker error correction

**Status**: R&D direction for Phase 3+ (6-12 months)

---

*For business strategy and pricing, see [Business Strategy](./BUSINESS_STRATEGY.md)*  
*For implementation timeline, see [Roadmap](./ROADMAP.md)*  
*For detailed voice AI comparison, see [Voice AI Technologies](../research/VOICE_AI_TECHNOLOGIES.md)*
