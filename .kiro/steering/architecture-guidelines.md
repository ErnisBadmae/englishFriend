---
description: Architecture guidelines for English Friend project
inclusion: always
---

# Architecture Guidelines

## CDC-Based Microservices Architecture

**Event-Driven Design:**

- **PostgreSQL** → **Debezium** → **Kafka** → **Sync Services** (Neo4j, Qdrant)
- All writes to PostgreSQL automatically trigger Kafka events via CDC
- Sync services independently consume events and update specialized databases
- API servers only write to PostgreSQL, no direct Neo4j/Qdrant access

**Design Patterns:**

```python
# Service layer pattern (app/services/)
class LearningPlanService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def set_goal(self, user_id: int, goal: str) -> LearningPlan:
        """Set learning goal, generate roadmap via LLM."""
        detected_goal = await detect_goal_from_message(goal)
        roadmap = await generate_roadmap_for_goal(detected_goal)

        # Update PostgreSQL - Debezium will emit event to Kafka
        plan = await self.update_plan(user_id, {
            "goal": detected_goal,
            "roadmap": roadmap
        })
        return plan

# API endpoint pattern with response mappers
@router.post("/users", response_model=UserResponse)
async def create_user(
    request: CreateUserRequest,
    db: AsyncSession = Depends(get_db)
):
    service = UserService(db)
    user = await service.create_user(
        telegram_id=request.telegram_id,
        username=request.username
    )
    return map_user_to_response(user)  # Use helper from response_mappers.py
```

**Key Considerations:**

- **CDC Events**: No manual Kafka publishing - Debezium handles it
- **Database Partitioning**: Sessions (monthly), Utterances (hash), XP events (monthly)
- **Row-Level Security (RLS)**: User data isolation enforced at PostgreSQL level
- **Helper Modules**: Use response_mappers, query_helpers, logger_helpers to reduce duplication
- **Async Everywhere**: FastAPI, asyncpg, httpx - no blocking operations

**Anti-Patterns:**

- ❌ Sync database calls (blocks event loop)
- ❌ Manual Kafka event publishing (Debezium does this)
- ❌ Direct Neo4j/Qdrant writes from API (use sync services)
- ❌ Missing user_id in queries (breaks RLS policies)

---

## Voice WebSocket Service

**WebSocket Architecture:**

- Endpoint: `/api/v1/voice/chat` (WebSocket connection)
- **STT**: Vosk runs in browser (local, privacy-preserving)
- **LLM**: Groq llama-3.3-70b for conversational responses
- **TTS**: edge-tts for audio synthesis (free, high quality)

**Learning System Patterns:**

```python
# Voice helpers pattern (consolidated logic)
from app.api.voice_helpers import (
    handle_goal_setting,
    award_session_gamification,
    rebuild_system_prompt
)

# WebSocket handler pattern
async def voice_chat(websocket: WebSocket, user_id: int, mode: str):
    # Initialize services
    llm = get_llm_provider()
    tts = get_tts_service()
    vocabulary_service = VocabularyService(db)

    # Build system prompt with current context
    system_prompt = rebuild_system_prompt(
        current_mode=mode,
        session_context=session_context,
        focus_area=focus_area,
        vocabulary_list=vocabulary_list,
        memory_section=memory_section
    )

    # Message loop
    while True:
        message = await websocket.receive_json()

        if message["type"] == "text":
            # Generate LLM response
            response = await llm.generate(
                user_message=message["text"],
                system_prompt=system_prompt,
                conversation_history=history[-20:]
            )

            # Synthesize and send audio
            audio_bytes = await tts.synthesize(response)
            await websocket.send_json({
                "type": "audio",
                "data": base64.b64encode(audio_bytes).decode()
            })
```

**Key Considerations:**

- **Context Window**: Limit conversation history to 20 messages (avoid token overflow)
- **Memory Extraction**: Process conversation every 5 turns for RAG
- **Mode Selection**: Auto-select based on user goals (assessment, vocabulary, mock interview, free conversation)
- **Gamification**: Award XP + streak on session end
- **Timeouts**: 30s for LLM, handle gracefully on failure

**Anti-Patterns:**

- ❌ Unbounded conversation history (OOM on long sessions)
- ❌ Blocking TTS synthesis (use async edge-tts)
- ❌ Missing LLM timeout (can hang indefinitely)
- ❌ Forgetting to award XP/streak on disconnect

---

## Integration Patterns

**Groq LLM Integration:**

- **Location**: `app/services/ai/llm_provider.py`
- **Model**: llama-3.3-70b-versatile (fast, cost-effective)
- **Timeout**: 30s default (configurable)
- **Context**: System prompt + last 20 messages from conversation
- **Max Tokens**: 250 for voice responses (keep concise for TTS)

**edge-tts Integration:**

- **Location**: `app/services/ai/tts_service.py`
- **Voice**: en-US-AndrewNeural (male) or en-US-JennyNeural (female)
- **Async**: Uses `edge_tts.Communicate` with async iteration
- **Format**: MP3 output, base64 encoded for WebSocket
- **Free**: No API key required, no rate limits

**FSRS Vocabulary System:**

- **Location**: `app/services/ai/vocabulary_service.py`
- **Library**: `fsrs` 6.3.0 (use `Scheduler` class, not deprecated `FSRS`)
- **States**: New, Learning, Review, Relearning
- **Scheduling**: Automatic optimal intervals based on user performance

**PostgreSQL Async Patterns:**

- **Location**: `app/core/database.py` (get_db dependency)
- **ORM Models**:
  - Core: `app/models/core_tables.py` (User, Session, Utterance)
  - Extended: `app/models/extended_tables.py` (Memory, LearningPlan, XPEvent, VocabularyCard)
  - Dimensions: `app/models/enums_and_dimensions.py` (DimEmotion, DimTopic, DimAccent)
- **Migrations**: Flyway-style SQL in `db/migrations/postgres/` (000-011)
- **Partitioning**: Managed via `scripts/manage_partitions.sh`

---

## Domain-Specific Guidelines

**Voice WebSocket Flow:**

1. **Connection**: Send greeting + session context (mode, goal, due vocabulary count)
2. **Message Loop**: Receive text → LLM generates response → TTS synthesizes → Send audio
3. **Memory Extraction**: Every 5 turns, extract facts via RAG pipeline
4. **Session End**: Post-session analysis, create vocabulary cards, award XP/streak

**Learning Modes (Auto-Selected):**

- **ASSESSMENT**: Evaluate English level, ask diagnostic questions
- **MOCK_INTERVIEW**: Simulate job interview scenarios
- **VOCABULARY_DRILL**: FSRS spaced repetition of due vocabulary cards
- **FREE_CONVERSATION**: Open-ended chat with corrections

**Gamification Logic:**

- **Session Complete**: +10 XP base reward
- **Streak Bonus**: +(streak_count * 5) XP if streak > 1 day
- **First Session**: +50 XP one-time bonus
- **Comeback**: +20 XP if returning after 7+ days gap
- **Streak Tracking**: Check-in on every session end via `StreakService`

**Memory RAG Pipeline:**

```python
# Extract and store memories from conversation
memories = await memory_pipeline.process_conversation(
    user_id=user_id,
    messages=conversation_history[-10:],  # Last 10 messages
    session_id=session_id
)
# Returns list[Memory] with salience scores
# Automatically embedded and synced to Qdrant via CDC
```

**Database Partitions (Auto-Managed):**

- **Sessions**: Monthly partitions (`sessions_2025_01`, `sessions_2025_02`)
- **Utterances**: 8 hash partitions (`utterances_p0` to `utterances_p7`)
- **XP Events**: Monthly partitions (`xp_events_2025_01`)
- **Management**: `scripts/manage_partitions.sh` creates future/drops old partitions

**CDC Event Topics:**

- `memories.public.memories` → sync-vector → Qdrant (embeddings for semantic search)
- `graph.public.sessions` → sync-graph → Neo4j (session nodes)
- `graph.public.utterances` → sync-graph → Neo4j (conversation edges)
- `graph.public.user_interest` → sync-graph → Neo4j (interest relationships)

**Helper Module Usage:**

- **response_mappers.py**: Use for all API responses (eliminates 30% duplication)
- **query_helpers.py**: `get_by_id()`, `get_top_by_field()` for common queries
- **logger_helpers.py**: `format_user_info()`, `format_data_preview()` for consistent logging
- **voice_helpers.py**: `handle_goal_setting()`, `award_session_gamification()`, `rebuild_system_prompt()`

---

## Architecture Decision Rationale

**Why Groq instead of OpenAI?**

- **Cost**: Free for development (0.59 USD/1M tokens vs OpenAI $15/1M)
- **Speed**: Fast inference critical for voice UX (< 2s response time)
- **Quality**: llama-3.3-70b competitive with GPT-4 for conversation

**Why edge-tts instead of paid TTS?**

- **Cost**: Free (Microsoft Edge TTS API, no API keys)
- **Quality**: Neural voices sound natural (better than AWS Polly free tier)
- **Simplicity**: No rate limits, no authentication, no billing

**Why Vosk in browser instead of server STT?**

- **Privacy**: Speech never leaves user's device (GDPR compliant)
- **Latency**: No network round-trip for audio upload (saves ~500ms)
- **Cost**: No Whisper API costs (Groq Whisper fast but uses token quota)

**Why FSRS for vocabulary instead of simple SRS?**

- **Science**: Evidence-based algorithm trained on 20k+ users
- **Adaptivity**: Automatically adjusts to each user's retention rate
- **Simplicity**: `fsrs` library handles all scheduling (no custom logic)

**Why Debezium CDC instead of application-level events?**

- **Reliability**: Database writes are source of truth (no missed events)
- **Simplicity**: No manual Kafka publishing in application code
- **Decoupling**: Can add new sync consumers without touching API code
- **Auditability**: All data changes flow through single pipeline

**Why separate sync services instead of direct Neo4j/Qdrant writes?**

- **Scalability**: API servers don't need Neo4j/Qdrant clients (fewer dependencies)
- **Reliability**: Failed syncs retry from DLQ without blocking API responses
- **Separation of Concerns**: API writes to PostgreSQL, sync services propagate

**Why asyncpg + SQLAlchemy?**

- **Async Performance**: Non-blocking database I/O (critical for WebSocket)
- **ORM Benefits**: Type safety, relationship management, query building
- **Partitioning**: SQLAlchemy supports partition routing
