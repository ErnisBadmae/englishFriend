"""LangGraph Agent v2 - Simplified 4-node LLM-driven architecture.

Architecture:
    router → onboarding → learning → session_end

Features:
- LLM-driven decisions with structured JSON output
- Prompt templates from database (A/B testable)
- Simplified flow: 4 nodes instead of 11
- Comprehensive metrics
- Langfuse tracing for observability

Usage:
    from app.agent.graph_v2 import run_agent_turn_v2, initialize_session_v2

    state = await initialize_session_v2(user_id, session_id, ...)
    state = await run_agent_turn_v2(state, user_message="hello")
"""

import logging
import os
import time
from typing import Optional, Any, Literal

from langgraph.graph import StateGraph, END

from app.agent.state import AgentState, AgentPhase
from app.data.interview_tracks import get_interview_track
from app.data.interview_questions import select_questions_for_track
from app.agent.nodes_v2 import (
    router_node,
    route_after_router,
    onboarding_node,
    route_after_onboarding,
    learning_node,
    route_after_learning,
    session_end_node,
)
from app.services.pedagogy_logger import get_pedagogy_logger
from app.services.ai.mode_prompts import LearningMode
from app.core.observability import (
    set_request_context,
    get_langfuse,
    get_request_id,
)

logger = logging.getLogger(__name__)

# Feature flag for v2
USE_AGENT_V2 = os.getenv("USE_AGENT_V2", "true").lower() == "true"


def create_agent_graph_v2() -> StateGraph:
    """Create the simplified 4-node LangGraph.

    Graph structure:
        START → router
        router → {onboarding, learning, session_end}
        onboarding → {END (wait for input), learning, session_end}
        learning → {END (wait for input), session_end}
        session_end → END

    Key insight: After each node processes, if needs_user_input=True,
    route to END to pause the graph. Next call to run_agent_turn_v2()
    will restart from router with the user's response.

    Returns:
        Compiled StateGraph
    """
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("router", router_node)
    graph.add_node("onboarding", onboarding_node)
    graph.add_node("learning", learning_node)
    graph.add_node("session_end", session_end_node)

    # Set entry point
    graph.set_entry_point("router")

    # Router edges
    graph.add_conditional_edges(
        "router",
        route_after_router,
        {
            "onboarding": "onboarding",
            "learning": "learning",
            "session_end": "session_end",
        },
    )

    # Onboarding edges - pause for user input by routing to END
    graph.add_conditional_edges(
        "onboarding",
        route_after_onboarding,
        {
            "wait_for_input": END,  # Pause graph, wait for next user message
            "learning": "learning",
            "session_end": "session_end",
        },
    )

    # Learning edges - pause for user input by routing to END
    graph.add_conditional_edges(
        "learning",
        route_after_learning,
        {
            "wait_for_input": END,  # Pause graph, wait for next user message
            "session_end": "session_end",
        },
    )

    # Session end terminates
    graph.add_edge("session_end", END)

    return graph.compile()


# Singleton compiled graph
_agent_graph_v2: Optional[StateGraph] = None


def get_agent_graph_v2() -> StateGraph:
    """Get or create the compiled graph singleton."""
    global _agent_graph_v2
    if _agent_graph_v2 is None:
        _agent_graph_v2 = create_agent_graph_v2()
        logger.info("[Agent V2] Graph created with 4 nodes: router, onboarding, learning, session_end")
    return _agent_graph_v2


async def initialize_session_v2(
    user_id: int,
    session_id: str,
    username: str = "Student",
    is_new_user: bool = True,
    language_level: str = "B1",
    confirmed_goal: Optional[str] = None,
    confirmed_interests: Optional[list[str]] = None,
    roadmap: Optional[dict] = None,
    due_vocabulary_count: int = 0,
    due_vocabulary_words: Optional[list[str]] = None,
    memory_section: str = "",
    explicit_mode: Optional[str] = None,
    interview_track_id: Optional[str] = None,
    mission_task_type: Optional[str] = None,
    mission_title: Optional[str] = None,
    mission_reason: Optional[str] = None,
    mission_success_signal: Optional[str] = None,
    mission_linked_goal_context: Optional[str] = None,
) -> AgentState:
    """Initialize a new agent session.

    Args:
        user_id: User ID
        session_id: Session UUID
        username: User's display name
        is_new_user: Whether this is a new user
        language_level: CEFR level
        confirmed_goal: Pre-confirmed goal (for returning users)
        confirmed_interests: Pre-confirmed interests
        roadmap: Learning roadmap from DB
        due_vocabulary_count: Number of words due for review
        due_vocabulary_words: List of words due
        memory_section: Formatted memory context

    Returns:
        Initialized AgentState
    """
    pedagogy = get_pedagogy_logger(user_id)

    # Log session start
    pedagogy.log_session_started(
        user_id=user_id,
        session_id=session_id,
        is_new_user=is_new_user,
    )

    # Extract focus areas from roadmap
    focus_areas = []
    if roadmap and isinstance(roadmap, dict):
        focus_areas = [
            fa.get("area", fa) if isinstance(fa, dict) else fa
            for fa in roadmap.get("focus_areas", [])
        ]
    goal_brief = roadmap.get("goal_brief") if isinstance(roadmap, dict) else None
    proficiency_profile = roadmap.get("proficiency_profile") if isinstance(roadmap, dict) else None
    assessed_level = None
    assessment_scores: dict[str, Any] = {}
    assessment_status = None
    baseline_provisional = False
    baseline_confidence = 0.0
    goal_setup_complete = False
    if goal_brief:
        goal_setup_complete = goal_brief.get("status") in {"draft", "confirmed"}
    if proficiency_profile:
        assessed_level = proficiency_profile.get("cefr_level")
        assessment_scores = {
            "fluency": proficiency_profile.get("fluency"),
            "grammar": proficiency_profile.get("grammar_accuracy"),
            "vocabulary": proficiency_profile.get("professional_vocabulary"),
            "comprehension": proficiency_profile.get("listening_comprehension"),
        }
        assessment_status = proficiency_profile.get("status")
        baseline_provisional = bool(proficiency_profile.get("provisional"))
        baseline_confidence = float(proficiency_profile.get("confidence") or 0.0)
        if assessed_level:
            language_level = assessed_level

    selected_track = get_interview_track(interview_track_id)

    # Pre-select curated questions for this session (deterministic per session_id)
    interview_question_prompts: list[str] = []
    if selected_track:
        qs = select_questions_for_track(
            selected_track["id"],
            limit=4,
            session_seed=session_id,
        )
        interview_question_prompts = [q["prompt"] for q in qs]

    # Determine initial mode
    initial_mode = LearningMode.FREE_CONVERSATION
    if due_vocabulary_count >= 10:
        initial_mode = LearningMode.VOCABULARY_DRILL
    elif confirmed_goal and "interview" in confirmed_goal.lower():
        initial_mode = LearningMode.MOCK_INTERVIEW
    if explicit_mode:
        try:
            initial_mode = LearningMode(explicit_mode)
        except ValueError:
            logger.warning(f"[Agent V2] Unknown explicit mode ignored: {explicit_mode}")

    resolved_mission_task_type = mission_task_type
    resolved_mission_title = mission_title
    resolved_mission_reason = mission_reason
    resolved_mission_success_signal = mission_success_signal
    resolved_mission_linked_goal_context = mission_linked_goal_context

    program_plan = roadmap.get("program_plan") if isinstance(roadmap, dict) else {}
    current_stage = (program_plan or {}).get("current_stage")
    weekly_focus = (program_plan or {}).get("weekly_focus") or []

    if not resolved_mission_task_type and initial_mode == LearningMode.FREE_CONVERSATION:
        if current_stage == "foundation":
            resolved_mission_task_type = "foundation_speaking_drill"
            resolved_mission_title = resolved_mission_title or "Run a foundation speaking drill"
            resolved_mission_reason = (
                resolved_mission_reason
                or (weekly_focus[0] if weekly_focus else "Stabilize grammar and fluency before higher-pressure scenarios.")
            )
            resolved_mission_success_signal = (
                resolved_mission_success_signal
                or "You can answer in English with fewer corrections and clearer delivery."
            )
            resolved_mission_linked_goal_context = resolved_mission_linked_goal_context or "foundation"
        elif any("grammar" in str(area).lower() for area in focus_areas):
            resolved_mission_task_type = "grammar_rescue"
            resolved_mission_title = resolved_mission_title or "Do a grammar rescue session"
            resolved_mission_reason = (
                resolved_mission_reason
                or (weekly_focus[0] if weekly_focus else "Clean up the most common spoken grammar issue.")
            )
            resolved_mission_success_signal = (
                resolved_mission_success_signal
                or "The same grammar issue appears less often in the next answer."
            )
            resolved_mission_linked_goal_context = resolved_mission_linked_goal_context or "grammar"

    state: AgentState = {
        # User info
        "user_id": user_id,
        "username": username,
        "is_new_user": is_new_user,
        "language_level": language_level,

        # Session info
        "session_id": session_id,
        "turn_count": 0,
        "current_phase": AgentPhase.START,

        # Goals & Interests
        "confirmed_goal": confirmed_goal,
        "detected_goal": None,
        "goal_needs_confirmation": False,
        "goal_brief": goal_brief,
        "goal_setup_complete": goal_setup_complete,
        "confirmed_interests": confirmed_interests or [],

        # Assessment
        "assessed_level": assessed_level,
        "assessment_scores": assessment_scores,
        "assessment_status": assessment_status,
        "baseline_provisional": baseline_provisional,
        "baseline_confidence": baseline_confidence,
        "assessment_step_index": 0,
        "assessment_answers": {},

        # Learning program
        "roadmap": roadmap,
        "focus_areas": focus_areas,
        "interview_track_id": selected_track["id"] if selected_track else None,
        "interview_track_title": selected_track["title"] if selected_track else None,
        "session_focus": selected_track["prompt_focus"] if selected_track else None,
        "interview_question_prompts": interview_question_prompts,
        "mission_task_type": resolved_mission_task_type,
        "mission_title": resolved_mission_title,
        "mission_reason": resolved_mission_reason,
        "mission_success_signal": resolved_mission_success_signal,
        "mission_linked_goal_context": resolved_mission_linked_goal_context,

        # Current session
        "current_mode": initial_mode,
        "conversation_history": [],
        "system_prompt": None,
        "low_signal_turn_streak": 0,
        "anchor_question_id": 0,
        "anchor_follow_up_pending": False,

        # Vocabulary
        "due_vocabulary_count": due_vocabulary_count,
        "due_vocabulary_words": due_vocabulary_words or [],
        "vocabulary_reviewed": [],

        # Memory
        "memory_section": memory_section,
        "new_memories_to_save": [],

        # Corrections
        "corrections_made": [],

        # Gamification
        "xp_earned": 0,

        # Logging
        "decision_log": [],

        # Response
        "pending_response": None,
        "needs_user_input": True,
        "session_complete_reason": None,
        "session_complete_return_screen": None,

        # Control
        "should_end_session": False,
        "last_user_message": None,
        "_route": None,
        "_skip_goal": False,
        "_skip_interests": False,
        "_skip_assessment": False,
        "setup_step": "ready_for_program" if assessed_level else ("baseline_assessment" if goal_setup_complete else "goal_setup"),
        "last_question_type": None,
    }

    logger.info(
        f"[Agent V2] Session initialized: user={user_id}, is_new={is_new_user}, "
        f"goal={confirmed_goal}, level={language_level}"
    )

    return state


async def run_agent_turn_v2(
    state: AgentState,
    user_message: Optional[str] = None,
) -> AgentState:
    """Run a single agent turn.

    Args:
        state: Current agent state
        user_message: User's message (None for initial greeting)

    Returns:
        Updated state after processing
    """
    start_time = time.time()

    # Update state with user message
    if user_message is not None:
        state["last_user_message"] = user_message

    phase = state.get("current_phase", AgentPhase.START)
    user_id = state.get("user_id")
    session_id = state.get("session_id")
    turn_count = state.get("turn_count", 0)

    # Set request context for this turn (enables log correlation)
    request_id = set_request_context(user_id=user_id, session_id=session_id)

    logger.info(
        f"[Agent V2] ▶ Turn start | phase={phase.value if hasattr(phase, 'value') else phase} | "
        f"user_msg='{(user_message or '')[:50]}...'"
    )

    # Start Langfuse trace for this turn
    langfuse = get_langfuse()
    trace = None
    if langfuse:
        try:
            trace = langfuse.trace(
                name="agent_turn",
                id=request_id,
                user_id=str(user_id) if user_id else None,
                session_id=session_id,
                metadata={
                    "turn_count": turn_count,
                    "phase": phase.value if hasattr(phase, "value") else str(phase),
                    "user_message": (user_message or "")[:100],
                },
            )
        except Exception as e:
            logger.warning(f"Failed to create Langfuse trace: {e}")

    # Get compiled graph
    graph = get_agent_graph_v2()

    # Run graph
    try:
        # LangGraph invoke returns final state
        result = await graph.ainvoke(state)

        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000

        # Log completion
        response = result.get("pending_response", "")[:50]
        new_phase = result.get("current_phase", phase)

        logger.info(
            f"[Agent V2] ◀ Turn complete | phase={new_phase.value if hasattr(new_phase, 'value') else new_phase} | "
            f"latency={latency_ms:.0f}ms | response='{response}...'"
        )

        # Log decision summary
        decision_log = result.get("decision_log", [])
        if decision_log:
            latest = decision_log[-1] if decision_log else {}
            logger.info(
                f"[Agent V2] 📋 Decision: node={latest.get('node')} | "
                f"action={latest.get('action')} | reason={latest.get('reason')}"
            )

        # Update Langfuse trace with results
        if trace:
            try:
                trace.update(
                    output=result.get("pending_response", "")[:500],
                    metadata={
                        "turn_count": turn_count,
                        "phase_start": phase.value if hasattr(phase, "value") else str(phase),
                        "phase_end": new_phase.value if hasattr(new_phase, "value") else str(new_phase),
                        "latency_ms": round(latency_ms, 2),
                        "decision": latest if decision_log else None,
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to update Langfuse trace: {e}")

        return result

    except Exception as e:
        logger.error(f"[Agent V2] Error running graph: {e}", exc_info=True)

        # Log error to Langfuse
        if trace:
            try:
                trace.update(
                    metadata={"error": str(e)},
                    level="ERROR",
                )
            except Exception:
                pass

        state["pending_response"] = "I'm having trouble. Could you repeat that?"
        state["needs_user_input"] = True
        return state


# For backwards compatibility, re-export with v2 suffix
__all__ = [
    "create_agent_graph_v2",
    "get_agent_graph_v2",
    "initialize_session_v2",
    "run_agent_turn_v2",
    "USE_AGENT_V2",
]
