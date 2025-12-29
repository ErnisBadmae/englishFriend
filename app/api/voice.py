"""WebSocket API для голосовых диалогов."""

import json
import uuid
import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.ai import get_ai_provider, VoiceSession
from app.services.database import UserService

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])

# Системный промпт ментора
MENTOR_PROMPT = """You are English Friend, a warm and encouraging AI English tutor.

## Your Role
- Patient, friendly English teacher for Russian speakers
- Focus on conversation practice, not lectures
- Correct mistakes gently without interrupting flow

## Guidelines
1. Keep responses short (2-3 sentences)
2. Ask follow-up questions to encourage speaking
3. Correct errors naturally: "Oh, you WENT there! That sounds fun..."
4. Speak clearly at moderate pace

## Correction Style
- Minor errors: note and summarize at end
- Major errors: gently rephrase in your response
- Example: User says "I goed there" → You say "Oh, you went there! Tell me more..."
"""


@router.websocket("/stream")
async def voice_stream(
    websocket: WebSocket,
    user_id: int = Query(..., description="ID пользователя"),
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint для голосового диалога.

    Протокол:
    - Client -> Server: {"type": "audio", "data": "<base64 PCM16 24kHz>"}
    - Server -> Client: {"type": "audio", "data": "<base64 PCM16 24kHz>"}
    - Server -> Client: {"type": "transcript", "role": "user|assistant", "text": "...", "is_final": bool}
    - Server -> Client: {"type": "error", "message": "..."}
    """
    await websocket.accept()

    # Проверяем пользователя
    user_service = UserService(db)
    user = await user_service.get_user(user_id)
    if not user:
        await websocket.send_json({"type": "error", "message": "User not found"})
        await websocket.close()
        return

    # Создаём сессию
    session = VoiceSession(
        session_id=str(uuid.uuid4()),
        user_id=user_id,
        system_prompt=MENTOR_PROMPT,
    )

    # Подключаемся к AI провайдеру
    provider = get_ai_provider()

    try:
        await provider.connect(session)
        await websocket.send_json({
            "type": "connected",
            "session_id": session.session_id,
            "message": "Ready to talk!",
        })

        # Запускаем приём от AI в фоне
        import asyncio

        async def forward_ai_events():
            """Пересылаем события от AI клиенту."""
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

        # Принимаем аудио от клиента
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
