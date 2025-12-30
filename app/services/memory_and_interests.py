from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.models.extended_tables import UserInterest, Memory, LearningPlan, XPEvent
from app.schemas.additional_schemas import (
    UserInterestCreate, MemoryCreate, LearningPlanCreate, XPEventCreate,
    UserInterestUpdate, MemoryUpdate, LearningPlanUpdate
)
from app.models.enums_and_dimensions import MemoryKind, CEFRLevel

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
        """Создать запись памяти (соответствует схеме 005_memories_learning_plan.sql)"""
        # Конвертируем входное значение в MemoryKind для корректного ENUM биндинга
        if isinstance(memory_data.kind, MemoryKind):
            kind_enum = memory_data.kind
        else:
            kind_enum = MemoryKind(memory_data.kind)
        
        db_memory = Memory(
            user_id=memory_data.user_id,
            kind=kind_enum,
            content=memory_data.content,
            meta=memory_data.meta,
            salience=memory_data.salience
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
            # Use .value to ensure string comparison with PostgreSQL enum
            kind_value = kind.value if isinstance(kind, MemoryKind) else kind
            query = query.where(Memory.kind == kind_value)

        result = await self.db.execute(
            query.order_by(Memory.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def update_memory(self, memory_id: str, update_data: MemoryUpdate) -> Optional[Memory]:
        """Обновить запись памяти (соответствует схеме 005_memories_learning_plan.sql)"""
        values = {}
        if update_data.content is not None:
            values['content'] = update_data.content
        if update_data.meta is not None:
            values['meta'] = update_data.meta
        if update_data.salience is not None:
            values['salience'] = update_data.salience
        
        stmt = (
            update(Memory)
            .where(Memory.id == memory_id)
            .values(**values)
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
    
    async def update_memory_access(self, memory_id: str) -> Optional[Memory]:
        """Обновить время доступа к памяти (вызовет триггер для last_refreshed)"""
        # Получаем текущую запись с использованием подзапроса
        subquery = select(Memory.salience).where(Memory.id == memory_id).scalar_subquery()
        
        # Обновляем запись с текущим значением salience - триггер автоматически обновит last_refreshed
        stmt = (
            update(Memory)
            .where(Memory.id == memory_id)
            .values(salience=subquery)  # dummy update to trigger the database trigger
            .returning(Memory)
        )
        result = await self.db.execute(stmt)
        updated_memory = result.scalar_one_or_none()
        if updated_memory:
            await self.db.commit()
        return updated_memory

class LearningPlanService:
    """Сервис для работы с планами обучения"""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_plan(self, plan_data: LearningPlanCreate) -> LearningPlan:
        """Создать план обучения (соответствует схеме 005_memories_learning_plan.sql)"""
        # Конвертируем level_target в CEFRLevel для корректного ENUM биндинга
        if plan_data.level_target is None:
            level_target_enum = None
        elif isinstance(plan_data.level_target, CEFRLevel):
            level_target_enum = plan_data.level_target
        else:
            level_target_enum = CEFRLevel(plan_data.level_target)
        
        db_plan = LearningPlan(
            user_id=plan_data.user_id,
            level_target=level_target_enum,
            next_review_at=plan_data.next_review_at,
            roadmap=plan_data.roadmap
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

    async def get_user_plan(self, user_id: int) -> Optional[LearningPlan]:
        """Получить план обучения пользователя (соответствует схеме 005_memories_learning_plan.sql)"""
        result = await self.db.execute(
            select(LearningPlan)
            .where(LearningPlan.user_id == user_id)
            .order_by(LearningPlan.updated_at.desc())
        )
        return result.scalar_one_or_none()
    
    async def get_user_active_plan(self, user_id: int) -> Optional[LearningPlan]:
        """Получить активный план обучения пользователя (alias для get_user_plan)"""
        return await self.get_user_plan(user_id)

    async def update_plan(self, plan_id: str, plan_data: LearningPlanUpdate) -> Optional[LearningPlan]:
        """Обновить план обучения (соответствует схеме 005_memories_learning_plan.sql)"""
        values = {}
        if plan_data.level_target is not None:
            values['level_target'] = (
                plan_data.level_target
                if isinstance(plan_data.level_target, CEFRLevel)
                else CEFRLevel(plan_data.level_target)
            )
        if plan_data.next_review_at is not None:
            values['next_review_at'] = plan_data.next_review_at
        if plan_data.roadmap is not None:
            values['roadmap'] = plan_data.roadmap
        
        values['updated_at'] = datetime.utcnow()
        
        stmt = (
            update(LearningPlan)
            .where(LearningPlan.id == plan_id)
            .values(**values)
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
        """Создать событие XP (соответствует схеме 005_memories_learning_plan.sql)"""
        db_event = XPEvent(
            user_id=event_data.user_id,
            session_id=event_data.session_id,
            kind=event_data.kind,
            points=event_data.points
        )
        self.db.add(db_event)
        await self.db.commit()
        await self.db.refresh(db_event)
        return db_event

    async def get_user_xp_events(self, user_id: int, skip: int = 0, limit: int = 100) -> List[XPEvent]:
        """Получить события XP пользователя (соответствует схеме 005_memories_learning_plan.sql)"""
        result = await self.db.execute(
            select(XPEvent)
            .where(XPEvent.user_id == user_id)
            .order_by(XPEvent.happened_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_total_xp(self, user_id: int) -> int:
        """Получить общий XP пользователя (соответствует схеме 005_memories_learning_plan.sql)"""
        result = await self.db.execute(
            select(func.sum(XPEvent.points))
            .where(XPEvent.user_id == user_id)
        )
        total_xp = result.scalar() or 0
        return int(total_xp)
