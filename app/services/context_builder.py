"""
Сервис для сборки контекста пользователя из PostgreSQL.

Извлекает данные из БД и преобразует их в формат для UniversalPromptBuilder.
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.core_tables import User, Session, Utterance, Feedback
from app.models.extended_tables import UserInterest, Memory, LearningPlan, XPEvent
from app.models.enums_and_dimensions import DimTopic
from app.prompts.universal import (
    UserProfile,
    UserInterest as PromptUserInterest,
    Memory as PromptMemory,
    RecentUtterance,
    LearningProgress,
    SessionContext
)


class ContextBuilder:
    """Сборщик контекста из БД для универсального промпта"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_profile(self, user_id: int) -> Optional[UserProfile]:
        """
        Получить профиль пользователя.
        
        Args:
            user_id: ID пользователя
        
        Returns:
            Профиль пользователя или None
        """
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        return UserProfile(
            user_id=user.id,
            username=user.username,
            language_level=user.language_level or "B1",
            session_count=len(user.sessions) if user.sessions else 0,
            created_at=user.created_at,
            accent_pref=user.accent_pref
        )
    
    async def get_user_interests(self, user_id: int) -> List[PromptUserInterest]:
        """
        Получить интересы пользователя с весами.
        
        Args:
            user_id: ID пользователя
        
        Returns:
            Список интересов с весами
        """
        stmt = (
            select(UserInterest, DimTopic)
            .join(DimTopic, UserInterest.topic_id == DimTopic.id)
            .where(UserInterest.user_id == user_id)
            .order_by(UserInterest.weight.desc())
        )
        
        result = await self.db.execute(stmt)
        rows = result.all()
        
        interests = []
        for user_interest, topic in rows:
            interests.append(PromptUserInterest(
                topic_name=topic.name_en or topic.name_ru,
                weight=user_interest.weight,
                last_mentioned=user_interest.last_mentioned
            ))
        
        return interests
    
    async def get_user_memories(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[PromptMemory]:
        """
        Получить воспоминания пользователя, отсортированные по salience.
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество воспоминаний
        
        Returns:
            Список воспоминаний
        """
        stmt = (
            select(Memory)
            .where(Memory.user_id == user_id)
            .order_by(Memory.salience.desc(), Memory.last_refreshed.desc())
            .limit(limit)
        )
        
        result = await self.db.execute(stmt)
        memories = result.scalars().all()
        
        return [
            PromptMemory(
                kind=mem.kind,
                content=mem.content,
                salience=mem.salience,
                created_at=mem.created_at
            )
            for mem in memories
        ]
    
    async def get_recent_utterances(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[RecentUtterance]:
        """
        Получить последние реплики из сессии.
        
        Args:
            session_id: ID сессии
            limit: Максимальное количество реплик
        
        Returns:
            Список последних реплик
        """
        stmt = (
            select(Utterance)
            .where(Utterance.session_id == session_id)
            .order_by(Utterance.t_start_ms.desc())
            .limit(limit)
        )
        
        result = await self.db.execute(stmt)
        utterances = result.scalars().all()
        
        # Переворачиваем, чтобы был хронологический порядок
        utterances.reverse()
        
        return [
            RecentUtterance(
                speaker=utt.speaker,
                text=utt.text,
                emotion_code=utt.emotion_code,
                grammar_score=utt.grammar_score
            )
            for utt in utterances
        ]
    
    async def get_learning_progress(self, user_id: int) -> LearningProgress:
        """
        Получить прогресс обучения пользователя.
        
        Args:
            user_id: ID пользователя
        
        Returns:
            Прогресс обучения
        """
        # Подсчитать общий XP
        xp_stmt = (
            select(func.sum(XPEvent.xp_amount))
            .where(XPEvent.user_id == user_id)
        )
        xp_result = await self.db.execute(xp_stmt)
        total_xp = xp_result.scalar() or 0
        
        # Получить последние достижения (по XP событиям)
        achievements_stmt = (
            select(XPEvent)
            .where(XPEvent.user_id == user_id)
            .order_by(XPEvent.happened_at.desc())
            .limit(5)
        )
        achievements_result = await self.db.execute(achievements_stmt)
        xp_events = achievements_result.scalars().all()
        
        achievements = [
            f"{event.description or event.event_type} (+{event.xp_amount} XP)"
            for event in xp_events
        ]
        
        # Получить план обучения
        plan_stmt = (
            select(LearningPlan)
            .where(LearningPlan.user_id == user_id)
            .order_by(LearningPlan.updated_at.desc())
            .limit(1)
        )
        plan_result = await self.db.execute(plan_stmt)
        learning_plan = plan_result.scalar_one_or_none()
        
        plan_description = None
        next_review = None
        if learning_plan:
            plan_description = f"Target level: {learning_plan.level_target or 'Not set'}"
            next_review = learning_plan.next_review_at
        
        return LearningProgress(
            total_xp=int(total_xp),
            recent_achievements=achievements,
            learning_plan=plan_description,
            next_review_at=next_review
        )
    
    async def get_session_context(self, session_id: str) -> Optional[SessionContext]:
        """
        Получить контекст текущей сессии.
        
        Args:
            session_id: ID сессии
        
        Returns:
            Контекст сессии или None
        """
        stmt = (
            select(Session)
            .where(Session.id == session_id)
            .options(selectinload(Session.utterances))
        )
        
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            return None
        
        # Извлечь темы из utterances
        topics = set()
        emotions = []
        
        for utt in session.utterances:
            if utt.topics:
                if isinstance(utt.topics, dict):
                    topics.update(utt.topics.keys())
                elif isinstance(utt.topics, list):
                    topics.update(utt.topics)
            
            if utt.emotion_code:
                emotions.append(utt.emotion_code)
        
        # Определить доминирующую эмоцию
        dominant_emotion = None
        if emotions:
            from collections import Counter
            emotion_counts = Counter(emotions)
            dominant_emotion = emotion_counts.most_common(1)[0][0]
        
        return SessionContext(
            session_id=session.id,
            started_at=session.started_at,
            utterance_count=len(session.utterances),
            topics_discussed=list(topics)[:5],
            dominant_emotion=dominant_emotion
        )
    
    async def build_full_context(
        self,
        user_id: int,
        session_id: Optional[str] = None
    ) -> dict:
        """
        Собрать полный контекст для универсального промпта.
        
        Args:
            user_id: ID пользователя
            session_id: ID текущей сессии (опционально)
        
        Returns:
            Словарь с всеми данными для промпта
        """
        context = {}
        
        # Профиль пользователя
        context['user_profile'] = await self.get_user_profile(user_id)
        if not context['user_profile']:
            raise ValueError(f"User {user_id} not found")
        
        # Интересы
        context['interests'] = await self.get_user_interests(user_id)
        
        # Воспоминания
        context['memories'] = await self.get_user_memories(user_id)
        
        # Прогресс
        context['progress'] = await self.get_learning_progress(user_id)
        
        # Контекст сессии и реплики
        if session_id:
            context['session_context'] = await self.get_session_context(session_id)
            context['recent_utterances'] = await self.get_recent_utterances(session_id)
        else:
            context['session_context'] = None
            context['recent_utterances'] = []
        
        return context

