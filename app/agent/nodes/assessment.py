"""Assessment Node - evaluates user's English level.

This node conducts an informal assessment through conversation:
1. Ask questions of increasing difficulty (A1 -> C1)
2. Evaluate responses for vocabulary, grammar, fluency
3. Determine CEFR level
4. Communicate results to user

The assessment is conversational, not test-like, to keep users comfortable.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.agent.state import AgentState, AgentPhase, add_decision_log
from app.services.pedagogy_logger import get_pedagogy_logger
from app.services.ai.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)

# Assessment questions by level
ASSESSMENT_QUESTIONS = {
    "A1": [
        "What's your name and where are you from?",
        "Tell me about your family.",
    ],
    "A2": [
        "What do you like to do in your free time?",
        "Can you describe your typical day?",
    ],
    "B1": [
        "What would you do if you won a million dollars?",
        "Tell me about a memorable trip or experience you've had.",
    ],
    "B2": [
        "What are the advantages and disadvantages of working from home?",
        "How do you think technology will change education in the future?",
    ],
    "C1": [
        "What ethical considerations should companies keep in mind when using AI?",
        "How would you explain a complex technical concept to someone without technical background?",
    ],
}

# System prompt for level assessment
LEVEL_ASSESSMENT_PROMPT = """You are evaluating a student's English proficiency based on their response.

Assessment criteria:
1. Vocabulary: Range and precision of words used (simple vs. sophisticated)
2. Grammar: Accuracy of tenses, articles, prepositions, sentence structure
3. Fluency: Natural flow and coherence of ideas
4. Comprehension: Understanding of the question asked

Question asked (target level {target_level}): "{question}"
Student's response: "{response}"

Rate each criterion from 1-5:
- 1: Beginner (A1)
- 2: Elementary (A2)
- 3: Intermediate (B1)
- 4: Upper-Intermediate (B2)
- 5: Advanced (C1)

Respond in this exact format:
vocabulary: X
grammar: X
fluency: X
comprehension: X

Scores:"""


async def assessment_node(state: AgentState) -> AgentState:
    """Node that assesses user's English level through conversation.

    Conducts a brief, informal assessment by asking 3-4 questions
    and evaluating responses.

    Args:
        state: Current agent state

    Returns:
        Updated agent state
    """
    pedagogy = get_pedagogy_logger(state["user_id"])
    llm = get_llm_provider()

    user_message = state.get("last_user_message", "")

    # Get or initialize assessment state
    assessment_state = state.get("assessment_scores", {})
    questions_asked = assessment_state.get("questions_asked", 0)
    cumulative_scores = assessment_state.get("cumulative_scores", {
        "vocabulary": [],
        "grammar": [],
        "fluency": [],
        "comprehension": [],
    })

    # Determine which level to test
    levels = ["A2", "B1", "B2", "C1"]  # Start at A2, most users aren't A1
    current_level_idx = min(questions_asked, len(levels) - 1)
    current_level = levels[current_level_idx]

    # Sub-state 1: Ask first question
    if questions_asked == 0 and not user_message:
        question = ASSESSMENT_QUESTIONS[current_level][0]

        state["pending_response"] = question
        state["needs_user_input"] = True

        assessment_state["questions_asked"] = 0
        assessment_state["current_question"] = question
        assessment_state["current_level"] = current_level
        state["assessment_scores"] = assessment_state

        pedagogy.log_assessment_started(
            user_id=state["user_id"],
            current_level=state.get("language_level"),
        )
        pedagogy.log_assessment_question(
            user_id=state["user_id"],
            question_number=1,
            target_level=current_level,
            question=question,
        )

        add_decision_log(
            state,
            node="assessment",
            action="ask_first_question",
            reason=f"Starting assessment at {current_level} level",
        )

        logger.info(f"[Assessment] Starting assessment for user {state['user_id']}")
        return state

    # Sub-state 2: Evaluate response and ask next question (or finish)
    if user_message:
        # Evaluate the response
        current_question = assessment_state.get("current_question", "")
        target_level = assessment_state.get("current_level", "B1")

        scores = await _evaluate_response(llm, current_question, user_message, target_level)

        # Add scores to cumulative
        for key in cumulative_scores:
            if key in scores:
                cumulative_scores[key].append(scores[key])

        assessment_state["cumulative_scores"] = cumulative_scores
        questions_asked += 1
        assessment_state["questions_asked"] = questions_asked

        # Decide: ask more or finish?
        if questions_asked >= 3:  # 3 questions is enough for assessment
            # Calculate final level
            final_level, confidence, avg_scores = _calculate_final_level(cumulative_scores)

            state["assessed_level"] = final_level
            state["level_confidence"] = confidence
            state["language_level"] = final_level
            state["current_phase"] = AgentPhase.PROGRAM_BUILD

            # Create assessment summary
            summary = _create_assessment_summary(final_level, avg_scores, state.get("username", ""))

            state["pending_response"] = summary
            state["needs_user_input"] = True

            pedagogy.log_level_assessed(
                user_id=state["user_id"],
                level=final_level,
                scores=avg_scores,
                confidence=confidence,
            )
            pedagogy.log_phase_transition(
                user_id=state["user_id"],
                from_phase="assessment",
                to_phase="program_build",
                reason="assessment_complete",
            )

            add_decision_log(
                state,
                node="assessment",
                action="assessment_complete",
                reason=f"Assessed level: {final_level} (confidence: {confidence:.2f})",
                data={"level": final_level, "scores": avg_scores},
            )

            logger.info(f"[Assessment] Complete. Level: {final_level}, Confidence: {confidence:.2f}")
            return state

        else:
            # Ask next question
            next_level_idx = min(questions_asked, len(levels) - 1)
            next_level = levels[next_level_idx]
            question_idx = questions_asked % len(ASSESSMENT_QUESTIONS[next_level])
            next_question = ASSESSMENT_QUESTIONS[next_level][question_idx]

            # Add a brief acknowledgment before next question
            acknowledgments = [
                "Interesting! ",
                "Great, thanks! ",
                "I see. ",
                "Got it! ",
            ]
            ack = acknowledgments[questions_asked % len(acknowledgments)]

            response = f"{ack}Now, {next_question}"

            state["pending_response"] = response
            state["needs_user_input"] = True

            assessment_state["current_question"] = next_question
            assessment_state["current_level"] = next_level
            state["assessment_scores"] = assessment_state

            pedagogy.log_assessment_question(
                user_id=state["user_id"],
                question_number=questions_asked + 1,
                target_level=next_level,
                question=next_question,
            )

            add_decision_log(
                state,
                node="assessment",
                action="ask_next_question",
                reason=f"Question {questions_asked + 1}, target level {next_level}",
            )

            logger.info(f"[Assessment] Question {questions_asked + 1}/{3}")
            return state

    # Fallback
    state["needs_user_input"] = True
    return state


async def _evaluate_response(
    llm,
    question: str,
    response: str,
    target_level: str,
) -> dict[str, float]:
    """Evaluate a student's response for language proficiency.

    Args:
        llm: LLM provider instance
        question: The question that was asked
        response: Student's response
        target_level: Target CEFR level

    Returns:
        Dictionary of scores by category
    """
    try:
        prompt = LEVEL_ASSESSMENT_PROMPT.format(
            target_level=target_level,
            question=question,
            response=response,
        )

        llm_response = await llm.generate(
            user_message=response,
            system_prompt=prompt,
            max_tokens=100,
        )

        # Parse scores
        scores = {}
        for line in llm_response.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip().lower()
                try:
                    scores[key] = float(value.strip())
                except ValueError:
                    pass

        # Ensure all categories have scores
        for key in ["vocabulary", "grammar", "fluency", "comprehension"]:
            if key not in scores:
                scores[key] = 3.0  # Default to B1

        return scores

    except Exception as e:
        logger.warning(f"Error evaluating response: {e}")
        return {"vocabulary": 3.0, "grammar": 3.0, "fluency": 3.0, "comprehension": 3.0}


def _calculate_final_level(cumulative_scores: dict) -> tuple[str, float, dict]:
    """Calculate final CEFR level from cumulative scores.

    Args:
        cumulative_scores: Dictionary of score lists by category

    Returns:
        Tuple of (level, confidence, average_scores)
    """
    # Calculate averages
    avg_scores = {}
    for key, values in cumulative_scores.items():
        if values:
            avg_scores[key] = sum(values) / len(values)
        else:
            avg_scores[key] = 3.0  # Default B1

    # Overall average
    overall = sum(avg_scores.values()) / len(avg_scores) if avg_scores else 3.0

    # Map score to CEFR level
    if overall < 1.5:
        level = "A1"
    elif overall < 2.5:
        level = "A2"
    elif overall < 3.5:
        level = "B1"
    elif overall < 4.5:
        level = "B2"
    else:
        level = "C1"

    # Confidence based on score consistency
    if avg_scores:
        variance = sum((v - overall) ** 2 for v in avg_scores.values()) / len(avg_scores)
        confidence = max(0.5, 1.0 - variance / 4)  # Higher variance = lower confidence
    else:
        confidence = 0.5

    return level, confidence, avg_scores


def _create_assessment_summary(level: str, scores: dict, username: str) -> str:
    """Create a friendly assessment summary for the user.

    Args:
        level: Assessed CEFR level
        scores: Average scores by category
        username: User's name

    Returns:
        Summary message
    """
    level_descriptions = {
        "A1": "Beginner - You're just starting your English journey",
        "A2": "Elementary - You can handle simple everyday situations",
        "B1": "Intermediate - You can handle most everyday situations well",
        "B2": "Upper-Intermediate - You can discuss complex topics fluently",
        "C1": "Advanced - You have near-native proficiency",
    }

    # Find strengths and areas to improve
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    strengths = [k.capitalize() for k, v in sorted_scores[:2] if v >= 3.0]
    improvements = [k.capitalize() for k, v in sorted_scores[-2:] if v < 4.0]

    summary = f"Based on our conversation, I'd say your level is around {level} - {level_descriptions.get(level, '')}. "

    if strengths:
        summary += f"Your strengths are {' and '.join(strengths)}. "

    if improvements and improvements != strengths:
        summary += f"To keep improving, let's focus on {' and '.join(improvements)}. "

    summary += "Now let me put together a learning plan for you!"

    return summary


def route_after_assessment(state: AgentState) -> str:
    """Conditional edge function to route after assessment.

    Args:
        state: Current agent state

    Returns:
        Name of the next node to execute
    """
    if state.get("assessed_level"):
        return "program_build"

    return "assessment"
