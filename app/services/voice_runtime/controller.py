"""Modular controller for the experimental realtime voice runtime."""

from __future__ import annotations

import base64
import logging
import time
from typing import Any, Optional

from fastapi import WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import AgentPhase, LearningModeEnum, run_agent_turn
from app.agent.graph_v2 import USE_AGENT_V2, run_agent_turn_v2
from app.core.metrics import (
    agent_version_onboarding_complete,
    agent_version_sessions,
    voice_errors_total,
    voice_messages_total,
    voice_tts_latency_seconds,
    voice_turn_total_seconds,
)
from app.services.voice_session import (
    BootstrapContext,
    SessionBootstrapService,
    SessionPersistRequest,
    SessionPersistenceService,
    VoiceSessionDependencies,
)
from app.services.voice_runtime.base import (
    STTProvider,
    TTSProvider,
    TransportAdapter,
    TurnDetector,
    VoiceControllerOutcome,
    VoiceRuntimeResult,
)

logger = logging.getLogger(__name__)


def _enum_value(value: Any, default: str) -> str:
    """Convert Enum-like values to strings without assuming a specific type."""
    if value is None:
        return default
    return getattr(value, "value", str(value))


VoiceRuntimeDependencies = VoiceSessionDependencies


class VoiceSessionController:
    """Feature-flagged modular voice runtime.

    The controller keeps transport, STT/TTS, turn detection, and product-state
    orchestration separate so the endpoint stays thin and future providers can
    be swapped in without rewriting the session loop.
    """

    def __init__(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        mode: Optional[str],
        interview_track: Optional[str],
        mission_task_type: Optional[str] = None,
        mission_title: Optional[str] = None,
        mission_reason: Optional[str] = None,
        mission_success_signal: Optional[str] = None,
        mission_linked_goal_context: Optional[str] = None,
        transport: TransportAdapter,
        stt_provider: STTProvider,
        tts_provider: TTSProvider,
        turn_detector: TurnDetector,
        dependencies: Optional[VoiceRuntimeDependencies] = None,
        use_v2_agent: Optional[bool] = None,
    ) -> None:
        self._db = db
        self._user_id = user_id
        self._mode = mode
        self._interview_track = interview_track
        self._mission_task_type = mission_task_type
        self._mission_title = mission_title
        self._mission_reason = mission_reason
        self._mission_success_signal = mission_success_signal
        self._mission_linked_goal_context = mission_linked_goal_context
        self._transport = transport
        self._stt_provider = stt_provider
        self._tts_provider = tts_provider
        self._turn_detector = turn_detector
        self._deps = dependencies or VoiceRuntimeDependencies()
        self._use_v2_agent = USE_AGENT_V2 if use_v2_agent is None else use_v2_agent

        self._bootstrap_service = SessionBootstrapService(db, dependencies=self._deps)
        self._persistence_service = SessionPersistenceService(
            db,
            dependencies=self._deps,
            learning_plan_service=self._bootstrap_service.learning_plan_service,
            memory_pipeline=self._bootstrap_service.memory_pipeline,
        )

        self._context = BootstrapContext()
        self._agent_state: dict[str, Any] = {}
        self._agent_version = "v2" if self._use_v2_agent else "v1"
        self._final_mode = "unknown"
        self._completion_signal_sent = False

    async def run(self) -> VoiceRuntimeResult:
        """Run the modular runtime until the session closes."""
        await self._transport.accept()

        try:
            start_outcome = await self.initialize()
            await self._send_events(start_outcome.events)

            while True:
                try:
                    message = await self._transport.receive()
                except WebSocketDisconnect:
                    disconnect_outcome = await self.handle_disconnect()
                    return VoiceRuntimeResult(
                        status=disconnect_outcome.status or "disconnected",
                        final_mode=self._final_mode,
                    )

                outcome = await self.handle_message(message)
                await self._send_events(outcome.events)
                if outcome.should_close:
                    return VoiceRuntimeResult(
                        status=outcome.status or "completed",
                        final_mode=self._final_mode,
                    )
        except WebSocketDisconnect:
            disconnect_outcome = await self.handle_disconnect()
            return VoiceRuntimeResult(
                status=disconnect_outcome.status or "disconnected",
                final_mode=self._final_mode,
            )

    async def initialize(self) -> VoiceControllerOutcome:
        """Load user/product context and emit the initial greeting."""
        self._context = await self._bootstrap_service.build(
            user_id=self._user_id,
            session_id=self._context.session_id,
        )
        agent_version_sessions.labels(version=self._agent_version).inc()

        self._agent_state = await self._bootstrap_service.initialize_agent_state(
            user_id=self._user_id,
            context=self._context,
            use_v2_agent=self._use_v2_agent,
            explicit_mode=self._mode,
            interview_track_id=self._interview_track,
            mission_task_type=self._mission_task_type,
            mission_title=self._mission_title,
            mission_reason=self._mission_reason,
            mission_success_signal=self._mission_success_signal,
            mission_linked_goal_context=self._mission_linked_goal_context,
        )
        self._agent_state = await self._run_agent_turn(user_message=None)

        current_phase = _enum_value(
            self._agent_state.get("current_phase", AgentPhase.START),
            AgentPhase.START.value,
        )
        current_mode = _enum_value(
            self._agent_state.get("current_mode", LearningModeEnum.FREE_CONVERSATION),
            LearningModeEnum.FREE_CONVERSATION.value,
        )
        self._final_mode = current_mode

        events = [
            {
                "type": "connected",
                "session_id": self._context.session_id,
                "phase": current_phase,
                "mode": current_mode,
                "is_new_user": self._context.is_new_user,
                "goal": self._context.confirmed_goal,
                "due_vocabulary_count": self._context.due_vocabulary_count,
                "runtime": "modular",
            }
        ]

        initial_response = self._agent_state.get("pending_response", "")
        if initial_response:
            events.extend(
                await self._build_assistant_events(
                    initial_response,
                    phase=current_phase,
                    mode=current_mode,
                    turn=None,
                )
            )

        return VoiceControllerOutcome(events=events)

    async def handle_message(self, message: dict[str, Any]) -> VoiceControllerOutcome:
        """Handle a single normalized client message."""
        decision = self._turn_detector.detect(message)

        if decision.disposition == "ignore":
            if decision.reason == "unsupported_message":
                return VoiceControllerOutcome(
                    events=[
                        {
                            "type": "error",
                            "message": "Unsupported realtime message type.",
                        }
                    ]
                )
            return VoiceControllerOutcome()

        if decision.disposition == "end":
            return await self._complete_session()

        stt_event = await self._stt_provider.transcribe_text(
            decision.text,
            user_id=self._user_id,
            session_id=self._context.session_id,
        )
        if stt_event.type == "error":
            voice_errors_total.labels(stage="stt").inc()
            return VoiceControllerOutcome(
                events=[{"type": "error", "message": stt_event.text or "STT failed."}]
            )

        user_text = stt_event.text.strip()
        if not user_text:
            return VoiceControllerOutcome()

        if self._agent_state.get("session_complete_reason"):
            events = self._build_session_complete_events()
            events.append(
                {
                    "type": "error",
                    "message": "This setup session is already complete. End it and start your first mission from the dashboard.",
                }
            )
            return VoiceControllerOutcome(events=events)

        turn_start = time.time()
        voice_messages_total.labels(direction="inbound", type="text").inc()

        events = [{"type": "transcript", "role": "user", "text": user_text}]

        old_phase = _enum_value(
            self._agent_state.get("current_phase", AgentPhase.START),
            AgentPhase.START.value,
        )

        self._agent_state = await self._run_agent_turn(user_message=user_text)

        current_phase = _enum_value(
            self._agent_state.get("current_phase", AgentPhase.START),
            AgentPhase.START.value,
        )
        current_mode = _enum_value(
            self._agent_state.get("current_mode", LearningModeEnum.FREE_CONVERSATION),
            LearningModeEnum.FREE_CONVERSATION.value,
        )
        turn_count = int(self._agent_state.get("turn_count", 0) or 0)
        self._final_mode = current_mode

        if old_phase != current_phase:
            events.append(
                {
                    "type": "phase_changed",
                    "phase": current_phase,
                    "mode": current_mode,
                }
            )

            if current_phase == AgentPhase.LEARNING_SESSION.value:
                agent_version_onboarding_complete.labels(version=self._agent_version).inc()

        response_text = self._agent_state.get("pending_response", "")
        if response_text:
            assistant_events = await self._build_assistant_events(
                response_text,
                phase=current_phase,
                mode=current_mode,
                turn=turn_count,
            )
            events.extend(assistant_events)
            voice_turn_total_seconds.labels(mode=current_mode).observe(time.time() - turn_start)

        events.extend(self._build_session_complete_events())

        if self._agent_state.get("should_end_session"):
            await self._persist_session(status="completed")
            return VoiceControllerOutcome(
                events=events,
                should_close=True,
                status="completed",
            )

        return VoiceControllerOutcome(events=events)

    async def handle_disconnect(self) -> VoiceControllerOutcome:
        """Persist best-effort state on disconnect."""
        await self._persist_session(status="disconnected")
        return VoiceControllerOutcome(should_close=True, status="disconnected")

    async def _complete_session(self) -> VoiceControllerOutcome:
        """Explicitly end the session via the agent session_end path."""
        self._agent_state["should_end_session"] = True
        self._agent_state = await self._run_agent_turn(user_message=None)

        events: list[dict[str, Any]] = []
        farewell = self._agent_state.get("pending_response", "")
        if farewell:
            events.extend(
                await self._build_assistant_events(
                    farewell,
                    phase="session_end",
                    mode=self._final_mode,
                    turn=None,
                )
            )

        events.extend(self._build_session_complete_events())
        await self._persist_session(status="completed")
        return VoiceControllerOutcome(events=events, should_close=True, status="completed")

    async def _run_agent_turn(self, user_message: Optional[str]) -> dict[str, Any]:
        if self._use_v2_agent:
            return await run_agent_turn_v2(self._agent_state, user_message=user_message)
        return await run_agent_turn(self._agent_state, user_message=user_message)

    async def _build_assistant_events(
        self,
        text: str,
        *,
        phase: str,
        mode: str,
        turn: Optional[int],
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = [
            {
                "type": "transcript",
                "role": "assistant",
                "text": text,
                "phase": phase,
                "mode": mode,
            }
        ]
        if turn is not None:
            events[0]["turn"] = turn

        try:
            tts_start = time.time()
            audio_bytes = await self._tts_provider.synthesize(text)
            voice_tts_latency_seconds.observe(time.time() - tts_start)

            events.append(
                {
                    "type": "audio",
                    "data": base64.b64encode(audio_bytes).decode(),
                    "format": "mp3",
                }
            )
            voice_messages_total.labels(direction="outbound", type="audio").inc()
        except Exception as exc:
            logger.warning("[VoiceRuntime] TTS error: %s", exc)
            voice_errors_total.labels(stage="tts").inc()

        return events

    async def _persist_session(self, *, status: str) -> VoiceControllerOutcome:
        """Persist the session state using the shared lifecycle service."""
        request = SessionPersistRequest.from_agent_state(
            status=status,
            user_id=self._user_id,
            session_id=self._context.session_id,
            final_mode=self._final_mode,
            existing_goal=self._context.confirmed_goal,
            agent_state=self._agent_state,
        )
        completion = await self._persistence_service.persist(request)
        if completion.error:
            logger.warning("[VoiceRuntime] Persist failed (%s): %s", status, completion.error)
        return VoiceControllerOutcome(status=completion.status)

    def _build_session_complete_events(self) -> list[dict[str, Any]]:
        if self._completion_signal_sent or not self._agent_state.get("session_complete_reason"):
            return []

        self._completion_signal_sent = True
        return [
            {
                "type": "session_complete",
                "reason": self._agent_state.get("session_complete_reason"),
                "return_screen": self._agent_state.get("session_complete_return_screen") or "home",
            }
        ]

    async def _send_events(self, events: list[dict[str, Any]]) -> None:
        for event in events:
            await self._transport.send(event)
