"""Shared application-layer services for voice session lifecycle."""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph_v2 import initialize_session_v2
from app.api.voice_helpers import (
    award_session_gamification,
    persist_goal_state_if_needed,
    persist_interview_run_if_needed,
    persist_session_evidence_if_needed,
)
from app.core.metrics import voice_errors_total
from app.schemas.user import UserCreate
from app.services.ai.learner_profile_service import (
    LearnerProfileService,
    create_learner_profile_service,
)
from app.services.ai.memory_contracts import LearnerProfileSummary, MissionMemoryContext
from app.services.ai.memory_pipeline import MemoryPipeline, create_memory_pipeline
from app.services.ai.vocabulary_service import VocabularyService
from app.services.database import UserService
from app.services.learning_plan_service import LearningPlanService
from app.services.voice_observability import (
    VoiceSessionScope,
    log_voice_event,
    make_turn_envelope,
    observe_voice_stage,
    record_voice_persistence,
)

logger = logging.getLogger(__name__)

_EMBEDDED_BASELINE_MISSION_TYPES = {
    "technical_project_walkthrough",
    "project_walkthrough_drill",
    "stakeholder_explanation_drill",
    "foundation_speaking_drill",
}
_EMBEDDED_BASELINE_TECH_PATTERNS = (
    "model",
    "models",
    "dataset",
    "pipeline",
    "metric",
    "metrics",
    "stakeholder",
    "project",
    "deployment",
    "latency",
    "feature",
    "trade-off",
    "tradeoff",
)


@dataclass
class BootstrapContext:
    """Loaded user and learning context for a single voice session."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[int] = None
    telegram_id: Optional[int] = None
    username: str = "Student"
    language_level: str = "B1"
    is_new_user: bool = True
    confirmed_goal: Optional[str] = None
    confirmed_interests: Optional[list[str]] = None
    roadmap: Optional[dict[str, Any]] = None
    due_vocabulary_count: int = 0
    due_vocabulary_words: list[str] = field(default_factory=list)
    memory_section: str = ""
    learner_profile_summary: Optional[LearnerProfileSummary] = None
    mission_memory_context: Optional[MissionMemoryContext] = None


@dataclass
class SessionPersistRequest:
    """Structured request for post-session persistence."""

    status: str
    user_id: int
    session_id: str
    final_mode: str
    existing_goal: Optional[str]
    agent_state: dict[str, Any]
    runtime: str = "unknown"
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    turn_count: int = 0
    assessed_level: Optional[str] = None
    assessment_scores: Optional[dict[str, Any]] = None
    baseline_provisional: bool = False
    baseline_confidence: Optional[float] = None
    assessment_source: Optional[str] = None
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
        runtime: str,
        existing_goal: Optional[str],
        agent_state: dict[str, Any],
        ) -> "SessionPersistRequest":
        """Build a persistence request from the current agent state."""
        assessment_source = agent_state.get("assessment_source")
        return cls(
            status=status,
            user_id=user_id,
            session_id=session_id,
            final_mode=final_mode,
            runtime=runtime,
            existing_goal=existing_goal,
            agent_state=agent_state,
            conversation_history=list(agent_state.get("conversation_history", []) or []),
            turn_count=int(agent_state.get("turn_count", 0) or 0),
            assessed_level=agent_state.get("assessed_level") if assessment_source else None,
            assessment_scores=agent_state.get("assessment_scores") if assessment_source else None,
            baseline_provisional=bool(agent_state.get("baseline_provisional")) if assessment_source else False,
            baseline_confidence=agent_state.get("baseline_confidence") if assessment_source else None,
            assessment_source=assessment_source,
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
    learner_profile_service_factory: Callable[
        [AsyncSession, LearningPlanService, MemoryPipeline],
        LearnerProfileService,
    ] = create_learner_profile_service


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
        self._learner_profile_service = self._deps.learner_profile_service_factory(
            db,
            self._learning_plan_service,
            self._memory_pipeline,
        )

    @property
    def learning_plan_service(self) -> LearningPlanService:
        return self._learning_plan_service

    @property
    def memory_pipeline(self) -> MemoryPipeline:
        return self._memory_pipeline

    async def _rollback_if_needed(self) -> None:
        rollback = getattr(self._db, "rollback", None)
        if rollback is None:
            return
        try:
            await rollback()
        except Exception as exc:  # pragma: no cover - defensive rollback guard
            logger.warning("[VoiceSession] Rollback failed: %s", exc)

    async def _resolve_user_record(self, requested_user_id: int) -> Any | None:
        user = await self._user_service.get_user(requested_user_id)
        if user:
            return user

        user = await self._user_service.get_user_by_telegram_id(requested_user_id)
        if user:
            return user

        logger.info("[VoiceSession] User %s not found, auto-creating by telegram_id", requested_user_id)
        return await self._user_service.create_user(
            UserCreate(
                telegram_id=requested_user_id,
                username=f"User_{requested_user_id}",
                language_level="B1",
            )
        )

    async def build(
        self,
        *,
        user_id: int,
        session_id: Optional[str] = None,
        runtime: str = "unknown",
        stt_provider: Optional[str] = None,
    ) -> BootstrapContext:
        """Build the shared user/session context used by voice runtimes."""
        context = BootstrapContext(session_id=session_id or str(uuid.uuid4()))
        scope = VoiceSessionScope(
            runtime=runtime,
            session_id=context.session_id,
            user_id=user_id,
            stt_provider=stt_provider,
        )
        build_start = time.perf_counter()
        log_voice_event(
            logger,
            envelope=make_turn_envelope(scope),
            layer="bootstrap",
            event="session_bootstrap_started",
        )

        try:
            user = await self._resolve_user_record(user_id)

            if user:
                context.user_id = int(getattr(user, "id", user_id) or user_id)
                context.telegram_id = int(getattr(user, "telegram_id", user_id) or user_id)
                context.username = user.username or "Student"
                context.language_level = user.language_level or "B1"
        except Exception as exc:
            logger.warning("[VoiceSession] Could not fetch/create user %s: %s", user_id, exc)
            voice_errors_total.labels(stage="db").inc()
            await self._rollback_if_needed()

        resolved_user_id = int(context.user_id or user_id)
        if context.user_id is None:
            context.user_id = resolved_user_id
        if context.telegram_id is None:
            context.telegram_id = user_id

        try:
            learning_plan = await self._learning_plan_service.get_or_create_plan(resolved_user_id)
            context.confirmed_goal = self._learning_plan_service.get_goal(learning_plan)
            context.roadmap = learning_plan.roadmap
            context.language_level = (
                self._learning_plan_service.get_current_level(learning_plan)
                or context.language_level
            )

            total_sessions = self._learning_plan_service.get_session_count(learning_plan)
            context.is_new_user = total_sessions == 0 and not context.confirmed_goal

            due_vocabulary = await self._vocabulary_service.get_due_cards(resolved_user_id, limit=10)
            context.due_vocabulary_count = len(due_vocabulary)
            context.due_vocabulary_words = [card.word for card in due_vocabulary]
            context.learner_profile_summary = await self._learner_profile_service.build_summary(
                user_id=resolved_user_id,
                plan=learning_plan,
            )
            context.mission_memory_context = await self._learner_profile_service.build_mission_context(
                user_id=resolved_user_id,
                profile_summary=context.learner_profile_summary,
                plan=learning_plan,
            )
            context.memory_section = context.mission_memory_context.to_prompt_section()
        except Exception as exc:
            logger.warning("[VoiceSession] Could not load learning context for %s: %s", resolved_user_id, exc)
            voice_errors_total.labels(stage="db").inc()
            await self._rollback_if_needed()

        observe_voice_stage(
            runtime=runtime,
            stage="bootstrap",
            duration_seconds=time.perf_counter() - build_start,
        )
        log_voice_event(
            logger,
            envelope=make_turn_envelope(scope),
            layer="bootstrap",
            event="session_bootstrap_ready",
            is_new_user=context.is_new_user,
            goal_present=bool(context.confirmed_goal),
            due_vocabulary_count=context.due_vocabulary_count,
            learner_profile_present=bool(context.learner_profile_summary),
        )

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
        runtime: str = "unknown",
        stt_provider: Optional[str] = None,
    ) -> dict[str, Any]:
        """Initialize the agent state from the shared bootstrap context."""
        resolved_user_id = int(context.user_id or user_id)
        context.user_id = resolved_user_id
        context.mission_memory_context = await self._learner_profile_service.build_mission_context(
            user_id=resolved_user_id,
            mission_task_type=mission_task_type,
            mission_title=mission_title,
            mission_reason=mission_reason,
            mission_success_signal=mission_success_signal,
            mission_linked_goal_context=mission_linked_goal_context,
            profile_summary=context.learner_profile_summary,
        )
        context.memory_section = context.mission_memory_context.to_prompt_section()
        scope = VoiceSessionScope(
            runtime=runtime,
            session_id=context.session_id,
            user_id=resolved_user_id,
            mission_task_type=mission_task_type,
            stt_provider=stt_provider,
        )
        log_voice_event(
            logger,
            envelope=make_turn_envelope(scope),
            layer="memory",
            event="memory_context_loaded",
            learner_profile_present=bool(context.learner_profile_summary),
            learner_profile_updated_at=(
                context.learner_profile_summary.last_updated
                if context.learner_profile_summary
                else None
            ),
            mission_memory_count=len(context.mission_memory_context.relevant_memories)
            if context.mission_memory_context
            else 0,
            due_vocabulary_count=context.due_vocabulary_count,
        )

        return await initialize_session_v2(
            user_id=resolved_user_id,
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
            learner_profile_summary=(
                context.learner_profile_summary.to_dict()
                if context.learner_profile_summary
                else None
            ),
            mission_memory_context=(
                context.mission_memory_context.to_dict()
                if context.mission_memory_context
                else None
            ),
            explicit_mode=explicit_mode,
            interview_track_id=interview_track_id,
            mission_task_type=mission_task_type,
            mission_title=mission_title,
            mission_reason=mission_reason,
            mission_success_signal=mission_success_signal,
            mission_linked_goal_context=mission_linked_goal_context,
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

    def _has_existing_proficiency(self, request: SessionPersistRequest) -> bool:
        roadmap = request.agent_state.get("roadmap") or {}
        return bool((roadmap or {}).get("proficiency_profile"))

    def _should_capture_embedded_baseline(self, request: SessionPersistRequest) -> bool:
        if request.assessment_source or request.assessed_level:
            return False
        if self._has_existing_proficiency(request):
            return False
        mission_task_type = str(request.agent_state.get("mission_task_type") or "")
        if mission_task_type not in _EMBEDDED_BASELINE_MISSION_TYPES:
            return False
        user_messages = [
            str(message.get("content") or "").strip()
            for message in request.conversation_history
            if message.get("role") == "user" and str(message.get("content") or "").strip()
        ]
        return len(user_messages) >= 1

    def _infer_embedded_baseline(
        self,
        request: SessionPersistRequest,
    ) -> tuple[str, dict[str, float], bool, float]:
        user_messages = [
            str(message.get("content") or "").strip()
            for message in request.conversation_history
            if message.get("role") == "user" and str(message.get("content") or "").strip()
        ]
        combined = " ".join(user_messages)
        token_count = len(re.findall(r"[A-Za-z']+|\d+", combined))
        user_turns = len(user_messages)
        normalized = combined.lower()
        has_technical_signal = any(pattern in normalized for pattern in _EMBEDDED_BASELINE_TECH_PATTERNS)

        if token_count < 10:
            level = "A2"
            scores = {
                "fluency": 3.9,
                "grammar": 3.8,
                "vocabulary": 4.1,
                "comprehension": 4.5,
            }
        elif token_count < 28:
            level = "B1"
            scores = {
                "fluency": 4.9,
                "grammar": 4.7,
                "vocabulary": 5.1,
                "comprehension": 5.2,
            }
        else:
            level = "B1"
            scores = {
                "fluency": 5.6,
                "grammar": 5.2,
                "vocabulary": 5.7,
                "comprehension": 5.6,
            }

        if has_technical_signal:
            scores["vocabulary"] = min(9.5, round(scores["vocabulary"] + 0.4, 1))

        provisional = user_turns < 2 or token_count < 18
        confidence = 0.44 if provisional else 0.63
        normalized_scores = {key: round(float(value), 1) for key, value in scores.items()}
        return level, normalized_scores, provisional, confidence

    async def persist(self, request: SessionPersistRequest) -> SessionCompletion:
        """Run the shared post-session pipeline once."""
        scope = VoiceSessionScope(
            runtime=request.runtime,
            session_id=request.session_id,
            user_id=request.user_id,
            mission_task_type=request.agent_state.get("mission_task_type"),
        )
        envelope = make_turn_envelope(
            scope,
            phase=str(request.agent_state.get("current_phase") or ""),
            mode=request.final_mode,
        )
        if self._persistence_done:
            log_voice_event(
                logger,
                envelope=envelope,
                layer="persistence",
                event="persistence_skipped_already_done",
                status=request.status,
            )
            return SessionCompletion(status=request.status, already_persisted=True)

        persist_start = time.perf_counter()
        log_voice_event(
            logger,
            envelope=envelope,
            layer="persistence",
            event="persistence_started",
            status=request.status,
            turn_count=request.turn_count,
        )

        try:
            persisted_goal = await persist_goal_state_if_needed(
                user_id=request.user_id,
                existing_goal=request.existing_goal,
                agent_state=request.agent_state,
                learning_plan_service=self._learning_plan_service,
            )

            if self._should_capture_embedded_baseline(request):
                (
                    request.assessed_level,
                    request.assessment_scores,
                    request.baseline_provisional,
                    request.baseline_confidence,
                ) = self._infer_embedded_baseline(request)
                request.assessment_source = "embedded_first_mission"
                request.agent_state["assessment_source"] = "embedded_first_mission"
                request.agent_state["assessed_level"] = request.assessed_level
                request.agent_state["assessment_scores"] = request.assessment_scores
                request.agent_state["baseline_provisional"] = request.baseline_provisional
                request.agent_state["baseline_confidence"] = request.baseline_confidence

            if request.assessed_level and request.assessment_source:
                await self._learning_plan_service.record_assessment(
                    request.user_id,
                    assessed_level=request.assessed_level,
                    scores=request.assessment_scores,
                    provisional=request.baseline_provisional,
                    confidence_override=request.baseline_confidence,
                    source=request.assessment_source,
                )

            await self._learning_plan_service.increment_session_count(
                request.user_id,
                mode=request.final_mode,
                duration_minutes=request.turn_count * 2,
            )

            saved_memories: list[Any] = []
            memory_start = time.perf_counter()
            memory_outcome = None
            if request.conversation_history:
                memory_outcome = await self._memory_pipeline.process_conversation_with_outcome(
                    user_id=request.user_id,
                    messages=request.conversation_history,
                    session_id=request.session_id,
                )
                saved_memories = memory_outcome.saved_memories
            observe_voice_stage(
                runtime=request.runtime,
                stage="memory",
                duration_seconds=time.perf_counter() - memory_start,
            )
            if memory_outcome and memory_outcome.status == "soft_failed":
                log_voice_event(
                    logger,
                    envelope=envelope,
                    layer="memory",
                    event="memory_extraction_skipped",
                    level=logging.INFO,
                    failure_class="transient_provider_failure",
                    reason=memory_outcome.reason,
                    error_type=memory_outcome.error_type,
                    error=memory_outcome.error,
                    saved_memory_count=0,
                    conversation_messages=len(request.conversation_history),
                )
            elif memory_outcome and memory_outcome.status == "failed":
                log_voice_event(
                    logger,
                    envelope=envelope,
                    layer="memory",
                    event="memory_extraction_failed",
                    level=logging.ERROR,
                    failure_class="unexpected_bug",
                    reason=memory_outcome.reason,
                    error_type=memory_outcome.error_type,
                    error=memory_outcome.error,
                    saved_memory_count=0,
                    conversation_messages=len(request.conversation_history),
                )
            else:
                log_voice_event(
                    logger,
                    envelope=envelope,
                    layer="memory",
                    event="memory_saved",
                    saved_memory_count=len(saved_memories),
                    conversation_messages=len(request.conversation_history),
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
                mission_task_type=request.agent_state.get("mission_task_type"),
                mission_title=request.agent_state.get("mission_title"),
                mission_reason=request.agent_state.get("mission_reason"),
                mission_linked_goal_context=request.agent_state.get("mission_linked_goal_context"),
                conversation_history=request.conversation_history,
                corrections_made=request.corrections_made,
                vocabulary_reviewed=request.vocabulary_reviewed,
                duration_minutes=request.turn_count * 2,
                assessed_level=request.assessed_level,
                assessment_scores=request.assessment_scores or {},
                assessment_source=request.assessment_source,
                interview_run=interview_run,
                next_mission_choice=request.agent_state.get("next_mission_choice") or None,
            )
            if request.turn_count > 0:
                await award_session_gamification(
                    self._db,
                    request.user_id,
                    request.session_id,
                )
        except Exception as exc:
            logger.warning("[VoiceSession] Persist failed (%s): %s", request.status, exc)
            observe_voice_stage(
                runtime=request.runtime,
                stage="persist",
                duration_seconds=time.perf_counter() - persist_start,
            )
            record_voice_persistence(runtime=request.runtime, status="error")
            log_voice_event(
                logger,
                envelope=envelope,
                layer="persistence",
                event="persistence_failed",
                level=logging.WARNING,
                status=request.status,
                error=str(exc),
            )
            return SessionCompletion(status=request.status, error=str(exc))

        self._persistence_done = True
        observe_voice_stage(
            runtime=request.runtime,
            stage="persist",
            duration_seconds=time.perf_counter() - persist_start,
        )
        record_voice_persistence(runtime=request.runtime, status=request.status)
        log_voice_event(
            logger,
            envelope=envelope,
            layer="persistence",
            event="persistence_completed",
            status=request.status,
            goal_persisted=bool(persisted_goal),
            interview_run_persisted=bool(interview_run),
            session_evidence_persisted=bool(session_evidence),
        )
        return SessionCompletion(
            status=request.status,
            persisted_goal=persisted_goal,
            interview_run=interview_run,
            session_evidence=session_evidence,
        )
