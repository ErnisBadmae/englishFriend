"""Modular controller for the experimental realtime voice runtime."""

from __future__ import annotations

import base64
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from fastapi import WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import AgentPhase, LearningModeEnum, run_agent_turn
from app.agent.graph import initialize_session
from app.agent.graph_v2 import USE_AGENT_V2, initialize_session_v2, run_agent_turn_v2
from app.api.voice_helpers import (
    award_session_gamification,
    persist_goal_state_if_needed,
    persist_interview_run_if_needed,
    persist_session_evidence_if_needed,
)
from app.core.metrics import (
    agent_version_onboarding_complete,
    agent_version_sessions,
    voice_errors_total,
    voice_messages_total,
    voice_tts_latency_seconds,
    voice_turn_total_seconds,
)
from app.schemas.user import UserCreate
from app.services.ai.memory_pipeline import MemoryPipeline, create_memory_pipeline
from app.services.ai.vocabulary_service import VocabularyService
from app.services.database import UserService
from app.services.learning_plan_service import LearningPlanService
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


@dataclass
class RuntimeSessionContext:
    """Loaded context for the modular runtime session."""

    session_id: str
    username: str = "Student"
    language_level: str = "B1"
    is_new_user: bool = True
    confirmed_goal: Optional[str] = None
    confirmed_interests: Optional[list[str]] = None
    roadmap: Optional[dict[str, Any]] = None
    due_vocabulary_count: int = 0
    due_vocabulary_words: list[str] = field(default_factory=list)
    memory_section: str = ""


@dataclass
class VoiceRuntimeDependencies:
    """Factories for external services used by the runtime."""

    user_service_factory: Callable[[AsyncSession], UserService] = UserService
    learning_plan_service_factory: Callable[[AsyncSession], LearningPlanService] = LearningPlanService
    vocabulary_service_factory: Callable[[AsyncSession], VocabularyService] = VocabularyService
    memory_pipeline_factory: Callable[[AsyncSession], MemoryPipeline] = create_memory_pipeline


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

        self._learning_plan_service = self._deps.learning_plan_service_factory(db)
        self._vocabulary_service = self._deps.vocabulary_service_factory(db)
        self._memory_pipeline = self._deps.memory_pipeline_factory(db)

        self._context = RuntimeSessionContext(session_id=str(uuid.uuid4()))
        self._agent_state: dict[str, Any] = {}
        self._agent_version = "v2" if self._use_v2_agent else "v1"
        self._final_mode = "unknown"

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
        await self._load_session_context()
        agent_version_sessions.labels(version=self._agent_version).inc()

        self._agent_state = await self._initialize_agent_state()
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

        if self._agent_state.get("should_end_session"):
            complete_outcome = await self._persist_session(status="completed")
            events.extend(complete_outcome.events)
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

        persist_outcome = await self._persist_session(status="completed")
        events.extend(persist_outcome.events)
        return VoiceControllerOutcome(events=events, should_close=True, status="completed")

    async def _load_session_context(self) -> None:
        """Populate user, learning, vocabulary, and memory context."""
        user_service = self._deps.user_service_factory(self._db)

        try:
            user = await user_service.get_user(self._user_id)
            if not user:
                logger.info("[VoiceRuntime] User %s not found, auto-creating", self._user_id)
                user = await user_service.create_user(
                    UserCreate(
                        telegram_id=self._user_id,
                        username=f"User_{self._user_id}",
                        language_level="B1",
                    )
                )

            if user:
                self._context.username = user.username or "Student"
                self._context.language_level = user.language_level or "B1"
        except Exception as exc:
            logger.warning("[VoiceRuntime] Could not fetch/create user: %s", exc)
            voice_errors_total.labels(stage="db").inc()

        try:
            learning_plan = await self._learning_plan_service.get_or_create_plan(self._user_id)
            self._context.confirmed_goal = self._learning_plan_service.get_goal(learning_plan)
            self._context.roadmap = learning_plan.roadmap
            self._context.language_level = (
                self._learning_plan_service.get_current_level(learning_plan)
                or self._context.language_level
            )

            total_sessions = self._learning_plan_service.get_session_count(learning_plan)
            self._context.is_new_user = total_sessions == 0 and not self._context.confirmed_goal

            due_vocabulary = await self._vocabulary_service.get_due_cards(self._user_id, limit=10)
            self._context.due_vocabulary_count = len(due_vocabulary)
            self._context.due_vocabulary_words = [card.word for card in due_vocabulary]
            self._context.memory_section = await self._memory_pipeline.format_memory_for_prompt(
                self._user_id
            )
        except Exception as exc:
            logger.warning("[VoiceRuntime] Could not load learning context: %s", exc)
            voice_errors_total.labels(stage="db").inc()

    async def _initialize_agent_state(self) -> dict[str, Any]:
        if self._use_v2_agent:
            return await initialize_session_v2(
                user_id=self._user_id,
                session_id=self._context.session_id,
                username=self._context.username,
                is_new_user=self._context.is_new_user,
                language_level=self._context.language_level,
                confirmed_goal=self._context.confirmed_goal,
                confirmed_interests=self._context.confirmed_interests,
                roadmap=self._context.roadmap,
                due_vocabulary_count=self._context.due_vocabulary_count,
                due_vocabulary_words=self._context.due_vocabulary_words,
                memory_section=self._context.memory_section,
                explicit_mode=self._mode,
                interview_track_id=self._interview_track,
                mission_task_type=self._mission_task_type,
                mission_title=self._mission_title,
                mission_reason=self._mission_reason,
                mission_success_signal=self._mission_success_signal,
                mission_linked_goal_context=self._mission_linked_goal_context,
            )

        return await initialize_session(
            user_id=self._user_id,
            session_id=self._context.session_id,
            username=self._context.username,
            is_new_user=self._context.is_new_user,
            language_level=self._context.language_level,
            confirmed_goal=self._context.confirmed_goal,
            confirmed_interests=self._context.confirmed_interests,
            roadmap=self._context.roadmap,
            due_vocabulary_count=self._context.due_vocabulary_count,
            due_vocabulary_words=self._context.due_vocabulary_words,
            memory_section=self._context.memory_section,
        )

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
        """Persist the session state using the same business services as `/chat/v2`."""
        try:
            await persist_goal_state_if_needed(
                user_id=self._user_id,
                existing_goal=self._context.confirmed_goal,
                agent_state=self._agent_state,
                learning_plan_service=self._learning_plan_service,
            )

            if self._agent_state.get("assessed_level"):
                await self._learning_plan_service.record_assessment(
                    self._user_id,
                    assessed_level=self._agent_state["assessed_level"],
                    scores=self._agent_state.get("assessment_scores"),
                    provisional=bool(self._agent_state.get("baseline_provisional")),
                    confidence_override=self._agent_state.get("baseline_confidence"),
                )

            await self._learning_plan_service.increment_session_count(
                self._user_id,
                mode=self._final_mode,
                duration_minutes=int(self._agent_state.get("turn_count", 0) or 0) * 2,
            )

            conversation_history = self._agent_state.get("conversation_history", [])
            if conversation_history:
                await self._memory_pipeline.process_conversation(
                    user_id=self._user_id,
                    messages=conversation_history,
                    session_id=self._context.session_id,
                )

            if int(self._agent_state.get("turn_count", 0) or 0) > 0:
                await award_session_gamification(
                    self._db,
                    self._user_id,
                    self._context.session_id,
                )

            interview_run = await persist_interview_run_if_needed(
                db=self._db,
                user_id=self._user_id,
                session_id=self._context.session_id,
                current_mode=self._final_mode,
                interview_track_id=self._agent_state.get("interview_track_id"),
                conversation_history=conversation_history,
                corrections_made=len(self._agent_state.get("corrections_made", [])),
                vocabulary_reviewed=self._agent_state.get("vocabulary_reviewed", []),
            )
            await persist_session_evidence_if_needed(
                db=self._db,
                user_id=self._user_id,
                session_id=self._context.session_id,
                current_mode=self._final_mode,
                conversation_history=conversation_history,
                corrections_made=self._agent_state.get("corrections_made", []),
                vocabulary_reviewed=self._agent_state.get("vocabulary_reviewed", []),
                duration_minutes=int(self._agent_state.get("turn_count", 0) or 0) * 2,
                assessed_level=self._agent_state.get("assessed_level"),
                assessment_scores=self._agent_state.get("assessment_scores", {}),
                interview_run=interview_run,
            )
        except Exception as exc:
            logger.warning("[VoiceRuntime] Persist failed (%s): %s", status, exc)

        return VoiceControllerOutcome(status=status)

    async def _send_events(self, events: list[dict[str, Any]]) -> None:
        for event in events:
            await self._transport.send(event)
