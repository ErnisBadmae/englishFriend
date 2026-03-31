"""Unified Memory Pipeline для EnglishFriend."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums_and_dimensions import MemoryKind
from app.models.extended_tables import Memory
from app.services.ai.embedding_service import (
    EmbeddingService,
    EmbeddingUnavailableError,
    get_embedding_service,
)
from app.services.ai.memory_extraction_service import (
    MemoryExtractionService,
    get_memory_extraction_service,
)
from app.services.ai.qdrant_service import QdrantService, get_qdrant_service

logger = logging.getLogger(__name__)


@dataclass
class MemoryContext:
    """Контекст памяти для использования в промптах."""

    facts: list[str]
    preferences: list[str]
    goals: list[str]
    error_patterns: list[str]
    relevant_memories: list[str]


class MemoryPipeline:
    """Унифицированный pipeline для работы с памятью."""

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: Optional[EmbeddingService] = None,
        extraction_service: Optional[MemoryExtractionService] = None,
        qdrant_service: Optional[QdrantService] = None,
    ):
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
        """Обработать диалог и сохранить извлечённые воспоминания."""
        if not messages:
            return []

        try:
            existing = await self._get_existing_memories(user_id)
            extracted = await self._extraction.extract_from_conversation(
                messages=messages,
                existing_memories=[memory.content for memory in existing],
            )
            if not extracted:
                logger.debug("No new memories extracted for user %s", user_id)
                return []

            contents = [memory.content for memory in extracted]
            embeddings: list[list[float]] | None = None
            if self._embedding.is_available():
                embeddings = await self._embedding.embed_texts(contents)
            else:
                logger.info("Vector memory unavailable, saving extracted memories in DB-only mode")

            created_memories = []
            for index, extracted_memory in enumerate(extracted):
                embedding = embeddings[index] if embeddings else None
                memory = await self._save_memory(
                    user_id=user_id,
                    content=extracted_memory.content,
                    kind=extracted_memory.kind,
                    salience=extracted_memory.salience,
                    embedding=embedding,
                    meta={
                        "session_id": session_id,
                        "extracted_at": datetime.utcnow().isoformat(),
                    },
                )
                if memory:
                    created_memories.append(memory)

            logger.info("Saved %s new memories for user %s", len(created_memories), user_id)
            return created_memories
        except Exception as exc:
            logger.error("Failed to process conversation for user %s: %s", user_id, exc)
            return []

    async def get_relevant_context(
        self,
        user_id: int,
        current_message: str,
        limit: int = 5,
    ) -> MemoryContext:
        """Получить релевантный контекст памяти для текущего сообщения."""
        context = MemoryContext(
            facts=[],
            preferences=[],
            goals=[],
            error_patterns=[],
            relevant_memories=[],
        )

        try:
            existing = await self._get_existing_memories(user_id)
            for memory in existing:
                if memory.kind == MemoryKind.FACT:
                    context.facts.append(memory.content)
                elif memory.kind == MemoryKind.PREFERENCE:
                    context.preferences.append(memory.content)
                elif memory.kind == MemoryKind.GOAL:
                    context.goals.append(memory.content)
                elif memory.kind == MemoryKind.ERROR_PATTERN:
                    context.error_patterns.append(memory.content)

            if (
                current_message
                and self._embedding.is_available()
                and await self._qdrant.health_check()
            ):
                similar = await self._qdrant.search_by_text(
                    query_text=current_message,
                    user_id=user_id,
                    embedding_service=self._embedding,
                    limit=limit,
                    min_score=0.6,
                )
                context.relevant_memories = [memory.content for memory in similar]

            return context
        except Exception as exc:
            logger.error("Failed to get memory context for user %s: %s", user_id, exc)
            return context

    async def format_memory_for_prompt(
        self,
        user_id: int,
        current_message: Optional[str] = None,
    ) -> str:
        """Сформировать секцию памяти для системного промпта."""
        context = await self.get_relevant_context(user_id, current_message or "")
        sections = []

        if context.facts:
            sections.append("## Known facts about the student:\n" + "\n".join(f"- {item}" for item in context.facts[:5]))
        if context.goals:
            sections.append("## Student's learning goals:\n" + "\n".join(f"- {item}" for item in context.goals[:3]))
        if context.preferences:
            sections.append("## Preferences:\n" + "\n".join(f"- {item}" for item in context.preferences[:3]))
        if context.error_patterns:
            sections.append("## Common mistakes to address:\n" + "\n".join(f"- {item}" for item in context.error_patterns[:3]))
        if context.relevant_memories:
            sections.append("## Relevant context from previous sessions:\n" + "\n".join(f"- {item}" for item in context.relevant_memories[:3]))

        return "\n\n".join(sections)

    async def save_single_memory(
        self,
        user_id: int,
        content: str,
        kind: MemoryKind,
        salience: float = 0.5,
        meta: Optional[dict] = None,
    ) -> Optional[Memory]:
        """Сохранить одно воспоминание напрямую."""
        try:
            embedding = None
            if self._embedding.is_available():
                embedding = await self._embedding.embed_text(content)
            else:
                logger.info("Skipping vector upsert for single memory because embeddings are unavailable")

            return await self._save_memory(
                user_id=user_id,
                content=content,
                kind=kind,
                salience=salience,
                embedding=embedding,
                meta=meta,
            )
        except EmbeddingUnavailableError as exc:
            logger.warning("Embeddings unavailable while saving single memory: %s", exc)
            return await self._save_memory(
                user_id=user_id,
                content=content,
                kind=kind,
                salience=salience,
                embedding=None,
                meta=meta,
            )
        except Exception as exc:
            logger.error("Failed to save single memory: %s", exc)
            return None

    async def _get_existing_memories(self, user_id: int, limit: int = 50) -> list[Memory]:
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
        embedding: Optional[list[float]],
        meta: Optional[dict] = None,
    ) -> Optional[Memory]:
        """Сохранить воспоминание в PostgreSQL и, при наличии embedding, в Qdrant."""
        import uuid

        try:
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
        except Exception as exc:
            logger.error("Failed to save memory in PostgreSQL: %s", exc)
            await self.db.rollback()
            return None

        if embedding is None:
            logger.debug("Saved memory %s without vector embedding", memory.id)
            return memory

        qdrant_saved = await self._qdrant.upsert_memory(
            memory_id=memory.id,
            user_id=user_id,
            content=content,
            embedding=embedding,
            kind=kind.value,
            salience=salience,
            meta=meta,
        )
        if not qdrant_saved:
            logger.warning("Saved memory %s in PostgreSQL but skipped Qdrant sync", memory.id)
        else:
            logger.debug("Saved memory %s in PostgreSQL and Qdrant", memory.id)

        return memory


def create_memory_pipeline(db: AsyncSession) -> MemoryPipeline:
    """Создать экземпляр MemoryPipeline."""
    return MemoryPipeline(db=db)
