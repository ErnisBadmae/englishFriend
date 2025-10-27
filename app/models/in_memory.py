from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
import uuid

class CEFRLevel(str, Enum):
    """Уровни английского языка по CEFR"""
    A1 = "A1"
    A2 = "A2"
    B1 = "B1" 
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"

class SessionStatus(str, Enum):
    """Статусы сессии"""
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class User:
    """Модель пользователя для in-memory хранения"""
    
    def __init__(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        language_level: Optional[CEFRLevel] = None
    ):
        self.id: int = 0  # Будет установлен при сохранении
        self.telegram_id: int = telegram_id
        self.username: Optional[str] = username
        self.language_level: Optional[CEFRLevel] = language_level
        self.created_at: datetime = datetime.now()

class Session:
    """Модель сессии для in-memory хранения"""
    
    def __init__(
        self,
        user_id: int,
        lang_code: str = "en"
    ):
        self.id: str = str(uuid.uuid4())
        self.user_id: int = user_id
        self.started_at: datetime = datetime.now()
        self.ended_at: Optional[datetime] = None
        self.audio_url: Optional[str] = None
        self.lang_code: str = lang_code
        self.status: SessionStatus = SessionStatus.ACTIVE
