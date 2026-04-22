"""Program Build Node - creates personalized learning roadmap.

This node creates a learning program based on:
- Confirmed goal
- Confirmed interests
- Assessed level

The roadmap includes milestones, recommended vocabulary, and focus areas.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Any

from app.agent.state import AgentState, AgentPhase, add_decision_log
from app.services.pedagogy_logger import get_pedagogy_logger
from app.services.ai.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)

# Roadmap templates by goal
ROADMAP_TEMPLATES = {
    "ML/Data Science Interview Preparation": {
        "focus_areas": [
            {"area": "technical_vocabulary", "description": "ML terms and concepts"},
            {"area": "behavioral_questions", "description": "STAR method answers"},
            {"area": "explain_concepts", "description": "Simplifying complex ideas"},
            {"area": "project_walkthrough", "description": "Describing your work"},
        ],
        "milestones": [
            {"name": "Master 50 ML terms", "type": "vocabulary", "target": 50},
            {"name": "Complete 5 mock interviews", "type": "mock_interview", "target": 5},
            {"name": "Practice STAR method", "type": "skill"},
            {"name": "System design explanations", "type": "skill"},
        ],
        "recommended_vocabulary": [
            "implementation", "deployment", "inference", "training", "validation",
            "feature engineering", "cross-validation", "hyperparameter", "overfitting",
            "precision", "recall", "accuracy", "pipeline", "scalability", "optimization",
            "architecture", "framework", "algorithm", "dataset", "preprocessing",
        ],
        "preferred_mode": "mock_interview",
    },
    "Software Engineering Interview Preparation": {
        "focus_areas": [
            {"area": "technical_discussion", "description": "System design, algorithms"},
            {"area": "behavioral_questions", "description": "Team collaboration stories"},
            {"area": "code_explanation", "description": "Walking through your code"},
        ],
        "milestones": [
            {"name": "Master 40 tech terms", "type": "vocabulary", "target": 40},
            {"name": "Complete 5 mock interviews", "type": "mock_interview", "target": 5},
            {"name": "System design practice", "type": "skill"},
        ],
        "recommended_vocabulary": [
            "scalability", "architecture", "microservices", "deployment", "debugging",
            "refactoring", "optimization", "dependency", "integration", "abstraction",
            "inheritance", "encapsulation", "polymorphism", "asynchronous", "concurrent",
        ],
        "preferred_mode": "mock_interview",
    },
    "Job Interview Preparation": {
        "focus_areas": [
            {"area": "self_introduction", "description": "Tell me about yourself"},
            {"area": "behavioral_questions", "description": "Experience stories"},
            {"area": "professional_vocabulary", "description": "Workplace terminology"},
        ],
        "milestones": [
            {"name": "Master 30 business terms", "type": "vocabulary", "target": 30},
            {"name": "Complete 5 mock interviews", "type": "mock_interview", "target": 5},
            {"name": "Perfect self-introduction", "type": "skill"},
        ],
        "recommended_vocabulary": [
            "achievement", "responsibility", "collaboration", "deadline", "initiative",
            "leadership", "teamwork", "problem-solving", "communication", "feedback",
        ],
        "preferred_mode": "mock_interview",
    },
    "IELTS Preparation": {
        "focus_areas": [
            {"area": "speaking_fluency", "description": "Part 1, 2, 3 practice"},
            {"area": "vocabulary_range", "description": "Academic vocabulary"},
            {"area": "grammar_accuracy", "description": "Complex structures"},
        ],
        "milestones": [
            {"name": "Master 100 academic words", "type": "vocabulary", "target": 100},
            {"name": "Complete 10 speaking tests", "type": "practice", "target": 10},
            {"name": "Advanced grammar structures", "type": "skill"},
        ],
        "recommended_vocabulary": [
            "approximately", "significantly", "furthermore", "nevertheless", "consequently",
            "illustrate", "demonstrate", "analyze", "evaluate", "synthesize",
        ],
        "preferred_mode": "assessment",
    },
    "Business English": {
        "focus_areas": [
            {"area": "meetings", "description": "Participating in meetings"},
            {"area": "presentations", "description": "Giving presentations"},
            {"area": "email_communication", "description": "Professional writing"},
        ],
        "milestones": [
            {"name": "Master 50 business phrases", "type": "vocabulary", "target": 50},
            {"name": "Practice 5 presentations", "type": "practice", "target": 5},
        ],
        "recommended_vocabulary": [
            "agenda", "stakeholder", "deliverable", "ROI", "KPI",
            "synergy", "leverage", "streamline", "optimize", "implement",
        ],
        "preferred_mode": "free_conversation",
    },
    "General Fluency": {
        "focus_areas": [
            {"area": "conversation", "description": "Natural speaking flow"},
            {"area": "vocabulary", "description": "Expanding word range"},
            {"area": "grammar", "description": "Common mistake correction"},
        ],
        "milestones": [
            {"name": "Learn 100 new words", "type": "vocabulary", "target": 100},
            {"name": "Practice 10 hours", "type": "practice", "target": 600},
        ],
        "recommended_vocabulary": [],
        "preferred_mode": "free_conversation",
    },
}

# LLM prompt for generating personalized roadmap details
ROADMAP_GENERATION_PROMPT = """You are creating a personalized English learning roadmap.

Student profile:
- Name: {username}
- Goal: {goal}
- Current level: {level}
- Interests: {interests}

Based on their goal and interests, create 2-3 specific practice activities they should do.
Keep it brief and actionable.

Format:
1. [Activity name] - [Brief description]
2. [Activity name] - [Brief description]
3. [Activity name] - [Brief description]

Activities:"""


async def program_build_node(state: AgentState) -> AgentState:
    """Node that creates a personalized learning program.

    Args:
        state: Current agent state

    Returns:
        Updated agent state with roadmap
    """
    pedagogy = get_pedagogy_logger(state["user_id"])
    llm = get_llm_provider()

    goal = state.get("confirmed_goal", "General Fluency")
    level = state.get("assessed_level", state.get("language_level", "B1"))
    interests = state.get("confirmed_interests", [])
    username = state.get("username", "Student")

    # Get template for goal
    template = ROADMAP_TEMPLATES.get(goal, ROADMAP_TEMPLATES["General Fluency"])

    # Build roadmap
    roadmap = {
        "goal": goal,
        "goal_template": goal,
        "current_level": level,
        "focus_areas": template["focus_areas"],
        "milestones": [
            {**m, "progress": 0, "done": False}
            for m in template["milestones"]
        ],
        "recommended_vocabulary": template["recommended_vocabulary"],
        "preferred_mode": template["preferred_mode"],
        "interests": interests,
        "created_at": datetime.utcnow().isoformat(),
        "sessions_completed": 0,
        "total_practice_minutes": 0,
    }

    # Generate personalized activities using LLM
    try:
        activities = await _generate_activities(llm, username, goal, level, interests)
        if activities:
            roadmap["personalized_activities"] = activities
    except Exception as e:
        logger.warning(f"Could not generate personalized activities: {e}")

    # Store in state
    state["roadmap"] = roadmap
    state["focus_areas"] = [fa["area"] for fa in template["focus_areas"]]
    state["preferred_mode"] = template["preferred_mode"]
    state["current_phase"] = AgentPhase.LEARNING_SESSION

    # Create user-facing summary
    summary = _create_roadmap_summary(goal, level, template, interests, username)

    state["pending_response"] = summary
    state["needs_user_input"] = True

    pedagogy.log_phase_transition(
        user_id=state["user_id"],
        from_phase="program_build",
        to_phase="learning_session",
        reason="roadmap_created",
    )

    add_decision_log(
        state,
        node="program_build",
        action="roadmap_created",
        reason=f"Created roadmap for goal: {goal}",
        data={
            "goal": goal,
            "level": level,
            "preferred_mode": template["preferred_mode"],
            "milestones_count": len(roadmap["milestones"]),
        },
    )

    logger.info(f"[ProgramBuild] Created roadmap for user {state['user_id']}: {goal}")
    return state


async def _generate_activities(
    llm,
    username: str,
    goal: str,
    level: str,
    interests: list[str],
) -> list[str]:
    """Generate personalized practice activities using LLM.

    Args:
        llm: LLM provider instance
        username: User's name
        goal: Learning goal
        level: CEFR level
        interests: User's interests

    Returns:
        List of activity descriptions
    """
    try:
        prompt = ROADMAP_GENERATION_PROMPT.format(
            username=username,
            goal=goal,
            level=level,
            interests=", ".join(interests) if interests else "general topics",
        )

        response = await llm.generate(
            user_message=f"Goal: {goal}, Level: {level}",
            system_prompt=prompt,
            max_tokens=200,
        )

        # Parse numbered list
        activities = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                # Remove number/bullet and clean up
                activity = line.lstrip("0123456789.-) ").strip()
                if activity:
                    activities.append(activity)

        return activities[:3]  # Max 3 activities

    except Exception as e:
        logger.warning(f"Error generating activities: {e}")
        return []


def _create_roadmap_summary(
    goal: str,
    level: str,
    template: dict[str, Any],
    interests: list[str],
    username: str,
) -> str:
    """Create a user-friendly roadmap summary.

    Args:
        goal: Learning goal
        level: CEFR level
        template: Roadmap template
        interests: User's interests
        username: User's name

    Returns:
        Summary message
    """
    # Build summary
    summary = f"Perfect, {username}! Here's your personalized learning plan:\n\n"
    summary += f"Goal: {goal}\n"
    summary += f"Starting level: {level}\n\n"

    # Focus areas
    if template["focus_areas"]:
        focus_names = [fa["description"] for fa in template["focus_areas"][:3]]
        summary += f"We'll focus on: {', '.join(focus_names)}.\n\n"

    # First milestone
    if template["milestones"]:
        first_milestone = template["milestones"][0]
        summary += f"First milestone: {first_milestone['name']}.\n\n"

    summary += "Ready to start practicing? Let's go!"

    return summary


def route_after_program_build(state: AgentState) -> str:
    """Conditional edge function to route after program build.

    Args:
        state: Current agent state

    Returns:
        Name of the next node to execute
    """
    return "mode_router"
