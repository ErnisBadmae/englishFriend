"""Hume EVI (Empathic Voice Interface) провайдер.

Преимущества:
- $0.072/мин (в 2 раза дешевле OpenAI)
- Эмоциональный интеллект - понимает тон голоса
- Можно использовать с любым LLM (Claude, GPT, etc.)
- Низкая задержка ~300ms

Документация: https://dev.hume.ai/docs/empathic-voice-interface-evi/overview
"""

from __future__ import annotations

import json
import base64
import asyncio
from typing import AsyncIterator

import websockets
from websockets.asyncio.client import ClientConnection

from app.core.config import settings
from app.services.ai.base import AIProvider, VoiceSession


class HumeEVIProvider(AIProvider):
    """Провайдер на базе Hume EVI (Empathic Voice Interface)."""

    EVI_URL = "wss://api.hume.ai/v0/evi/chat"

    def __init__(self):
        self._ws: ClientConnection | None = None
        self._session: VoiceSession | None = None
        self._receive_task: asyncio.Task | None = None
        self._event_queue: asyncio.Queue[dict] = asyncio.Queue()

    async def connect(self, session: VoiceSession) -> None:
        """Установить соединение с Hume EVI."""
        self._session = session

        # Hume использует API key в URL параметрах
        url = f"{self.EVI_URL}?api_key={settings.hume_api_key}"

        self._ws = await websockets.connect(url)

        # Отправляем конфигурацию сессии
        await self._send_event({
            "type": "session_settings",
            "system_prompt": session.system_prompt,
            "language": "en",
            # Можно добавить свой LLM
            # "custom_llm": {
            #     "model": "claude-3-5-sonnet",
            #     "api_key": "..."
            # }
        })

        # Запускаем фоновый приём событий
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def send_audio(self, audio_chunk: bytes) -> None:
        """Отправить аудио чанк."""
        if not self._ws:
            raise RuntimeError("Not connected")

        await self._send_event({
            "type": "audio_input",
            "data": base64.b64encode(audio_chunk).decode(),
        })

    async def receive(self) -> AsyncIterator[dict]:
        """Получить события от Hume EVI."""
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
        """Фоновый цикл приёма событий от Hume."""
        if not self._ws:
            return

        try:
            async for message in self._ws:
                event = json.loads(message)
                await self._handle_event(event)
        except websockets.ConnectionClosed:
            await self._event_queue.put({"type": "error", "message": "Connection closed"})

    async def _handle_event(self, event: dict) -> None:
        """Обработать событие от Hume и преобразовать в наш формат."""
        event_type = event.get("type", "")

        if event_type == "audio_output":
            # Аудио ответ
            audio_data = base64.b64decode(event.get("data", ""))
            await self._event_queue.put({"type": "audio", "data": audio_data})

        elif event_type == "assistant_message":
            # Транскрипт ответа AI
            await self._event_queue.put({
                "type": "transcript",
                "role": "assistant",
                "text": event.get("message", {}).get("content", ""),
                "is_final": True,
                # Hume добавляет эмоции!
                "emotions": event.get("models", {}).get("prosody", {}).get("scores", {}),
            })

        elif event_type == "user_message":
            # Транскрипт речи пользователя
            await self._event_queue.put({
                "type": "transcript",
                "role": "user",
                "text": event.get("message", {}).get("content", ""),
                "is_final": True,
                "emotions": event.get("models", {}).get("prosody", {}).get("scores", {}),
            })

        elif event_type == "error":
            await self._event_queue.put({
                "type": "error",
                "message": event.get("message", "Unknown error"),
            })
