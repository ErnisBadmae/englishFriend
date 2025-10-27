from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.models.extended_tables import UserInterest, Memory, LearningPlan, XPEvent, EmotionalStateLog
from app.schemas.additional_schemas import (
    UserInterestCreate, MemoryCreate, LearningPlanCreate, XPEventCreate, EmotionalStateLogCreate,
    UserInterestUpdate, MemoryUpdate, LearningPlanUpdate
)
from app.models.enums_and_dimensions import MemoryKind

class UserInterestService:
    """Сервис для работы с интересами пользователя"""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_interest(self, interest_data: UserInterestCreate) -> UserInterest:
        """Создать интерес пользователя"""
        db_interest = UserInterest(
            user_id=interest_data.user_id,
            topic_id=interest_data.topic_id,
            weight=interest_data.weight,
            last_mentioned=interest_data.last_mentioned
        )
        self.db.add(db_interest)
        await self.db.commit()
        await self.db.refresh(db_interest)
        return db_interest

    async def get_user_interests(self, user_id: int, skip: int = 0, limit: int = 100) -> List[UserInterest]:
        """Получить интересы пользователя"""
        result = await self.db.execute(
            select(UserInterest)
            .where(UserInterest.user_id == user_id)
            .order_by(UserInterest.weight.desc(), UserInterest.last_mentioned.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_interest_weight(self, user_id: int, topic_id: str, weight: float) -> Optional[UserInterest]:
        """Обновить вес интереса"""
        stmt = (
            update(UserInterest)
            .where(UserInterest.user_id == user_id, UserInterest.topic_id == topic_id)
            .values(weight=weight, last_mentioned=datetime.utcnow())
            .returning(UserInterest)
        )
        result = await self.db.execute(stmt)
        updated_interest = result.scalar_one_or_none()
        if updated_interest:
            await self.db.commit()
            await self.db.refresh(updated_interest)
        return updated_interest

    async def get_top_interests(self, user_id: int, limit: int = 10) -> List[UserInterest]:
        """Получить топ интересов пользователя"""
        result = await self.db.execute(
            select(UserInterest)
            .where(UserInterest.user_id == user_id)
            .order_by(UserInterest.weight.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

class MemoryService:
    """Сервис для работы с памятью"""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_memory(self, memory_data: MemoryCreate) -> Memory:
        """Создать запись памяти"""
        db_memory = Memory(
            user_id=memory_data.user_id,
            session_id=memory_data.session_id,
            utterance_id=memory_data.utterance_id,
            kind=memory_data.kind,
            content=memory_data.content,
            metadata=memory_data.metadata
        )
        self.db.add(db_memory)
        await self.db.commit()
        await self.db.refresh(db_memory)
        return db_memory

    async def get_memory(self, memory_id: str) -> Optional[Memory]:
        """Получить запись памяти по ID"""
        result = await self.db.execute(
            select(Memory).where(Memory.id == memory_id)
        )
        return result.scalar_one_or_none()

    async def get_user_memories(self, user_id: int, kind: Optional[MemoryKind] = None, skip: int = 0, limit: int = 100) -> List[Memory]:
        """Получить записи памяти пользователя"""
        query = select(Memory).where(Memory.user_id == user_id)
        if kind:
            query = query.where(Memory.kind == kind.value)
        
        result = await self.db.execute(
            query.order_by(Memory.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def update_memory_access(self, memory_id: str) -> Optional[Memory]:
        """Обновить время последнего доступа к памяти"""
        stmt = (
            update(Memory)
            .where(Memory.id == memory_id)
            .values(last_accessed=datetime.utcnow())
            .returning(Memory)
        )
        result = await self.db.execute(stmt)
        updated_memory = result.scalar_one_or_none()
        if updated_memory:
            await self.db.commit()
            await self.db.refresh(updated_memory)
        return updated_memory

    async def search_memories(self, user_id: int, query_text: str, limit: int = 20) -> List[Memory]:
        """Поиск по содержимому памяти (простой текстовый поиск)"""
        result = await self.db.execute(
            select(Memory)
            .where(Memory.user_id == user_id)
            .where(Memory.content.ilike(f"%{query_text}%"))
            .order_by(Memory.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

class LearningPlanService:
    """Сервис для работы с планами обучения"""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_plan(self, plan_data: LearningPlanCreate) -> LearningPlan:
        """Создать план обучения"""
        db_plan = LearningPlan(
            user_id=plan_data.user_id,
            target_level=plan_data.target_level,
            current_level=plan_data.current_level,
            topics=plan_data.topics,
            milestones=plan_data.milestones,
            is_active=plan_data.is_active
        )
        self.db.add(db_plan)
        await self.db.commit()
        await self.db.refresh(db_plan)
        return db_plan

    async def get_plan(self, plan_id: str) -> Optional[LearningPlan]:
        """Получить план обучения по ID"""
        result = await self.db.execute(
            select(LearningPlan).where(LearningPlan.id == plan_id)
        )
        return result.scalar_one_or_none()

    async def get_user_active_plan(self, user_id: int) -> Optional[LearningPlan]:
        """Получить активный план обучения пользователя"""
        result = await self.db.execute(
            select(LearningPlan)
            .where(LearningPlan.user_id == user_id, LearningPlan.is_active == True)
            .order_by(LearningPlan.created_at.desc())
        )
        return result.scalar_one_or_none()

    async def update_plan(self, plan_id: str, plan_data: LearningPlanUpdate) -> Optional[LearningPlan]:
        """Обновить план обучения"""
        stmt = (
            update(LearningPlan)
            .where(LearningPlan.id == plan_id)
            .values(
                target_level=plan_data.target_level,
                current_level=plan_data.current_level,
                topics=plan_data.topics,
                milestones=plan_data.milestones,
                is_active=plan_data.is_active,
                updated_at=datetime.utcnow()
            )
            .returning(LearningPlan)
        )
        result = await self.db.execute(stmt)
        updated_plan = result.scalar_one_or_none()
        if updated_plan:
            await self.db.commit()
            await self.db.refresh(updated_plan)
        return updated_plan

class XPEventService:
    """Сервис для работы с событиями XP"""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_xp_event(self, event_data: XPEventCreate) -> XPEvent:
        """Создать событие XP"""
        db_event = XPEvent(
            user_id=event_data.user_id,
            session_id=event_data.session_id,
            event_type=event_data.event_type,
            xp_delta=event_data.xp_delta,
            metadata=event_data.metadata
        )
        self.db.add(db_event)
        await self.db.commit()
        await self.db.refresh(db_event)
        return db_event

    async def get_user_xp_events(self, user_id: int, skip: int = 0, limit: int = 100) -> List[XPEvent]:
        """Получить события XP пользователя"""
        result = await self.db.execute(
            select(XPEvent)
            .where(XPEvent.user_id == user_id)
            .order_by(XPEvent.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_total_xp(self, user_id: int) -> int:
        """Получить общий XP пользователя"""
        result = await self.db.execute(
            select(func.sum(XPEvent.xp_delta))
            .where(XPEvent.user_id == user_id)
        )
        total_xp = result.scalar() or 0
        return int(total_xp)

class EmotionalStateLogService:
    """Сервис для работы с логом эмоционального состояния"""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_emotional_log(self, log_data: EmotionalStateLogCreate) -> EmotionalStateLog:
        """Создать запись в логе эмоций"""
        db_log = EmotionalStateLog(
            user_id=log_data.user_id,
            session_id=log_data.session_id,
            emotion_code=log_data.emotion_code,
            intensity=log_data.intensity,
            context=log_data.context
        )
        self.db.add(db_log)
        await self.db.commit()
        await self.db.refresh(db_log)
        return db_log

    async def get_user_emotional_logs(self, user_id: int, skip: int = 0, limit: int = 100) -> List[EmotionalStateLog]:
        """Получить лог эмоций пользователя"""
        result = await self.db.execute(
            select(EmotionalStateLog)
            .where(EmotionalStateLog.user_id == user_id)
            .order_by(EmotionalStateLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_session_emotional_logs(self, session_id: str) -> List[EmotionalStateLog]:
        """Получить лог эмоций сессии"""
        result = await self.db.execute(
            select(EmotionalStateLog)
            .where(EmotionalStateLog.session_id == session_id)
            .order_by(EmotionalStateLog.created_at)
        )
        return list(result.scalars().all())
