"""Сервис для работы с Qdrant vector database.

Функции:
- Сохранение воспоминаний с эмбеддингами
- Семантический поиск похожих воспоминаний (RAG retrieval)
- Управление коллекцией user_memories

Collection schema:
- vectors: 1536 dimensions (text-embedding-3-small), Cosine distance
- payload: user_id, kind, salience, created_at, emotion_code, topic_ids
"""

import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchParams,
    Distance,
    VectorParams,
)

logger = logging.getLogger(__name__)

# Константы
COLLECTION_NAME = "user_memories"
VECTOR_SIZE = 1536
QDRANT_URL = "http://localhost:6333"


@dataclass
class MemorySearchResult:
    """Результат поиска воспоминания."""
    id: str
    content: str
    kind: str
    salience: float
    score: float  # Similarity score (0-1)
    created_at: Optional[datetime] = None


class QdrantService:
    """Сервис для работы с Qdrant."""

    def __init__(
        self,
        url: str = QDRANT_URL,
        collection_name: str = COLLECTION_NAME,
    ):
        """
        Args:
            url: URL Qdrant сервера
            collection_name: Имя коллекции
        """
        self._client = AsyncQdrantClient(url=url)
        self._collection = collection_name
        self._initialized = False
        logger.info(f"QdrantService initialized with url={url}, collection={collection_name}")

    async def ensure_collection(self) -> bool:
        """Убедиться что коллекция существует, создать если нет.

        Returns:
            True если коллекция готова
        """
        if self._initialized:
            return True

        try:
            collections = await self._client.get_collections()
            exists = any(c.name == self._collection for c in collections.collections)

            if not exists:
                logger.info(f"Creating collection {self._collection}")
                await self._client.create_collection(
                    collection_name=self._collection,
                    vectors_config=VectorParams(
                        size=VECTOR_SIZE,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info(f"Collection {self._collection} created")

            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"Failed to ensure collection: {e}")
            return False

    async def upsert_memory(
        self,
        memory_id: str,
        user_id: int,
        content: str,
        embedding: list[float],
        kind: str,
        salience: float = 0.5,
        meta: Optional[dict] = None,
    ) -> bool:
        """Сохранить или обновить воспоминание в Qdrant.

        Args:
            memory_id: UUID воспоминания (из PostgreSQL)
            user_id: ID пользователя
            content: Текст воспоминания
            embedding: Вектор эмбеддинга (1536 dimensions)
            kind: Тип воспоминания (fact, preference, goal, etc.)
            salience: Важность (0-1)
            meta: Дополнительные метаданные

        Returns:
            True если успешно
        """
        await self.ensure_collection()

        try:
            point = PointStruct(
                id=memory_id,
                vector=embedding,
                payload={
                    "user_id": user_id,
                    "content": content,
                    "kind": kind,
                    "salience": salience,
                    "created_at": int(datetime.utcnow().timestamp()),
                    "last_refreshed": int(datetime.utcnow().timestamp()),
                    **(meta or {}),
                },
            )

            await self._client.upsert(
                collection_name=self._collection,
                points=[point],
            )

            logger.debug(f"Upserted memory {memory_id} for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to upsert memory: {e}")
            return False

    async def search_similar(
        self,
        query_embedding: list[float],
        user_id: int,
        limit: int = 5,
        min_score: float = 0.7,
        kind_filter: Optional[list[str]] = None,
    ) -> list[MemorySearchResult]:
        """Найти похожие воспоминания (RAG retrieval).

        Args:
            query_embedding: Вектор запроса
            user_id: ID пользователя (фильтр безопасности)
            limit: Максимальное количество результатов
            min_score: Минимальный score для включения
            kind_filter: Фильтр по типам воспоминаний

        Returns:
            Список найденных воспоминаний, отсортированных по релевантности
        """
        await self.ensure_collection()

        try:
            # Строим фильтр
            must_conditions = [
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id),
                )
            ]

            if kind_filter:
                # Qdrant поддерживает OR через should, но для простоты используем отдельные запросы
                # или используем match any
                pass  # TODO: добавить kind фильтр если нужно

            search_filter = Filter(must=must_conditions)

            results = await self._client.search(
                collection_name=self._collection,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=limit,
                score_threshold=min_score,
                search_params=SearchParams(
                    exact=False,  # Используем HNSW приблизительный поиск (быстрее)
                    hnsw_ef=128,
                ),
            )

            memories = []
            for result in results:
                payload = result.payload or {}
                memories.append(MemorySearchResult(
                    id=str(result.id),
                    content=payload.get("content", ""),
                    kind=payload.get("kind", ""),
                    salience=payload.get("salience", 0.5),
                    score=result.score,
                    created_at=datetime.fromtimestamp(payload["created_at"])
                    if payload.get("created_at") else None,
                ))

            logger.debug(f"Found {len(memories)} similar memories for user {user_id}")
            return memories

        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            return []

    async def search_by_text(
        self,
        query_text: str,
        user_id: int,
        embedding_service,  # Avoid circular import
        limit: int = 5,
        min_score: float = 0.7,
    ) -> list[MemorySearchResult]:
        """Поиск по тексту (автоматически создаёт эмбеддинг).

        Args:
            query_text: Текст запроса
            user_id: ID пользователя
            embedding_service: EmbeddingService для векторизации
            limit: Максимальное количество
            min_score: Минимальный score

        Returns:
            Список найденных воспоминаний
        """
        query_embedding = await embedding_service.embed_text(query_text)
        return await self.search_similar(
            query_embedding=query_embedding,
            user_id=user_id,
            limit=limit,
            min_score=min_score,
        )

    async def delete_user_memories(self, user_id: int) -> int:
        """Удалить все воспоминания пользователя (GDPR right to be forgotten).

        Args:
            user_id: ID пользователя

        Returns:
            Количество удалённых записей
        """
        await self.ensure_collection()

        try:
            result = await self._client.delete(
                collection_name=self._collection,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="user_id",
                            match=MatchValue(value=user_id),
                        )
                    ]
                ),
            )
            logger.info(f"Deleted memories for user {user_id}")
            return 1  # Qdrant doesn't return count
        except Exception as e:
            logger.error(f"Failed to delete user memories: {e}")
            return 0

    async def get_collection_info(self) -> dict:
        """Получить информацию о коллекции."""
        try:
            info = await self._client.get_collection(self._collection)
            return {
                "name": self._collection,
                "points_count": info.points_count,
                "vectors_count": info.vectors_count,
                "status": info.status,
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {"error": str(e)}

    async def health_check(self) -> bool:
        """Проверить доступность Qdrant."""
        try:
            await self._client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False


# Singleton instance
_qdrant_service: Optional[QdrantService] = None


def get_qdrant_service() -> QdrantService:
    """Получить singleton экземпляр QdrantService."""
    global _qdrant_service
    if _qdrant_service is None:
        _qdrant_service = QdrantService()
    return _qdrant_service
