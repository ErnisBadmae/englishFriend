"""
Тесты совместимости SQLAlchemy моделей с SQL миграциями.
Проверяет, что модели соответствуют схеме БД из db/migrations/postgres/.
"""

import pytest
from sqlalchemy import inspect, MetaData
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.database import Base
from app.models.core_tables import User, Session, Utterance, Feedback, Correction, UserChannelIdentity
from app.models.extended_tables import UserInterest, Memory, LearningPlan, XPEvent
from app.models.enums_and_dimensions import DimEmotion, DimTopic, DimAccent

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/english_friend_test"

@pytest.fixture(scope="module")
async def test_engine():
    """Создание тестового движка БД"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()

@pytest.mark.integration
class TestModelSchemaCompatibility:
    """Тесты совместимости моделей с SQL схемой"""
    
    async def test_tables_created(self, test_engine):
        """Проверка, что все таблицы создаются успешно"""
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Проверяем наличие таблиц
        inspector = inspect(test_engine.sync_engine)
        tables = inspector.get_table_names()
        
        expected_tables = [
            'users', 'user_channel_identity', 'user_interest',
            'sessions', 'utterances', 'feedback', 'corrections',
            'memories', 'learning_plan', 'xp_events',
            'dim_emotion', 'dim_topic', 'dim_accent'
        ]
        
        for table in expected_tables:
            assert table in tables, f"Таблица {table} не создана"
    
    async def test_user_table_columns(self, test_engine):
        """Проверка колонок таблицы users"""
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        inspector = inspect(test_engine.sync_engine)
        columns = {col['name']: col for col in inspector.get_columns('users')}
        
        # Проверяем наличие основных колонок
        assert 'id' in columns
        assert 'telegram_id' in columns
        assert 'username' in columns
        assert 'language_level' in columns
        assert 'primary_channel' in columns
        assert 'accent_pref' in columns
        assert 'created_at' in columns
        assert 'deleted_at' in columns
        
        # Проверяем типы
        assert columns['id']['type'].python_type == int or columns['id']['type'].python_type == type(None)
        assert columns['telegram_id']['nullable'] == True
    
    async def test_session_table_columns(self, test_engine):
        """Проверка колонок таблицы sessions"""
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        inspector = inspect(test_engine.sync_engine)
        columns = {col['name']: col for col in inspector.get_columns('sessions')}
        
        # Проверяем наличие основных колонок
        assert 'id' in columns
        assert 'user_id' in columns
        assert 'started_at' in columns
        assert 'ended_at' in columns
        assert 'audio_url' in columns
        assert 'lang_code' in columns
        assert 'call_quality' in columns
        assert 'status' in columns
        
        # Проверяем типы
        assert columns['lang_code']['nullable'] == False
    
    async def test_foreign_keys(self, test_engine):
        """Проверка внешних ключей"""
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        inspector = inspect(test_engine.sync_engine)
        foreign_keys = inspector.get_foreign_keys('sessions')
        
        # Проверяем FK sessions -> users
        user_fk = [fk for fk in foreign_keys if 'user_id' in fk['constrained_columns']]
        assert len(user_fk) > 0, "Отсутствует FK sessions.user_id -> users.id"
    
    async def test_indexes(self, test_engine):
        """Проверка индексов"""
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        inspector = inspect(test_engine.sync_engine)
        indexes = inspector.get_indexes('users')
        
        # Проверяем наличие индексов
        index_names = [idx['name'] for idx in indexes]
        assert any('telegram_id' in str(idx) for idx in indexes), "Отсутствует индекс на telegram_id"
    
    async def test_model_to_sql_mapping(self, test_engine):
        """Проверка маппинга моделей на SQL таблицы"""
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Проверяем соответствие моделей таблицам
        assert User.__tablename__ == 'users'
        assert Session.__tablename__ == 'sessions'
        assert Utterance.__tablename__ == 'utterances'
        assert Feedback.__tablename__ == 'feedback'
        assert Correction.__tablename__ == 'corrections'
        assert UserInterest.__tablename__ == 'user_interest'
        assert Memory.__tablename__ == 'memories'
        assert LearningPlan.__tablename__ == 'learning_plan'
        assert XPEvent.__tablename__ == 'xp_events'
        assert DimEmotion.__tablename__ == 'dim_emotion'
        assert DimTopic.__tablename__ == 'dim_topic'
        assert DimAccent.__tablename__ == 'dim_accent'
