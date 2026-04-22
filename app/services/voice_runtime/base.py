"""Core models and interfaces for the modular voice runtime."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal, Optional


VoiceStatus = Literal["completed", "disconnected", "error"]
TurnDisposition = Literal["commit", "end", "ignore"]
STTEventType = Literal["partial", "final", "error"]


@dataclass
class STTEvent:
    """Normalized speech-to-text event."""

    type: STTEventType
    text: str = ""
    confidence: Optional[float] = None
    language: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnDetection:
    """Decision returned by a turn detector."""

    disposition: TurnDisposition
    text: str = ""
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VoiceControllerOutcome:
    """Batch of outbound events plus loop control flags."""

    events: list[dict[str, Any]] = field(default_factory=list)
    should_close: bool = False
    status: Optional[VoiceStatus] = None


@dataclass
class VoiceRuntimeResult:
    """Final result returned by a runtime session."""

    status: VoiceStatus
    final_mode: str


class TransportAdapter(ABC):
    """Boundary between the runtime controller and the external transport."""

    @abstractmethod
    async def accept(self) -> None:
        """Accept the underlying connection."""

    @abstractmethod
    async def receive(self) -> dict[str, Any]:
        """Receive the next client event."""

    @abstractmethod
    async def send(self, event: dict[str, Any]) -> None:
        """Send a normalized outbound event."""

    @abstractmethod
    async def close(self, code: Optional[int] = None, reason: Optional[str] = None) -> None:
        """Close the underlying connection."""


class STTProvider(ABC):
    """Speech-to-text provider boundary for the modular runtime."""

    async def transcribe_text(
        self,
        text: str,
        *,
        user_id: int,
        session_id: str,
    ) -> STTEvent:
        """Normalize already-transcribed text from the client."""
        return STTEvent(type="final", text=text)

    async def transcribe_stream(
        self,
        audio_chunks: AsyncIterator[bytes],
        *,
        user_id: int,
        session_id: str,
    ) -> AsyncIterator[STTEvent]:
        """Streaming audio transcription for future realtime providers."""
        raise NotImplementedError("Streaming STT is not implemented for this provider")

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        *,
        content_type: Optional[str],
        user_id: int,
        session_id: str,
    ) -> STTEvent:
        """Batch audio transcription for backend STT providers."""
        raise NotImplementedError("Batch audio transcription is not implemented for this provider")


class TurnDetector(ABC):
    """Turn detection boundary for explicit or semantic commit logic."""

    @abstractmethod
    def detect(self, message: dict[str, Any]) -> TurnDetection:
        """Classify an inbound transport event."""


class TTSProvider(ABC):
    """Text-to-speech boundary for the modular runtime."""

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Synthesize an audio response for the assistant text."""
