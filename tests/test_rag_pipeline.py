"""Тесты для RAG pipeline.

Покрывает:
- EmbeddingService: генерация векторов
- MemoryExtractionService: извлечение фактов
- QdrantService: работа с векторной базой
- MemoryPipeline: полный цикл
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.models.enums_and_dimensions import MemoryKind


# =============================================================================
# EmbeddingService Tests
# =============================================================================

class TestEmbeddingService:
    """Тесты для EmbeddingService."""

    @pytest.mark.asyncio
    async def test_embed_text_returns_vector(self):
        """Проверяем что embed_text возвращает вектор правильной размерности."""
        with patch('app.services.ai.embedding_service.AsyncOpenAI') as mock_openai:
            # Mock the embeddings response
            mock_embedding = [0.1] * 1536
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=mock_embedding)]
            mock_openai.return_value.embeddings.create = AsyncMock(return_value=mock_response)

            from app.services.ai.embedding_service import EmbeddingService
            service = EmbeddingService(api_key="test-key")

            result = await service.embed_text("Hello world")

            assert isinstance(result, list)
            assert len(result) == 1536
            assert all(isinstance(x, (int, float)) for x in result)

    @pytest.mark.asyncio
    async def test_embed_empty_text_returns_zeros(self):
        """Проверяем что пустой текст возвращает нулевой вектор."""
        with patch('app.services.ai.embedding_service.AsyncOpenAI') as mock_openai:
            from app.services.ai.embedding_service import EmbeddingService
            service = EmbeddingService(api_key="test-key")

            result = await service.embed_text("")

            assert isinstance(result, list)
            assert len(result) == 1536
            assert all(x == 0.0 for x in result)

    @pytest.mark.asyncio
    async def test_embed_texts_batch(self):
        """Проверяем batch embedding."""
        with patch('app.services.ai.embedding_service.AsyncOpenAI') as mock_openai:
            mock_embeddings = [[0.1] * 1536, [0.2] * 1536]
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=e) for e in mock_embeddings]
            mock_openai.return_value.embeddings.create = AsyncMock(return_value=mock_response)

            from app.services.ai.embedding_service import EmbeddingService
            service = EmbeddingService(api_key="test-key")

            result = await service.embed_texts(["Hello", "World"])

            assert len(result) == 2
            assert all(len(e) == 1536 for e in result)

    def test_cosine_similarity(self):
        """Проверяем вычисление косинусного сходства."""
        from app.services.ai.embedding_service import EmbeddingService

        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        assert EmbeddingService._cosine_similarity(vec1, vec2) == pytest.approx(1.0)

        vec3 = [0.0, 1.0, 0.0]
        assert EmbeddingService._cosine_similarity(vec1, vec3) == pytest.approx(0.0)


# =============================================================================
# MemoryExtractionService Tests
# =============================================================================

class TestMemoryExtractionService:
    """Тесты для MemoryExtractionService."""

    @pytest.mark.asyncio
    async def test_extract_from_conversation(self):
        """Проверяем извлечение фактов из диалога."""
        with patch('app.services.ai.memory_extraction_service.get_llm_provider') as mock_provider:
            # Mock LLM response with valid JSON
            mock_llm = MagicMock()
            mock_llm.generate = AsyncMock(return_value='''[
                {"kind": "fact", "content": "Student is from Russia", "salience": 0.9},
                {"kind": "goal", "content": "Wants to pass ML interview", "salience": 0.95}
            ]''')
            mock_provider.return_value = mock_llm

            from app.services.ai.memory_extraction_service import MemoryExtractionService
            service = MemoryExtractionService()

            messages = [
                {"role": "user", "content": "Hi, I'm Aaron from Russia"},
                {"role": "assistant", "content": "Nice to meet you, Aaron!"},
                {"role": "user", "content": "I want to prepare for ML interview"},
            ]

            result = await service.extract_from_conversation(messages)

            assert len(result) == 2
            assert result[0].kind == MemoryKind.FACT
            assert "Russia" in result[0].content
            assert result[1].kind == MemoryKind.GOAL
            assert "ML" in result[1].content

    @pytest.mark.asyncio
    async def test_extract_empty_conversation(self):
        """Проверяем обработку пустого диалога."""
        from app.services.ai.memory_extraction_service import MemoryExtractionService
        service = MemoryExtractionService()

        result = await service.extract_from_conversation([])
        assert result == []

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self):
        """Проверяем обработку невалидного JSON."""
        with patch('app.services.ai.memory_extraction_service.get_llm_provider') as mock_provider:
            mock_llm = MagicMock()
            mock_llm.generate = AsyncMock(return_value="Not a valid JSON")
            mock_provider.return_value = mock_llm

            from app.services.ai.memory_extraction_service import MemoryExtractionService
            service = MemoryExtractionService()

            result = await service.extract_from_conversation([
                {"role": "user", "content": "Hello"},
            ])

            assert result == []

    @pytest.mark.asyncio
    async def test_extract_error_patterns(self):
        """Проверяем извлечение паттернов ошибок."""
        with patch('app.services.ai.memory_extraction_service.get_llm_provider') as mock_provider:
            mock_llm = MagicMock()
            mock_llm.generate = AsyncMock(return_value='''[
                {"kind": "error_pattern", "content": "Omits articles before nouns", "salience": 0.8}
            ]''')
            mock_provider.return_value = mock_llm

            from app.services.ai.memory_extraction_service import MemoryExtractionService
            service = MemoryExtractionService()

            result = await service.extract_error_patterns([
                "I went to store",
                "He is good man",
            ])

            assert len(result) == 1
            assert result[0].kind == MemoryKind.ERROR_PATTERN


# =============================================================================
# QdrantService Tests
# =============================================================================

class TestQdrantService:
    """Тесты для QdrantService."""

    @pytest.mark.asyncio
    async def test_upsert_memory(self):
        """Проверяем сохранение воспоминания в Qdrant."""
        # Сначала импортируем модуль
        import app.services.ai.qdrant_service as qdrant_module

        mock_client_instance = MagicMock()
        mock_client_instance.get_collections = AsyncMock(return_value=MagicMock(collections=[
            MagicMock(name="user_memories")
        ]))
        mock_client_instance.upsert = AsyncMock()

        with patch.object(qdrant_module, 'AsyncQdrantClient', return_value=mock_client_instance):
            # Сбрасываем singleton
            qdrant_module._qdrant_service = None

            service = qdrant_module.QdrantService()

            result = await service.upsert_memory(
                memory_id="test-uuid",
                user_id=1,
                content="User is from Russia",
                embedding=[0.1] * 1536,
                kind="fact",
                salience=0.9,
            )

            assert result is True
            mock_client_instance.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_similar(self):
        """Проверяем поиск похожих воспоминаний."""
        import app.services.ai.qdrant_service as qdrant_module

        mock_client_instance = MagicMock()
        mock_client_instance.get_collections = AsyncMock(return_value=MagicMock(collections=[
            MagicMock(name="user_memories")
        ]))
        mock_client_instance.search = AsyncMock(return_value=[
            MagicMock(
                id="mem-1",
                score=0.95,
                payload={
                    "content": "User loves Python",
                    "kind": "preference",
                    "salience": 0.8,
                    "created_at": int(datetime.utcnow().timestamp()),
                }
            ),
        ])

        with patch.object(qdrant_module, 'AsyncQdrantClient', return_value=mock_client_instance):
            qdrant_module._qdrant_service = None
            service = qdrant_module.QdrantService()

            results = await service.search_similar(
                query_embedding=[0.1] * 1536,
                user_id=1,
                limit=5,
            )

            assert len(results) == 1
            assert results[0].content == "User loves Python"
            assert results[0].score == 0.95

    @pytest.mark.asyncio
    async def test_ensure_collection_creates_if_missing(self):
        """Проверяем создание коллекции если её нет."""
        import app.services.ai.qdrant_service as qdrant_module

        mock_client_instance = MagicMock()
        mock_client_instance.get_collections = AsyncMock(return_value=MagicMock(collections=[]))
        mock_client_instance.create_collection = AsyncMock()

        with patch.object(qdrant_module, 'AsyncQdrantClient', return_value=mock_client_instance):
            qdrant_module._qdrant_service = None
            service = qdrant_module.QdrantService()

            result = await service.ensure_collection()

            assert result is True
            mock_client_instance.create_collection.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Проверяем успешный health check."""
        import app.services.ai.qdrant_service as qdrant_module

        mock_client_instance = MagicMock()
        mock_client_instance.get_collections = AsyncMock(return_value=MagicMock(collections=[]))

        with patch.object(qdrant_module, 'AsyncQdrantClient', return_value=mock_client_instance):
            qdrant_module._qdrant_service = None
            service = qdrant_module.QdrantService()

            result = await service.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Проверяем неуспешный health check."""
        import app.services.ai.qdrant_service as qdrant_module

        mock_client_instance = MagicMock()
        mock_client_instance.get_collections = AsyncMock(side_effect=Exception("Connection failed"))

        with patch.object(qdrant_module, 'AsyncQdrantClient', return_value=mock_client_instance):
            qdrant_module._qdrant_service = None
            service = qdrant_module.QdrantService()

            result = await service.health_check()
            assert result is False


# =============================================================================
# MemoryPipeline Tests
# =============================================================================

class TestMemoryPipeline:
    """Тесты для MemoryPipeline."""

    @pytest.mark.asyncio
    async def test_format_memory_for_prompt(self):
        """Проверяем форматирование памяти для промпта."""
        with patch('app.services.ai.memory_pipeline.get_embedding_service') as mock_embed, \
             patch('app.services.ai.memory_pipeline.get_memory_extraction_service') as mock_extract, \
             patch('app.services.ai.memory_pipeline.get_qdrant_service') as mock_qdrant:

            # Mock dependencies
            mock_qdrant_instance = MagicMock()
            mock_qdrant_instance.health_check = AsyncMock(return_value=False)
            mock_qdrant.return_value = mock_qdrant_instance

            # Mock DB session
            mock_db = MagicMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [
                MagicMock(content="User is Aaron", kind=MemoryKind.FACT),
                MagicMock(content="Wants ML job", kind=MemoryKind.GOAL),
            ]
            mock_db.execute = AsyncMock(return_value=mock_result)

            from app.services.ai.memory_pipeline import MemoryPipeline
            pipeline = MemoryPipeline(db=mock_db)

            result = await pipeline.format_memory_for_prompt(user_id=1)

            assert "Aaron" in result
            assert "ML job" in result
            assert "Known facts" in result
            assert "learning goals" in result

    @pytest.mark.asyncio
    async def test_save_single_memory(self):
        """Проверяем сохранение одного воспоминания."""
        with patch('app.services.ai.memory_pipeline.get_embedding_service') as mock_embed, \
             patch('app.services.ai.memory_pipeline.get_memory_extraction_service') as mock_extract, \
             patch('app.services.ai.memory_pipeline.get_qdrant_service') as mock_qdrant:

            # Mock embedding
            mock_embed_instance = MagicMock()
            mock_embed_instance.embed_text = AsyncMock(return_value=[0.1] * 1536)
            mock_embed.return_value = mock_embed_instance

            # Mock Qdrant
            mock_qdrant_instance = MagicMock()
            mock_qdrant_instance.upsert_memory = AsyncMock(return_value=True)
            mock_qdrant.return_value = mock_qdrant_instance

            # Mock DB session
            mock_db = MagicMock()
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()

            from app.services.ai.memory_pipeline import MemoryPipeline
            pipeline = MemoryPipeline(db=mock_db)

            result = await pipeline.save_single_memory(
                user_id=1,
                content="User loves Python",
                kind=MemoryKind.PREFERENCE,
                salience=0.7,
            )

            # Should have called embedding service
            mock_embed_instance.embed_text.assert_called_once()
            # Should have saved to DB
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            # Should have saved to Qdrant
            mock_qdrant_instance.upsert_memory.assert_called_once()


# =============================================================================
# Integration-style Tests (with mocked external services)
# =============================================================================

class TestRAGIntegration:
    """Интеграционные тесты для RAG pipeline."""

    @pytest.mark.asyncio
    async def test_full_conversation_to_memory_flow(self):
        """Тест полного цикла: диалог → извлечение → сохранение."""
        with patch('app.services.ai.memory_pipeline.get_embedding_service') as mock_embed, \
             patch('app.services.ai.memory_pipeline.get_memory_extraction_service') as mock_extract, \
             patch('app.services.ai.memory_pipeline.get_qdrant_service') as mock_qdrant:

            # Mock embedding service
            mock_embed_instance = MagicMock()
            mock_embed_instance.embed_texts = AsyncMock(return_value=[[0.1] * 1536])
            mock_embed.return_value = mock_embed_instance

            # Mock extraction service
            from app.services.ai.memory_extraction_service import ExtractedMemory
            mock_extract_instance = MagicMock()
            mock_extract_instance.extract_from_conversation = AsyncMock(return_value=[
                ExtractedMemory(
                    kind=MemoryKind.FACT,
                    content="User is from Russia",
                    salience=0.9,
                ),
            ])
            mock_extract.return_value = mock_extract_instance

            # Mock Qdrant service
            mock_qdrant_instance = MagicMock()
            mock_qdrant_instance.upsert_memory = AsyncMock(return_value=True)
            mock_qdrant.return_value = mock_qdrant_instance

            # Mock DB session
            mock_db = MagicMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()
            mock_db.rollback = AsyncMock()

            from app.services.ai.memory_pipeline import MemoryPipeline
            pipeline = MemoryPipeline(db=mock_db)

            # Process a conversation
            messages = [
                {"role": "user", "content": "Hi, I'm Aaron from Russia"},
                {"role": "assistant", "content": "Nice to meet you!"},
            ]

            result = await pipeline.process_conversation(
                user_id=1,
                messages=messages,
                session_id="test-session",
            )

            # Should have extracted memories
            mock_extract_instance.extract_from_conversation.assert_called_once()

            # Should have generated embeddings
            mock_embed_instance.embed_texts.assert_called_once()

            # Should have saved to DB and Qdrant
            mock_db.add.assert_called()
            mock_qdrant_instance.upsert_memory.assert_called()


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
