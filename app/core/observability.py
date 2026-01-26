"""Observability module for English Friend.

Provides:
- Langfuse client singleton for LLM tracing
- Request context (request_id) for correlation
- Helper functions for creating traces and spans

Usage:
    from app.core.observability import get_langfuse, get_request_id, set_request_context

    # In middleware: set request context
    set_request_context(request_id="abc123", user_id=1)

    # In LLM calls: create traces
    langfuse = get_langfuse()
    trace = langfuse.trace(name="chat", user_id=str(user_id))

    # Get current request_id anywhere
    request_id = get_request_id()
"""

import logging
import uuid
from contextvars import ContextVar
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Context variables for request correlation
_request_id: ContextVar[str] = ContextVar("request_id", default="")
_user_id: ContextVar[Optional[int]] = ContextVar("user_id", default=None)
_session_id: ContextVar[Optional[str]] = ContextVar("session_id", default=None)

# Langfuse client singleton
_langfuse_client = None


def get_langfuse():
    """Get or create Langfuse client singleton.

    Returns None if Langfuse is disabled or credentials are missing.
    """
    global _langfuse_client

    if _langfuse_client is not None:
        return _langfuse_client

    if not settings.langfuse_enabled:
        logger.info("Langfuse disabled via config")
        return None

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.warning(
            "Langfuse credentials not configured. Set LANGFUSE_PUBLIC_KEY and "
            "LANGFUSE_SECRET_KEY in .env to enable LLM tracing."
        )
        return None

    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        logger.info(f"Langfuse initialized: {settings.langfuse_host}")
        return _langfuse_client
    except ImportError:
        logger.warning("langfuse package not installed. Run: pip install langfuse")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Langfuse: {e}")
        return None


def shutdown_langfuse():
    """Flush and shutdown Langfuse client."""
    global _langfuse_client
    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
            _langfuse_client.shutdown()
            logger.info("Langfuse shutdown complete")
        except Exception as e:
            logger.error(f"Error shutting down Langfuse: {e}")
        finally:
            _langfuse_client = None


# ============== Request Context ==============


def generate_request_id() -> str:
    """Generate a short request ID for logging.

    Returns 8-character hex string (e.g., "a1b2c3d4").
    """
    return uuid.uuid4().hex[:8]


def set_request_context(
    request_id: Optional[str] = None,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
) -> str:
    """Set request context for current async task.

    Args:
        request_id: Request ID (generated if not provided)
        user_id: User ID for the request
        session_id: Session ID for the request

    Returns:
        The request_id that was set
    """
    rid = request_id or generate_request_id()
    _request_id.set(rid)
    if user_id is not None:
        _user_id.set(user_id)
    if session_id is not None:
        _session_id.set(session_id)
    return rid


def get_request_id() -> str:
    """Get current request ID."""
    return _request_id.get()


def get_user_id() -> Optional[int]:
    """Get current user ID."""
    return _user_id.get()


def get_session_id() -> Optional[str]:
    """Get current session ID."""
    return _session_id.get()


def clear_request_context():
    """Clear request context."""
    _request_id.set("")
    _user_id.set(None)
    _session_id.set(None)


# ============== Langfuse Helpers ==============


def create_trace(
    name: str,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    """Create a Langfuse trace for the current request.

    Args:
        name: Trace name (e.g., "agent_turn", "chat")
        user_id: User ID (uses context if not provided)
        session_id: Session ID (uses context if not provided)
        metadata: Additional metadata

    Returns:
        Langfuse trace object or None if Langfuse is disabled
    """
    langfuse = get_langfuse()
    if langfuse is None:
        return None

    uid = user_id or get_user_id()
    sid = session_id or get_session_id()
    rid = get_request_id()

    try:
        trace = langfuse.trace(
            name=name,
            id=rid if rid else None,  # Use request_id as trace_id for correlation
            user_id=str(uid) if uid else None,
            session_id=sid,
            metadata=metadata or {},
        )
        return trace
    except Exception as e:
        logger.error(f"Failed to create Langfuse trace: {e}")
        return None


def create_generation(
    trace,
    name: str,
    model: str,
    input_messages: list[dict],
    output: str,
    usage: Optional[dict] = None,
    latency_ms: Optional[float] = None,
    metadata: Optional[dict] = None,
):
    """Log an LLM generation to Langfuse.

    Args:
        trace: Parent trace (from create_trace)
        name: Generation name (e.g., "router_llm", "onboarding_llm")
        model: Model name (e.g., "groq/llama-3.3-70b")
        input_messages: List of message dicts
        output: LLM output text
        usage: Token usage dict (input_tokens, output_tokens)
        latency_ms: Latency in milliseconds
        metadata: Additional metadata
    """
    if trace is None:
        return None

    try:
        generation = trace.generation(
            name=name,
            model=model,
            input=input_messages,
            output=output,
            usage=usage,
            metadata={
                **(metadata or {}),
                "latency_ms": latency_ms,
            },
        )
        return generation
    except Exception as e:
        logger.error(f"Failed to log generation to Langfuse: {e}")
        return None


def create_span(trace, name: str, metadata: Optional[dict] = None):
    """Create a span within a trace.

    Args:
        trace: Parent trace
        name: Span name (e.g., "router", "onboarding")
        metadata: Additional metadata

    Returns:
        Langfuse span object or None
    """
    if trace is None:
        return None

    try:
        return trace.span(name=name, metadata=metadata or {})
    except Exception as e:
        logger.error(f"Failed to create Langfuse span: {e}")
        return None
