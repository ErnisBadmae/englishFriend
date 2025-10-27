from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from app.models.in_memory import User, Session, CEFRLevel, SessionStatus
from app.schemas.user import UserCreate, UserUpdate
from app.schemas.session import SessionCreate, SessionUpdate

class UserService:
    """Сервис для работы с пользователями в памяти"""
    
    def __init__(self):
        # In-memory хранилище пользователей
        self._users: Dict[int, User] = {}
        self._next_id = 1
    
    def create_user(self, user_data: UserCreate) -> User:
        """Создать нового пользователя"""
        # Проверяем, что Telegram ID уникален
        for user in self._users.values():
            if user.telegram_id == user_data.telegram_id:
                raise ValueError(f"Пользователь с Telegram ID {user_data.telegram_id} уже существует")
        
        user = User(
            telegram_id=user_data.telegram_id,
            username=user_data.username,
            language_level=user_data.language_level
        )
        user.id = self._next_id
        self._next_id += 1
        
        self._users[user.id] = user
        return user
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID"""
        return self._users.get(user_id)
    
    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получить пользователя по Telegram ID"""
        for user in self._users.values():
            if user.telegram_id == telegram_id:
                return user
        return None
    
    def get_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Получить список пользователей с пагинацией"""
        users = list(self._users.values())
        return users[skip:skip + limit]
    
    def update_user(self, user_id: int, user_data: UserUpdate) -> Optional[User]:
        """Обновить данные пользователя"""
        user = self._users.get(user_id)
        if not user:
            return None
        
        if user_data.username is not None:
            user.username = user_data.username
        if user_data.language_level is not None:
            user.language_level = user_data.language_level
        
        return user
    
    def delete_user(self, user_id: int) -> bool:
        """Удалить пользователя"""
        if user_id in self._users:
            del self._users[user_id]
            return True
        return False
    
    def get_total_count(self) -> int:
        """Получить общее количество пользователей"""
        return len(self._users)

class SessionService:
    """Сервис для работы с сессиями в памяти"""
    
    def __init__(self):
        # In-memory хранилище сессий
        self._sessions: Dict[str, Session] = {}
    
    def create_session(self, session_data: SessionCreate) -> Session:
        """Создать новую сессию"""
        session = Session(
            user_id=session_data.user_id,
            lang_code=session_data.lang_code
        )
        
        self._sessions[session.id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Получить сессию по ID"""
        return self._sessions.get(session_id)
    
    def get_user_sessions(self, user_id: int) -> List[Session]:
        """Получить все сессии пользователя"""
        return [session for session in self._sessions.values() if session.user_id == user_id]
    
    def update_session(self, session_id: str, session_data: SessionUpdate) -> Optional[Session]:
        """Обновить данные сессии"""
        session = self._sessions.get(session_id)
        if not session:
            return None
        
        if session_data.ended_at is not None:
            session.ended_at = session_data.ended_at
        if session_data.audio_url is not None:
            session.audio_url = session_data.audio_url
        if session_data.status is not None:
            session.status = session_data.status
        
        return session
    
    def complete_session(self, session_id: str) -> Optional[Session]:
        """Завершить сессию"""
        session = self._sessions.get(session_id)
        if not session:
            return None
        
        session.ended_at = datetime.now()
        session.status = SessionStatus.COMPLETED
        return session

# Глобальные экземпляры сервисов
user_service = UserService()
session_service = SessionService()
