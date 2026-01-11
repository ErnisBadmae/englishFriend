"""Сервис генерации векторных эмбеддингов.

Поддерживает:
- OpenAI text-embedding-3-small (1536 dimensions, дешёвый, хорошее качество)
- OpenAI text-embedding-3-large (3072 dimensions, лучшее качество)
- Groq (через совместимый API, если доступно)

Используется для:
- Векторизации воспоминаний перед сохранением в Qdrant
- Создания query vectors для семантического поиска
"""

from typing import Optional
from openai import AsyncOpenAI
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Размерности эмбеддингов
EMBEDDING_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

# Модель по умолчанию (самая экономичная)
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


class EmbeddingService:
    """Сервис для генерации векторных эмбеддингов."""

    def __init__(
        self,
        model: str = DEFAULT_EMBEDDING_MODEL,
        api_key: Optional[str] = None,
    ):
        """
        Args:
            model: Модель эмбеддингов OpenAI
            api_key: API ключ (если None, берётся из settings)
        """
        self.model = model
        self.dimensions = EMBEDDING_DIMENSIONS.get(model, 1536)

        # Используем OpenAI API key (или Groq если настроен OpenAI-совместимый endpoint)
        api_key = api_key or settings.openai_api_key
        if not api_key:
            logger.warning("OpenAI API key not configured, embeddings will fail")

        self._client = AsyncOpenAI(api_key=api_key or "dummy")
        logger.info(f"EmbeddingService initialized with model={model}, dimensions={self.dimensions}")

    async def embed_text(self, text: str) -> list[float]:
        """Создать эмбеддинг для текста.

        Args:
            text: Текст для векторизации

        Returns:
            Список float значений (вектор)
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return [0.0] * self.dimensions

        try:
            response = await self._client.embeddings.create(
                model=self.model,
                input=text.strip(),
            )
            embedding = response.data[0].embedding
            logger.debug(f"Generated embedding for text ({len(text)} chars)")
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Создать эмбеддинги для нескольких текстов (batch).

        Args:
            texts: Список текстов

        Returns:
            Список векторов
        """
        if not texts:
            return []

        # Фильтруем пустые строки
        valid_texts = [t.strip() for t in texts if t and t.strip()]
        if not valid_texts:
            return [[0.0] * self.dimensions] * len(texts)

        try:
            response = await self._client.embeddings.create(
                model=self.model,
                input=valid_texts,
            )

            # Результаты приходят в том же порядке
            embeddings = [item.embedding for item in response.data]
            logger.debug(f"Generated {len(embeddings)} embeddings (batch)")
            return embeddings
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise

    async def similarity(self, text1: str, text2: str) -> float:
        """Вычислить косинусное сходство между двумя текстами.

        Args:
            text1: Первый текст
            text2: Второй текст

        Returns:
            Косинусное сходство (0.0 - 1.0)
        """
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


# Singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Получить singleton экземпляр EmbeddingService."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
