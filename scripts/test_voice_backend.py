"""Smoke checks for the voice backend stack.

Run:
    python scripts/test_voice_backend.py

What it does:
- verifies the configured vLLM OpenAI-compatible endpoint via `/v1/models`
- verifies the configured vLLM generate path through the shared provider
- optionally verifies Groq if a key is configured
- verifies edge-tts synthesis
- runs a short end-to-end text -> LLM -> TTS pipeline
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from urllib.parse import urljoin

import httpx
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


async def test_vllm_connectivity() -> bool:
    """Verify that the configured OpenAI-compatible endpoint is reachable."""
    print("\n=== vLLM connectivity ===")

    from app.core.config import settings

    models_url = urljoin(settings.vllm_base_url.rstrip("/") + "/", "models")
    headers: dict[str, str] = {}
    if settings.vllm_api_key:
        headers["Authorization"] = f"Bearer {settings.vllm_api_key}"

    print(f"URL: {settings.vllm_base_url}")
    print(f"API key present: {bool(settings.vllm_api_key)}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(models_url, headers=headers)
        response.raise_for_status()
        payload = response.json()
        model_count = len(payload.get("data") or []) if isinstance(payload, dict) else 0
        print(f"/models OK, found {model_count} model(s)")
        return True
    except Exception as exc:
        print(f"Connectivity error: {exc}")
        print("Check VLLM_BASE_URL, VLLM_API_KEY, and LAN reachability.")
        return False


async def test_vllm_generate() -> bool:
    """Verify the shared vLLM provider generate path."""
    print("\n=== vLLM generate ===")

    from app.core.config import settings
    from app.services.ai.llm_provider import get_llm_provider

    print(f"URL: {settings.vllm_base_url}")
    print(f"Model: {settings.vllm_model}")
    print(f"API key present: {bool(settings.vllm_api_key)}")

    try:
        llm = get_llm_provider("vllm")

        start_time = time.time()
        response = await llm.generate(
            user_message="Hello! How are you today?",
            system_prompt="You are a friendly English tutor. Keep responses short (1-2 sentences).",
            max_tokens=50,
        )
        elapsed = time.time() - start_time

        print(f"Response: {response}")
        print(f"Time: {elapsed:.2f}s")
        return True
    except Exception as exc:
        print(f"vLLM error: {exc}")
        print("Check that local/team Qwen is reachable through VLLM_BASE_URL.")
        return False


async def test_groq() -> bool:
    """Verify Groq only when a key is configured."""
    print("\n=== Groq API ===")

    from app.core.config import settings
    from app.services.ai.llm_provider import get_llm_provider

    if not settings.groq_api_key:
        print("GROQ_API_KEY is not configured in .env")
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

        print(f"Response: {response}")
        print(f"Time: {elapsed:.2f}s")
        return True
    except Exception as exc:
        print(f"Groq error: {exc}")
        return False


async def test_tts() -> bool:
    """Verify edge-tts synthesis."""
    print("\n=== edge-tts ===")

    from app.services.ai.tts_service import get_tts_service

    tts = get_tts_service()

    try:
        audio_bytes = await tts.synthesize(
            "Hello! Welcome to English Friend. Let's practice speaking!"
        )
        print(f"Audio generated: {len(audio_bytes)} bytes")

        output_file = "test_output.mp3"
        with open(output_file, "wb") as handle:
            handle.write(audio_bytes)
        print(f"Saved to {output_file}")
        return True
    except Exception as exc:
        print(f"TTS error: {exc}")
        return False


async def test_full_pipeline() -> bool:
    """Run a short text -> LLM -> TTS pipeline."""
    print("\n=== full pipeline ===")

    from app.core.config import settings
    from app.services.ai.llm_provider import get_llm_provider
    from app.services.ai.mentor_prompt import build_simple_prompt
    from app.services.ai.tts_service import get_tts_service

    print(f"LLM provider: {settings.llm_provider}")

    llm = get_llm_provider()
    tts = get_tts_service()
    system_prompt = build_simple_prompt("Test User", "B1")

    user_inputs = [
        "Hi! I'm learning English.",
        "I went to the store yesterday.",
        "What should I practice today?",
    ]

    conversation_history: list[dict[str, str]] = []
    total_llm_time = 0.0

    for user_text in user_inputs:
        print(f"\nUser: {user_text}")

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

        conversation_history.append({"role": "user", "content": user_text})
        conversation_history.append({"role": "assistant", "content": response})

        start_time = time.time()
        audio_bytes = await tts.synthesize(response)
        tts_time = time.time() - start_time
        print(f"TTS: {len(audio_bytes)} bytes, {tts_time:.2f}s")

    print(f"\nAverage LLM time: {total_llm_time / len(user_inputs):.2f}s")
    print("Full pipeline OK")
    return True


async def main() -> None:
    print("=" * 50)
    print("English Friend backend smoke")
    print("=" * 50)

    from app.core.config import settings

    print(f"\nCurrent LLM provider: {settings.llm_provider}")

    results: list[tuple[str, bool]] = []
    results.append(("edge-tts", await test_tts()))
    results.append(("vLLM connectivity", await test_vllm_connectivity()))
    results.append(("vLLM generate", await test_vllm_generate()))
    results.append(("Groq API", await test_groq()))
    results.append(("Full pipeline", await test_full_pipeline()))

    print("\n" + "=" * 50)
    print("Results:")
    for name, success in results:
        status = "OK" if success else "FAIL"
        print(f"  {name}: {status}")
    print("=" * 50)

    if os.path.exists("test_output.mp3"):
        os.remove("test_output.mp3")
        print("Removed test_output.mp3")


if __name__ == "__main__":
    asyncio.run(main())
