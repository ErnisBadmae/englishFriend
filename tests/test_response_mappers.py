"""Unit tests for API response mappers."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock
from app.api.response_mappers import (
    map_interest_to_response,
    map_interests_to_list_response,
    map_memory_to_response,
    map_memories_to_list_response,
    map_xp_event_to_response,
    map_xp_events_to_list_response,
    map_learning_plan_to_response,
)
from app.models.enums_and_dimensions import MemoryKind


def test_map_interest_to_response():
    """Test interest model to response mapping."""
    # Create mock interest
    interest = MagicMock()
    interest.user_id = 1
    interest.topic_id = "technology"
    interest.weight = 0.85
    interest.last_mentioned = datetime(2024, 1, 1)

    # Map to response
    response = map_interest_to_response(interest)

    # Verify fields
    assert response.user_id == 1
    assert response.topic_id == "technology"
    assert response.weight == 0.85
    assert response.last_mentioned == datetime(2024, 1, 1)


def test_map_interests_to_list_response():
    """Test list of interests to list response mapping."""
    # Create mock interests
    interest1 = MagicMock(user_id=1, topic_id="tech", weight=0.9, last_mentioned=None)
    interest2 = MagicMock(user_id=1, topic_id="sports", weight=0.7, last_mentioned=None)
    interests = [interest1, interest2]

    # Map to list response
    response = map_interests_to_list_response(interests)

    # Verify
    assert response.total == 2
    assert len(response.interests) == 2
    assert response.interests[0].topic_id == "tech"
    assert response.interests[1].topic_id == "sports"


def test_map_memory_to_response():
    """Test memory model to response mapping."""
    # Create mock memory
    memory = MagicMock()
    memory.id = "mem-123"
    memory.user_id = 1
    memory.kind = MemoryKind.EPISODIC
    memory.content = "User attended ML conference"
    memory.meta = {"location": "SF"}
    memory.salience = 0.9
    memory.created_at = datetime(2024, 1, 1)
    memory.last_refreshed = datetime(2024, 1, 2)

    # Map to response
    response = map_memory_to_response(memory)

    # Verify all fields
    assert response.id == "mem-123"
    assert response.user_id == 1
    assert response.kind == MemoryKind.EPISODIC
    assert response.content == "User attended ML conference"
    assert response.meta == {"location": "SF"}
    assert response.salience == 0.9
    assert response.created_at == datetime(2024, 1, 1)
    assert response.last_refreshed == datetime(2024, 1, 2)


def test_map_memories_to_list_response():
    """Test list of memories to list response mapping."""
    # Create mock memories
    memory1 = MagicMock(
        id="m1", user_id=1, kind=MemoryKind.EPISODIC,
        content="Event 1", meta={}, salience=0.9,
        created_at=datetime.now(), last_refreshed=datetime.now()
    )
    memory2 = MagicMock(
        id="m2", user_id=1, kind=MemoryKind.SEMANTIC,
        content="Fact 1", meta={}, salience=0.8,
        created_at=datetime.now(), last_refreshed=datetime.now()
    )
    memories = [memory1, memory2]

    # Map to list response
    response = map_memories_to_list_response(memories)

    # Verify
    assert response.total == 2
    assert len(response.memories) == 2
    assert response.memories[0].kind == MemoryKind.EPISODIC
    assert response.memories[1].kind == MemoryKind.SEMANTIC


def test_map_xp_event_to_response():
    """Test XP event model to response mapping."""
    # Create mock XP event
    event = MagicMock()
    event.id = "xp-123"
    event.user_id = 1
    event.session_id = "session-456"
    event.kind = "SESSION_COMPLETE"
    event.points = 50
    event.happened_at = datetime(2024, 1, 1, 12, 0)

    # Map to response
    response = map_xp_event_to_response(event)

    # Verify all fields
    assert response.id == "xp-123"
    assert response.user_id == 1
    assert response.session_id == "session-456"
    assert response.kind == "SESSION_COMPLETE"
    assert response.points == 50
    assert response.happened_at == datetime(2024, 1, 1, 12, 0)


def test_map_xp_events_to_list_response():
    """Test list of XP events to list response mapping."""
    # Create mock events
    event1 = MagicMock(
        id="e1", user_id=1, session_id="s1",
        kind="SESSION_COMPLETE", points=50,
        happened_at=datetime.now()
    )
    event2 = MagicMock(
        id="e2", user_id=1, session_id="s1",
        kind="STREAK_BONUS", points=10,
        happened_at=datetime.now()
    )
    events = [event1, event2]

    # Map to list response
    response = map_xp_events_to_list_response(events)

    # Verify
    assert response.total == 2
    assert len(response.events) == 2
    assert response.events[0].kind == "SESSION_COMPLETE"
    assert response.events[1].kind == "STREAK_BONUS"
    assert response.events[0].points == 50
    assert response.events[1].points == 10


def test_map_learning_plan_to_response():
    """Test learning plan model to response mapping."""
    # Create mock learning plan
    plan = MagicMock()
    plan.id = "plan-123"
    plan.user_id = 1
    plan.level_target = "C1"
    plan.next_review_at = datetime(2024, 2, 1)
    plan.roadmap = {
        "goal": "ML interview prep",
        "milestones": [{"name": "Complete assessment", "done": True}]
    }
    plan.updated_at = datetime(2024, 1, 15)

    # Map to response
    response = map_learning_plan_to_response(plan)

    # Verify all fields
    assert response.id == "plan-123"
    assert response.user_id == 1
    assert response.level_target == "C1"
    assert response.next_review_at == datetime(2024, 2, 1)
    assert response.roadmap["goal"] == "ML interview prep"
    assert response.updated_at == datetime(2024, 1, 15)


def test_mappers_handle_none_fields():
    """Test that mappers handle optional/nullable fields correctly."""
    # Create mock with some None fields
    interest = MagicMock()
    interest.user_id = 1
    interest.topic_id = "tech"
    interest.weight = 0.5
    interest.last_mentioned = None  # Nullable field

    # Should not raise
    response = map_interest_to_response(interest)
    assert response.last_mentioned is None


def test_empty_list_mapping():
    """Test mapping empty lists."""
    # Test empty interests
    response = map_interests_to_list_response([])
    assert response.total == 0
    assert len(response.interests) == 0

    # Test empty memories
    response = map_memories_to_list_response([])
    assert response.total == 0
    assert len(response.memories) == 0

    # Test empty XP events
    response = map_xp_events_to_list_response([])
    assert response.total == 0
    assert len(response.events) == 0
