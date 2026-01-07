from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
from contextlib import asynccontextmanager
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.api import users, sessions, dimensions, utterances_and_feedback, memory_and_interests, voice, agent_chat, gamification
from app.core.config import settings
from app.core.database import init_db
from app.core.middleware import PrometheusMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения."""
    try:
        await init_db()
        print("База данных инициализирована")
    except Exception as e:
        print(f"Ошибка инициализации БД: {e}")
        print("Продолжаем без БД...")

    yield

    print("Приложение остановлено")


app = FastAPI(
    title=settings.api_title,
    description="API для ИИ-репетитора по английскому языку",
    version=settings.api_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

app.add_middleware(PrometheusMiddleware)

# CORS для фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "https://*.telegram.org"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роутеры
app.include_router(users.router)
app.include_router(sessions.router)
app.include_router(dimensions.router)
app.include_router(utterances_and_feedback.router)
app.include_router(memory_and_interests.router)
app.include_router(voice.router)
app.include_router(agent_chat.router)
app.include_router(gamification.router)


@app.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "healthy", "message": "English Friend API работает"}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
