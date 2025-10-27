import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Настройки приложения"""
    
    # База данных
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/english_friend"
    database_url_sync: str = "postgresql://postgres:password@localhost:5432/english_friend"
    
    # API настройки
    api_title: str = "English Friend API"
    api_version: str = "3.0.0"
    debug: bool = True
    
    # CORS настройки
    allowed_origins: list = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Глобальный экземпляр настроек
settings = Settings()
