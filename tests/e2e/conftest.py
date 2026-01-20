"""Fixtures for E2E Business Logic Tests.

Provides mock database sessions, services, and test data.
"""

from __future__ import annotations

import pytest
from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock


@dataclass
class MockUser:
    """Mock User object for testing."""
    id: int = 1
    username: str = "testuser"
    channel_id: str = "telegram"
    identity: str = "test_123"
    language_level: str = "B1"
    native_language: str = "ru"
    total_xp: int = 0
    current_streak: int = 0
    max_streak: int = 0
    last_activity_date: Optional[date] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MockLearningPlan:
    """Mock LearningPlan object for testing."""
    id: int = 1
    user_id: int = 1
    roadmap: dict = field(default_factory=dict)
    level_target: Optional[str] = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MockVocabularyCard:
    """Mock VocabularyCard object for testing."""
    id: int = 1
    user_id: int = 1
    word: str = "example"
    translation: Optional[str] = None
    example_sentence: Optional[str] = None
    fsrs_state: int = 0
    fsrs_step: int = 0
    fsrs_stability: float = 0.0
    fsrs_difficulty: float = 0.0
    due_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    review_count: int = 0
    correct_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MockXPEvent:
    """Mock XPEvent object for testing."""
    id: int = 1
    user_id: int = 1
    session_id: Optional[str] = None
    kind: str = "session_complete"
    points: int = 10
    happened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MockAsyncSession:
    """Mock async database session."""

    def __init__(self):
        self._storage: dict[str, list[Any]] = {
            "users": [],
            "learning_plans": [],
            "vocabulary_cards": [],
            "xp_events": [],
        }
        self._committed = False
        self._commit_called = False
        self._added_objects: list[Any] = []

    async def execute(self, statement):
        """Mock execute."""
        return MagicMock(
            scalar_one_or_none=MagicMock(return_value=None),
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
            scalar=MagicMock(return_value=0),
        )

    async def get(self, model_class, pk):
        """Mock get by primary key."""
        if model_class.__name__ == "User":
            if self._storage["users"]:
                return self._storage["users"][0]
            return MockUser(id=pk)
        return None

    def add(self, obj):
        """Mock add object to session."""
        self._added_objects.append(obj)

    async def commit(self):
        """Mock commit."""
        self._commit_called = True
        self._committed = True

    async def refresh(self, obj):
        """Mock refresh."""
        pass

    async def rollback(self):
        """Mock rollback."""
        self._committed = False

    @property
    def commit_was_called(self) -> bool:
        """Check if commit was called."""
        return self._commit_called


@pytest.fixture
def mock_db() -> MockAsyncSession:
    """Provide mock database session."""
    return MockAsyncSession()


@pytest.fixture
def mock_user() -> MockUser:
    """Provide mock user."""
    return MockUser()


@pytest.fixture
def mock_learning_plan() -> MockLearningPlan:
    """Provide mock learning plan."""
    return MockLearningPlan(
        roadmap={
            "goal": None,
            "focus_areas": [],
            "milestones": [],
            "preferred_mode": "free_conversation",
        }
    )


@pytest.fixture
def test_messages() -> dict[str, str]:
    """Provide test messages for various scenarios."""
    return {
        "ml_interview": "I want to prepare for ML interview",
        "software_interview": "Help me practice for software developer interview",
        "general_fluency": "I want to improve my English fluency",
        "job_interview": "I need to prepare for a job interview",
        "ielts": "I'm preparing for IELTS exam",
        "business": "I want to learn business English",
        "no_goal": "Hello, how are you?",
    }


class E2ETestContext:
    """Context for E2E test execution."""

    def __init__(self):
        self.user = MockUser()
        self.db = MockAsyncSession()
        self.learning_plan: Optional[MockLearningPlan] = None
        self.detected_goal: Optional[str] = None
        self.selected_mode: Optional[str] = None
        self.vocabulary_cards: list[MockVocabularyCard] = []
        self.xp_events: list[MockXPEvent] = []
        self.streak_info: Optional[dict] = None

        # Track method calls for assertions
        self.calls: dict[str, list[dict]] = {
            "db_commit": [],
            "goal_detection": [],
            "mode_selection": [],
            "vocabulary_creation": [],
            "xp_award": [],
            "streak_checkin": [],
        }


@pytest.fixture
def e2e_context() -> E2ETestContext:
    """Provide E2E test context."""
    return E2ETestContext()
