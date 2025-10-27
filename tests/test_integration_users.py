"""
Интеграционные тесты для Users API с реальной БД.
Требуют запущенного PostgreSQL.
"""

import pytest
import pytest_asyncio
import random
from httpx import AsyncClient

from main import app

@pytest_asyncio.fixture(scope="function")
async def async_client():
    """Async клиент для тестирования с реальной БД"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.mark.integration
@pytest.mark.asyncio
class TestUsersAPI:
    """Интеграционные тесты для Users API"""
    
    async def test_create_user_success(self, async_client):
        """Тест успешного создания пользователя"""
        user_data = {
            "telegram_id": random.randint(1000000000, 9999999999),
            "username": "test_user",
            "language_level": "B1"
        }
        
        response = await async_client.post("/api/v1/users/", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["telegram_id"] == user_data["telegram_id"]
        assert data["username"] == "test_user"
        assert data["language_level"] == "B1"
        assert "id" in data
        assert "created_at" in data
    
    async def test_create_user_duplicate_telegram_id(self, async_client):
        """Тест создания пользователя с дублирующимся Telegram ID"""
        telegram_id = random.randint(1000000000, 9999999999)
        
        # Создаем первого пользователя
        user_data = {
            "telegram_id": telegram_id,
            "username": "first_user"
        }
        await async_client.post("/api/v1/users/", json=user_data)
        
        # Пытаемся создать второго с тем же Telegram ID
        response = await async_client.post("/api/v1/users/", json=user_data)
        
        assert response.status_code == 400
        assert "уже существует" in response.json()["detail"]
    
    async def test_get_user_by_id(self, async_client):
        """Тест получения пользователя по ID"""
        # Создаем пользователя
        user_data = {
            "telegram_id": random.randint(1000000000, 9999999999),
            "username": "get_user_test"
        }
        create_response = await async_client.post("/api/v1/users/", json=user_data)
        user_id = create_response.json()["id"]
        
        # Получаем пользователя
        response = await async_client.get(f"/api/v1/users/{user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert data["telegram_id"] == user_data["telegram_id"]
        assert data["username"] == "get_user_test"
    
    async def test_get_user_not_found(self, async_client):
        """Тест получения несуществующего пользователя"""
        response = await async_client.get("/api/v1/users/99999")
        
        assert response.status_code == 404
        assert "не найден" in response.json()["detail"]
    
    async def test_get_users_list(self, async_client):
        """Тест получения списка пользователей"""
        # Создаем несколько пользователей
        for i in range(3):
            user_data = {
                "telegram_id": random.randint(1000000000, 9999999999),
                "username": f"user_{i}"
            }
            await async_client.post("/api/v1/users/", json=user_data)
        
        # Получаем список
        response = await async_client.get("/api/v1/users/")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["users"]) >= 3
        assert data["total"] >= 3
    
    async def test_update_user(self, async_client):
        """Тест обновления пользователя"""
        # Создаем пользователя
        user_data = {
            "telegram_id": random.randint(1000000000, 9999999999),
            "username": "original_name",
            "language_level": "A1"
        }
        create_response = await async_client.post("/api/v1/users/", json=user_data)
        user_id = create_response.json()["id"]
        
        # Обновляем пользователя
        update_data = {
            "username": "updated_name",
            "language_level": "B2"
        }
        response = await async_client.put(f"/api/v1/users/{user_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "updated_name"
        assert data["language_level"] == "B2"
    
    async def test_delete_user(self, async_client):
        """Тест удаления пользователя (мягкое удаление)"""
        # Создаем пользователя
        user_data = {
            "telegram_id": random.randint(1000000000, 9999999999),
            "username": "to_delete"
        }
        create_response = await async_client.post("/api/v1/users/", json=user_data)
        user_id = create_response.json()["id"]
        
        # Удаляем пользователя
        response = await async_client.delete(f"/api/v1/users/{user_id}")
        
        assert response.status_code == 204
        
        # Проверяем, что пользователь недоступен через обычный GET
        get_response = await async_client.get(f"/api/v1/users/{user_id}")
        assert get_response.status_code == 404
    
    async def test_get_user_by_telegram_id(self, async_client):
        """Тест получения пользователя по Telegram ID"""
        telegram_id = random.randint(1000000000, 9999999999)
        
        # Создаем пользователя
        user_data = {
            "telegram_id": telegram_id,
            "username": "telegram_user"
        }
        await async_client.post("/api/v1/users/", json=user_data)
        
        # Получаем по Telegram ID
        response = await async_client.get(f"/api/v1/users/telegram/{telegram_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["telegram_id"] == telegram_id
        assert data["username"] == "telegram_user"
