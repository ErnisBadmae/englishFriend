"""
Простые тесты для базовых endpoints без мокирования.
"""
import pytest
from fastapi.testclient import TestClient

from main import app


class TestBasicEndpoints:
    """Тесты для базовых endpoints"""
    
    def test_health_endpoint(self):
        """Тест endpoint проверки здоровья"""
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "English Friend API работает" in data["message"]
    
    def test_hello_endpoint(self):
        """Тест приветственного endpoint"""
        client = TestClient(app)
        response = client.get("/api/v1/hello")
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Привет! Я English Friend API"
        assert data["version"] == "3.0.0"
        assert "PostgreSQL интеграция" in data["new_features"]
    
    def test_status_endpoint(self):
        """Тест endpoint статуса"""
        client = TestClient(app)
        response = client.get("/api/v1/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["api_status"] == "running"
        assert data["database"] == "postgresql"
        assert data["current_stage"] == "Этап 3: PostgreSQL + SQLAlchemy"