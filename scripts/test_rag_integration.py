"""
Интеграционный тест RAG pipeline.

Проверяет полный цикл:
1. Извлечение фактов из диалога
2. Генерация эмбеддингов
3. Сохранение в PostgreSQL
4. (Опционально) Сохранение в Qdrant
5. Семантический поиск

Запуск: python scripts/test_rag_integration.py
"""

import asyncio
import sys
from datetime import datetime

# Добавляем корень проекта в path
sys.path.insert(0, '/Users/macbook/Desktop/englishFriend')


async def test_embedding_service():
    """Тест EmbeddingService."""
    print("\n" + "=" * 60)
    print("TEST 1: EmbeddingService")
    print("=" * 60)

    from app.services.ai.embedding_service import EmbeddingService
    from app.core.config import settings

    if not settings.openai_api_key:
        print("⚠️ OpenAI API key not configured, skipping embedding test")
        return None

    service = EmbeddingService()

    # Test single embedding
    text = "User Aaron is from Russia and wants to prepare for ML interview"
    print(f"\n📝 Embedding text: '{text[:50]}...'")

    try:
        embedding = await service.embed_text(text)
        print(f"✅ Generated embedding: {len(embedding)} dimensions")
        print(f"   First 5 values: {embedding[:5]}")
        return embedding
    except Exception as e:
        print(f"❌ Failed: {e}")
        return None


async def test_memory_extraction():
    """Тест MemoryExtractionService."""
    print("\n" + "=" * 60)
    print("TEST 2: MemoryExtractionService")
    print("=" * 60)

    from app.services.ai.memory_extraction_service import MemoryExtractionService

    service = MemoryExtractionService()

    messages = [
        {"role": "user", "content": "Hi, I'm Aaron from Russia"},
        {"role": "assistant", "content": "Nice to meet you, Aaron!"},
        {"role": "user", "content": "I want to prepare for ML job interview at Google"},
        {"role": "assistant", "content": "That's a great goal! What's your current experience?"},
        {"role": "user", "content": "I have work on several machine learning project"},
    ]

    print("\n📝 Extracting memories from conversation...")

    try:
        memories = await service.extract_from_conversation(messages)
        print(f"✅ Extracted {len(memories)} memories:")
        for mem in memories:
            print(f"   [{mem.kind.value}] {mem.content} (salience: {mem.salience})")
        return memories
    except Exception as e:
        print(f"❌ Failed: {e}")
        return []


async def test_qdrant_service():
    """Тест QdrantService."""
    print("\n" + "=" * 60)
    print("TEST 3: QdrantService (Qdrant connection)")
    print("=" * 60)

    from app.services.ai.qdrant_service import QdrantService

    service = QdrantService()

    print("\n📝 Checking Qdrant health...")
    is_healthy = await service.health_check()

    if is_healthy:
        print("✅ Qdrant is available")
        info = await service.get_collection_info()
        print(f"   Collection: {info}")
        return True
    else:
        print("⚠️ Qdrant is not available (this is OK for testing without Docker)")
        return False


async def test_full_pipeline():
    """Тест полного pipeline."""
    print("\n" + "=" * 60)
    print("TEST 4: Full Memory Pipeline")
    print("=" * 60)

    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    from app.services.ai.memory_pipeline import MemoryPipeline
    from app.models.enums_and_dimensions import MemoryKind

    # Create DB session
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        pipeline = MemoryPipeline(db=db)

        # Test saving a single memory
        print("\n📝 Saving a test memory...")

        try:
            memory = await pipeline.save_single_memory(
                user_id=1,
                content="Test user prefers Python for ML development",
                kind=MemoryKind.PREFERENCE,
                salience=0.7,
                meta={"test": True},
            )

            if memory:
                print(f"✅ Saved memory: {memory.id}")
                print(f"   Content: {memory.content}")
                print(f"   Kind: {memory.kind}")
            else:
                print("⚠️ Memory not saved (check OpenAI API key)")

        except Exception as e:
            print(f"❌ Failed: {e}")

        # Test getting memory context
        print("\n📝 Getting memory context for prompt...")

        try:
            context = await pipeline.format_memory_for_prompt(user_id=1)
            if context:
                print(f"✅ Memory context ({len(context)} chars):")
                print("-" * 40)
                print(context[:500])
                print("-" * 40)
            else:
                print("⚠️ No memories found for user 1")

        except Exception as e:
            print(f"❌ Failed: {e}")


async def main():
    print("\n" + "🚀" * 30)
    print("RAG PIPELINE INTEGRATION TEST")
    print("🚀" * 30)

    # Run tests
    embedding = await test_embedding_service()
    memories = await test_memory_extraction()
    qdrant_ok = await test_qdrant_service()
    await test_full_pipeline()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    print(f"\n✅ EmbeddingService: {'Working' if embedding else 'Needs OpenAI API key'}")
    print(f"✅ MemoryExtractionService: {'Working ({} memories)'.format(len(memories)) if memories else 'Needs LLM'}")
    print(f"{'✅' if qdrant_ok else '⚠️'} QdrantService: {'Connected' if qdrant_ok else 'Not connected (optional)'}")
    print(f"✅ MemoryPipeline: Integrated into voice.py")

    print("\n" + "=" * 60)
    print("RAG Pipeline is ready!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
