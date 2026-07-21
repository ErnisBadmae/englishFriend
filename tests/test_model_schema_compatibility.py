"""
Тесты совместимости SQLAlchemy моделей с SQL миграциями.
Проверяет, что модели соответствуют схеме БД из db/migrations/postgres/.
"""

import os

import pytest
import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database import Base
from app.models.core_tables import (
    User,
    Session,
    Utterance,
    Feedback,
    Correction,
    UserChannelIdentity,
)
from app.models.extended_tables import UserInterest, Memory, LearningPlan, XPEvent
from app.models.enums_and_dimensions import DimEmotion, DimTopic, DimAccent
from app.models.ml_technical import (
    MlProgressReview,
    MlTechnicalAttempt,
    MlTechnicalExternalReview,
    MlTechnicalSession,
    MlTechnicalSessionItem,
)

TEST_DATABASE_URL = os.getenv("ML_TECHNICAL_PG_TEST_URL")


@pytest_asyncio.fixture()
async def test_engine():
    """Создание тестового движка БД"""
    if not TEST_DATABASE_URL:
        pytest.skip("ML_TECHNICAL_PG_TEST_URL is not configured; schema checks skipped")
    if "postgresql" not in TEST_DATABASE_URL:
        pytest.skip("schema compatibility checks require PostgreSQL")

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
    except (OperationalError, ProgrammingError) as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL schema unavailable: {exc.__class__.__name__}")

    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.mark.integration
class TestModelSchemaCompatibility:
    """Тесты совместимости моделей с SQL схемой"""

    async def test_tables_created(self, test_engine):
        """Проверка, что все таблицы создаются успешно"""
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            tables = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )

        # Проверяем наличие таблиц
        expected_tables = [
            "users",
            "user_channel_identity",
            "user_interest",
            "sessions",
            "utterances",
            "feedback",
            "corrections",
            "memories",
            "learning_plan",
            "xp_events",
            "dim_emotion",
            "dim_topic",
            "dim_accent",
            "ml_technical_sessions",
            "ml_technical_session_items",
            "ml_technical_attempts",
            "ml_technical_external_reviews",
            "ml_progress_reviews",
        ]

        for table in expected_tables:
            assert table in tables, f"Таблица {table} не создана"

    async def test_user_table_columns(self, test_engine):
        """Проверка колонок таблицы users"""
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            columns = await conn.run_sync(
                lambda sync_conn: {
                    col["name"]: col for col in inspect(sync_conn).get_columns("users")
                }
            )

        # Проверяем наличие основных колонок
        assert "id" in columns
        assert "telegram_id" in columns
        assert "username" in columns
        assert "language_level" in columns
        assert "primary_channel" in columns
        assert "accent_pref" in columns
        assert "created_at" in columns
        assert "deleted_at" in columns

        # Проверяем типы
        assert columns["id"]["type"].python_type == int or columns["id"][
            "type"
        ].python_type == type(None)
        assert columns["telegram_id"]["nullable"] == True

    async def test_session_table_columns(self, test_engine):
        """Проверка колонок таблицы sessions"""
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            columns = await conn.run_sync(
                lambda sync_conn: {
                    col["name"]: col
                    for col in inspect(sync_conn).get_columns("sessions")
                }
            )

        # Проверяем наличие основных колонок
        assert "id" in columns
        assert "user_id" in columns
        assert "started_at" in columns
        assert "ended_at" in columns
        assert "audio_url" in columns
        assert "lang_code" in columns
        assert "call_quality" in columns
        assert "status" in columns

        # Проверяем типы
        assert columns["lang_code"]["nullable"] == False

    async def test_foreign_keys(self, test_engine):
        """Проверка внешних ключей"""
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            foreign_keys = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_foreign_keys("sessions")
            )

        # Проверяем FK sessions -> users
        user_fk = [fk for fk in foreign_keys if "user_id" in fk["constrained_columns"]]
        assert len(user_fk) > 0, "Отсутствует FK sessions.user_id -> users.id"

    async def test_indexes(self, test_engine):
        """Проверка индексов"""
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            indexes = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_indexes("users")
            )

        # Проверяем наличие индексов
        index_names = [idx["name"] for idx in indexes]
        assert any(
            "telegram_id" in str(idx) for idx in indexes
        ), "Отсутствует индекс на telegram_id"

    async def test_model_to_sql_mapping(self, test_engine):
        """Проверка маппинга моделей на SQL таблицы"""
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Проверяем соответствие моделей таблицам
        assert User.__tablename__ == "users"
        assert Session.__tablename__ == "sessions"
        assert Utterance.__tablename__ == "utterances"
        assert Feedback.__tablename__ == "feedback"
        assert Correction.__tablename__ == "corrections"
        assert UserInterest.__tablename__ == "user_interest"
        assert Memory.__tablename__ == "memories"
        assert LearningPlan.__tablename__ == "learning_plan"
        assert XPEvent.__tablename__ == "xp_events"
        assert DimEmotion.__tablename__ == "dim_emotion"
        assert DimTopic.__tablename__ == "dim_topic"
        assert DimAccent.__tablename__ == "dim_accent"
        assert MlTechnicalSession.__tablename__ == "ml_technical_sessions"
        assert MlTechnicalSessionItem.__tablename__ == "ml_technical_session_items"
        assert MlTechnicalAttempt.__tablename__ == "ml_technical_attempts"
        assert (
            MlTechnicalExternalReview.__tablename__ == "ml_technical_external_reviews"
        )
        assert MlProgressReview.__tablename__ == "ml_progress_reviews"
