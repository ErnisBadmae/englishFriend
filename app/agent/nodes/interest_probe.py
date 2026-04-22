"""Interest Probe Node - discovers user's interests for personalized content.

This node discovers what topics the user enjoys discussing:
1. Ask about interests
2. Extract interests from response
3. Confirm and store for personalization

Interests are used to make conversations more engaging and relevant.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.agent.state import AgentState, AgentPhase, add_decision_log
from app.services.pedagogy_logger import get_pedagogy_logger
from app.services.ai.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)

# System prompt for interest extraction
INTEREST_EXTRACTION_PROMPT = """You are analyzing a user's message to extract their interests and hobbies.

Common interest categories:
- Technology (AI, programming, gadgets, startups)
- Sports (football, basketball, fitness, hiking)
- Entertainment (movies, music, gaming, TV shows)
- Science (physics, biology, space, environment)
- Business (entrepreneurship, investing, marketing)
- Arts (painting, photography, design, writing)
- Travel (countries, cultures, food, languages)
- Lifestyle (cooking, health, fashion, pets)

Extract 1-4 main interests from the user's message.
Return them as a comma-separated list.

If no clear interests are mentioned, return "NONE".

User message: {message}

Interests (comma-separated):"""


async def interest_probe_node(state: AgentState) -> AgentState:
    """Node that discovers user's interests for personalization.

    Args:
        state: Current agent state

    Returns:
        Updated agent state
    """
    pedagogy = get_pedagogy_logger(state["user_id"])
    llm = get_llm_provider()

    user_message = state.get("last_user_message", "")

    # Check if we already have confirmed interests
    if state.get("confirmed_interests"):
        # Skip interest probe, go to assessment
        state["current_phase"] = AgentPhase.ASSESSMENT
        state["needs_user_input"] = False

        add_decision_log(
            state,
            node="interest_probe",
            action="skip_already_have_interests",
            reason="User already has confirmed interests",
            data={"interests": state["confirmed_interests"]},
        )

        return state

    # Sub-state 1: Ask about interests (first entry)
    if not state.get("detected_interests") and not state.get("interests_need_confirmation"):
        # This prompt was already sent from goal_discovery when it transitioned
        # But if we enter directly, we need to ask
        if not user_message:
            response = (
                "What topics do you enjoy talking about? "
                "For example: technology, sports, movies, science, travel... "
                "This helps me make our conversations more interesting for you!"
            )

            state["pending_response"] = response
            state["needs_user_input"] = True

            add_decision_log(
                state,
                node="interest_probe",
                action="ask_interests",
                reason="Initial interest probe",
            )

            logger.info(f"[InterestProbe] Asking user {state['user_id']} about interests")
            return state

    # Sub-state 2: User responded, extract interests
    if user_message and not state.get("interests_need_confirmation"):
        detected_interests = await _extract_interests(llm, user_message)

        if detected_interests:
            state["detected_interests"] = detected_interests
            state["interests_need_confirmation"] = True

            interests_str = ", ".join(detected_interests)
            confirmation = (
                f"Great! So you're interested in {interests_str}. "
                "I'll keep that in mind during our conversations. "
                "Now, let me get a sense of your current English level. "
                "I'll ask you a few questions - just answer naturally!"
            )

            state["pending_response"] = confirmation
            state["confirmed_interests"] = detected_interests  # Auto-confirm for smoother flow
            state["interests_need_confirmation"] = False
            state["current_phase"] = AgentPhase.ASSESSMENT
            state["needs_user_input"] = True

            pedagogy.log_interests_detected(
                user_id=state["user_id"],
                interests=detected_interests,
                source="user_response",
            )
            pedagogy.log_interests_confirmed(
                user_id=state["user_id"],
                interests=detected_interests,
            )
            pedagogy.log_phase_transition(
                user_id=state["user_id"],
                from_phase="interest_probe",
                to_phase="assessment",
                reason="interests_confirmed",
            )

            add_decision_log(
                state,
                node="interest_probe",
                action="interests_detected_confirmed",
                reason=f"Detected interests: {detected_interests}",
                data={"interests": detected_interests},
            )

            logger.info(f"[InterestProbe] Interests confirmed: {detected_interests}")
            return state

        else:
            # Could not extract interests - that's okay, move on
            state["confirmed_interests"] = ["general topics"]
            state["current_phase"] = AgentPhase.ASSESSMENT

            response = (
                "No worries! We can chat about all sorts of things. "
                "Let me get a sense of your English level first. "
                "I'll ask you a few questions - just answer naturally!"
            )

            state["pending_response"] = response
            state["needs_user_input"] = True

            pedagogy.log_interests_detected(
                user_id=state["user_id"],
                interests=["general topics"],
                source="default",
            )
            pedagogy.log_phase_transition(
                user_id=state["user_id"],
                from_phase="interest_probe",
                to_phase="assessment",
                reason="interests_defaulted",
            )

            add_decision_log(
                state,
                node="interest_probe",
                action="interests_defaulted",
                reason="Could not extract specific interests",
            )

            logger.info(f"[InterestProbe] Using default interests")
            return state

    # Fallback
    state["needs_user_input"] = True
    return state


async def _extract_interests(llm, message: str) -> list[str]:
    """Use LLM to extract interests from user message.

    Args:
        llm: LLM provider instance
        message: User's message

    Returns:
        List of extracted interests
    """
    try:
        prompt = INTEREST_EXTRACTION_PROMPT.format(message=message)

        response = await llm.generate(
            user_message=message,
            system_prompt=prompt,
            max_tokens=100,
        )

        # Parse comma-separated response
        result = response.strip()
        if result == "NONE" or not result:
            return []

        interests = [i.strip() for i in result.split(",")]
        # Filter out empty strings and limit to 4 interests
        interests = [i for i in interests if i and len(i) > 1][:4]

        return interests

    except Exception as e:
        logger.warning(f"Error extracting interests: {e}")
        return []


def route_after_interest_probe(state: AgentState) -> str:
    """Conditional edge function to route after interest probe.

    Args:
        state: Current agent state

    Returns:
        Name of the next node to execute
    """
    if state.get("current_phase") == AgentPhase.ASSESSMENT:
        return "assessment"

    # Stay in interest probe if not done
    return "interest_probe"
