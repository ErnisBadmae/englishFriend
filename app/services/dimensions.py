from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from app.models.enums_and_dimensions import DimEmotion, DimTopic, DimAccent
from app.schemas.dimensions import DimEmotionCreate, DimTopicCreate, DimAccentCreate

class DimensionService:
    """Сервис для работы со справочниками"""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    # Методы для DimEmotion
    async def create_emotion(self, emotion_data: DimEmotionCreate) -> DimEmotion:
        """Создать новую эмоцию в справочнике"""
        db_emotion = DimEmotion(
            code=emotion_data.code,
            name_ru=emotion_data.name_ru,
            valence=emotion_data.valence,
            arousal=emotion_data.arousal
        )
        self.db.add(db_emotion)
        await self.db.commit()
        await self.db.refresh(db_emotion)
        return db_emotion

    async def get_emotion(self, code: str) -> Optional[DimEmotion]:
        """Получить эмоцию по коду"""
        result = await self.db.execute(
            select(DimEmotion).where(DimEmotion.code == code)
        )
        return result.scalar_one_or_none()

    async def get_emotions(self, skip: int = 0, limit: int = 100) -> List[DimEmotion]:
        """Получить список эмоций"""
        result = await self.db.execute(
            select(DimEmotion).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    # Методы для DimTopic
    async def create_topic(self, topic_data: DimTopicCreate) -> DimTopic:
        """Создать новую тему в справочнике"""
        db_topic = DimTopic(
            slug=topic_data.slug,
            display_name=topic_data.display_name,
            parent_id=topic_data.parent_id
        )
        self.db.add(db_topic)
        await self.db.commit()
        await self.db.refresh(db_topic)
        return db_topic

    async def get_topic(self, topic_id: str) -> Optional[DimTopic]:
        """Получить тему по ID"""
        result = await self.db.execute(
            select(DimTopic).where(DimTopic.id == topic_id)
        )
        return result.scalar_one_or_none()

    async def get_topic_by_slug(self, slug: str) -> Optional[DimTopic]:
        """Получить тему по слагу"""
        result = await self.db.execute(
            select(DimTopic).where(DimTopic.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_topics(self, skip: int = 0, limit: int = 100) -> List[DimTopic]:
        """Получить список тем"""
        result = await self.db.execute(
            select(DimTopic).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_topics_tree(self) -> List[DimTopic]:
        """Получить дерево тем с загрузкой связей"""
        result = await self.db.execute(
            select(DimTopic).options(selectinload(DimTopic.children))
        )
        return list(result.scalars().all())

    # Методы для DimAccent
    async def create_accent(self, accent_data: DimAccentCreate) -> DimAccent:
        """Создать новый акцент в справочнике"""
        db_accent = DimAccent(
            code=accent_data.code,
            display_name=accent_data.display_name
        )
        self.db.add(db_accent)
        await self.db.commit()
        await self.db.refresh(db_accent)
        return db_accent

    async def get_accent(self, code: str) -> Optional[DimAccent]:
        """Получить акцент по коду"""
        result = await self.db.execute(
            select(DimAccent).where(DimAccent.code == code)
        )
        return result.scalar_one_or_none()

    async def get_accents(self, skip: int = 0, limit: int = 100) -> List[DimAccent]:
        """Получить список акцентов"""
        result = await self.db.execute(
            select(DimAccent).offset(skip).limit(limit)
        )
        return list(result.scalars().all())
