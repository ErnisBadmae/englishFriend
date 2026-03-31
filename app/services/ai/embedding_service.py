"""Сервис генерации векторных эмбеддингов."""

from __future__ import annotations

import logging
from typing import Optional

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


EMBEDDING_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class EmbeddingUnavailableError(RuntimeError):
    """Embedding backend is disabled or not configured."""


class EmbeddingService:
    """Сервис для генерации векторных эмбеддингов."""

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        enabled: Optional[bool] = None,
    ):
        self.model = model or settings.openai_embedding_model
        self.dimensions = EMBEDDING_DIMENSIONS.get(self.model, 1536)
        self.enabled = settings.vector_memory_enabled if enabled is None else enabled
        self._api_key = api_key or settings.openai_api_key
        self._available = self.enabled and bool(self._api_key)
        self._client = AsyncOpenAI(api_key=self._api_key) if self._available else None

        if not self.enabled:
            logger.info("EmbeddingService disabled by VECTOR_MEMORY_ENABLED=false")
        elif not self._api_key:
            logger.warning("OpenAI API key not configured, vector memory will run in DB-only mode")

        logger.info(
            "EmbeddingService initialized with model=%s dimensions=%s available=%s",
            self.model,
            self.dimensions,
            self._available,
        )

    def is_available(self) -> bool:
        """Return True when embeddings can be requested from the provider."""
        return self._available

    def _ensure_available(self) -> None:
        if self._available:
            return

        if not self.enabled:
            raise EmbeddingUnavailableError("Vector memory is disabled")

        raise EmbeddingUnavailableError("OPENAI_API_KEY is not configured for embeddings")

    async def embed_text(self, text: str) -> list[float]:
        """Создать эмбеддинг для текста."""
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return [0.0] * self.dimensions

        self._ensure_available()
        response = await self._client.embeddings.create(
            model=self.model,
            input=text.strip(),
        )
        embedding = response.data[0].embedding
        logger.debug("Generated embedding for text (%s chars)", len(text))
        return embedding

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Создать эмбеддинги для нескольких текстов."""
        if not texts:
            return []

        valid_texts = [text.strip() for text in texts if text and text.strip()]
        if not valid_texts:
            return [[0.0] * self.dimensions] * len(texts)

        self._ensure_available()
        response = await self._client.embeddings.create(
            model=self.model,
            input=valid_texts,
        )
        embeddings = [item.embedding for item in response.data]
        logger.debug("Generated %s embeddings (batch)", len(embeddings))
        return embeddings

    async def similarity(self, text1: str, text2: str) -> float:
        """Вычислить косинусное сходство между двумя текстами."""
        embeddings = await self.embed_texts([text1, text2])
        return self._cosine_similarity(embeddings[0], embeddings[1])

    @staticmethod
    def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """Вычислить косинусное сходство между двумя векторами."""
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have same dimension")

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Получить singleton экземпляр EmbeddingService."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
