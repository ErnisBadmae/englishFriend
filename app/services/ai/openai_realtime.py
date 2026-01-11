"""OpenAI Realtime API провайдер для голосовых диалогов."""

from __future__ import annotations

import json
import base64
import asyncio
from typing import AsyncIterator

import websockets
from websockets.asyncio.client import ClientConnection

from app.core.config import settings
from app.services.ai.base import AIProvider, VoiceSession


class OpenAIRealtimeProvider(AIProvider):
    """Провайдер на базе OpenAI Realtime API (gpt-4o-realtime)."""

    REALTIME_URL = "wss://api.openai.com/v1/realtime"

    def __init__(self):
        self._ws: ClientConnection | None = None
        self._session: VoiceSession | None = None
        self._receive_task: asyncio.Task | None = None
        self._event_queue: asyncio.Queue[dict] = asyncio.Queue()

    async def connect(self, session: VoiceSession) -> None:
        """Установить соединение с OpenAI Realtime API."""
        self._session = session

        url = f"{self.REALTIME_URL}?model={settings.openai_realtime_model}"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "OpenAI-Beta": "realtime=v1",
        }

        self._ws = await websockets.connect(url, additional_headers=headers)

        # Конфигурируем сессию
        await self._send_event({
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": session.system_prompt,
                "voice": settings.openai_realtime_voice,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {"model": "whisper-1"},
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500,
                },
            },
        })

        # Запускаем фоновый приём событий
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def send_audio(self, audio_chunk: bytes) -> None:
        """Отправить аудио чанк (PCM16, 24kHz, mono)."""
        if not self._ws:
            raise RuntimeError("Not connected")

        await self._send_event({
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(audio_chunk).decode(),
        })

    async def receive(self) -> AsyncIterator[dict]:
        """Получить события от OpenAI."""
        while True:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=0.1)
                yield event
                if event.get("type") == "error":
                    break
            except asyncio.TimeoutError:
                if self._receive_task and self._receive_task.done():
                    break
                continue

    async def disconnect(self) -> None:
        """Закрыть соединение."""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            await self._ws.close()
            self._ws = None

    async def _send_event(self, event: dict) -> None:
        """Отправить событие в WebSocket."""
        if self._ws:
            await self._ws.send(json.dumps(event))

    async def _receive_loop(self) -> None:
        """Фоновый цикл приёма событий от OpenAI."""
        if not self._ws:
            return

        try:
            async for message in self._ws:
                event = json.loads(message)
                await self._handle_event(event)
        except websockets.ConnectionClosed:
            await self._event_queue.put({"type": "error", "message": "Connection closed"})

    async def _handle_event(self, event: dict) -> None:
        """Обработать событие от OpenAI и преобразовать в наш формат."""
        event_type = event.get("type", "")

        if event_type == "response.audio.delta":
            # Аудио ответ
            audio_data = base64.b64decode(event.get("delta", ""))
            await self._event_queue.put({"type": "audio", "data": audio_data})

        elif event_type == "response.audio_transcript.delta":
            # Частичный транскрипт ответа AI
            await self._event_queue.put({
                "type": "transcript",
                "role": "assistant",
                "text": event.get("delta", ""),
                "is_final": False,
            })

        elif event_type == "response.audio_transcript.done":
            # Финальный транскрипт ответа AI
            await self._event_queue.put({
                "type": "transcript",
                "role": "assistant",
                "text": event.get("transcript", ""),
                "is_final": True,
            })

        elif event_type == "conversation.item.input_audio_transcription.completed":
            # Транскрипт речи пользователя
            await self._event_queue.put({
                "type": "transcript",
                "role": "user",
                "text": event.get("transcript", ""),
                "is_final": True,
            })

        elif event_type == "error":
            await self._event_queue.put({
                "type": "error",
                "message": event.get("error", {}).get("message", "Unknown error"),
            })
