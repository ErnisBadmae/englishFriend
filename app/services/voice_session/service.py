"""Shared application-layer services for voice session lifecycle."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import initialize_session
from app.agent.graph_v2 import initialize_session_v2
from app.api.voice_helpers import (
    award_session_gamification,
    persist_goal_state_if_needed,
    persist_interview_run_if_needed,
    persist_session_evidence_if_needed,
)
from app.core.metrics import voice_errors_total
from app.schemas.user import UserCreate
from app.services.ai.memory_pipeline import MemoryPipeline, create_memory_pipeline
from app.services.ai.vocabulary_service import VocabularyService
from app.services.database import UserService
from app.services.learning_plan_service import LearningPlanService

logger = logging.getLogger(__name__)


@dataclass
class BootstrapContext:
    """Loaded user and learning context for a single voice session."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
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
class SessionPersistRequest:
    """Structured request for post-session persistence."""

    status: str
    user_id: int
    session_id: str
    final_mode: str
    existing_goal: Optional[str]
    agent_state: dict[str, Any]
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    turn_count: int = 0
    assessed_level: Optional[str] = None
    assessment_scores: Optional[dict[str, Any]] = None
    baseline_provisional: bool = False
    baseline_confidence: Optional[float] = None
    interview_track_id: Optional[str] = None
    corrections_made: list[dict[str, Any]] = field(default_factory=list)
    vocabulary_reviewed: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_agent_state(
        cls,
        *,
        status: str,
        user_id: int,
        session_id: str,
        final_mode: str,
        existing_goal: Optional[str],
        agent_state: dict[str, Any],
    ) -> "SessionPersistRequest":
        """Build a persistence request from the current agent state."""
        return cls(
            status=status,
            user_id=user_id,
            session_id=session_id,
            final_mode=final_mode,
            existing_goal=existing_goal,
            agent_state=agent_state,
            conversation_history=list(agent_state.get("conversation_history", []) or []),
            turn_count=int(agent_state.get("turn_count", 0) or 0),
            assessed_level=agent_state.get("assessed_level"),
            assessment_scores=agent_state.get("assessment_scores"),
            baseline_provisional=bool(agent_state.get("baseline_provisional")),
            baseline_confidence=agent_state.get("baseline_confidence"),
            interview_track_id=agent_state.get("interview_track_id"),
            corrections_made=list(agent_state.get("corrections_made", []) or []),
            vocabulary_reviewed=list(agent_state.get("vocabulary_reviewed", []) or []),
        )


@dataclass
class SessionCompletion:
    """Structured result for a persistence run."""

    status: str
    already_persisted: bool = False
    persisted_goal: Optional[str] = None
    interview_run: Optional[dict[str, Any]] = None
    session_evidence: Optional[dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class VoiceSessionDependencies:
    """Factories for external services used across voice lifecycles."""

    user_service_factory: Callable[[AsyncSession], UserService] = UserService
    learning_plan_service_factory: Callable[[AsyncSession], LearningPlanService] = LearningPlanService
    vocabulary_service_factory: Callable[[AsyncSession], VocabularyService] = VocabularyService
    memory_pipeline_factory: Callable[[AsyncSession], MemoryPipeline] = create_memory_pipeline


class SessionBootstrapService:
    """Load product context and initialize the bounded coach session."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        dependencies: Optional[VoiceSessionDependencies] = None,
    ) -> None:
        self._db = db
        self._deps = dependencies or VoiceSessionDependencies()
        self._user_service = self._deps.user_service_factory(db)
        self._learning_plan_service = self._deps.learning_plan_service_factory(db)
        self._vocabulary_service = self._deps.vocabulary_service_factory(db)
        self._memory_pipeline = self._deps.memory_pipeline_factory(db)

    @property
    def learning_plan_service(self) -> LearningPlanService:
        return self._learning_plan_service

    @property
    def memory_pipeline(self) -> MemoryPipeline:
        return self._memory_pipeline

    async def build(
        self,
        *,
        user_id: int,
        session_id: Optional[str] = None,
    ) -> BootstrapContext:
        """Build the shared user/session context used by voice runtimes."""
        context = BootstrapContext(session_id=session_id or str(uuid.uuid4()))

        try:
            user = await self._user_service.get_user(user_id)
            if not user:
                logger.info("[VoiceSession] User %s not found, auto-creating", user_id)
                user = await self._user_service.create_user(
                    UserCreate(
                        telegram_id=user_id,
                        username=f"User_{user_id}",
                        language_level="B1",
                    )
                )

            if user:
                context.username = user.username or "Student"
                context.language_level = user.language_level or "B1"
        except Exception as exc:
            logger.warning("[VoiceSession] Could not fetch/create user %s: %s", user_id, exc)
            voice_errors_total.labels(stage="db").inc()

        try:
            learning_plan = await self._learning_plan_service.get_or_create_plan(user_id)
            context.confirmed_goal = self._learning_plan_service.get_goal(learning_plan)
            context.roadmap = learning_plan.roadmap
            context.language_level = (
                self._learning_plan_service.get_current_level(learning_plan)
                or context.language_level
            )

            total_sessions = self._learning_plan_service.get_session_count(learning_plan)
            context.is_new_user = total_sessions == 0 and not context.confirmed_goal

            due_vocabulary = await self._vocabulary_service.get_due_cards(user_id, limit=10)
            context.due_vocabulary_count = len(due_vocabulary)
            context.due_vocabulary_words = [card.word for card in due_vocabulary]
            context.memory_section = await self._memory_pipeline.format_memory_for_prompt(user_id)
        except Exception as exc:
            logger.warning("[VoiceSession] Could not load learning context for %s: %s", user_id, exc)
            voice_errors_total.labels(stage="db").inc()

        return context

    async def initialize_agent_state(
        self,
        *,
        user_id: int,
        context: BootstrapContext,
        use_v2_agent: bool,
        explicit_mode: Optional[str] = None,
        interview_track_id: Optional[str] = None,
        mission_task_type: Optional[str] = None,
        mission_title: Optional[str] = None,
        mission_reason: Optional[str] = None,
        mission_success_signal: Optional[str] = None,
        mission_linked_goal_context: Optional[str] = None,
    ) -> dict[str, Any]:
        """Initialize the agent state from the shared bootstrap context."""
        if use_v2_agent:
            return await initialize_session_v2(
                user_id=user_id,
                session_id=context.session_id,
                username=context.username,
                is_new_user=context.is_new_user,
                language_level=context.language_level,
                confirmed_goal=context.confirmed_goal,
                confirmed_interests=context.confirmed_interests,
                roadmap=context.roadmap,
                due_vocabulary_count=context.due_vocabulary_count,
                due_vocabulary_words=context.due_vocabulary_words,
                memory_section=context.memory_section,
                explicit_mode=explicit_mode,
                interview_track_id=interview_track_id,
                mission_task_type=mission_task_type,
                mission_title=mission_title,
                mission_reason=mission_reason,
                mission_success_signal=mission_success_signal,
                mission_linked_goal_context=mission_linked_goal_context,
            )

        return await initialize_session(
            user_id=user_id,
            session_id=context.session_id,
            username=context.username,
            is_new_user=context.is_new_user,
            language_level=context.language_level,
            confirmed_goal=context.confirmed_goal,
            confirmed_interests=context.confirmed_interests,
            roadmap=context.roadmap,
            due_vocabulary_count=context.due_vocabulary_count,
            due_vocabulary_words=context.due_vocabulary_words,
            memory_section=context.memory_section,
        )


class SessionPersistenceService:
    """Persist session side effects once per session lifecycle."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        dependencies: Optional[VoiceSessionDependencies] = None,
        learning_plan_service: Optional[LearningPlanService] = None,
        memory_pipeline: Optional[MemoryPipeline] = None,
    ) -> None:
        self._db = db
        self._deps = dependencies or VoiceSessionDependencies()
        self._learning_plan_service = (
            learning_plan_service or self._deps.learning_plan_service_factory(db)
        )
        self._memory_pipeline = memory_pipeline or self._deps.memory_pipeline_factory(db)
        self._persistence_done = False

    async def persist(self, request: SessionPersistRequest) -> SessionCompletion:
        """Run the shared post-session pipeline once."""
        if self._persistence_done:
            return SessionCompletion(status=request.status, already_persisted=True)

        try:
            persisted_goal = await persist_goal_state_if_needed(
                user_id=request.user_id,
                existing_goal=request.existing_goal,
                agent_state=request.agent_state,
                learning_plan_service=self._learning_plan_service,
            )

            if request.assessed_level:
                await self._learning_plan_service.record_assessment(
                    request.user_id,
                    assessed_level=request.assessed_level,
                    scores=request.assessment_scores,
                    provisional=request.baseline_provisional,
                    confidence_override=request.baseline_confidence,
                )

            await self._learning_plan_service.increment_session_count(
                request.user_id,
                mode=request.final_mode,
                duration_minutes=request.turn_count * 2,
            )

            if request.conversation_history:
                await self._memory_pipeline.process_conversation(
                    user_id=request.user_id,
                    messages=request.conversation_history,
                    session_id=request.session_id,
                )

            if request.turn_count > 0:
                await award_session_gamification(
                    self._db,
                    request.user_id,
                    request.session_id,
                )

            interview_run = await persist_interview_run_if_needed(
                db=self._db,
                user_id=request.user_id,
                session_id=request.session_id,
                current_mode=request.final_mode,
                interview_track_id=request.interview_track_id,
                conversation_history=request.conversation_history,
                corrections_made=len(request.corrections_made),
                vocabulary_reviewed=request.vocabulary_reviewed,
            )
            session_evidence = await persist_session_evidence_if_needed(
                db=self._db,
                user_id=request.user_id,
                session_id=request.session_id,
                current_mode=request.final_mode,
                conversation_history=request.conversation_history,
                corrections_made=request.corrections_made,
                vocabulary_reviewed=request.vocabulary_reviewed,
                duration_minutes=request.turn_count * 2,
                assessed_level=request.assessed_level,
                assessment_scores=request.assessment_scores or {},
                interview_run=interview_run,
            )
        except Exception as exc:
            logger.warning("[VoiceSession] Persist failed (%s): %s", request.status, exc)
            return SessionCompletion(status=request.status, error=str(exc))

        self._persistence_done = True
        return SessionCompletion(
            status=request.status,
            persisted_goal=persisted_goal,
            interview_run=interview_run,
            session_evidence=session_evidence,
        )
