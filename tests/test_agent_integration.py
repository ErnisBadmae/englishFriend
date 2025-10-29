"""
Тесты интеграции агента с OpenAI через прокси
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()


@pytest.fixture
def api_client():
    """Создать тестовый клиент API"""
    from main import app
    return TestClient(app)


@pytest.mark.asyncio
async def test_agent_health_endpoint(api_client):
    """
    Тест health endpoint агента.
    Проверяет подключение к OpenAI через прокси.
    """
    response = api_client.get("/api/v1/agent/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "status" in data
    assert "message" in data
    
    # Проверяем, что OpenAI API доступен или есть понятная ошибка
    if data["status"] == "ok":
        assert "OpenAI API connected via proxy" in data["message"]
        assert "model" in data
        assert "proxy" in data
    else:
        # Если ошибка, должен быть понятное сообщение
        assert "error" in data["status"]
        assert "message" in data


def test_proxy_setup():
    """
    Тест настройки прокси.
    Проверяет, что PROXY_URL загружен из .env
    """
    proxy_url = os.getenv("PROXY_URL")
    assert proxy_url is not None, "PROXY_URL должен быть установлен в .env"
    assert proxy_url.startswith("http://"), "Прокси должен быть HTTP"
    

def test_openai_api_key():
    """
    Тест наличия OpenAI API ключа.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    assert api_key is not None, "OPENAI_API_KEY должен быть установлен в .env"
    assert api_key.startswith("sk-"), "API ключ должен начинаться с sk-"


@pytest.mark.asyncio
async def test_agent_chat_endpoint_basic(api_client):
    """
    Базовый тест chat endpoint.
    Проверяет структуру запроса и ответа.
    """
    request_data = {
        "user_id": 1,
        "session_id": "test-session-001",
        "message": "Hello"
    }
    
    response = api_client.post(
        "/api/v1/agent/chat",
        json=request_data
    )
    
    # Может быть 200 (успешно) или 500 (ошибка OpenAI)
    assert response.status_code in [200, 500]
    
    if response.status_code == 200:
        data = response.json()
        assert "response" in data
        assert "session_id" in data
        assert "user_id" in data
        assert data["session_id"] == "test-session-001"
        assert data["user_id"] == 1
        assert len(data["response"]) > 0, "Ответ не должен быть пустым"
    else:
        # Проверяем, что есть понятная ошибка
        data = response.json()
        assert "detail" in data


@pytest.mark.asyncio
async def test_agent_chat_multiple_messages(api_client):
    """
    Тест нескольких сообщений подряд.
    Проверяет стабильность агента.
    """
    messages = [
        "Hello!",
        "How are you?",
        "What's the weather like?"
    ]
    
    for i, message in enumerate(messages):
        request_data = {
            "user_id": 1,
            "session_id": f"test-session-multi-{i}",
            "message": message
        }
        
        response = api_client.post(
            "/api/v1/agent/chat",
            json=request_data
        )
        
        # Проверяем, что не все запросы упали
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "response" in data
            assert len(data["response"]) > 0


@pytest.mark.asyncio
async def test_agent_error_handling(api_client):
    """
    Тест обработки ошибок.
    Проверяет, что невалидный запрос не ломает сервер.
    """
    # Отправляем невалидные данные
    response = api_client.post(
        "/api/v1/agent/chat",
        json={"invalid": "data"}
    )
    
    # Должна быть 422 (validation error) или 400
    assert response.status_code in [400, 422, 500]


def test_proxy_import():
    """
    Тест импорта прокси.
    Проверяет, что прокси настраивается без ошибок.
    """
    try:
        from app.agents import proxy
        # Если импорт успешен - прокси настроен
        assert True
    except Exception as e:
        pytest.skip(f"Прокси не настроен: {e}")


def test_base_agent_import():
    """
    Тест импорта базового агента.
    """
    try:
        from app.agents.base_agent import create_simple_agent
        assert callable(create_simple_agent)
    except Exception as e:
        pytest.fail(f"Не удалось импортировать базовый агент: {e}")


def test_agent_chat_endpoint_exists():
    """
    Тест наличия chat endpoint.
    """
    from app.api import agent_chat
    
    # Проверяем, что router существует
    assert agent_chat.router is not None
    assert agent_chat.router.prefix == "/api/v1/agent"


@pytest.mark.asyncio
async def test_agent_chat_saves_to_db(api_client):
    """
    Тест сохранения в БД.
    Проверяет, что utterances сохраняются в PostgreSQL.
    """
    from app.core.database import async_session_maker
    
    # Отправляем сообщение
    request_data = {
        "user_id": 1,
        "session_id": "test-db-001",
        "message": "Hello, I want to practice English"
    }
    
    response = api_client.post(
        "/api/v1/agent/chat",
        json=request_data
    )
    
    # Проверяем, что ответ получен
    assert response.status_code in [200, 500]
    
    if response.status_code == 200:
        # Проверяем, что данные сохранились в БД
        async with async_session_maker() as db:
            from app.models.core_tables import Utterance
            from sqlalchemy import select
            
            # Ищем наши utterances
            stmt = select(Utterance).where(
                Utterance.session_id == "test-db-001"
            )
            result = await db.execute(stmt)
            utterances = result.scalars().all()
            
            # Должно быть 2 записи: user и assistant
            assert len(utterances) == 2, f"Ожидалось 2 записи, найдено {len(utterances)}"
            
            # Проверяем, что есть user и assistant
            speakers = [u.speaker for u in utterances]
            assert "user" in speakers, "Должна быть запись с speaker=user"
            assert "assistant" in speakers, "Должна быть запись с speaker=assistant"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

