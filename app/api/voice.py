"""WebSocket API для голосовых диалогов.

Архитектура Vosk + Groq + edge-tts:
- Фронтенд (Telegram Mini App) использует Vosk для STT локально
- Отправляет текст на бэкенд через WebSocket
- Бэкенд генерирует ответ через Groq (Llama-70B)
- Синтезирует речь через edge-tts
- Отправляет аудио обратно
"""

import json
import uuid
import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.database import UserService
from app.services.ai.llm_provider import get_llm_provider
from app.services.ai.tts_service import get_tts_service
from app.services.ai.mentor_prompt import build_mentor_prompt, build_simple_prompt, UserContext

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])


@router.websocket("/chat")
async def voice_chat(
    websocket: WebSocket,
    user_id: int = Query(..., description="ID пользователя"),
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint для голосового чата (Vosk + Groq + edge-tts).

    Протокол:
    - Client -> Server: {"type": "text", "text": "распознанный текст от Vosk"}
    - Server -> Client: {"type": "transcript", "role": "assistant", "text": "ответ ментора"}
    - Server -> Client: {"type": "audio", "data": "<base64 MP3>", "format": "mp3"}
    - Server -> Client: {"type": "error", "message": "..."}
    """
    await websocket.accept()

    try:
        # === INITIALIZATION BLOCK (может упасть) ===

        # Проверяем пользователя (опционально, может работать без БД)
        user = None
        try:
            user_service = UserService(db)
            user = await user_service.get_user(user_id)
        except Exception as e:
            print(f"Warning: Could not fetch user from DB: {e}")

        # Инициализируем сервисы
        llm = get_llm_provider()  # vLLM по умолчанию, переключается через LLM_PROVIDER
        tts = get_tts_service()

        # История диалога для контекста
        conversation_history: list[dict] = []

        # Строим системный промпт с обработкой ошибок
        try:
            if user:
                user_context = UserContext(
                    user_id=user_id,
                    username=user.username or f"User_{user_id}",  # Используем username из БД
                    language_level=user.language_level or "B1",  # Берём из профиля с fallback
                )
                system_prompt = await build_mentor_prompt(db, user_context)
            else:
                system_prompt = build_simple_prompt()
        except Exception as e:
            print(f"Error building mentor prompt: {e}")
            system_prompt = build_simple_prompt()

        session_id = str(uuid.uuid4())

        # === MESSAGE LOOP ===
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "Ready to talk! Say something in English.",
        })

        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                if message.get("type") == "text":
                    user_text = message.get("text", "").strip()
                    if not user_text:
                        continue

                    # Отправляем подтверждение получения текста
                    await websocket.send_json({
                        "type": "transcript",
                        "role": "user",
                        "text": user_text,
                    })

                    # Генерируем ответ через LLM (vLLM/Groq/OpenAI)
                    try:
                        response_text = await llm.generate(
                            user_message=user_text,
                            system_prompt=system_prompt,
                            conversation_history=conversation_history,
                            max_tokens=150,  # Короткие ответы для голоса
                        )
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"LLM error: {str(e)}",
                        })
                        continue

                    # Добавляем в историю
                    conversation_history.append({"role": "user", "content": user_text})
                    conversation_history.append({"role": "assistant", "content": response_text})

                    # Ограничиваем историю последними 10 сообщениями
                    if len(conversation_history) > 20:
                        conversation_history = conversation_history[-20:]

                    # Отправляем текст ответа
                    await websocket.send_json({
                        "type": "transcript",
                        "role": "assistant",
                        "text": response_text,
                    })

                    # Синтезируем и отправляем аудио
                    try:
                        audio_bytes = await tts.synthesize(response_text)
                        await websocket.send_json({
                            "type": "audio",
                            "data": base64.b64encode(audio_bytes).decode(),
                            "format": "mp3",
                        })
                    except Exception as e:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"TTS error: {str(e)}",
                        })

                elif message.get("type") == "end":
                    break

            except WebSocketDisconnect:
                print(f"Client disconnected: session {session_id}")
                break

    except Exception as e:
        # Top-level error во время инициализации или message loop
        print(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": "Server error. Please refresh the page.",
            })
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass  # Connection already closed

    finally:
        # Cleanup
        try:
            await websocket.close()
        except Exception:
            pass


# Legacy endpoint для обратной совместимости с OpenAI Realtime
@router.websocket("/stream")
async def voice_stream_legacy(
    websocket: WebSocket,
    user_id: int = Query(..., description="ID пользователя"),
    db: AsyncSession = Depends(get_db),
):
    """
    Legacy WebSocket endpoint для потокового аудио.

    Использует старые провайдеры (OpenAI Realtime, Hume EVI).
    Для нового Vosk + Groq используйте /chat.
    """
    from app.services.ai import get_ai_provider, VoiceSession

    await websocket.accept()

    user_service = UserService(db)
    user = await user_service.get_user(user_id)
    if not user:
        await websocket.send_json({"type": "error", "message": "User not found"})
        await websocket.close()
        return

    session = VoiceSession(
        session_id=str(uuid.uuid4()),
        user_id=user_id,
        system_prompt=build_simple_prompt(),
    )

    provider = get_ai_provider()

    try:
        await provider.connect(session)
        await websocket.send_json({
            "type": "connected",
            "session_id": session.session_id,
            "message": "Ready to talk!",
        })

        import asyncio

        async def forward_ai_events():
            async for event in provider.receive():
                if event["type"] == "audio":
                    await websocket.send_json({
                        "type": "audio",
                        "data": base64.b64encode(event["data"]).decode(),
                    })
                elif event["type"] == "transcript":
                    session.transcript.append({
                        "role": event["role"],
                        "text": event["text"],
                    })
                    await websocket.send_json(event)
                elif event["type"] == "error":
                    await websocket.send_json(event)
                    break

        ai_task = asyncio.create_task(forward_ai_events())

        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)

                if message.get("type") == "audio":
                    audio_bytes = base64.b64decode(message["data"])
                    await provider.send_audio(audio_bytes)

                elif message.get("type") == "end":
                    break

        except WebSocketDisconnect:
            pass
        finally:
            ai_task.cancel()

    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})

    finally:
        await provider.disconnect()
        await websocket.close()
