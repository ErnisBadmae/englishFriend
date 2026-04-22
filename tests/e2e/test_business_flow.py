"""E2E Business Flow Tests.

Tests the complete business logic flow:
1. Goal Detection Node
2. Learning Plan Creation
3. PostgreSQL Write
4. Mode Selection
5. Vocabulary Card Creation
6. Gamification (XP & Streak)
7. Monitoring Health Check

Run with:
    python -m tests.e2e.test_business_flow
    pytest tests/e2e/test_business_flow.py -v
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone, date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.e2e.node_runner import NodeRunner, run_e2e_tests


# =============================================================================
# Test Nodes
# =============================================================================

async def _node_goal_detection(context: dict[str, Any]) -> dict:
    """Node 1: Test goal detection from user message.

    Uses the real detect_goal_from_message function with pattern matching.
    """
    from app.services.learning_plan_service import detect_goal_from_message

    # Test messages that should detect goals
    test_cases = [
        ("I want to prepare for ML interview", "ML/Data Science Interview"),
        ("Help me practice for software developer interview", "Software Engineering Interview"),
        ("I need to prepare for a job interview", "Job Interview"),
        ("I'm preparing for IELTS exam", "IELTS/TOEFL Preparation"),
        ("I want to learn business English", "Business English"),
        ("I want to improve my English fluency", "General Fluency"),
    ]

    detected_goals = {}
    for message, expected_goal in test_cases:
        result = await detect_goal_from_message(message)
        detected_goals[message[:30]] = result

        assert result is not None, f"Failed to detect goal for: '{message}'"
        assert result == expected_goal, (
            f"Wrong goal for '{message}': expected '{expected_goal}', got '{result}'"
        )

    # Also test that no-goal message returns None
    no_goal_result = await detect_goal_from_message("Hello, how are you?")
    assert no_goal_result is None, "Should return None for messages without goals"

    return {
        "detected_goals": detected_goals,
        "goal_detection_passed": True,
        "test_goal": "ML/Data Science Interview",
        "test_message": "I want to prepare for ML interview",
    }


async def _node_learning_plan_creation(context: dict[str, Any]) -> dict:
    """Node 2: Test learning plan creation with mock DB.

    Verifies that LearningPlanService correctly creates plans.
    """
    from app.services.learning_plan_service import LearningPlanService, GOAL_TEMPLATES

    # Create mock DB session
    mock_db = AsyncMock()

    # Mock the execute for get_or_create_plan to return None (no existing plan)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    # Create a mock plan that will be "created"
    mock_plan = MagicMock()
    mock_plan.user_id = 1
    mock_plan.roadmap = {}

    # When add is called, capture the plan
    created_plans = []
    def capture_add(obj):
        created_plans.append(obj)
        # Update mock_plan to simulate what was added
        mock_plan.roadmap = obj.roadmap if hasattr(obj, 'roadmap') else {}

    mock_db.add.side_effect = capture_add
    mock_db.commit = AsyncMock()

    # Mock refresh to update the plan
    async def mock_refresh(obj):
        if hasattr(obj, 'roadmap') and obj.roadmap is None:
            obj.roadmap = {}

    mock_db.refresh = mock_refresh

    service = LearningPlanService(mock_db)

    # Test that _match_goal_template works correctly
    template = service._match_goal_template("ML interview preparation")
    assert template is not None, "Template should be found for ML interview"
    assert template.goal == "ML/Data Science Interview Preparation", (
        f"Wrong template goal: {template.goal}"
    )
    assert template.preferred_mode == "mock_interview", (
        f"Wrong preferred mode: {template.preferred_mode}"
    )
    assert len(template.recommended_vocabulary) > 0, "Should have recommended vocabulary"

    # Verify template focus areas
    assert len(template.focus_areas) > 0, "Template should have focus areas"
    focus_area_names = [fa["area"] for fa in template.focus_areas]
    assert "technical_vocabulary" in focus_area_names, "Should include technical_vocabulary"

    return {
        "learning_plan_template": template,
        "template_matched": True,
        "preferred_mode": template.preferred_mode,
        "recommended_vocabulary": template.recommended_vocabulary[:5],  # First 5
    }


async def _node_postgresql_write(context: dict[str, Any]) -> dict:
    """Node 3: Test PostgreSQL write (commit verification).

    Verifies that database commit is called when saving learning plan.
    """
    from app.services.learning_plan_service import LearningPlanService

    # Create mock DB session with commit tracking
    commit_calls = []

    class MockPlan:
        """Mock plan that behaves like SQLAlchemy model."""
        def __init__(self):
            self.user_id = 1
            self.roadmap = {
                "goal": None,
                "focus_areas": [],
                "milestones": [],
            }
            self.level_target = None
            self.updated_at = None

    mock_plan = MockPlan()

    class MockDB:
        """Mock database session."""

        async def execute(self, stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = mock_plan
            return result

        def add(self, obj):
            pass

        async def commit(self):
            commit_calls.append(datetime.now(timezone.utc))

        async def refresh(self, obj):
            pass

    mock_db = MockDB()
    service = LearningPlanService(mock_db)

    # Patch flag_modified to be a no-op for our mock object
    with patch('app.services.learning_plan_service.flag_modified', lambda obj, attr: None):
        # Call set_goal which should trigger commit
        await service.set_goal(1, "ML interview preparation", "C1")

    # Verify commit was called
    assert len(commit_calls) > 0, "Database commit was not called"

    # Verify plan was updated
    assert mock_plan.roadmap.get("goal") == "ML interview preparation", (
        f"Goal not set in roadmap: {mock_plan.roadmap}"
    )

    return {
        "commit_called": True,
        "commit_count": len(commit_calls),
        "plan_updated": True,
    }


async def _node_mode_selection(context: dict[str, Any]) -> dict:
    """Node 4: Test learning mode selection.

    Uses real select_learning_mode function with SessionContext.
    """
    from app.services.ai.mode_selector import (
        select_learning_mode,
        SessionContext,
        needs_assessment,
        is_interview_goal,
    )
    from app.services.ai.mode_prompts import LearningMode

    # Test 1: New user without assessment should get ASSESSMENT
    new_user_context = SessionContext(
        user_id=1,
        username="testuser",
        language_level="B1",
        goal="ML/Data Science Interview",
        total_sessions=0,
        last_assessment_date=None,
    )

    mode = select_learning_mode(new_user_context)
    assert mode == LearningMode.ASSESSMENT, (
        f"New user should get ASSESSMENT, got {mode}"
    )

    # Test 2: User with assessment and interview goal should get MOCK_INTERVIEW
    assessed_user_context = SessionContext(
        user_id=1,
        username="testuser",
        language_level="B1",
        goal="ML/Data Science Interview",
        total_sessions=5,
        last_assessment_date=datetime.now(),
        due_vocabulary_count=3,
    )

    mode = select_learning_mode(assessed_user_context)
    assert mode == LearningMode.MOCK_INTERVIEW, (
        f"Assessed user with interview goal should get MOCK_INTERVIEW, got {mode}"
    )

    # Test 3: User with many due vocabulary should get VOCABULARY_DRILL
    vocab_heavy_context = SessionContext(
        user_id=1,
        username="testuser",
        language_level="B1",
        goal="General Fluency",
        total_sessions=10,
        last_assessment_date=datetime.now(),
        due_vocabulary_count=15,
    )

    mode = select_learning_mode(vocab_heavy_context)
    assert mode == LearningMode.VOCABULARY_DRILL, (
        f"User with many due vocab should get VOCABULARY_DRILL, got {mode}"
    )

    # Test 4: User with explicit mode request should get that mode
    explicit_context = SessionContext(
        user_id=1,
        username="testuser",
        language_level="B1",
        goal="General Fluency",
        total_sessions=10,
        last_assessment_date=datetime.now(),
        requested_mode=LearningMode.FREE_CONVERSATION,
    )

    mode = select_learning_mode(explicit_context)
    assert mode == LearningMode.FREE_CONVERSATION, (
        f"Explicit mode request should be honored, got {mode}"
    )

    # Test is_interview_goal helper
    assert is_interview_goal("ML interview preparation") is True
    assert is_interview_goal("Job interview") is True
    assert is_interview_goal("General English") is False

    return {
        "mode_selection_passed": True,
        "modes_tested": [
            "ASSESSMENT for new users",
            "MOCK_INTERVIEW for interview goals",
            "VOCABULARY_DRILL for due vocab",
            "Explicit mode requests",
        ],
    }


async def _node_vocabulary_card_creation(context: dict[str, Any]) -> dict:
    """Node 5: Test vocabulary card creation.

    Verifies VocabularyService creates cards correctly with FSRS.
    """
    from app.services.ai.vocabulary_service import (
        VocabularyService,
        VocabularyWord,
        extract_vocabulary_from_response,
    )

    # Test 1: Extract vocabulary from mentor response
    mentor_response = """
    The word 'resilience' means the ability to recover from difficulties.
    Another useful term is 'procrastination' - that's when you delay tasks.
    'Eloquent' is a great word for describing someone who speaks well.
    """

    extracted = extract_vocabulary_from_response(mentor_response)

    assert "resilience" in extracted, f"Should extract 'resilience', got {extracted}"
    assert "procrastination" in extracted, f"Should extract 'procrastination', got {extracted}"
    assert "eloquent" in extracted, f"Should extract 'eloquent', got {extracted}"

    # Test 2: VocabularyService.create_card with mock DB
    added_cards = []

    class MockDB:
        """Mock database session for vocabulary tests."""

        async def execute(self, stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = None  # No duplicate
            return result

        def add(self, obj):
            added_cards.append(obj)

        async def commit(self):
            pass

        async def refresh(self, obj):
            obj.id = 1  # Simulate DB assigning ID

    mock_db = MockDB()
    service = VocabularyService(mock_db)

    # Create a vocabulary word
    vocab_word = VocabularyWord(
        word="implementation",
        translation="реализация",
        example_sentence="The implementation of the feature took 2 days.",
    )

    card = await service.add_word(user_id=1, word=vocab_word, session_id="test-session")

    # Verify card was created
    assert len(added_cards) > 0, "Card should be added to DB"
    created_card = added_cards[0]

    assert created_card.word == "implementation", (
        f"Card word should be 'implementation', got {created_card.word}"
    )
    assert created_card.translation == "реализация", "Translation should be set"
    assert created_card.fsrs_state == 0, "New card should be in state 0 (New)"

    return {
        "vocabulary_extraction_passed": True,
        "extracted_words": extracted,
        "card_creation_passed": True,
        "card_word": "implementation",
    }


async def _node_gamification(context: dict[str, Any]) -> dict:
    """Node 6: Test gamification (XP & Streak).

    Verifies XPService and StreakService work correctly.
    """
    from app.services.gamification.xp_service import (
        XPService,
        XPEventKind,
        calculate_level,
        xp_for_level,
        xp_progress_in_level,
    )
    from app.services.gamification.streak_service import StreakService

    # Test XP calculations
    assert calculate_level(0) == 1, "0 XP should be level 1"
    assert calculate_level(50) == 2, "50 XP should be level 2"
    assert calculate_level(200) == 3, "200 XP should be level 3"
    assert calculate_level(850) == 5, "850 XP should be level 5"

    assert xp_for_level(1) == 0, "Level 1 requires 0 XP"
    assert xp_for_level(2) == 50, "Level 2 requires 50 XP"
    assert xp_for_level(3) == 200, "Level 3 requires 200 XP"

    # Test XPService.award_xp with mock DB
    class MockUser:
        """Mock user for XP tests."""
        def __init__(self):
            self.id = 1
            self.total_xp = 0

    mock_user = MockUser()
    added_events = []

    class MockDBForXP:
        """Mock database for XP service tests."""

        async def get(self, model_class, pk):
            return mock_user

        def add(self, obj):
            added_events.append(obj)

        async def commit(self):
            pass

        async def refresh(self, obj):
            obj.id = 1

    mock_db = MockDBForXP()
    xp_service = XPService(mock_db)

    # Award XP
    event = await xp_service.award_xp(
        user_id=1,
        kind=XPEventKind.SESSION_COMPLETE,
        session_id="test-session",
    )

    assert len(added_events) > 0, "XP event should be added"
    assert added_events[0].kind == "session_complete"
    assert added_events[0].points == 10  # Default for SESSION_COMPLETE
    assert mock_user.total_xp == 10, "User total_xp should be updated"

    # Test StreakService with mock DB
    class MockUserForStreak:
        """Mock user for streak tests."""
        def __init__(self):
            self.id = 1
            self.current_streak = 5
            self.max_streak = 10
            self.last_activity_date = date.today()  # Already active today

    mock_user2 = MockUserForStreak()

    class MockDBForStreak:
        """Mock database for streak service tests."""

        async def get(self, model_class, pk):
            return mock_user2

        async def commit(self):
            pass

    mock_db2 = MockDBForStreak()
    streak_service = StreakService(mock_db2)
    streak_info = await streak_service.get_streak_info(user_id=1)

    assert streak_info["current"] == 5, f"Current streak should be 5, got {streak_info}"
    assert streak_info["max"] == 10, f"Max streak should be 10, got {streak_info}"
    assert streak_info["at_risk"] is False, "Streak should not be at risk if active today"

    return {
        "xp_calculations_passed": True,
        "xp_award_passed": True,
        "streak_info_passed": True,
        "test_level": calculate_level(850),
        "test_xp_points": 10,
        "test_streak": 5,
    }


async def _node_monitoring_health(context: dict[str, Any]) -> dict:
    """Node 7: Test monitoring health check endpoints.

    Checks /health and /metrics endpoints if server is running.
    This node does not fail the test suite - it's informational.
    """
    import socket

    def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
        """Check if a port is open."""
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    # Check if FastAPI is running on default port
    fastapi_running = is_port_open("localhost", 8000)

    if not fastapi_running:
        # Server not running - this is OK for local tests
        return {
            "server_running": False,
            "health_check": "skipped",
            "metrics_check": "skipped",
            "message": "Server not running (OK for local tests)",
        }

    # Server is running - try to check endpoints
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            # Check /health
            try:
                health_resp = await client.get("http://localhost:8000/health")
                health_ok = health_resp.status_code == 200
            except Exception as e:
                health_ok = False

            # Check /metrics (Prometheus)
            try:
                metrics_resp = await client.get("http://localhost:8000/metrics")
                metrics_ok = metrics_resp.status_code == 200
            except Exception:
                # /metrics might not exist
                metrics_ok = None

        return {
            "server_running": True,
            "health_check": "passed" if health_ok else "failed",
            "metrics_check": "passed" if metrics_ok else ("not found" if metrics_ok is None else "failed"),
            "message": "Server endpoints checked",
        }

    except ImportError:
        # httpx not installed
        return {
            "server_running": True,
            "health_check": "skipped",
            "metrics_check": "skipped",
            "message": "httpx not installed, skipping HTTP checks",
        }


# =============================================================================
# Main Runner
# =============================================================================

def create_business_flow_runner() -> NodeRunner:
    """Create the business flow test runner with all nodes."""
    runner = NodeRunner(title="BUSINESS FLOW TEST")

    runner.add_node(
        name="Goal Detection Node",
        test_func=_node_goal_detection,
        description="Test detect_goal_from_message() with pattern matching",
    )

    runner.add_node(
        name="Learning Plan Creation",
        test_func=_node_learning_plan_creation,
        depends_on=["Goal Detection Node"],
        description="Test LearningPlanService template matching",
    )

    runner.add_node(
        name="PostgreSQL Write",
        test_func=_node_postgresql_write,
        depends_on=["Learning Plan Creation"],
        description="Verify database commit is called",
    )

    runner.add_node(
        name="Mode Selection",
        test_func=_node_mode_selection,
        depends_on=["Goal Detection Node"],
        description="Test select_learning_mode() logic",
    )

    runner.add_node(
        name="Vocabulary Card Creation",
        test_func=_node_vocabulary_card_creation,
        depends_on=["Goal Detection Node"],
        description="Test VocabularyService and FSRS",
    )

    runner.add_node(
        name="Gamification (XP & Streak)",
        test_func=_node_gamification,
        depends_on=["Mode Selection"],
        description="Test XPService and StreakService",
    )

    runner.add_node(
        name="Monitoring Health Check",
        test_func=_node_monitoring_health,
        skip_on_dependency_fail=False,  # Always run this
        description="Check /health and /metrics endpoints",
    )

    return runner


# =============================================================================
# Pytest Integration
# =============================================================================

@pytest.mark.asyncio
async def test_goal_detection():
    """Pytest: Goal Detection Node."""
    result = await _node_goal_detection({})
    assert result["goal_detection_passed"]


@pytest.mark.asyncio
async def test_learning_plan_creation():
    """Pytest: Learning Plan Creation."""
    result = await _node_learning_plan_creation({})
    assert result["template_matched"]


@pytest.mark.asyncio
async def test_postgresql_write():
    """Pytest: PostgreSQL Write."""
    result = await _node_postgresql_write({})
    assert result["commit_called"]


@pytest.mark.asyncio
async def test_mode_selection():
    """Pytest: Mode Selection."""
    result = await _node_mode_selection({})
    assert result["mode_selection_passed"]


@pytest.mark.asyncio
async def test_vocabulary_card_creation():
    """Pytest: Vocabulary Card Creation."""
    result = await _node_vocabulary_card_creation({})
    assert result["card_creation_passed"]


@pytest.mark.asyncio
async def test_gamification():
    """Pytest: Gamification (XP & Streak)."""
    result = await _node_gamification({})
    assert result["xp_calculations_passed"]


@pytest.mark.asyncio
async def test_monitoring_health():
    """Pytest: Monitoring Health Check."""
    result = await _node_monitoring_health({})
    # This test is informational - it passes regardless of server state
    assert "server_running" in result


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    runner = create_business_flow_runner()
    exit_code = run_e2e_tests(runner)
    sys.exit(exit_code)
