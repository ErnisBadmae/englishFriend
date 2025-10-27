"""
Тесты для конфигурации приложения.
"""
import pytest
from app.core.config import settings


class TestConfig:
    """Тесты для настроек приложения"""
    
    def test_settings_loaded(self):
        """Проверяем, что настройки загружаются корректно"""
        assert settings.api_title == "English Friend API"
        assert settings.api_version == "3.0.0"
        assert settings.debug is True
    
    def test_database_url_format(self):
        """Проверяем формат URL базы данных"""
        assert "postgresql+asyncpg://" in settings.database_url
        assert "postgresql://" in settings.database_url_sync
        assert "localhost:5432" in settings.database_url
        assert "english_friend" in settings.database_url
    
    def test_cors_settings(self):
        """Проверяем настройки CORS"""
        assert isinstance(settings.allowed_origins, list)
        assert "*" in settings.allowed_origins
