from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator, Optional, Any
from sqlalchemy import event

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
            echo=False,
            future=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=settings.db_pool_pre_ping,
        )

        @event.listens_for(_engine.sync_engine, "connect")
        def _register_enum_codecs(dbapi_connection, connection_record):
            """Регистрируем codec для enum типов, чтобы asyncpg принимал строки."""
            info = connection_record.info
            if info.get("enum_codecs_registered"):
                return

            asyncpg_conn = dbapi_connection.driver_connection
            enums = ("memory_kind", "cefr_level", "access_channel")
            for enum_name in enums:
                dbapi_connection.await_(
                    asyncpg_conn.set_type_codec(
                        enum_name,
                        schema="public",
                        encoder=str,
                        decoder=str,
                        format="text"
                    )
                )
            info["enum_codecs_registered"] = True

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


# Экспорт для тестов
async_session_maker = _get_session_maker


def get_async_session():
    """
    Получить контекстный менеджер для создания async сессии.

    Используется в сервисах для прямого создания сессий:

    async with get_async_session()() as session:
        result = await session.execute(...)

    Returns:
        Фабрика async_sessionmaker
    """
    return _get_session_maker()