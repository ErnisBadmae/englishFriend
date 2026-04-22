# LangGraph Agent for English Friend

This module implements the conversational AI for English Friend as a LangGraph state machine.

## Overview

The agent replaces hardcoded goal detection and conversation logic with a structured, logged, and testable state machine.

### Key Improvements over Legacy `/chat`:

1. **Goal Discovery with Confirmation**: Agent asks user about their goal, extracts it via LLM, and confirms before proceeding
2. **Interest Probing**: Actively discovers user interests for personalization
3. **Structured Assessment**: 3-question conversational assessment with CEFR scoring
4. **Pedagogical Logging**: All key decisions logged via `pedagogy_logger` for transparency
5. **Explicit State Machine**: Clear phases and transitions

## Architecture

### Conversation Flow

```
                    ┌─────────────────┐
                    │   START_NODE    │
                    │ (new/returning?)│
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                              ▼
    ┌─────────────────┐            ┌─────────────────┐
    │  GOAL_DISCOVERY │            │  MODE_ROUTER    │
    │  (ask & confirm)│            │  (returning     │
    │                 │            │   user w/ goal) │
    └────────┬────────┘            └────────┬────────┘
             │                              │
             ▼                              │
    ┌─────────────────┐                     │
    │  INTEREST_PROBE │                     │
    │  (discover      │                     │
    │   interests)    │                     │
    └────────┬────────┘                     │
             │                              │
             ▼                              │
    ┌─────────────────┐                     │
    │   ASSESSMENT    │                     │
    │  (evaluate      │                     │
    │   level)        │                     │
    └────────┬────────┘                     │
             │                              │
             ▼                              │
    ┌─────────────────┐                     │
    │  PROGRAM_BUILD  │                     │
    │  (create        │                     │
    │   roadmap)      │                     │
    └────────┬────────┘                     │
             │                              │
             ▼                              │
    ┌─────────────────────────────────────────────────┐
    │              LEARNING_SESSION                   │
    │  ┌─────────────────────────────────────────┐    │
    │  │         TURN_PROCESSOR (loop)           │◄───┘
    │  └─────────────────────────────────────────┘    │
    └─────────────────────────────────────────────────┘
             │
             ▼
    ┌─────────────────────────────────────────────────┐
    │              SESSION_END                        │
    └─────────────────────────────────────────────────┘
```

### Nodes

All nodes are in `app/agent/nodes/`:

- **start.py**: Entry point, routes based on user status (new/returning, has goal?)
- **goal_discovery.py**: Multi-step goal discovery with LLM extraction and user confirmation
- **interest_probe.py**: Discovers user interests through conversation
- **assessment.py**: Conducts 3-question CEFR assessment (A1-C1)
- **program_build.py**: Creates personalized learning roadmap based on goal, interests, level
- **mode_router.py**: Selects learning mode (mock_interview, vocab_drill, free_conversation, grammar_focus)
- **turn_processor.py**: Handles conversation turns, checks for mode changes, session end
- **session_end.py**: Processes session termination, generates farewell, triggers persistence

### State

`AgentState` (defined in `state.py`) is a TypedDict that flows through all nodes:

```python
class AgentState(TypedDict):
    # User info
    user_id: int
    username: str
    is_new_user: bool
    language_level: str

    # Goals & Interests
    detected_goal: Optional[str]
    confirmed_goal: Optional[str]
    detected_interests: list[str]
    confirmed_interests: list[str]

    # Assessment
    assessed_level: Optional[str]
    level_confidence: float
    assessment_scores: dict

    # Learning Program
    roadmap: Optional[dict]
    current_milestone: Optional[str]

    # Current Session
    current_mode: LearningModeEnum
    conversation_history: list[dict]
    system_prompt: Optional[str]

    # Vocabulary (FSRS)
    due_vocabulary_count: int
    due_vocabulary_words: list[str]

    # Memory (RAG)
    relevant_memories: list[str]
    new_memories_to_save: list[dict]

    # Logging
    decision_log: list[DecisionLogEntry]

    # Response
    pending_response: Optional[str]
    pending_audio: Optional[bytes]

    # Control
    should_end_session: bool
    needs_user_input: bool
```

## Usage

### In Voice API

```python
from app.agent.graph import run_agent_turn, initialize_session

# Initialize session
agent_state = await initialize_session(
    user_id=user_id,
    session_id=session_id,
    username=username,
    is_new_user=True,
    language_level="B1",
    # ... load from DB
)

# Run first turn (greeting/first question)
agent_state = await run_agent_turn(agent_state, user_message=None)
greeting = agent_state.get("pending_response")

# Message loop
while True:
    user_message = await get_user_message()

    # Run agent turn
    agent_state = await run_agent_turn(agent_state, user_message=user_message)

    # Get response
    response = agent_state.get("pending_response")
    await send_response(response)

    # Check for end
    if agent_state.get("should_end_session"):
        break
```

### API Endpoints

**New endpoint**: `/api/v1/voice/chat/v2`
- Uses LangGraph agent
- Full goal discovery flow
- Pedagogical logging

**Legacy endpoint**: `/api/v1/voice/chat`
- Hardcoded logic (preserved for compatibility)
- Uses deprecated `detect_goal_from_message()`

## Logging

All pedagogical decisions are logged via `app/services/pedagogy_logger.py`:

```python
from app.services.pedagogy_logger import get_pedagogy_logger

pedagogy = get_pedagogy_logger(user_id)

# Goal events
pedagogy.log_goal_detected(user_id, message, goal, confidence)
pedagogy.log_goal_confirmed(user_id, goal, user_response)
pedagogy.log_goal_rejected(user_id, goal, user_response)

# Interest events
pedagogy.log_interests_detected(user_id, interests)

# Assessment events
pedagogy.log_assessment_started(user_id, current_level)
pedagogy.log_level_assessed(user_id, level, scores, confidence)

# Mode events
pedagogy.log_mode_selected(user_id, mode, reason, context)
pedagogy.log_mode_changed(user_id, from_mode, to_mode, trigger)

# Error correction
pedagogy.log_error_corrected(user_id, error_type, original, corrected)

# Memory events
pedagogy.log_memory_retrieved(user_id, count, query)
pedagogy.log_memory_saved(user_id, memory_type, content_preview)

# Session events
pedagogy.log_session_started(user_id, session_id, is_new_user)
pedagogy.log_session_ended(user_id, session_id, turn_count, duration, mode)

# Phase transitions
pedagogy.log_phase_transition(user_id, from_phase, to_phase, reason)
```

Logs appear with `[PEDAGOGY]` prefix:

```
INFO [PEDAGOGY] 🎯 [GOAL] [user:123] Detected: ML/Data Science Interview Preparation | confidence=0.80
INFO [PEDAGOGY] ❓ [GOAL] [user:123] Requesting confirmation: ML/Data Science Interview Preparation
INFO [PEDAGOGY] ✅ [GOAL] [user:123] CONFIRMED by user: ML/Data Science Interview Preparation
INFO [PEDAGOGY] 💡 [INTEREST] [user:123] Detected: ['technology', 'machine learning', 'data science']
INFO [PEDAGOGY] 🔀 [MODE] [user:123] Selected: mock_interview | reason=Goal alignment
```

## Testing

### Unit Tests

```bash
# Test individual nodes
pytest tests/agent/test_goal_discovery.py -v
pytest tests/agent/test_assessment.py -v

# Test state transitions
pytest tests/agent/test_graph.py -v
```

### Integration Tests

```bash
# Test full flow
pytest tests/agent/test_integration.py -v
```

### E2E Tests

```bash
# Test via WebSocket
python tests/e2e/test_agent_voice.py
```

## Migration from Legacy

### Deprecated Functions

The following are now deprecated:

- `app.services.learning_plan_service.detect_goal_from_message()` → Use `goal_discovery_node`
- `app.services.learning_plan_service.GOAL_TEMPLATES` → Use `program_build_node.ROADMAP_TEMPLATES`

### Migration Path

1. **Immediate**: Use `/chat/v2` for new users
2. **Gradual**: Migrate existing users on next session
3. **Complete**: Deprecate `/chat` after testing period

### Backwards Compatibility

Legacy `/chat` endpoint is preserved and functional. New features (confirmed goals, interest probing) are only available in `/chat/v2`.

## Development

### Adding a New Node

1. Create node file in `app/agent/nodes/`
2. Define node function: `async def my_node(state: AgentState) -> AgentState`
3. Add routing function: `def route_after_my_node(state: AgentState) -> str`
4. Register in `graph.py`:
   ```python
   graph.add_node("my_node", my_node)
   graph.add_conditional_edges("my_node", route_after_my_node, {...})
   ```
5. Add to `nodes/__init__.py`
6. Write tests in `tests/agent/test_my_node.py`

### Debugging

Enable debug logging:

```python
import logging
logging.getLogger("app.agent").setLevel(logging.DEBUG)
logging.getLogger("pedagogy").setLevel(logging.DEBUG)
```

Inspect decision log:

```python
decision_log = agent_state.get("decision_log", [])
for entry in decision_log:
    print(f"{entry['node']}: {entry['action']} - {entry['reason']}")
```

## Dependencies

- `langgraph>=0.2.0`: State machine framework
- `langchain-core>=0.3.0`: Core utilities for LangGraph

## See Also

- [CLAUDE.md](../../CLAUDE.md) - Project-wide documentation
- [app/services/pedagogy_logger.py](../services/pedagogy_logger.py) - Logging implementation
- [app/api/voice.py](../api/voice.py) - WebSocket endpoints
