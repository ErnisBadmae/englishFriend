"""Тест бэкенда голосового чата (vLLM/Groq + edge-tts).

Запуск:
    python scripts/test_voice_backend.py

По умолчанию тестирует vLLM на 192.168.0.88:8000
"""

import asyncio
import os
import sys
import time

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def test_vllm():
    """Тест vLLM сервера."""
    print("\n=== Тест vLLM ===")

    from app.services.ai.llm_provider import get_llm_provider
    from app.core.config import settings

    print(f"URL: {settings.vllm_base_url}")
    print(f"Модель: {settings.vllm_model}")

    try:
        llm = get_llm_provider("vllm")

        start_time = time.time()
        response = await llm.generate(
            user_message="Hello! How are you today?",
            system_prompt="You are a friendly English tutor. Keep responses short (1-2 sentences).",
            max_tokens=50,
        )
        elapsed = time.time() - start_time

        print(f"Ответ: {response}")
        print(f"Время: {elapsed:.2f}s")
        return True
    except Exception as e:
        print(f"Ошибка vLLM: {e}")
        print("Проверьте что сервер запущен на 192.168.0.88:8000")
        return False


async def test_groq():
    """Тест Groq API."""
    print("\n=== Тест Groq API ===")

    from app.services.ai.llm_provider import get_llm_provider
    from app.core.config import settings

    if not settings.groq_api_key:
        print("GROQ_API_KEY не установлен в .env")
        print("Получить ключ: https://console.groq.com/keys")
        return False

    try:
        llm = get_llm_provider("groq")

        start_time = time.time()
        response = await llm.generate(
            user_message="Hello! How are you today?",
            system_prompt="You are a friendly English tutor. Keep responses short (1-2 sentences).",
            max_tokens=50,
        )
        elapsed = time.time() - start_time

        print(f"Ответ: {response}")
        print(f"Время: {elapsed:.2f}s")
        return True
    except Exception as e:
        print(f"Ошибка Groq: {e}")
        return False


async def test_tts():
    """Тест edge-tts."""
    print("\n=== Тест edge-tts ===")

    from app.services.ai.tts_service import get_tts_service

    tts = get_tts_service()

    try:
        audio_bytes = await tts.synthesize("Hello! Welcome to English Friend. Let's practice speaking!")
        print(f"Аудио сгенерировано: {len(audio_bytes)} байт")

        # Сохраняем для проверки
        output_file = "test_output.mp3"
        with open(output_file, "wb") as f:
            f.write(audio_bytes)
        print(f"Аудио сохранено в {output_file}")
        return True
    except Exception as e:
        print(f"Ошибка TTS: {e}")
        return False


async def test_full_pipeline():
    """Тест полного пайплайна: текст -> LLM -> edge-tts -> аудио."""
    print("\n=== Тест полного пайплайна ===")

    from app.services.ai.llm_provider import get_llm_provider
    from app.services.ai.tts_service import get_tts_service
    from app.services.ai.mentor_prompt import build_simple_prompt
    from app.core.config import settings

    print(f"LLM Provider: {settings.llm_provider}")

    llm = get_llm_provider()  # Использует LLM_PROVIDER из настроек
    tts = get_tts_service()
    system_prompt = build_simple_prompt("Test User", "B1")

    # Симулируем диалог
    user_inputs = [
        "Hi! I'm learning English.",
        "I went to the store yesterday.",
        "What should I practice today?",
    ]

    conversation_history = []
    total_llm_time = 0

    for user_text in user_inputs:
        print(f"\nUser: {user_text}")

        # Генерируем ответ
        start_time = time.time()
        response = await llm.generate(
            user_message=user_text,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            max_tokens=100,
        )
        llm_time = time.time() - start_time
        total_llm_time += llm_time

        print(f"Mentor: {response}")
        print(f"LLM time: {llm_time:.2f}s")

        # Обновляем историю
        conversation_history.append({"role": "user", "content": user_text})
        conversation_history.append({"role": "assistant", "content": response})

        # Синтезируем аудио
        start_time = time.time()
        audio_bytes = await tts.synthesize(response)
        tts_time = time.time() - start_time
        print(f"TTS: {len(audio_bytes)} bytes, {tts_time:.2f}s")

    print(f"\nСреднее время LLM: {total_llm_time / len(user_inputs):.2f}s")
    print("Полный пайплайн работает!")
    return True


async def main():
    print("=" * 50)
    print("Тестирование бэкенда English Friend")
    print("=" * 50)

    from app.core.config import settings
    print(f"\nТекущий LLM провайдер: {settings.llm_provider}")

    results = []

    # Тест TTS (не требует API ключа)
    results.append(("edge-tts", await test_tts()))

    # Тест vLLM
    results.append(("vLLM", await test_vllm()))

    # Тест Groq (требует API ключа)
    results.append(("Groq API", await test_groq()))

    # Полный пайплайн
    results.append(("Full Pipeline", await test_full_pipeline()))

    print("\n" + "=" * 50)
    print("Результаты:")
    for name, success in results:
        status = "OK" if success else "FAIL"
        print(f"  {name}: {status}")
    print("=" * 50)

    # Cleanup
    if os.path.exists("test_output.mp3"):
        os.remove("test_output.mp3")
        print("Тестовый файл удалён")


if __name__ == "__main__":
    asyncio.run(main())
