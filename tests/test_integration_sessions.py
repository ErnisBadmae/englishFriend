"""
Интеграционные тесты для Sessions API с реальной БД.
Требуют запущенного PostgreSQL.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from datetime import datetime

from main import app
from app.core.database import Base, get_db
from app.models.core_tables import User, Session
from datetime import datetime

# Тестовая БД
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/english_friend_test"

@pytest.fixture(scope="function")
async def test_db_session():
    """Создание тестовой БД и сессии для каждого теста"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture(scope="function")
def test_client(test_db_session):
    """Переопределяем get_db для использования тестовой БД"""
    async def override_get_db():
        yield test_db_session
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def test_user(test_client):
    """Создает тестового пользователя"""
    user_data = {
        "telegram_id": 555666777,
        "username": "session_test_user"
    }
    response = test_client.post("/api/v1/users/", json=user_data)
    return response.json()

@pytest.mark.integration
class TestSessionsAPI:
    """Интеграционные тесты для Sessions API"""
    
    def test_create_session_success(self, test_client, test_user):
        """Тест успешного создания сессии"""
        session_data = {
            "user_id": test_user["id"],
            "lang_code": "en"
        }
        
        response = test_client.post("/api/v1/sessions/", json=session_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == test_user["id"]
        assert data["lang_code"] == "en"
        assert data["status"] == "active"
        assert "id" in data
        assert "started_at" in data
    
    def test_get_session_by_id(self, test_client, test_user):
        """Тест получения сессии по ID"""
        # Создаем сессию
        session_data = {
            "user_id": test_user["id"],
            "lang_code": "ru"
        }
        create_response = test_client.post("/api/v1/sessions/", json=session_data)
        session_id = create_response.json()["id"]
        
        # Получаем сессию
        response = test_client.get(f"/api/v1/sessions/{session_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_id
        assert data["user_id"] == test_user["id"]
        assert data["lang_code"] == "ru"
    
    def test_get_session_not_found(self, test_client):
        """Тест получения несуществующей сессии"""
        response = test_client.get("/api/v1/sessions/00000000-0000-0000-0000-000000000000")
        
        assert response.status_code == 404
        assert "не найдена" in response.json()["detail"]
    
    def test_get_user_sessions(self, test_client, test_user):
        """Тест получения сессий пользователя"""
        # Создаем несколько сессий
        for i in range(3):
            session_data = {
                "user_id": test_user["id"],
                "lang_code": "en"
            }
            test_client.post("/api/v1/sessions/", json=session_data)
        
        # Получаем список сессий
        response = test_client.get(f"/api/v1/sessions/user/{test_user['id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["sessions"]) >= 3
        assert data["total"] >= 3
    
    def test_update_session(self, test_client, test_user):
        """Тест обновления сессии"""
        # Создаем сессию
        session_data = {
            "user_id": test_user["id"],
            "lang_code": "en"
        }
        create_response = test_client.post("/api/v1/sessions/", json=session_data)
        session_id = create_response.json()["id"]
        
        # Обновляем сессию
        update_data = {
            "audio_url": "http://example.com/audio.mp3",
            "lang_code": "ru"
        }
        response = test_client.put(f"/api/v1/sessions/{session_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["audio_url"] == "http://example.com/audio.mp3"
        assert data["lang_code"] == "ru"
    
    def test_complete_session(self, test_client, test_user):
        """Тест завершения сессии"""
        # Создаем сессию
        session_data = {
            "user_id": test_user["id"],
            "lang_code": "en"
        }
        create_response = test_client.post("/api/v1/sessions/", json=session_data)
        session_id = create_response.json()["id"]
        
        # Завершаем сессию
        response = test_client.post(f"/api/v1/sessions/{session_id}/complete")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["ended_at"] is not None
    
    def test_update_session_status(self, test_client, test_user):
        """Тест обновления статуса сессии"""
        # Создаем сессию
        session_data = {
            "user_id": test_user["id"],
            "lang_code": "en"
        }
        create_response = test_client.post("/api/v1/sessions/", json=session_data)
        session_id = create_response.json()["id"]
        
        # Обновляем статус
        update_data = {
            "status": "cancelled"
        }
        response = test_client.put(f"/api/v1/sessions/{session_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
