"""Transport adapters for the modular voice runtime."""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import WebSocket

from app.services.conversation_runtime.base import TransportAdapter


class WebSocketTransport(TransportAdapter):
    """FastAPI WebSocket adapter using the existing JSON protocol."""

    def __init__(self, websocket: WebSocket) -> None:
        self._websocket = websocket

    async def accept(self) -> None:
        await self._websocket.accept()

    async def receive(self) -> dict[str, Any]:
        payload = await self._websocket.receive_text()
        return json.loads(payload)

    async def send(self, event: dict[str, Any]) -> None:
        await self._websocket.send_json(event)

    async def close(self, code: Optional[int] = None, reason: Optional[str] = None) -> None:
        kwargs: dict[str, Any] = {}
        if code is not None:
            kwargs["code"] = code
        if reason is not None:
            kwargs["reason"] = reason
        await self._websocket.close(**kwargs)
