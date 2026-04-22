import logging
import sys

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
from contextlib import asynccontextmanager
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.api import (
    agent_chat,
    career,
    dimensions,
    gamification,
    interviews,
    memory_and_interests,
    programs,
    sessions,
    users,
    utterances_and_feedback,
    vocabulary,
    voice,
)
from app.core.config import settings
from app.core.database import init_db
from app.core.middleware import PrometheusMiddleware, RequestIDMiddleware, MetricsLogFilter, RequestIDFormatter
from app.core.observability import get_langfuse, shutdown_langfuse


# =============================================================================
# Logging Configuration
# =============================================================================

def setup_logging():
    """Configure logging for the application.

    Loggers:
    - root: General application logs (INFO)
    - pedagogy: Pedagogical decisions from LangGraph agent (INFO)
    - app.agent: Agent state machine logs (DEBUG)
    - sqlalchemy.engine: SQL queries (WARNING by default, INFO for debugging)

    Features:
    - Request ID included in logs via RequestIDFormatter
    - /metrics and /health filtered from access logs via MetricsLogFilter
    """
    # Format with timestamp, request ID, and logger name
    formatter = RequestIDFormatter(
        "%(asctime)s %(request_id)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    # Console handler with metrics filter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(MetricsLogFilter())

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # Clear existing handlers to avoid duplicates on reload
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    # Pedagogy logger - shows agent decisions with emojis
    pedagogy_logger = logging.getLogger("pedagogy")
    pedagogy_logger.setLevel(logging.INFO)

    # Agent logger - shows state transitions
    agent_logger = logging.getLogger("app.agent")
    agent_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    # Reduce SQLAlchemy noise (echo=False in database.py, but also set logger)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Reduce httpx/httpcore noise
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Silence noisy third-party loggers
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("langgraph").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
    logging.getLogger("langchain_core").setLevel(logging.WARNING)
    logging.getLogger("groq").setLevel(logging.WARNING)
    logging.getLogger("langfuse").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

    # Filter uvicorn access logs for /metrics spam
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.addFilter(MetricsLogFilter())


setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    logger = logging.getLogger(__name__)

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database init failed: {e}")
        logger.info("Continuing without database...")

    # Initialize Langfuse (lazy, logs warning if not configured)
    langfuse = get_langfuse()
    if langfuse:
        logger.info("Langfuse observability enabled")

    yield

    # Shutdown Langfuse (flush pending traces)
    shutdown_langfuse()
    logger.info("Application stopped")


app = FastAPI(
    title=settings.api_title,
    description="API для ИИ-репетитора по английскому языку",
    version=settings.api_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Request ID middleware (must be first to set context for other middleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(PrometheusMiddleware)

# CORS для фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# Роутеры
app.include_router(users.router)
app.include_router(sessions.router)
app.include_router(dimensions.router)
app.include_router(utterances_and_feedback.router)
app.include_router(memory_and_interests.router)
app.include_router(voice.router)
app.include_router(agent_chat.router)
app.include_router(career.router)
app.include_router(gamification.router)
app.include_router(vocabulary.router)
app.include_router(programs.router)
app.include_router(interviews.router)


@app.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "healthy", "message": "English Friend API работает"}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
