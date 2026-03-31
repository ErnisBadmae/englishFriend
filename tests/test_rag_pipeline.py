"""Tests for the RAG / memory pipeline."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums_and_dimensions import MemoryKind


class TestEmbeddingService:
    @pytest.mark.asyncio
    async def test_embed_text_returns_vector(self):
        with patch("app.services.ai.embedding_service.AsyncOpenAI") as mock_openai:
            mock_embedding = [0.1] * 1536
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=mock_embedding)]
            mock_openai.return_value.embeddings.create = AsyncMock(return_value=mock_response)

            from app.services.ai.embedding_service import EmbeddingService

            service = EmbeddingService(api_key="test-key")
            result = await service.embed_text("Hello world")

            assert isinstance(result, list)
            assert len(result) == 1536

    @pytest.mark.asyncio
    async def test_embed_empty_text_returns_zeros(self):
        from app.services.ai.embedding_service import EmbeddingService

        service = EmbeddingService(api_key="test-key")
        result = await service.embed_text("")

        assert len(result) == 1536
        assert all(value == 0.0 for value in result)

    def test_unavailable_without_api_key(self):
        from app.services.ai.embedding_service import EmbeddingService

        service = EmbeddingService(api_key="", enabled=True)
        assert service.is_available() is False

    def test_cosine_similarity(self):
        from app.services.ai.embedding_service import EmbeddingService

        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        vec3 = [0.0, 1.0, 0.0]

        assert EmbeddingService._cosine_similarity(vec1, vec2) == pytest.approx(1.0)
        assert EmbeddingService._cosine_similarity(vec1, vec3) == pytest.approx(0.0)


class TestMemoryExtractionService:
    @pytest.mark.asyncio
    async def test_extract_from_conversation(self):
        with patch("app.services.ai.memory_extraction_service.get_llm_provider") as mock_provider:
            mock_llm = MagicMock()
            mock_llm.generate = AsyncMock(
                return_value='[{"kind":"fact","content":"Student is from Russia","salience":0.9}]'
            )
            mock_provider.return_value = mock_llm

            from app.services.ai.memory_extraction_service import MemoryExtractionService

            service = MemoryExtractionService()
            result = await service.extract_from_conversation(
                [{"role": "user", "content": "Hi, I'm Aaron from Russia"}]
            )

            assert len(result) == 1
            assert result[0].kind == MemoryKind.FACT


class TestQdrantService:
    @pytest.mark.asyncio
    async def test_upsert_memory(self):
        import app.services.ai.qdrant_service as qdrant_module

        mock_client_instance = MagicMock()
        mock_client_instance.get_collections = AsyncMock(
            return_value=MagicMock(collections=[MagicMock(name="user_memories")])
        )
        mock_client_instance.upsert = AsyncMock()

        with patch.object(qdrant_module, "AsyncQdrantClient", return_value=mock_client_instance):
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
        import app.services.ai.qdrant_service as qdrant_module

        mock_client_instance = MagicMock()
        mock_client_instance.get_collections = AsyncMock(
            return_value=MagicMock(collections=[MagicMock(name="user_memories")])
        )
        mock_client_instance.search = AsyncMock(
            return_value=[
                MagicMock(
                    id="mem-1",
                    score=0.95,
                    payload={
                        "content": "User loves Python",
                        "kind": "preference",
                        "salience": 0.8,
                        "created_at": int(datetime.utcnow().timestamp()),
                    },
                )
            ]
        )

        with patch.object(qdrant_module, "AsyncQdrantClient", return_value=mock_client_instance):
            qdrant_module._qdrant_service = None
            service = qdrant_module.QdrantService()

            results = await service.search_similar([0.1] * 1536, user_id=1, limit=5)

            assert len(results) == 1
            assert results[0].content == "User loves Python"


class TestMemoryPipeline:
    @pytest.mark.asyncio
    async def test_format_memory_for_prompt(self):
        with patch("app.services.ai.memory_pipeline.get_embedding_service") as mock_embed, \
             patch("app.services.ai.memory_pipeline.get_memory_extraction_service"), \
             patch("app.services.ai.memory_pipeline.get_qdrant_service") as mock_qdrant:

            mock_embed.return_value.is_available.return_value = False
            mock_qdrant.return_value.health_check = AsyncMock(return_value=False)

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

    @pytest.mark.asyncio
    async def test_save_single_memory_with_embeddings(self):
        with patch("app.services.ai.memory_pipeline.get_embedding_service") as mock_embed, \
             patch("app.services.ai.memory_pipeline.get_memory_extraction_service"), \
             patch("app.services.ai.memory_pipeline.get_qdrant_service") as mock_qdrant:

            mock_embed.return_value.is_available.return_value = True
            mock_embed.return_value.embed_text = AsyncMock(return_value=[0.1] * 1536)
            mock_qdrant.return_value.upsert_memory = AsyncMock(return_value=True)

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

            assert result is not None
            mock_embed.return_value.embed_text.assert_called_once()
            mock_qdrant.return_value.upsert_memory.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_single_memory_without_embeddings_uses_db_only(self):
        with patch("app.services.ai.memory_pipeline.get_embedding_service") as mock_embed, \
             patch("app.services.ai.memory_pipeline.get_memory_extraction_service"), \
             patch("app.services.ai.memory_pipeline.get_qdrant_service") as mock_qdrant:

            mock_embed.return_value.is_available.return_value = False
            mock_qdrant.return_value.upsert_memory = AsyncMock(return_value=True)

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

            assert result is not None
            mock_qdrant.return_value.upsert_memory.assert_not_called()


class TestRAGIntegration:
    @pytest.mark.asyncio
    async def test_full_conversation_to_memory_flow(self):
        with patch("app.services.ai.memory_pipeline.get_embedding_service") as mock_embed, \
             patch("app.services.ai.memory_pipeline.get_memory_extraction_service") as mock_extract, \
             patch("app.services.ai.memory_pipeline.get_qdrant_service") as mock_qdrant:

            mock_embed.return_value.is_available.return_value = True
            mock_embed.return_value.embed_texts = AsyncMock(return_value=[[0.1] * 1536])

            from app.services.ai.memory_extraction_service import ExtractedMemory

            mock_extract.return_value.extract_from_conversation = AsyncMock(
                return_value=[
                    ExtractedMemory(
                        kind=MemoryKind.FACT,
                        content="User is from Russia",
                        salience=0.9,
                    )
                ]
            )
            mock_qdrant.return_value.upsert_memory = AsyncMock(return_value=True)

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
            result = await pipeline.process_conversation(
                user_id=1,
                messages=[
                    {"role": "user", "content": "Hi, I'm Aaron from Russia"},
                    {"role": "assistant", "content": "Nice to meet you!"},
                ],
                session_id="test-session",
            )

            assert len(result) == 1
            mock_extract.return_value.extract_from_conversation.assert_called_once()
            mock_embed.return_value.embed_texts.assert_called_once()
            mock_qdrant.return_value.upsert_memory.assert_called_once()
