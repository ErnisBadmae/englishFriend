---
description: Coding standards for English Friend project (FastAPI + PostgreSQL + CDC + Groq + edge-tts)
inclusion: always
---

# Coding Standards

## 1. Python Code Style

- **Python 3.12+** syntax only
- **Black** formatting (line length 100)
- **isort** for import sorting
- **Type hints** mandatory for all function signatures (`mypy --strict`)
- **Docstrings**: Google-style for public APIs
- **Logging**: Use `logger.info/debug/error`, never `print()`

```python
# Good
async def search_experts(codes: list[str]) -> list[Expert]:
    """Search for experts by specialization codes.

    Args:
        codes: List of specialization codes (e.g., ["2.1.2", "2.1.3"])

    Returns:
        List of Expert objects with active certificates
    """
    logger.info(f"Searching experts for codes: {codes}")
    ...
```

---

## 2. Async/Await Patterns

- **Always use async context managers** for resources (DB sessions, HTTP clients)
- **AsyncSessionLocal** from `app.core.database` for database access
- **Timeout** all external API calls with `httpx.Timeout`
- **No blocking operations** in async functions (no `requests`, no `time.sleep()`)
- **Connection pooling** with explicit limits

```python
# Good
async with AsyncSessionLocal() as session:
    result = await session.execute(select(Expert).where(...))
    experts = result.scalars().all()

# Good
client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
response = await client.get(url)

# Bad
session = AsyncSessionLocal()  # Missing context manager
experts = session.execute(...)  # Missing await
```

---

## 3. Service Layer Patterns

- **Service classes** encapsulate business logic (LearningPlanService, VocabularyService, etc.)
- **Helper modules** eliminate duplication (response_mappers, query_helpers, logger_helpers)
- **Data flow logging** via `data_logger` for all writes
- **Async all the way** - no blocking operations

```python
# Good - Service with helper usage
from app.services.query_helpers import get_by_id, get_top_by_field
from app.services.logger_helpers import format_user_info, format_data_preview

class LearningPlanService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def set_goal(self, user_id: int, goal: str) -> LearningPlan:
        """Set user learning goal."""
        # Detect goal from natural language
        detected_goal = await detect_goal_from_message(goal)

        # Generate roadmap via LLM
        roadmap = await generate_roadmap_for_goal(detected_goal)

        # Update database (Debezium emits CDC event)
        plan = await self.update_plan(user_id, {
            "goal": detected_goal,
            "roadmap": roadmap
        })

        # Log data flow
        data_logger.log_postgres_write(
            "learning_plan", {"goal": detected_goal}, "UPDATE", user_id
        )

        return plan

# Good - API endpoint with response mapper
from app.api.response_mappers import map_user_to_response

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await get_by_id(db, User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return map_user_to_response(user)  # Use helper, not manual mapping
```

---

## 4. Database Access

- **Pattern**: Always use `async with AsyncSessionLocal() as session:`
- **Queries**: `await session.execute(select(Model).where(...))`
- **Commits**: Automatic in context manager, manual rollback on error
- **Migrations**: SQL files in `migrations/` (auto-applied on first postgres start)
- **Schema**: Define in `app/models/orm.py` (SQLAlchemy ORM models)
- **Never use `.all()` without limit** - use pagination for large result sets

```python
# Good
async with AsyncSessionLocal() as session:
    result = await session.execute(
        select(Expert)
        .where(Expert.is_active == True)
        .options(selectinload(Expert.certificates))
        .limit(100)
    )
    experts = result.scalars().all()

# Bad
session = AsyncSessionLocal()  # Missing context manager
experts = session.query(Expert).all()  # Sync API, no limit
```

---

## 5. External Service Integration

### Groq LLM Client
- Use `get_llm_provider()` from `app/services/ai/llm_provider.py`
- **Model**: llama-3.3-70b-versatile
- **Timeout**: 30s default (voice responses must be fast)
- **Context**: System prompt + last 20 messages from conversation
- **Max Tokens**: 250 for voice (keep concise for TTS)

```python
# Good
llm = get_llm_provider()
response = await llm.generate(
    user_message=user_text,
    system_prompt=mode_prompt,
    conversation_history=history[-20:],  # Limit context
    max_tokens=250
)
```

### edge-tts Client
- Use `get_tts_service()` from `app/services/ai/tts_service.py`
- **Voice**: en-US-AndrewNeural (male) or en-US-JennyNeural (female)
- **Async**: Uses `edge_tts.Communicate` with async iteration
- **Format**: MP3 output, base64 encoded for WebSocket
- **Free**: No API key required

```python
# Good
tts = get_tts_service()
audio_bytes = await tts.synthesize(text, voice="en-US-AndrewNeural")
# Returns MP3 bytes ready for base64 encoding
```

### FSRS Vocabulary System
- Use `VocabularyService` from `app/services/ai/vocabulary_service.py`
- **Library**: `fsrs` 6.3.0 (use `Scheduler` class, not deprecated `FSRS`)
- **States**: New, Learning, Review, Relearning
- **Scheduling**: Automatic optimal intervals

```python
# Good - FSRS scheduling
from fsrs import Scheduler, Card, Rating, State

scheduler = Scheduler()
card = Card(state=State.New, due=datetime.now())

# After user review
updated_card = scheduler.review_card(card, Rating.Good)
# Returns card with new due date and state
```

---

## 6. Error Handling

- **Catch specific exceptions**, not broad `Exception`
- **Log with context**: operation, record ID, reason
- **Return partial results** when dependencies unavailable (fail-open for non-critical services)
- **User-facing errors**: Include in `execution_log` and `errors` state fields
- **Never expose internals** in API responses (DB connection strings, stack traces)

```python
# Good
try:
    experts = await search_experts_in_db(codes)
except DatabaseConnectionError as e:
    logger.error(f"DB connection failed for codes {codes}: {e}")
    return {
        "candidate_experts": [],
        "errors": [f"Database temporarily unavailable"],
        "execution_log": state.get("execution_log", []) + [{
            "node": "search",
            "status": "error",
            "error_type": "db_connection"
        }]
    }

# Bad
try:
    experts = await search_experts_in_db(codes)
except Exception as e:  # Too broad
    print(f"Error: {e}")  # Don't use print
    raise  # Don't crash the whole workflow
```

---

## 7. Testing

- **Unit tests**: `pytest tests/` with async support (`pytest-asyncio`)
- **Async test pattern**: `async def test_*()`
- **Integration tests**: `scripts/test_*.py` (can use full stack with Docker)
- **Docker tests**: `docker-compose up` for database + services
- **Coverage target**: 70% minimum for business logic (nodes, clients, API endpoints)
- **Before committing**: Run `python scripts/test_agent_e2e.py`

```python
# Good - Async test
@pytest.mark.asyncio
async def test_extraction_node():
    """Test extraction node with mock LLM client."""
    mock_client = MockLLMClient()
    state = {
        "document_text": "Строительство дома, код 2.1.2",
        "execution_log": []
    }

    result = await extraction_node(state)

    assert "specialization_codes" in result
    assert "2.1.2" in result["specialization_codes"]
    assert result["execution_log"][-1]["node"] == "extraction"
```

---

## 8. API Design

- **All endpoints**: FastAPI with type hints and Pydantic schemas
- **Voice endpoint**: `WebSocket /api/v1/voice/chat`
  - Query params: `user_id`, optional `mode`
  - Messages: `{"type": "text"|"set_goal"|"change_mode"|"end", ...}`
  - Responses: `{"type": "audio"|"transcript"|"mode_changed"|"error", ...}`
- **REST endpoints**: CRUD for users, sessions, memories, learning plans
- **Health check**: `GET /health` with DB connectivity status
- **Interactive docs**: Swagger UI at `/docs` (enabled by default)

```python
# Good - WebSocket endpoint
@router.websocket("/chat")
async def voice_chat(
    websocket: WebSocket,
    user_id: int = Query(...),
    mode: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Voice chat WebSocket with learning modes."""
    await websocket.accept()

    # Initialize services
    llm = get_llm_provider()
    tts = get_tts_service()

    # Send initial greeting
    await websocket.send_json({
        "type": "connected",
        "session_id": session_id,
        "mode": current_mode.value,
        "greeting": greeting
    })

    # Message loop
    while True:
        message = await websocket.receive_json()

        if message["type"] == "text":
            response = await llm.generate(...)
            audio = await tts.synthesize(response)
            await websocket.send_json({
                "type": "audio",
                "data": base64.b64encode(audio).decode()
            })

# Good - REST endpoint with response mapper
@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await get_by_id(db, User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return map_user_to_response(user)  # Use helper
```

---

## Key Principles

1. **Async-first**: All I/O operations must be async (FastAPI, asyncpg, httpx)
2. **Type safety**: mypy strict mode, no `# type: ignore` without justification
3. **Observability**: Data flow logging for all writes (data_logger)
4. **Helper modules**: Use response_mappers, query_helpers, logger_helpers to reduce duplication
5. **CDC-first**: Write to PostgreSQL, let Debezium emit events (no manual Kafka publishing)
6. **Test before commit**: Run unit tests, verify voice WebSocket flow
7. **No blocking**: Never use sync APIs (requests, time.sleep) in async code
8. **Explicit timeouts**: Every external call has timeout (30s for Groq, etc.)
9. **Context limits**: Limit conversation history to 20 messages (avoid token overflow)
10. **Partition awareness**: Use correct partition key for sessions/utterances/xp_events
