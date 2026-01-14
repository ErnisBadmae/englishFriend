"""
Сервис для построения контекста пользователя из БД.
Собирает данные из PostgreSQL для Universal Prompt.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.core_tables import User, Utterance, Session
from app.models.extended_tables import UserInterest, Memory
from app.prompts.universal import (
    UserProfile, UserInterest as PromptUserInterest,
    Memory as PromptMemory, RecentUtterance, LearningProgress,
    SessionContext
)
from app.services.query_helpers import (
    get_by_id,
    get_top_by_field,
)


class ContextBuilder:
    """Построитель контекста из БД"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def build_full_context(
        self,
        user_id: int,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Построить полный контекст для пользователя.
        
        Args:
            user_id: ID пользователя
            session_id: ID сессии
            
        Returns:
            dict с ключами: user_profile, interests, memories, 
            recent_utterances, progress, session_context
        """
        return {
            "user_profile": await self.get_user_profile(user_id),
            "interests": await self.get_user_interests(user_id),
            "memories": await self.get_user_memories(user_id),
            "recent_utterances": await self.get_recent_utterances(session_id),
            "progress": await self.get_learning_progress(user_id),
            "session_context": await self.get_session_context(session_id)
        }
    
    async def get_user_profile(self, user_id: int) -> Optional[UserProfile]:
        """Получить профиль пользователя"""
        user = await get_by_id(self.db, User, user_id)

        if not user:
            return None

        # Получаем дату последней сессии
        last_session_stmt = (
            select(func.max(Session.started_at))
            .where(Session.user_id == user_id)
        )
        last_session_result = await self.db.execute(last_session_stmt)
        last_session_date = last_session_result.scalar_one_or_none()

        return UserProfile(
            id=user.id,
            telegram_id=user.telegram_id,
            username=user.username,
            language_level=user.language_level,
            last_session_date=last_session_date
        )
    
    async def get_user_interests(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[PromptUserInterest]:
        """Получить интересы пользователя"""
        interests = await get_top_by_field(
            self.db, UserInterest, user_id,
            field_name="salience", limit=limit
        )

        return [
            PromptUserInterest(topic=interest.topic, salience=interest.salience)
            for interest in interests
        ]
    
    async def get_user_memories(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[PromptMemory]:
        """Получить воспоминания о пользователе"""
        memories = await get_top_by_field(
            self.db, Memory, user_id,
            field_name="salience", limit=limit
        )

        return [
            PromptMemory(
                kind=mem.kind,
                content=mem.content,
                salience=mem.salience
            )
            for mem in memories
        ]
    
    async def get_recent_utterances(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[RecentUtterance]:
        """Получить недавние реплики"""
        stmt = (
            select(Utterance)
            .where(Utterance.session_id == session_id)
            .order_by(Utterance.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        utterances = result.scalars().all()
        
        # Разворачиваем, чтобы были от старых к новым
        utterances.reverse()
        
        return [
            RecentUtterance(
                text=utt.text,
                speaker=utt.speaker,
                timestamp=utt.created_at
            )
            for utt in utterances
        ]
    
    async def get_learning_progress(self, user_id: int) -> LearningProgress:
        """Получить прогресс обучения"""
        # TODO: Реализовать когда будет таблица xp_events
        # Пока возвращаем заглушку
        return LearningProgress(
            total_xp=0,
            current_level=None,
            achievements=[]
        )
    
    async def get_session_context(
        self,
        session_id: str
    ) -> Optional[SessionContext]:
        """Получить контекст сессии"""
        session = await get_by_id(self.db, Session, session_id, id_field="id")

        if not session:
            return None

        # Подсчитываем количество реплик
        utt_stmt = select(func.count(Utterance.id)).where(
            Utterance.session_id == session_id
        )
        utt_result = await self.db.execute(utt_stmt)
        utterance_count = utt_result.scalar_one() or 0

        return SessionContext(
            session_id=session_id,
            utterance_count=utterance_count,
            duration_seconds=0,  # TODO: Вычислить из ended_at - started_at
            started_at=session.started_at
        )

