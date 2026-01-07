"""Unified Memory Pipeline для EnglishFriend.

Полный цикл работы с памятью:
1. Извлечение фактов из диалога (MemoryExtractionService)
2. Генерация эмбеддингов (EmbeddingService)
3. Сохранение в PostgreSQL + Qdrant (MemoryService + QdrantService)
4. Семантический поиск для RAG (QdrantService)

Этот сервис связывает все компоненты в единый pipeline.
"""

import logging
from typing import Optional
from datetime import datetime
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extended_tables import Memory
from app.models.enums_and_dimensions import MemoryKind
from app.services.ai.embedding_service import get_embedding_service, EmbeddingService
from app.services.ai.memory_extraction_service import (
    get_memory_extraction_service,
    MemoryExtractionService,
    ExtractedMemory,
)
from app.services.ai.qdrant_service import (
    get_qdrant_service,
    QdrantService,
    MemorySearchResult,
)

logger = logging.getLogger(__name__)


@dataclass
class MemoryContext:
    """Контекст памяти для использования в промптах."""
    facts: list[str]  # Факты о пользователе
    preferences: list[str]  # Предпочтения
    goals: list[str]  # Цели обучения
    error_patterns: list[str]  # Паттерны ошибок
    relevant_memories: list[str]  # Релевантные воспоминания для текущего контекста


class MemoryPipeline:
    """Унифицированный pipeline для работы с памятью."""

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: Optional[EmbeddingService] = None,
        extraction_service: Optional[MemoryExtractionService] = None,
        qdrant_service: Optional[QdrantService] = None,
    ):
        """
        Args:
            db: Async database session
            embedding_service: Сервис эмбеддингов (optional, создаётся автоматически)
            extraction_service: Сервис извлечения (optional)
            qdrant_service: Сервис Qdrant (optional)
        """
        self.db = db
        self._embedding = embedding_service or get_embedding_service()
        self._extraction = extraction_service or get_memory_extraction_service()
        self._qdrant = qdrant_service or get_qdrant_service()

    async def process_conversation(
        self,
        user_id: int,
        messages: list[dict],
        session_id: Optional[str] = None,
    ) -> list[Memory]:
        """Обработать диалог и сохранить извлечённые воспоминания.

        Args:
            user_id: ID пользователя
            messages: Список сообщений диалога
            session_id: ID сессии (для привязки)

        Returns:
            Список созданных Memory объектов
        """
        if not messages:
            return []

        try:
            # 1. Получаем существующие воспоминания (чтобы не дублировать)
            existing = await self._get_existing_memories(user_id)
            existing_contents = [m.content for m in existing]

            # 2. Извлекаем новые факты из диалога
            extracted = await self._extraction.extract_from_conversation(
                messages=messages,
                existing_memories=existing_contents,
            )

            if not extracted:
                logger.debug(f"No new memories extracted for user {user_id}")
                return []

            # 3. Генерируем эмбеддинги для всех извлечённых фактов
            contents = [e.content for e in extracted]
            embeddings = await self._embedding.embed_texts(contents)

            # 4. Сохраняем в PostgreSQL и Qdrant
            created_memories = []
            for i, ext_memory in enumerate(extracted):
                memory = await self._save_memory(
                    user_id=user_id,
                    content=ext_memory.content,
                    kind=ext_memory.kind,
                    salience=ext_memory.salience,
                    embedding=embeddings[i],
                    meta={
                        "session_id": session_id,
                        "extracted_at": datetime.utcnow().isoformat(),
                    },
                )
                if memory:
                    created_memories.append(memory)

            logger.info(f"Saved {len(created_memories)} new memories for user {user_id}")
            return created_memories

        except Exception as e:
            logger.error(f"Failed to process conversation for user {user_id}: {e}")
            return []

    async def get_relevant_context(
        self,
        user_id: int,
        current_message: str,
        limit: int = 5,
    ) -> MemoryContext:
        """Получить релевантный контекст памяти для текущего сообщения.

        Args:
            user_id: ID пользователя
            current_message: Текущее сообщение (для семантического поиска)
            limit: Максимум релевантных воспоминаний

        Returns:
            MemoryContext с категоризированными воспоминаниями
        """
        context = MemoryContext(
            facts=[],
            preferences=[],
            goals=[],
            error_patterns=[],
            relevant_memories=[],
        )

        try:
            # 1. Получаем все воспоминания пользователя из PostgreSQL
            existing = await self._get_existing_memories(user_id)

            # Категоризируем
            for mem in existing:
                if mem.kind == MemoryKind.FACT:
                    context.facts.append(mem.content)
                elif mem.kind == MemoryKind.PREFERENCE:
                    context.preferences.append(mem.content)
                elif mem.kind == MemoryKind.GOAL:
                    context.goals.append(mem.content)
                elif mem.kind == MemoryKind.ERROR_PATTERN:
                    context.error_patterns.append(mem.content)

            # 2. Семантический поиск релевантных воспоминаний через Qdrant
            if current_message and await self._qdrant.health_check():
                similar = await self._qdrant.search_by_text(
                    query_text=current_message,
                    user_id=user_id,
                    embedding_service=self._embedding,
                    limit=limit,
                    min_score=0.6,  # Чуть ниже порог для большего контекста
                )
                context.relevant_memories = [m.content for m in similar]

            return context

        except Exception as e:
            logger.error(f"Failed to get memory context for user {user_id}: {e}")
            return context

    async def format_memory_for_prompt(
        self,
        user_id: int,
        current_message: Optional[str] = None,
    ) -> str:
        """Сформировать секцию памяти для системного промпта.

        Args:
            user_id: ID пользователя
            current_message: Текущее сообщение для контекстного поиска

        Returns:
            Отформатированная строка для включения в промпт
        """
        context = await self.get_relevant_context(user_id, current_message or "")

        sections = []

        if context.facts:
            sections.append("## Known facts about the student:\n" +
                          "\n".join(f"- {f}" for f in context.facts[:5]))

        if context.goals:
            sections.append("## Student's learning goals:\n" +
                          "\n".join(f"- {g}" for g in context.goals[:3]))

        if context.preferences:
            sections.append("## Preferences:\n" +
                          "\n".join(f"- {p}" for p in context.preferences[:3]))

        if context.error_patterns:
            sections.append("## Common mistakes to address:\n" +
                          "\n".join(f"- {e}" for e in context.error_patterns[:3]))

        if context.relevant_memories:
            sections.append("## Relevant context from previous sessions:\n" +
                          "\n".join(f"- {m}" for m in context.relevant_memories[:3]))

        if not sections:
            return ""

        return "\n\n".join(sections)

    async def save_single_memory(
        self,
        user_id: int,
        content: str,
        kind: MemoryKind,
        salience: float = 0.5,
        meta: Optional[dict] = None,
    ) -> Optional[Memory]:
        """Сохранить одно воспоминание напрямую.

        Args:
            user_id: ID пользователя
            content: Текст воспоминания
            kind: Тип памяти
            salience: Важность
            meta: Метаданные

        Returns:
            Созданный Memory объект или None
        """
        try:
            # Генерируем эмбеддинг
            embedding = await self._embedding.embed_text(content)

            return await self._save_memory(
                user_id=user_id,
                content=content,
                kind=kind,
                salience=salience,
                embedding=embedding,
                meta=meta,
            )
        except Exception as e:
            logger.error(f"Failed to save single memory: {e}")
            return None

    async def _get_existing_memories(self, user_id: int, limit: int = 50) -> list[Memory]:
        """Получить существующие воспоминания из PostgreSQL."""
        from sqlalchemy import select

        result = await self.db.execute(
            select(Memory)
            .where(Memory.user_id == user_id)
            .order_by(Memory.salience.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _save_memory(
        self,
        user_id: int,
        content: str,
        kind: MemoryKind,
        salience: float,
        embedding: list[float],
        meta: Optional[dict] = None,
    ) -> Optional[Memory]:
        """Сохранить воспоминание в PostgreSQL и Qdrant."""
        import uuid

        try:
            # 1. Сохраняем в PostgreSQL
            memory = Memory(
                id=str(uuid.uuid4()),
                user_id=user_id,
                kind=kind,
                content=content,
                salience=salience,
                meta=meta or {},
            )
            self.db.add(memory)
            await self.db.commit()
            await self.db.refresh(memory)

            # 2. Сохраняем в Qdrant (с эмбеддингом)
            await self._qdrant.upsert_memory(
                memory_id=memory.id,
                user_id=user_id,
                content=content,
                embedding=embedding,
                kind=kind.value,
                salience=salience,
                meta=meta,
            )

            logger.debug(f"Saved memory {memory.id}: {content[:50]}...")
            return memory

        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
            await self.db.rollback()
            return None


def create_memory_pipeline(db: AsyncSession) -> MemoryPipeline:
    """Создать экземпляр MemoryPipeline.

    Args:
        db: Async database session

    Returns:
        Настроенный MemoryPipeline
    """
    return MemoryPipeline(db=db)
