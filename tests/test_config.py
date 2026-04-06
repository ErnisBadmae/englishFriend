"""Tests for application configuration."""

from app.core.config import settings


class TestConfig:
    def test_settings_loaded(self):
        assert settings.api_title == "English Friend API"
        assert settings.api_version == "3.0.0"
        assert settings.debug is True

    def test_database_url_format(self):
        assert "postgresql+asyncpg://" in settings.database_url
        assert "postgresql://" in settings.database_url_sync
        assert "localhost:5432" in settings.database_url
        assert "englishfriend_dev" in settings.database_url

    def test_cors_settings(self):
        assert isinstance(settings.allowed_origins, list)
        assert "*" in settings.allowed_origins

    def test_cluster_llm_defaults_present(self):
        assert settings.vllm_base_url == "http://192.168.0.27:8000/v1"
        assert settings.llama_cpp_base_url == "http://192.168.0.18:8001/v1"
        assert settings.llama_cpp_response_mode == "final_only"
        assert settings.llama_cpp_extra_body_json == ""
