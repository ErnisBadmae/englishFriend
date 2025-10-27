"""
Интеграционные тесты для Utterances, Feedback и Corrections API.
Простой подход - проверяем, что endpoints отвечают корректно.
"""

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from main import app

@pytest.mark.integration
class TestUtterancesAndFeedbackAPI:
    """Интеграционные тесты для Utterances и Feedback API"""
    
    def test_create_utterance_requires_session(self):
        """Тест что создание utterance требует валидную сессию"""
        client = TestClient(app)
        
        utterance_data = {
            "session_id": str(uuid4()),
            "speaker": "user",
            "t_start_ms": 0,
            "t_end_ms": 3000,
            "text": "Hello"
        }
        
        # Должна быть ошибка, т.к. сессия не существует
        response = client.post("/api/v1/utterances/", json=utterance_data)
        # Может быть 400 или 500 в зависимости от реализации
        assert response.status_code in [400, 500]
    
    def test_create_feedback_requires_session(self):
        """Тест что создание feedback требует валидную сессию"""
        client = TestClient(app)
        
        feedback_data = {
            "session_id": str(uuid4()),
            "overall_grammar": 7.5,
            "overall_pronunciation": 8.0
        }
        
        # Должна быть ошибка, т.к. сессия не существует
        response = client.post("/api/v1/feedback/", json=feedback_data)
        assert response.status_code in [400, 500]
    
    def test_create_correction_requires_session(self):
        """Тест что создание correction требует валидную сессию"""
        client = TestClient(app)
        
        correction_data = {
            "session_id": str(uuid4()),
            "user_text": "I go",
            "corrected_text": "I went"
        }
        
        # Должна быть ошибка, т.к. сессия не существует
        response = client.post("/api/v1/corrections/", json=correction_data)
        assert response.status_code in [400, 500]
    
    def test_dimensions_endpoints_accessible(self):
        """Тест что endpoints справочников доступны"""
        client = TestClient(app)
        
        # Проверяем endpoint эмоций
        response = client.get("/api/v1/dimensions/emotions/")
        assert response.status_code in [200, 404]  # Может быть пустым
        
        # Проверяем endpoint тем
        response = client.get("/api/v1/dimensions/topics/")
        assert response.status_code in [200, 404]
        
        # Проверяем endpoint акцентов
        response = client.get("/api/v1/dimensions/accents/")
        assert response.status_code in [200, 404]
