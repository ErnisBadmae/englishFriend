"""
Тесты для Pydantic схем.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserListResponse, CEFRLevel
from app.schemas.session import SessionCreate, SessionUpdate, SessionResponse, SessionStatus


class TestUserSchemas:
    """Тесты для схем пользователей"""
    
    def test_user_create_valid(self):
        """Тест создания пользователя с валидными данными"""
        user_data = UserCreate(
            telegram_id=123456,
            username="test_user",
            language_level=CEFRLevel.B1
        )
        
        assert user_data.telegram_id == 123456
        assert user_data.username == "test_user"
        assert user_data.language_level == CEFRLevel.B1
    
    def test_user_create_minimal(self):
        """Тест создания пользователя с минимальными данными"""
        user_data = UserCreate(telegram_id=789012)
        
        assert user_data.telegram_id == 789012
        assert user_data.username is None
        assert user_data.language_level is None
    
    def test_user_create_invalid_telegram_id(self):
        """Тест валидации невалидного Telegram ID"""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(telegram_id=-1)
        
        assert "Telegram ID должен быть положительным числом" in str(exc_info.value)
    
    def test_user_update_partial(self):
        """Тест частичного обновления пользователя"""
        update_data = UserUpdate(username="updated_user")
        
        assert update_data.username == "updated_user"
        assert update_data.language_level is None
    
    def test_user_response(self):
        """Тест схемы ответа пользователя"""
        response = UserResponse(
            id=1,
            telegram_id=123456,
            username="test_user",
            language_level=CEFRLevel.B1,
            created_at=datetime.now()
        )
        
        assert response.id == 1
        assert response.telegram_id == 123456
        assert response.username == "test_user"
        assert response.language_level == CEFRLevel.B1
        assert isinstance(response.created_at, datetime)
    
    def test_user_list_response(self):
        """Тест схемы списка пользователей"""
        users = [
            UserResponse(
                id=1,
                telegram_id=123456,
                username="user1",
                language_level=CEFRLevel.B1,
                created_at=datetime.now()
            ),
            UserResponse(
                id=2,
                telegram_id=789012,
                username="user2",
                language_level=CEFRLevel.A2,
                created_at=datetime.now()
            )
        ]
        
        response = UserListResponse(users=users, total=2)
        
        assert len(response.users) == 2
        assert response.total == 2
        assert response.users[0].username == "user1"
        assert response.users[1].username == "user2"


class TestSessionSchemas:
    """Тесты для схем сессий"""
    
    def test_session_create_valid(self):
        """Тест создания сессии с валидными данными"""
        session_data = SessionCreate(
            user_id=1,
            lang_code="en"
        )
        
        assert session_data.user_id == 1
        assert session_data.lang_code == "en"
    
    def test_session_create_default_lang(self):
        """Тест создания сессии с языком по умолчанию"""
        session_data = SessionCreate(user_id=1)
        
        assert session_data.user_id == 1
        assert session_data.lang_code == "en"
    
    def test_session_update(self):
        """Тест обновления сессии"""
        update_data = SessionUpdate(
            audio_url="https://example.com/audio.mp3",
            status=SessionStatus.COMPLETED
        )
        
        assert update_data.audio_url == "https://example.com/audio.mp3"
        assert update_data.status == SessionStatus.COMPLETED
        assert update_data.ended_at is None
    
    def test_session_response(self):
        """Тест схемы ответа сессии"""
        response = SessionResponse(
            id="test-session-id",
            user_id=1,
            started_at=datetime.now(),
            ended_at=None,
            audio_url=None,
            lang_code="en",
            status=SessionStatus.ACTIVE
        )
        
        assert response.id == "test-session-id"
        assert response.user_id == 1
        assert response.lang_code == "en"
        assert response.status == SessionStatus.ACTIVE
        assert response.ended_at is None
        assert response.audio_url is None


class TestEnums:
    """Тесты для enum типов"""
    
    def test_cefr_levels(self):
        """Тест уровней CEFR"""
        assert CEFRLevel.A1 == "A1"
        assert CEFRLevel.B1 == "B1"
        assert CEFRLevel.C2 == "C2"
        
        # Проверяем все уровни
        levels = [CEFRLevel.A1, CEFRLevel.A2, CEFRLevel.B1, CEFRLevel.B2, CEFRLevel.C1, CEFRLevel.C2]
        assert len(levels) == 6
    
    def test_session_status(self):
        """Тест статусов сессии"""
        assert SessionStatus.ACTIVE == "active"
        assert SessionStatus.COMPLETED == "completed"
        assert SessionStatus.CANCELLED == "cancelled"
