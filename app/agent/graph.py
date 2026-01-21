"""LangGraph state machine for English Friend agent.

This module assembles all nodes into a coherent conversation flow:

```
                    ┌─────────────────┐
                    │   START_NODE    │
                    │ (new/returning?)│
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                              ▼
    ┌─────────────────┐            ┌─────────────────┐
    │  GOAL_DISCOVERY │            │  MODE_ROUTER    │
    │  (ask & confirm)│            │  (returning     │
    │                 │            │   user w/ goal) │
    └────────┬────────┘            └────────┬────────┘
             │                              │
             ▼                              │
    ┌─────────────────┐                     │
    │  INTEREST_PROBE │                     │
    │  (discover      │                     │
    │   interests)    │                     │
    └────────┬────────┘                     │
             │                              │
             ▼                              │
    ┌─────────────────┐                     │
    │   ASSESSMENT    │                     │
    │  (evaluate      │                     │
    │   level)        │                     │
    └────────┬────────┘                     │
             │                              │
             ▼                              │
    ┌─────────────────┐                     │
    │  PROGRAM_BUILD  │                     │
    │  (create        │                     │
    │   roadmap)      │                     │
    └────────┬────────┘                     │
             │                              │
             ▼                              │
    ┌─────────────────────────────────────────────────┐
    │              LEARNING_SESSION                   │
    │  ┌─────────────────────────────────────────┐    │
    │  │           MODE_ROUTER                   │◄───┘
    │  │  (select: mock_interview, vocab_drill,  │
    │  │   free_conversation, grammar_focus)     │
    │  └──────────────┬──────────────────────────┘
    │                 │
    │                 ▼
    │  ┌─────────────────────────────────────────┐
    │  │         TURN_PROCESSOR                  │
    │  │  - Generate LLM response                │
    │  │  - Socratic recast correction           │
    │  │  - Extract vocabulary                   │
    │  │  - Trigger memory extraction            │
    │  └──────────────┬──────────────────────────┘
    │                 │
    │                 │ (loop until end)
    │                 │
    └─────────────────│───────────────────────────────┘
                      ▼
    ┌─────────────────────────────────────────────────┐
    │              SESSION_END                        │
    │  - XP/streak calculation                        │
    │  - Final memory extraction                      │
    │  - Farewell message                             │
    └─────────────────────────────────────────────────┘
```

The graph is designed for stateless operation:
- State is loaded from PostgreSQL at session start
- State is persisted to PostgreSQL at key checkpoints
- No Redis or external checkpoint storage required
"""

from __future__ import annotations

import logging
from typing import Optional, Any, Literal

from langgraph.graph import StateGraph, END

from app.agent.state import AgentState, AgentPhase, create_initial_state

# Import all nodes
from app.agent.nodes.start import start_node, route_after_start
from app.agent.nodes.goal_discovery import goal_discovery_node, route_after_goal_discovery
from app.agent.nodes.interest_probe import interest_probe_node, route_after_interest_probe
from app.agent.nodes.assessment import assessment_node, route_after_assessment
from app.agent.nodes.program_build import program_build_node, route_after_program_build
from app.agent.nodes.mode_router import mode_router_node, route_to_mode
from app.agent.nodes.turn_processor import turn_processor_node, route_after_turn
from app.agent.nodes.session_end import session_end_node

logger = logging.getLogger(__name__)


def create_agent_graph() -> StateGraph:
    """Create the LangGraph state machine for conversation flow.

    Returns:
        Compiled StateGraph ready for invocation
    """
    # Create graph with state schema
    graph = StateGraph(AgentState)

    # Add all nodes
    graph.add_node("start", start_node)
    graph.add_node("goal_discovery", goal_discovery_node)
    graph.add_node("interest_probe", interest_probe_node)
    graph.add_node("assessment", assessment_node)
    graph.add_node("program_build", program_build_node)
    graph.add_node("mode_router", mode_router_node)
    graph.add_node("turn_processor", turn_processor_node)
    graph.add_node("session_end", session_end_node)

    # Set entry point
    graph.set_entry_point("start")

    # Add edges with conditional routing

    # Start -> goal_discovery or mode_router (based on user status)
    graph.add_conditional_edges(
        "start",
        route_after_start,
        {
            "goal_discovery": "goal_discovery",
            "mode_router": "mode_router",
        },
    )

    # Goal discovery -> interest_probe or mode_router (based on confirmation)
    graph.add_conditional_edges(
        "goal_discovery",
        route_after_goal_discovery,
        {
            "goal_discovery": "goal_discovery",  # Loop for confirmation
            "interest_probe": "interest_probe",
            "mode_router": "mode_router",
        },
    )

    # Interest probe -> assessment or stay
    graph.add_conditional_edges(
        "interest_probe",
        route_after_interest_probe,
        {
            "interest_probe": "interest_probe",
            "assessment": "assessment",
        },
    )

    # Assessment -> program_build or stay
    graph.add_conditional_edges(
        "assessment",
        route_after_assessment,
        {
            "assessment": "assessment",
            "program_build": "program_build",
        },
    )

    # Program build -> mode_router
    graph.add_edge("program_build", "mode_router")

    # Mode router -> turn_processor
    graph.add_edge("mode_router", "turn_processor")

    # Turn processor -> turn_processor (loop) or session_end
    graph.add_conditional_edges(
        "turn_processor",
        route_after_turn,
        {
            "turn_processor": "turn_processor",
            "session_end": "session_end",
        },
    )

    # Session end -> END
    graph.add_edge("session_end", END)

    return graph.compile()


# Global compiled graph (lazy initialization)
_compiled_graph: Optional[StateGraph] = None


def get_agent_graph() -> StateGraph:
    """Get the compiled agent graph (singleton).

    Returns:
        Compiled StateGraph
    """
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = create_agent_graph()
        logger.info("[LangGraph] Agent graph compiled successfully")
    return _compiled_graph


async def run_agent_turn(
    state: AgentState,
    user_message: Optional[str] = None,
) -> AgentState:
    """Run a single turn of the agent.

    This is the main entry point for voice.py to interact with the agent.
    It handles:
    1. Setting user message in state
    2. Running the appropriate node based on current phase
    3. Returning updated state with response

    Args:
        state: Current agent state
        user_message: User's message (if any)

    Returns:
        Updated agent state with pending_response set
    """
    # Set user message
    if user_message is not None:
        state["last_user_message"] = user_message
        state["needs_user_input"] = False

    # Get current phase
    current_phase = state.get("current_phase", AgentPhase.START)

    logger.debug(f"[Agent] Running turn: phase={current_phase.value}, "
                 f"user_msg={user_message[:30] if user_message else None}...")

    # Route to appropriate node based on phase
    # For incremental turn processing, we don't run the full graph
    # Instead, we run the appropriate node directly

    if current_phase == AgentPhase.START:
        state = await start_node(state)
        # After start, run the appropriate next node
        next_node = route_after_start(state)
        if next_node == "goal_discovery":
            state = await goal_discovery_node(state)
        elif next_node == "mode_router":
            state = await mode_router_node(state)

    elif current_phase == AgentPhase.ONBOARDING:
        state = await goal_discovery_node(state)

    elif current_phase == AgentPhase.GOAL_DISCOVERY:
        state = await goal_discovery_node(state)
        # Check if we should transition
        next_node = route_after_goal_discovery(state)
        if next_node == "interest_probe":
            state = await interest_probe_node(state)
        elif next_node == "mode_router":
            state = await mode_router_node(state)

    elif current_phase == AgentPhase.GOAL_CONFIRMATION:
        state = await goal_discovery_node(state)

    elif current_phase == AgentPhase.INTEREST_PROBE:
        state = await interest_probe_node(state)
        next_node = route_after_interest_probe(state)
        if next_node == "assessment":
            state = await assessment_node(state)

    elif current_phase == AgentPhase.ASSESSMENT:
        state = await assessment_node(state)
        next_node = route_after_assessment(state)
        if next_node == "program_build":
            state = await program_build_node(state)
            state = await mode_router_node(state)

    elif current_phase == AgentPhase.PROGRAM_BUILD:
        state = await program_build_node(state)
        state = await mode_router_node(state)

    elif current_phase == AgentPhase.LEARNING_SESSION:
        # Check if this is first turn in session (needs mode selection)
        if state.get("turn_count", 0) == 0 and not state.get("system_prompt"):
            state = await mode_router_node(state)
        else:
            state = await turn_processor_node(state)

        # Check for session end
        if state.get("should_end_session"):
            state = await session_end_node(state)

    elif current_phase == AgentPhase.SESSION_END:
        state = await session_end_node(state)

    logger.debug(f"[Agent] Turn complete: phase={state.get('current_phase', AgentPhase.START).value}, "
                 f"response={'yes' if state.get('pending_response') else 'no'}")

    return state


async def initialize_session(
    user_id: int,
    session_id: str,
    username: str = "Student",
    is_new_user: bool = True,
    language_level: str = "B1",
    confirmed_goal: Optional[str] = None,
    confirmed_interests: Optional[list[str]] = None,
    roadmap: Optional[dict[str, Any]] = None,
    due_vocabulary_count: int = 0,
    due_vocabulary_words: Optional[list[str]] = None,
    memory_section: Optional[str] = None,
) -> AgentState:
    """Initialize agent state for a new session.

    This loads existing user data from the database and creates
    the initial state for the conversation.

    Args:
        user_id: User ID from database
        session_id: Unique session identifier
        username: User's display name
        is_new_user: Whether this is their first session
        language_level: Current CEFR level
        confirmed_goal: Previously confirmed goal (if any)
        confirmed_interests: Previously confirmed interests (if any)
        roadmap: Existing learning roadmap (if any)
        due_vocabulary_count: Count of words due for review
        due_vocabulary_words: List of words due for review
        memory_section: Formatted memory for prompt

    Returns:
        Initialized AgentState
    """
    state = create_initial_state(
        user_id=user_id,
        session_id=session_id,
        username=username,
        is_new_user=is_new_user,
        language_level=language_level,
    )

    # Load existing user context
    if confirmed_goal:
        state["confirmed_goal"] = confirmed_goal

    if confirmed_interests:
        state["confirmed_interests"] = confirmed_interests

    if roadmap:
        state["roadmap"] = roadmap
        state["focus_areas"] = [fa.get("area", "") for fa in roadmap.get("focus_areas", [])]
        state["preferred_mode"] = roadmap.get("preferred_mode", "free_conversation")

    if due_vocabulary_count:
        state["due_vocabulary_count"] = due_vocabulary_count

    if due_vocabulary_words:
        state["due_vocabulary_words"] = due_vocabulary_words

    if memory_section:
        state["memory_section"] = memory_section

    logger.info(f"[Agent] Session initialized: user={user_id}, is_new={is_new_user}, "
                f"goal={confirmed_goal}, level={language_level}")

    return state
