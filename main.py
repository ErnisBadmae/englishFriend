from fastapi import FastAPI
from fastapi.responses import JSONResponse
from typing import Dict, Any
from contextlib import asynccontextmanager

from app.api import users, sessions, dimensions, utterances_and_feedback, memory_and_interests, chat
from app.core.config import settings
from app.core.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения.
    
    Выполняется при запуске и остановке приложения.
    """
    # Запуск: инициализация БД (временно отключено)
    try:
        # await init_db()
        print("База данных пропущена")
    except Exception as e:
        print(f"Ошибка инициализации БД: {e}")
        print("Продолжаем без БД...")
    
    yield
    
    # Остановка: очистка ресурсов (если нужно)
    print("Приложение остановлено")

# Создаем экземпляр FastAPI приложения
app = FastAPI(
    title=settings.api_title,
    description="API для ИИ-репетитора по английскому языку с PostgreSQL",
    version=settings.api_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

app.include_router(users.router)
app.include_router(sessions.router)
app.include_router(dimensions.router)
app.include_router(utterances_and_feedback.router)
app.include_router(memory_and_interests.router)
app.include_router(chat.router)

@app.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Проверка здоровья сервера.
    Простой endpoint для мониторинга состояния API.
    """
    return {"status": "healthy", "message": "English Friend API работает"}

@app.get("/api/v1/hello")
async def hello_world() -> Dict[str, Any]:
    """
    Приветственный endpoint.
    Возвращает информацию о проекте и доступных возможностях.
    """
    return {
        "message": "Привет! Я English Friend API",
        "description": "ИИ-репетитор-компаньон по английскому языку",
        "features": [
            "Голосовые диалоги в реальном времени",
            "Анализ произношения и грамматики", 
            "Персонализированное обучение",
            "Векторная память о пользователе"
        ],
        "version": "3.0.0",
            "new_features": [
                "PostgreSQL интеграция",
                "SQLAlchemy ORM модели",
                "Async/await для БД",
                "Docker Compose для PostgreSQL",
                "Автоматическая инициализация БД",
                "Расширенная схема БД",
                "Справочники (эмоции, темы, акценты)",
                "Реплики и обратная связь",
                "Память и интересы пользователей",
                "Планы обучения и XP система",
                "Лог эмоционального состояния"
            ]
    }

@app.get("/api/v1/status")
async def api_status() -> Dict[str, Any]:
    """
    Статус API с дополнительной информацией.
    Показывает текущее состояние всех компонентов системы.
    """
    return {
        "api_status": "running",
        "database": "postgresql",  # Теперь используем PostgreSQL
        "vector_db": "not_connected",
        "graph_db": "not_connected",
        "components": {
            "postgresql": {"status": "connected", "description": "Подключен на этапе 3"},
            "qdrant": {"status": "pending", "description": "Будет добавлен на этапе 5"},
            "neo4j": {"status": "pending", "description": "Будет добавлен на этапе 6"}
        },
            "current_stage": "Этап 4: Расширенная схема БД"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)