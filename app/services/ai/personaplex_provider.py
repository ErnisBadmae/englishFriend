"""PersonaPlex speech-to-speech provider.

Connects to a self-hosted PersonaPlex (NVIDIA Moshi 7B) instance over
WebSocket and provides full-duplex audio streaming with pedagogical
prompt injection.

Architecture:
    Client audio  ──►  EnglishFriend  ──►  PersonaPlex (ws://host:8998/api/chat)
    Client audio  ◄──  EnglishFriend  ◄──  PersonaPlex

PersonaPlex events (server → client):
    {"type": "transcript", "role": "user"|"assistant", "text": "...", "is_final": bool}
    {"type": "audio", "data": <base64-opus>}
    {"type": "status", "message": "..."}
    {"type": "error", "message": "..."}
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import AsyncIterator, Optional
from urllib.parse import urlencode

import websockets
from websockets.legacy.client import WebSocketClientProtocol

from app.core.config import settings
from app.services.ai.base import AIProvider, VoiceSession

logger = logging.getLogger(__name__)


class PersonaPlexConnectionError(Exception):
    """Raised when the PersonaPlex server is unreachable or drops the connection."""


class PersonaPlexProvider(AIProvider):
    """PersonaPlex speech-to-speech via WebSocket.

    Usage::

        plex = PersonaPlexProvider()
        await plex.connect(session)

        # Send raw audio from the student
        await plex.send_audio(opus_chunk)

        # Receive events (audio + transcripts)
        async for event in plex.receive():
            if event["type"] == "audio":
                ...  # Forward to client
            elif event["type"] == "transcript":
                ...  # Log / feed to LangGraph
    """

    def __init__(self, voice: Optional[str] = None) -> None:
        self._voice = voice or settings.personaplex_default_voice
        self._ws: Optional[WebSocketClientProtocol] = None
        self._session: Optional[VoiceSession] = None
        self._connected = False

    # ------------------------------------------------------------------
    # AIProvider interface
    # ------------------------------------------------------------------

    async def connect(self, session: VoiceSession) -> None:
        """Open a WebSocket connection to PersonaPlex.

        The pedagogical system prompt is passed as ``text_prompt`` query
        parameter so PersonaPlex conditions its generation on it.
        """
        self._session = session
        params = {
            "voice_prompt": f"{self._voice}.pt",
            "text_prompt": session.system_prompt,
            "seed": str(session.user_id),
        }
        url = f"{settings.personaplex_ws_url}?{urlencode(params)}"

        try:
            self._ws = await websockets.connect(
                url,
                open_timeout=settings.personaplex_timeout,
                ping_interval=20,
                ping_timeout=20,
                max_size=2**22,  # 4 MB max message
            )
            self._connected = True
            logger.info(
                f"[PersonaPlex] Connected session={session.session_id[:8]} "
                f"voice={self._voice} prompt_len={len(session.system_prompt)}"
            )
        except Exception as exc:
            logger.error(f"[PersonaPlex] Connection failed: {exc}")
            raise PersonaPlexConnectionError(str(exc)) from exc

    async def send_audio(self, audio_chunk: bytes) -> None:
        """Send an Opus-encoded audio chunk to PersonaPlex."""
        if not self._ws or not self._connected:
            raise PersonaPlexConnectionError("Not connected")
        try:
            await self._ws.send(audio_chunk)
        except websockets.ConnectionClosed as exc:
            self._connected = False
            raise PersonaPlexConnectionError(f"Connection closed: {exc}") from exc

    async def receive(self) -> AsyncIterator[dict]:
        """Yield events from PersonaPlex.

        Events follow the same schema as other ``AIProvider`` implementations:
            - ``{"type": "audio", "data": bytes}``
            - ``{"type": "transcript", "role": "user"|"assistant", "text": str, "is_final": bool}``
            - ``{"type": "error", "message": str}``
        """
        if not self._ws or not self._connected:
            raise PersonaPlexConnectionError("Not connected")

        try:
            async for raw in self._ws:
                if isinstance(raw, bytes):
                    # Binary frame = Opus audio from PersonaPlex
                    yield {"type": "audio", "data": raw}
                else:
                    # Text frame = JSON event
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.warning(f"[PersonaPlex] Non-JSON text frame: {raw[:100]}")
                        continue

                    event_type = event.get("type", "")
                    if event_type == "transcript":
                        yield {
                            "type": "transcript",
                            "role": event.get("role", "assistant"),
                            "text": event.get("text", ""),
                            "is_final": event.get("is_final", True),
                        }
                    elif event_type == "audio":
                        # Some versions send audio as base64 in JSON
                        import base64

                        yield {
                            "type": "audio",
                            "data": base64.b64decode(event["data"]),
                        }
                    elif event_type == "error":
                        yield {"type": "error", "message": event.get("message", "Unknown error")}
                    elif event_type == "status":
                        logger.debug(f"[PersonaPlex] Status: {event.get('message')}")
                    else:
                        logger.debug(f"[PersonaPlex] Unknown event type: {event_type}")
        except websockets.ConnectionClosed:
            self._connected = False
            logger.info("[PersonaPlex] Connection closed by server")

    async def update_persona(self, system_prompt: str) -> None:
        """Update the system prompt mid-session.

        PersonaPlex supports dynamic prompt updates via a JSON control message.
        """
        if not self._ws or not self._connected:
            logger.warning("[PersonaPlex] Cannot update persona: not connected")
            return
        try:
            control_msg = json.dumps({
                "type": "update_prompt",
                "text_prompt": system_prompt,
            })
            await self._ws.send(control_msg)
            logger.info(
                f"[PersonaPlex] Persona updated, prompt_len={len(system_prompt)}"
            )
        except websockets.ConnectionClosed as exc:
            self._connected = False
            logger.warning(f"[PersonaPlex] Update persona failed: {exc}")

    async def disconnect(self) -> None:
        """Close the WebSocket connection."""
        self._connected = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
            logger.info("[PersonaPlex] Disconnected")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected and self._ws is not None
