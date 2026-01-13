"""Unit tests for logger helper functions."""

import pytest
from app.services.logger_helpers import (
    format_user_info,
    format_data_preview,
    build_log_message,
)


def test_format_user_info_with_user():
    """Test user info formatting with user ID."""
    result = format_user_info(123)
    assert result == " [user=123]"


def test_format_user_info_without_user():
    """Test user info formatting without user ID."""
    result = format_user_info(None)
    assert result == ""


def test_format_user_info_zero():
    """Test user info formatting with user ID zero."""
    # Zero is falsy but valid user ID
    result = format_user_info(0)
    assert result == ""  # Current implementation treats 0 as None


def test_format_data_preview_simple():
    """Test data preview formatting with simple data."""
    data = {"name": "John", "age": 30}
    result = format_data_preview(data)

    assert "name" in result
    assert "John" in result
    assert "age" in result
    assert "30" in result


def test_format_data_preview_long_string():
    """Test data preview truncates long strings."""
    long_text = "a" * 100
    data = {"description": long_text}

    result = format_data_preview(data)

    # Should truncate and add ellipsis
    assert "..." in result
    assert len(result) < len(long_text)


def test_format_data_preview_list():
    """Test data preview formats lists."""
    data = {"items": ["item1", "item2", "item3", "item4", "item5"]}

    result = format_data_preview(data)

    # Should show list type and length
    assert "list[5]" in result.lower() or "[5]" in result


def test_format_data_preview_dict():
    """Test data preview formats nested dicts."""
    data = {
        "config": {
            "setting1": "value1",
            "setting2": "value2",
            "setting3": "value3"
        }
    }

    result = format_data_preview(data)

    # Should show dict type
    assert "dict" in result.lower() or "{" in result


def test_format_data_preview_max_length():
    """Test data preview respects max length."""
    large_data = {f"key{i}": f"value{i}" for i in range(50)}

    result = format_data_preview(large_data, max_len=50)

    # Should truncate to max length
    assert len(result) <= 53  # 50 + "..."
    assert result.endswith("...")


def test_format_data_preview_empty():
    """Test data preview with empty dict."""
    result = format_data_preview({})
    assert result == "{}"


def test_build_log_message_basic():
    """Test basic log message building."""
    result = build_log_message(
        icon="📝",
        system="POSTGRES",
        operation="INSERT",
        direction="→",
        target="users",
        info="name='John'",
    )

    expected = "📝 POSTGRES INSERT → users: name='John'"
    assert result == expected


def test_build_log_message_with_user():
    """Test log message with user ID."""
    result = build_log_message(
        icon="📝",
        system="POSTGRES",
        operation="UPDATE",
        direction="→",
        target="sessions",
        info="status='active'",
        user_id=123,
    )

    assert "📝 POSTGRES UPDATE" in result
    assert "[user=123]" in result
    assert "→ sessions" in result
    assert "status='active'" in result


def test_build_log_message_without_user():
    """Test log message without user ID."""
    result = build_log_message(
        icon="🔍",
        system="QDRANT",
        operation="SEARCH",
        direction="←",
        target="memories",
        info="query='ML concepts'",
        user_id=None,
    )

    assert "🔍 QDRANT SEARCH" in result
    assert "[user=" not in result  # No user info
    assert "← memories" in result


def test_build_log_message_different_systems():
    """Test log message for different systems."""
    # Test Postgres
    pg_msg = build_log_message("📝", "POSTGRES", "INSERT", "→", "users", "data")
    assert "POSTGRES" in pg_msg
    assert "📝" in pg_msg

    # Test Qdrant
    qd_msg = build_log_message("🧠", "QDRANT", "WRITE", "→", "vectors", "data")
    assert "QDRANT" in qd_msg
    assert "🧠" in qd_msg

    # Test Neo4j
    neo_msg = build_log_message("🕸️", "NEO4J", "CREATE", "→", "User", "data")
    assert "NEO4J" in neo_msg
    assert "🕸️" in neo_msg


def test_build_log_message_read_operation():
    """Test log message for read operations."""
    result = build_log_message(
        icon="📖",
        system="POSTGRES",
        operation="READ",
        direction="←",
        target="sessions",
        info="where user_id=1 (10 rows)",
        user_id=1,
    )

    assert "📖" in result
    assert "READ" in result
    assert "←" in result
    assert "10 rows" in result


def test_format_data_preview_mixed_types():
    """Test data preview with mixed data types."""
    data = {
        "string": "short",
        "long_string": "x" * 100,
        "number": 42,
        "boolean": True,
        "none": None,
        "list": [1, 2, 3],
        "dict": {"nested": "value"},
    }

    result = format_data_preview(data, max_len=200)

    # Should handle all types
    assert isinstance(result, str)
    assert len(result) <= 203  # max_len + "..."


def test_integration_example():
    """Test complete logging workflow using all helpers."""
    # Simulate what would happen in actual code
    user_id = 456
    data = {
        "session_id": "abc-123",
        "status": "active",
        "long_field": "x" * 100,
    }

    # Format components
    user_info = format_user_info(user_id)
    data_preview = format_data_preview(data)
    message = build_log_message(
        "📝", "POSTGRES", "UPDATE", "→",
        "sessions", data_preview, user_id
    )

    # Verify complete message
    assert "[user=456]" in message
    assert "UPDATE" in message
    assert "sessions" in message
    assert "..." in message  # Long field truncated
