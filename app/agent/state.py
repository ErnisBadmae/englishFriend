"""Agent state definition for LangGraph.

This module defines the state that flows through the LangGraph nodes.
The state is loaded from PostgreSQL at session start and updates are
persisted during the session.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, TypedDict, Literal, Any


class AgentPhase(str, Enum):
    """Current phase of the conversation."""
    START = "start"
    ONBOARDING = "onboarding"
    GOAL_DISCOVERY = "goal_discovery"
    GOAL_CONFIRMATION = "goal_confirmation"
    INTEREST_PROBE = "interest_probe"
    ASSESSMENT = "assessment"
    PROGRAM_BUILD = "program_build"
    LEARNING_SESSION = "learning_session"
    SESSION_END = "session_end"


class LearningModeEnum(str, Enum):
    """Learning modes available in the session."""
    ASSESSMENT = "assessment"
    MOCK_INTERVIEW = "mock_interview"
    VOCABULARY_DRILL = "vocabulary_drill"
    FREE_CONVERSATION = "free_conversation"
    GRAMMAR_FOCUS = "grammar_focus"


class DecisionLogEntry(TypedDict):
    """A single entry in the decision log for debugging/transparency."""
    node: str
    timestamp: str
    action: str
    reason: Optional[str]
    data: Optional[dict[str, Any]]


class AgentState(TypedDict, total=False):
    """State that flows through the LangGraph agent.

    This state is:
    - Loaded from PostgreSQL at session start
    - Updated by nodes during conversation
    - Persisted to PostgreSQL at key checkpoints
    """

    # === User Info ===
    user_id: int
    username: str
    is_new_user: bool
    language_level: str  # CEFR level: A1, A2, B1, B2, C1, C2

    # === Session Info ===
    session_id: str
    turn_count: int
    current_phase: AgentPhase

    # === Goals & Interests ===
    detected_goal: Optional[str]  # LLM-extracted goal (before confirmation)
    confirmed_goal: Optional[str]  # User-confirmed goal
    goal_needs_confirmation: bool  # Flag: waiting for user to confirm
    detected_interests: list[str]
    confirmed_interests: list[str]
    interests_need_confirmation: bool

    # === Assessment ===
    assessed_level: Optional[str]  # CEFR level from assessment
    level_confidence: float  # 0.0 - 1.0 confidence score
    assessment_scores: dict[str, float]  # {vocabulary, grammar, fluency, comprehension}
    last_assessment_date: Optional[str]  # ISO format date

    # === Learning Program ===
    roadmap: Optional[dict[str, Any]]  # Full roadmap structure
    current_milestone: Optional[str]
    focus_areas: list[str]
    preferred_mode: Optional[str]

    # === Current Session Learning ===
    current_mode: LearningModeEnum
    mode_reason: Optional[str]  # Why this mode was selected
    conversation_history: list[dict[str, str]]  # {role, content}
    system_prompt: Optional[str]  # Current system prompt

    # === Vocabulary (FSRS) ===
    due_vocabulary_count: int
    due_vocabulary_words: list[str]
    vocabulary_reviewed: list[dict[str, Any]]  # Words reviewed this session

    # === Memory (RAG) ===
    relevant_memories: list[str]  # Retrieved from Qdrant
    new_memories_to_save: list[dict[str, Any]]  # To be saved after session
    memory_section: Optional[str]  # Formatted memory for prompt

    # === Corrections & Feedback ===
    errors_detected: list[dict[str, Any]]  # Grammar/vocab errors this session
    corrections_made: list[dict[str, Any]]  # Corrections applied

    # === Gamification ===
    xp_earned: int
    streak_count: int
    achievements_unlocked: list[str]

    # === Logging ===
    decision_log: list[DecisionLogEntry]  # Log of key decisions

    # === Response ===
    pending_response: Optional[str]  # Response to send to user
    pending_audio: Optional[bytes]  # TTS audio to send

    # === Control Flags ===
    should_end_session: bool
    needs_user_input: bool
    last_user_message: Optional[str]
    _route: Optional[str]  # Internal: router decision (onboarding/learning/session_end)
    _skip_goal: bool  # Internal: skip goal discovery in onboarding
    _skip_interests: bool  # Internal: skip interest probe in onboarding
    _skip_assessment: bool  # Internal: skip assessment in onboarding


def create_initial_state(
    user_id: int,
    session_id: str,
    username: str = "Student",
    is_new_user: bool = True,
    language_level: str = "B1",
) -> AgentState:
    """Create initial state for a new session.

    Args:
        user_id: User ID from database
        session_id: Unique session identifier
        username: User's display name
        is_new_user: Whether this is their first session
        language_level: Starting CEFR level

    Returns:
        Initialized AgentState
    """
    return AgentState(
        # User info
        user_id=user_id,
        username=username,
        is_new_user=is_new_user,
        language_level=language_level,

        # Session info
        session_id=session_id,
        turn_count=0,
        current_phase=AgentPhase.START,

        # Goals & Interests
        detected_goal=None,
        confirmed_goal=None,
        goal_needs_confirmation=False,
        detected_interests=[],
        confirmed_interests=[],
        interests_need_confirmation=False,

        # Assessment
        assessed_level=None,
        level_confidence=0.0,
        assessment_scores={},
        last_assessment_date=None,

        # Learning Program
        roadmap=None,
        current_milestone=None,
        focus_areas=[],
        preferred_mode=None,

        # Current Session
        current_mode=LearningModeEnum.FREE_CONVERSATION,
        mode_reason=None,
        conversation_history=[],
        system_prompt=None,

        # Vocabulary
        due_vocabulary_count=0,
        due_vocabulary_words=[],
        vocabulary_reviewed=[],

        # Memory
        relevant_memories=[],
        new_memories_to_save=[],
        memory_section=None,

        # Corrections
        errors_detected=[],
        corrections_made=[],

        # Gamification
        xp_earned=0,
        streak_count=0,
        achievements_unlocked=[],

        # Logging
        decision_log=[],

        # Response
        pending_response=None,
        pending_audio=None,

        # Control flags
        should_end_session=False,
        needs_user_input=True,
        last_user_message=None,
        _route=None,
        _skip_goal=False,
        _skip_interests=False,
        _skip_assessment=False,
    )


def add_decision_log(
    state: AgentState,
    node: str,
    action: str,
    reason: Optional[str] = None,
    data: Optional[dict[str, Any]] = None,
) -> None:
    """Add an entry to the decision log.

    This is for debugging and transparency - helps developers
    understand why the agent made certain decisions.

    Args:
        state: Current agent state
        node: Name of the node making the decision
        action: What action was taken
        reason: Why this action was taken
        data: Additional context data
    """
    entry = DecisionLogEntry(
        node=node,
        timestamp=datetime.utcnow().isoformat(),
        action=action,
        reason=reason,
        data=data,
    )
    state["decision_log"].append(entry)
