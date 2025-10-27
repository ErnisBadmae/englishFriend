from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator, Optional, Any

from app.core.config import settings

# Ленивая инициализация движка БД
_engine: Optional[AsyncEngine] = None
_AsyncSessionLocal: Optional[Any] = None

def _get_session_maker():
    """Получить или создать фабрику сессий"""
    global _engine, _AsyncSessionLocal
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            future=True
        )
        _AsyncSessionLocal = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    return _AsyncSessionLocal

class Base(DeclarativeBase):
    """Базовый класс для всех моделей SQLAlchemy"""
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency для получения сессии БД.
    
    Используется в FastAPI endpoints для автоматического
    управления сессиями БД.
    """
    AsyncSessionLocal = _get_session_maker()
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    """
    Инициализация базы данных.
    
    Создает все таблицы, определенные в моделях.
    Вызывается при старте приложения.
    """
    global _engine
    if _engine is None:
        AsyncSessionLocal = _get_session_maker()
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
