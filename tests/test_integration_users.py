"""
Интеграционные тесты для Users API с реальной БД.
Требуют запущенного PostgreSQL.
"""

import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from main import app
from app.core.database import Base, get_db
from app.models.core_tables import User
from app.schemas.user import UserCreate, CEFRLevel
from datetime import datetime

# Тестовая БД
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:password@localhost:5432/english_friend_test"

@pytest.fixture(scope="function")
async def test_db_session():
    """Создание тестовой БД и сессии для каждого теста"""
    # Создаем движок для тестовой БД
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Создаем все таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Создаем сессию
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session
    
    # Очистка после теста
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

@pytest.mark.integration
class TestUsersAPI:
    """Интеграционные тесты для Users API"""
    
    def test_create_user_success(self, test_client, test_db_session):
        """Тест успешного создания пользователя"""
        user_data = {
            "telegram_id": 123456789,
            "username": "test_user",
            "language_level": "B1"
        }
        
        response = test_client.post("/api/v1/users/", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["telegram_id"] == 123456789
        assert data["username"] == "test_user"
        assert data["language_level"] == "B1"
        assert "id" in data
        assert "created_at" in data
    
    def test_create_user_duplicate_telegram_id(self, test_client, test_db_session):
        """Тест создания пользователя с дублирующимся Telegram ID"""
        # Создаем первого пользователя
        user_data = {
            "telegram_id": 999999999,
            "username": "first_user"
        }
        test_client.post("/api/v1/users/", json=user_data)
        
        # Пытаемся создать второго с тем же Telegram ID
        response = test_client.post("/api/v1/users/", json=user_data)
        
        assert response.status_code == 400
        assert "уже существует" in response.json()["detail"]
    
    def test_get_user_by_id(self, test_client, test_db_session):
        """Тест получения пользователя по ID"""
        # Создаем пользователя
        user_data = {
            "telegram_id": 111222333,
            "username": "get_user_test"
        }
        create_response = test_client.post("/api/v1/users/", json=user_data)
        user_id = create_response.json()["id"]
        
        # Получаем пользователя
        response = test_client.get(f"/api/v1/users/{user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert data["telegram_id"] == 111222333
        assert data["username"] == "get_user_test"
    
    def test_get_user_not_found(self, test_client, test_db_session):
        """Тест получения несуществующего пользователя"""
        response = test_client.get("/api/v1/users/99999")
        
        assert response.status_code == 404
        assert "не найден" in response.json()["detail"]
    
    def test_get_users_list(self, test_client, test_db_session):
        """Тест получения списка пользователей"""
        # Создаем несколько пользователей
        for i in range(3):
            user_data = {
                "telegram_id": 100000000 + i,
                "username": f"user_{i}"
            }
            test_client.post("/api/v1/users/", json=user_data)
        
        # Получаем список
        response = test_client.get("/api/v1/users/")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["users"]) >= 3
        assert data["total"] >= 3
    
    def test_update_user(self, test_client, test_db_session):
        """Тест обновления пользователя"""
        # Создаем пользователя
        user_data = {
            "telegram_id": 444555666,
            "username": "original_name",
            "language_level": "A1"
        }
        create_response = test_client.post("/api/v1/users/", json=user_data)
        user_id = create_response.json()["id"]
        
        # Обновляем пользователя
        update_data = {
            "username": "updated_name",
            "language_level": "B2"
        }
        response = test_client.put(f"/api/v1/users/{user_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "updated_name"
        assert data["language_level"] == "B2"
    
    def test_delete_user(self, test_client, test_db_session):
        """Тест удаления пользователя (мягкое удаление)"""
        # Создаем пользователя
        user_data = {
            "telegram_id": 777888999,
            "username": "to_delete"
        }
        create_response = test_client.post("/api/v1/users/", json=user_data)
        user_id = create_response.json()["id"]
        
        # Удаляем пользователя
        response = test_client.delete(f"/api/v1/users/{user_id}")
        
        assert response.status_code == 204
        
        # Проверяем, что пользователь недоступен через обычный GET
        get_response = test_client.get(f"/api/v1/users/{user_id}")
        assert get_response.status_code == 404
    
    def test_get_user_by_telegram_id(self, test_client, test_db_session):
        """Тест получения пользователя по Telegram ID"""
        # Создаем пользователя
        user_data = {
            "telegram_id": 123456789,
            "username": "telegram_user"
        }
        test_client.post("/api/v1/users/", json=user_data)
        
        # Получаем по Telegram ID
        response = test_client.get("/api/v1/users/telegram/123456789")
        
        assert response.status_code == 200
        data = response.json()
        assert data["telegram_id"] == 123456789
        assert data["username"] == "telegram_user"
