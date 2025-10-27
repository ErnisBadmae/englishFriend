from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.models.database import User, Session
from app.schemas.user import UserCreate, UserUpdate
from app.schemas.session import SessionCreate, SessionUpdate

class UserService:
    """Сервис для работы с пользователями в PostgreSQL"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_user(self, user_data: UserCreate) -> User:
        """Создать нового пользователя"""
        # Проверяем уникальность Telegram ID
        existing_user = await self.get_user_by_telegram_id(user_data.telegram_id)
        if existing_user:
            raise ValueError(f"Пользователь с Telegram ID {user_data.telegram_id} уже существует")
        
        # Создаем нового пользователя
        user = User(
            telegram_id=user_data.telegram_id,
            username=user_data.username,
            language_level=user_data.language_level.value if user_data.language_level else None
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    async def get_user(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID"""
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получить пользователя по Telegram ID"""
        result = await self.db.execute(
            select(User).where(User.telegram_id == telegram_id, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()
    
    async def get_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Получить список пользователей с пагинацией"""
        result = await self.db.execute(
            select(User)
            .where(User.deleted_at.is_(None))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def update_user(self, user_id: int, user_data: UserUpdate) -> Optional[User]:
        """Обновить данные пользователя"""
        user = await self.get_user(user_id)
        if not user:
            return None
        
        # Обновляем поля
        update_data = {}
        if user_data.username is not None:
            update_data["username"] = user_data.username
        if user_data.language_level is not None:
            update_data["language_level"] = user_data.language_level.value
        
        if update_data:
            await self.db.execute(
                update(User)
                .where(User.id == user_id)
                .values(**update_data)
            )
            await self.db.commit()
            await self.db.refresh(user)
        
        return user
    
    async def delete_user(self, user_id: int) -> bool:
        """Мягкое удаление пользователя (устанавливаем deleted_at)"""
        result = await self.db.execute(
            update(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .values(deleted_at=datetime.utcnow())
        )
        
        if result.rowcount > 0:
            await self.db.commit()
            return True
        return False
    
    async def get_total_count(self) -> int:
        """Получить общее количество активных пользователей"""
        result = await self.db.execute(
            select(User).where(User.deleted_at.is_(None))
        )
        return len(result.scalars().all())

class SessionService:
    """Сервис для работы с сессиями в PostgreSQL"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_session(self, session_data: SessionCreate) -> Session:
        """Создать новую сессию"""
        session = Session(
            user_id=session_data.user_id,
            lang_code=session_data.lang_code
        )
        
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        
        return session
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Получить сессию по ID"""
        result = await self.db.execute(
            select(Session).where(Session.id == session_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_sessions(self, user_id: int) -> List[Session]:
        """Получить все сессии пользователя"""
        result = await self.db.execute(
            select(Session)
            .where(Session.user_id == user_id)
            .order_by(Session.started_at.desc())
        )
        return result.scalars().all()
    
    async def update_session(self, session_id: str, session_data: SessionUpdate) -> Optional[Session]:
        """Обновить данные сессии"""
        session = await self.get_session(session_id)
        if not session:
            return None
        
        # Обновляем поля (только те, что есть в SQL схеме)
        update_data = {}
        if session_data.ended_at is not None:
            update_data["ended_at"] = session_data.ended_at
        if session_data.audio_url is not None:
            update_data["audio_url"] = session_data.audio_url
        if session_data.lang_code is not None:
            update_data["lang_code"] = session_data.lang_code
        if session_data.call_quality is not None:
            update_data["call_quality"] = session_data.call_quality
        
        if update_data:
            await self.db.execute(
                update(Session)
                .where(Session.id == session_id)
                .values(**update_data)
            )
            await self.db.commit()
            await self.db.refresh(session)
        
        return session
    
    async def complete_session(self, session_id: str) -> Optional[Session]:
        """Завершить сессию"""
        from datetime import datetime
        
        result = await self.db.execute(
            update(Session)
            .where(Session.id == session_id)
            .values(ended_at=datetime.utcnow())
        )
        
        if result.rowcount > 0:
            await self.db.commit()
            return await self.get_session(session_id)
        return None
