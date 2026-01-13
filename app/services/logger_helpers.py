"""Helper functions for data flow logging to reduce code duplication."""

from typing import Optional, Any


def format_user_info(user_id: Optional[int]) -> str:
    """Format user ID for consistent logging across all log methods.

    Args:
        user_id: User ID or None

    Returns:
        Formatted string like " [user=123]" or empty string
    """
    return f" [user={user_id}]" if user_id else ""


def format_data_preview(data: dict, max_len: int = 100) -> str:
    """Format data preview for logging, truncating long values.

    Args:
        data: Dictionary of data to format
        max_len: Maximum length of formatted string

    Returns:
        Truncated string representation
    """
    preview = {}
    for key, value in data.items():
        if isinstance(value, str) and len(value) > 50:
            preview[key] = f"{value[:50]}..."
        elif isinstance(value, (list, dict)) and len(str(value)) > 50:
            preview[key] = f"{type(value).__name__}[{len(value)}]"
        else:
            preview[key] = value

    result = str(preview)
    if len(result) > max_len:
        return result[:max_len] + "..."
    return result


def build_log_message(
    icon: str,
    system: str,
    operation: str,
    direction: str,
    target: str,
    info: str,
    user_id: Optional[int] = None,
) -> str:
    """Build a standardized log message.

    Args:
        icon: Emoji icon for the log type
        system: System name (POSTGRES, QDRANT, NEO4J)
        operation: Operation type (INSERT, UPDATE, SEARCH, etc.)
        direction: Arrow direction (→ for write, ← for read)
        target: Target table/collection/node
        info: Additional information
        user_id: Optional user ID

    Returns:
        Formatted log message

    Example:
        >>> build_log_message("📝", "POSTGRES", "INSERT", "→", "users", "name='John'", 123)
        "📝 POSTGRES INSERT [user=123] → users: name='John'"
    """
    user_info = format_user_info(user_id)
    return f"{icon} {system} {operation}{user_info} {direction} {target}: {info}"
