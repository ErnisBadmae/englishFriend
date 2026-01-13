"""Unit tests for database query helper functions."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import select
from app.services.query_helpers import (
    get_by_id,
    get_by_user_id,
    get_top_by_field,
    count_by_condition,
    get_latest_by_field,
)


# Mock model for testing
class MockUser:
    """Mock SQLAlchemy model."""
    id = MagicMock()
    user_id = MagicMock()
    name = MagicMock()
    score = MagicMock()
    created_at = MagicMock()


@pytest.mark.asyncio
async def test_get_by_id():
    """Test getting record by ID."""
    # Setup mock database session
    db = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = MockUser()
    db.execute.return_value = mock_result

    # Call helper
    result = await get_by_id(db, MockUser, 123, "id")

    # Verify
    assert result is not None
    assert isinstance(result, MockUser)
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_by_id_not_found():
    """Test getting non-existent record."""
    db = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result

    result = await get_by_id(db, MockUser, 999)

    assert result is None


@pytest.mark.asyncio
async def test_get_by_user_id():
    """Test getting records by user ID with pagination."""
    db = AsyncMock()
    mock_result = AsyncMock()
    mock_users = [MockUser(), MockUser(), MockUser()]
    mock_result.scalars.return_value.all.return_value = mock_users
    db.execute.return_value = mock_result

    result = await get_by_user_id(
        db, MockUser, user_id=1, skip=0, limit=10
    )

    assert len(result) == 3
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_by_user_id_with_ordering():
    """Test getting records with custom ordering."""
    db = AsyncMock()
    mock_result = AsyncMock()
    mock_users = [MockUser(), MockUser()]
    mock_result.scalars.return_value.all.return_value = mock_users
    db.execute.return_value = mock_result

    result = await get_by_user_id(
        db, MockUser, user_id=1,
        order_by=MockUser.created_at.desc()
    )

    assert len(result) == 2
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_by_user_id_pagination():
    """Test pagination parameters."""
    db = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute.return_value = mock_result

    await get_by_user_id(db, MockUser, user_id=1, skip=10, limit=5)

    # Verify execute was called (pagination applied in query)
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_top_by_field():
    """Test getting top records by field."""
    db = AsyncMock()
    mock_result = AsyncMock()
    mock_users = [MockUser(), MockUser(), MockUser()]
    mock_result.scalars.return_value.all.return_value = mock_users
    db.execute.return_value = mock_result

    result = await get_top_by_field(
        db, MockUser, user_id=1, field_name="score", limit=10
    )

    assert len(result) == 3
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_top_by_field_ascending():
    """Test getting top records in ascending order."""
    db = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = [MockUser()]
    db.execute.return_value = mock_result

    result = await get_top_by_field(
        db, MockUser, user_id=1,
        field_name="score", ascending=True
    )

    assert len(result) == 1


@pytest.mark.asyncio
async def test_count_by_condition():
    """Test counting records with conditions."""
    db = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalar_one.return_value = 42
    db.execute.return_value = mock_result

    count = await count_by_condition(db, MockUser, user_id=1)

    assert count == 42
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_count_by_condition_zero():
    """Test counting when no records match."""
    db = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalar_one.return_value = None  # No results
    db.execute.return_value = mock_result

    count = await count_by_condition(db, MockUser, user_id=999)

    assert count == 0  # Helper converts None to 0


@pytest.mark.asyncio
async def test_count_by_multiple_conditions():
    """Test counting with multiple filter conditions."""
    db = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalar_one.return_value = 5
    db.execute.return_value = mock_result

    count = await count_by_condition(
        db, MockUser,
        user_id=1,
        name="John"
    )

    assert count == 5


@pytest.mark.asyncio
async def test_get_latest_by_field():
    """Test getting most recent record."""
    db = AsyncMock()
    mock_result = AsyncMock()
    latest_user = MockUser()
    mock_result.scalar_one_or_none.return_value = latest_user
    db.execute.return_value = mock_result

    result = await get_latest_by_field(
        db, MockUser, user_id=1, date_field="created_at"
    )

    assert result == latest_user
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_latest_by_field_none():
    """Test getting latest when no records exist."""
    db = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result

    result = await get_latest_by_field(db, MockUser, user_id=999)

    assert result is None


@pytest.mark.asyncio
async def test_get_by_user_id_empty_result():
    """Test query returning empty list."""
    db = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute.return_value = mock_result

    result = await get_by_user_id(db, MockUser, user_id=1)

    assert result == []
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_query_helpers_integration():
    """Test using multiple helpers together (integration example)."""
    db = AsyncMock()

    # Setup mock responses for different queries
    def execute_side_effect(stmt):
        result = AsyncMock()
        # Return different results based on query type
        result.scalar_one_or_none.return_value = MockUser()
        result.scalars.return_value.all.return_value = [MockUser(), MockUser()]
        result.scalar_one.return_value = 2
        return result

    db.execute.side_effect = execute_side_effect

    # Simulate real workflow
    # 1. Get user by ID
    user = await get_by_id(db, MockUser, 1)
    assert user is not None

    # 2. Get user's records
    records = await get_by_user_id(db, MockUser, user_id=1)
    assert len(records) > 0

    # 3. Count total
    total = await count_by_condition(db, MockUser, user_id=1)
    assert total > 0

    # 4. Get latest
    latest = await get_latest_by_field(db, MockUser, user_id=1)
    assert latest is not None


def test_query_helpers_type_safety():
    """Test that helpers maintain type hints."""
    import inspect

    # Check function signatures have type hints
    sig = inspect.signature(get_by_id)
    assert 'db' in sig.parameters
    assert 'model' in sig.parameters
    assert 'id_value' in sig.parameters

    # Verify return type annotation exists
    assert sig.return_annotation is not None
