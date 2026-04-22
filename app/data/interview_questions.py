"""Curated interview question bank for each track.

Questions are ordered easy → medium → hard within each track.
Used by select_questions_for_track to build session question sets.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

INTERVIEW_QUESTIONS: list[dict[str, Any]] = [
    # -------------------------------------------------------------------------
    # hr_intro
    # -------------------------------------------------------------------------
    {
        "id": "hr_01",
        "track_id": "hr_intro",
        "prompt": "Tell me about yourself and why this role is the right next step for you.",
        "follow_up_prompts": [
            "What specific experience makes you a strong fit?",
            "What would you want to accomplish in your first 90 days?",
        ],
        "difficulty": "easy",
        "tags": ["introduction", "motivation"],
        "evaluation_focus": ["structure", "confidence"],
    },
    {
        "id": "hr_02",
        "track_id": "hr_intro",
        "prompt": "What are your top two professional strengths, and how have you used them recently?",
        "follow_up_prompts": [
            "Can you give a specific example where that strength made a real difference?",
            "How do teammates usually notice that strength in you?",
        ],
        "difficulty": "easy",
        "tags": ["strengths", "self-awareness"],
        "evaluation_focus": ["clarity", "structure"],
    },
    {
        "id": "hr_03",
        "track_id": "hr_intro",
        "prompt": "Why are you looking to leave your current role?",
        "follow_up_prompts": [
            "What are you hoping to find that your current role doesn't offer?",
            "How did you decide this company is the right direction?",
        ],
        "difficulty": "easy",
        "tags": ["motivation", "career-change"],
        "evaluation_focus": ["clarity", "confidence"],
    },
    {
        "id": "hr_04",
        "track_id": "hr_intro",
        "prompt": "Describe a situation where you had to meet a tight deadline. What did you do?",
        "follow_up_prompts": [
            "What was the result, and what would you do differently?",
            "How did you prioritize tasks under that pressure?",
        ],
        "difficulty": "medium",
        "tags": ["STAR", "pressure", "delivery"],
        "evaluation_focus": ["structure", "accuracy"],
    },
    {
        "id": "hr_05",
        "track_id": "hr_intro",
        "prompt": "Tell me about a time you disagreed with your manager. How did you handle it?",
        "follow_up_prompts": [
            "What was the outcome?",
            "Would you approach it differently today?",
        ],
        "difficulty": "medium",
        "tags": ["STAR", "conflict", "communication"],
        "evaluation_focus": ["structure", "confidence", "vocabulary"],
    },
    {
        "id": "hr_06",
        "track_id": "hr_intro",
        "prompt": "Give me an example of when you had to collaborate closely with someone very different from you.",
        "follow_up_prompts": [
            "What was challenging about the collaboration?",
            "What did you learn from working with that person?",
        ],
        "difficulty": "medium",
        "tags": ["STAR", "teamwork", "collaboration"],
        "evaluation_focus": ["structure", "clarity"],
    },
    {
        "id": "hr_07",
        "track_id": "hr_intro",
        "prompt": "Tell me about a time you took ownership of something that was not technically your responsibility.",
        "follow_up_prompts": [
            "What motivated you to step up?",
            "How did it affect the team or the project?",
        ],
        "difficulty": "medium",
        "tags": ["STAR", "ownership", "initiative"],
        "evaluation_focus": ["structure", "vocabulary", "confidence"],
    },
    {
        "id": "hr_08",
        "track_id": "hr_intro",
        "prompt": "What is your biggest professional failure, and what did you learn from it?",
        "follow_up_prompts": [
            "How did you communicate that failure to stakeholders?",
            "What would you do differently if you faced the same situation today?",
        ],
        "difficulty": "hard",
        "tags": ["STAR", "failure", "growth"],
        "evaluation_focus": ["structure", "accuracy", "confidence"],
    },
    {
        "id": "hr_09",
        "track_id": "hr_intro",
        "prompt": "Describe a time when you had to influence a decision without having formal authority.",
        "follow_up_prompts": [
            "What approach did you use to get buy-in?",
            "What was the final decision and how did it turn out?",
        ],
        "difficulty": "hard",
        "tags": ["STAR", "influence", "leadership"],
        "evaluation_focus": ["vocabulary", "structure", "clarity"],
    },
    {
        "id": "hr_10",
        "track_id": "hr_intro",
        "prompt": "Where do you see yourself in three years, and how does this role fit that path?",
        "follow_up_prompts": [
            "What skills are you actively developing right now?",
            "What kind of problems do you want to be solving then?",
        ],
        "difficulty": "medium",
        "tags": ["motivation", "career-path"],
        "evaluation_focus": ["clarity", "confidence"],
    },
    {
        "id": "hr_11",
        "track_id": "hr_intro",
        "prompt": "Tell me about a time you received difficult feedback. How did you respond?",
        "follow_up_prompts": [
            "Did you agree with the feedback? Why or why not?",
            "What changed in your work after receiving it?",
        ],
        "difficulty": "medium",
        "tags": ["STAR", "feedback", "growth"],
        "evaluation_focus": ["structure", "accuracy"],
    },
    {
        "id": "hr_12",
        "track_id": "hr_intro",
        "prompt": "What motivates you more — working on a well-defined project or exploring an ambiguous problem?",
        "follow_up_prompts": [
            "Can you give an example from your recent work?",
            "How do you keep yourself productive when requirements are unclear?",
        ],
        "difficulty": "easy",
        "tags": ["self-awareness", "work-style"],
        "evaluation_focus": ["clarity", "vocabulary"],
    },
    {
        "id": "hr_13",
        "track_id": "hr_intro",
        "prompt": "Tell me about a project where things did not go as planned. What did you do?",
        "follow_up_prompts": [
            "How did you communicate the situation to your team?",
            "What was the final outcome?",
        ],
        "difficulty": "medium",
        "tags": ["STAR", "problem-solving", "resilience"],
        "evaluation_focus": ["structure", "clarity"],
    },
    {
        "id": "hr_14",
        "track_id": "hr_intro",
        "prompt": "How do you handle competing priorities when multiple urgent tasks appear at the same time?",
        "follow_up_prompts": [
            "Walk me through a recent example.",
            "How do you communicate when something must be deprioritized?",
        ],
        "difficulty": "medium",
        "tags": ["prioritization", "communication"],
        "evaluation_focus": ["structure", "confidence"],
    },
    {
        "id": "hr_15",
        "track_id": "hr_intro",
        "prompt": "Tell me about the most impactful project you delivered and why it mattered.",
        "follow_up_prompts": [
            "What was your specific role and contribution?",
            "How did you measure the impact?",
        ],
        "difficulty": "hard",
        "tags": ["STAR", "impact", "leadership"],
        "evaluation_focus": ["structure", "vocabulary", "clarity"],
    },

    # -------------------------------------------------------------------------
    # project_walkthrough
    # -------------------------------------------------------------------------
    {
        "id": "pw_01",
        "track_id": "project_walkthrough",
        "prompt": "Walk me through one project you are proud of and explain your role in it.",
        "follow_up_prompts": [
            "What was the core technical challenge you solved?",
            "What would you do differently if you started over today?",
        ],
        "difficulty": "easy",
        "tags": ["overview", "role", "contribution"],
        "evaluation_focus": ["clarity", "structure"],
    },
    {
        "id": "pw_02",
        "track_id": "project_walkthrough",
        "prompt": "Describe the tech stack you chose for a recent project and why you chose it.",
        "follow_up_prompts": [
            "What alternatives did you consider?",
            "Were there any limitations of your choice that appeared later?",
        ],
        "difficulty": "easy",
        "tags": ["tech-stack", "decision-making"],
        "evaluation_focus": ["vocabulary", "clarity"],
    },
    {
        "id": "pw_03",
        "track_id": "project_walkthrough",
        "prompt": "Explain the most important technical decision you made on a recent project.",
        "follow_up_prompts": [
            "What were the trade-offs you considered?",
            "What was the business or team impact of that decision?",
        ],
        "difficulty": "medium",
        "tags": ["trade-off", "decision-making", "architecture"],
        "evaluation_focus": ["vocabulary", "structure", "clarity"],
    },
    {
        "id": "pw_04",
        "track_id": "project_walkthrough",
        "prompt": "Tell me about a time you had to optimize something for performance. What was your approach?",
        "follow_up_prompts": [
            "How did you measure the improvement?",
            "What bottlenecks did you identify first?",
        ],
        "difficulty": "medium",
        "tags": ["performance", "optimization", "metrics"],
        "evaluation_focus": ["vocabulary", "accuracy"],
    },
    {
        "id": "pw_05",
        "track_id": "project_walkthrough",
        "prompt": "Describe a system you designed from scratch. Walk me through the architecture.",
        "follow_up_prompts": [
            "How did you handle scalability concerns?",
            "What would you change about the design now?",
        ],
        "difficulty": "hard",
        "tags": ["architecture", "design", "scalability"],
        "evaluation_focus": ["vocabulary", "clarity", "structure"],
    },
    {
        "id": "pw_06",
        "track_id": "project_walkthrough",
        "prompt": "Tell me about a time a technical project failed or underperformed. What happened?",
        "follow_up_prompts": [
            "What was the root cause?",
            "What did you learn and apply to later work?",
        ],
        "difficulty": "medium",
        "tags": ["failure", "learning", "debugging"],
        "evaluation_focus": ["structure", "accuracy"],
    },
    {
        "id": "pw_07",
        "track_id": "project_walkthrough",
        "prompt": "How did you ensure the quality and reliability of a system you built?",
        "follow_up_prompts": [
            "What testing strategy did you use?",
            "How did you handle production incidents?",
        ],
        "difficulty": "medium",
        "tags": ["reliability", "testing", "quality"],
        "evaluation_focus": ["vocabulary", "clarity"],
    },
    {
        "id": "pw_08",
        "track_id": "project_walkthrough",
        "prompt": "Describe a time when you had to integrate with an external API or third-party system.",
        "follow_up_prompts": [
            "What challenges did you face?",
            "How did you handle failures or rate limits?",
        ],
        "difficulty": "easy",
        "tags": ["integration", "API", "external-systems"],
        "evaluation_focus": ["vocabulary", "clarity"],
    },
    {
        "id": "pw_09",
        "track_id": "project_walkthrough",
        "prompt": "Walk me through how you approached a complex data pipeline or data processing task.",
        "follow_up_prompts": [
            "How did you validate the output?",
            "What was the latency or throughput target?",
        ],
        "difficulty": "medium",
        "tags": ["data-pipeline", "architecture", "throughput"],
        "evaluation_focus": ["vocabulary", "structure"],
    },
    {
        "id": "pw_10",
        "track_id": "project_walkthrough",
        "prompt": "Tell me about a refactoring effort you led or contributed to. What drove the decision?",
        "follow_up_prompts": [
            "How did you convince others it was worth the investment?",
            "What was the before and after state?",
        ],
        "difficulty": "medium",
        "tags": ["refactoring", "technical-debt", "communication"],
        "evaluation_focus": ["vocabulary", "structure"],
    },
    {
        "id": "pw_11",
        "track_id": "project_walkthrough",
        "prompt": "How did you handle a situation where business requirements changed significantly mid-project?",
        "follow_up_prompts": [
            "How did you communicate the impact to stakeholders?",
            "What technical decisions had to change?",
        ],
        "difficulty": "hard",
        "tags": ["requirements-change", "stakeholders", "adaptability"],
        "evaluation_focus": ["vocabulary", "clarity", "confidence"],
    },
    {
        "id": "pw_12",
        "track_id": "project_walkthrough",
        "prompt": "Describe a project where you had to balance technical correctness with delivery speed.",
        "follow_up_prompts": [
            "What trade-offs did you make?",
            "Did you accumulate technical debt, and how did you plan to address it?",
        ],
        "difficulty": "hard",
        "tags": ["trade-off", "delivery", "technical-debt"],
        "evaluation_focus": ["vocabulary", "structure", "clarity"],
    },
    {
        "id": "pw_13",
        "track_id": "project_walkthrough",
        "prompt": "Tell me about a time you had to debug a critical production issue. Walk me through your process.",
        "follow_up_prompts": [
            "How long did it take, and what was the root cause?",
            "What did you do to prevent a recurrence?",
        ],
        "difficulty": "medium",
        "tags": ["debugging", "production", "incident"],
        "evaluation_focus": ["structure", "vocabulary"],
    },
    {
        "id": "pw_14",
        "track_id": "project_walkthrough",
        "prompt": "How do you communicate a complex technical concept to a non-technical stakeholder?",
        "follow_up_prompts": [
            "Can you walk me through a real example?",
            "How do you adjust when they do not understand?",
        ],
        "difficulty": "medium",
        "tags": ["communication", "stakeholders", "explanation"],
        "evaluation_focus": ["clarity", "vocabulary"],
    },
    {
        "id": "pw_15",
        "track_id": "project_walkthrough",
        "prompt": "What is the most technically challenging problem you have solved, and why was it hard?",
        "follow_up_prompts": [
            "What approaches did you try before finding the solution?",
            "What was the measurable outcome?",
        ],
        "difficulty": "hard",
        "tags": ["challenge", "problem-solving", "impact"],
        "evaluation_focus": ["vocabulary", "structure", "clarity"],
    },

    # -------------------------------------------------------------------------
    # workplace_communication
    # -------------------------------------------------------------------------
    {
        "id": "wc_01",
        "track_id": "workplace_communication",
        "prompt": "Give me your standup update right now: what did you finish, what is next, what is blocked?",
        "follow_up_prompts": [
            "Can you be more specific about the blocker?",
            "What is your plan to unblock that today?",
        ],
        "difficulty": "easy",
        "tags": ["standup", "update", "conciseness"],
        "evaluation_focus": ["clarity", "structure"],
    },
    {
        "id": "wc_02",
        "track_id": "workplace_communication",
        "prompt": "How would you tell your team that you missed a deadline?",
        "follow_up_prompts": [
            "What would you say first — the problem or the plan?",
            "How do you keep the tone professional and forward-looking?",
        ],
        "difficulty": "easy",
        "tags": ["ownership", "communication", "accountability"],
        "evaluation_focus": ["clarity", "confidence", "vocabulary"],
    },
    {
        "id": "wc_03",
        "track_id": "workplace_communication",
        "prompt": "Describe how you would give feedback to a teammate whose code quality is inconsistent.",
        "follow_up_prompts": [
            "How would you frame it so it is constructive?",
            "What if they push back or disagree?",
        ],
        "difficulty": "medium",
        "tags": ["feedback", "collaboration", "communication"],
        "evaluation_focus": ["vocabulary", "accuracy", "clarity"],
    },
    {
        "id": "wc_04",
        "track_id": "workplace_communication",
        "prompt": "How do you explain a technical delay to a non-technical stakeholder?",
        "follow_up_prompts": [
            "What language do you avoid?",
            "How do you give a realistic timeline without overpromising?",
        ],
        "difficulty": "medium",
        "tags": ["stakeholders", "communication", "estimation"],
        "evaluation_focus": ["vocabulary", "clarity"],
    },
    {
        "id": "wc_05",
        "track_id": "workplace_communication",
        "prompt": "Tell me about a time when communication broke down on your team. What happened?",
        "follow_up_prompts": [
            "What caused the breakdown?",
            "What did you change afterward to prevent it?",
        ],
        "difficulty": "medium",
        "tags": ["communication-failure", "teamwork", "retrospective"],
        "evaluation_focus": ["structure", "clarity"],
    },
    {
        "id": "wc_06",
        "track_id": "workplace_communication",
        "prompt": "Walk me through how you would run a short retrospective after a sprint that went badly.",
        "follow_up_prompts": [
            "How do you keep it from becoming a blame session?",
            "What action items would you close with?",
        ],
        "difficulty": "medium",
        "tags": ["retrospective", "facilitation", "team-dynamics"],
        "evaluation_focus": ["vocabulary", "structure"],
    },
    {
        "id": "wc_07",
        "track_id": "workplace_communication",
        "prompt": "How do you handle a situation where another team's dependency is blocking your work?",
        "follow_up_prompts": [
            "How quickly do you escalate, and to whom?",
            "What do you say in the Slack message or email?",
        ],
        "difficulty": "medium",
        "tags": ["blockers", "cross-team", "escalation"],
        "evaluation_focus": ["vocabulary", "clarity", "confidence"],
    },
    {
        "id": "wc_08",
        "track_id": "workplace_communication",
        "prompt": "Describe how you would write an update email to your manager after completing a major milestone.",
        "follow_up_prompts": [
            "What key points would you include?",
            "How long should it be?",
        ],
        "difficulty": "easy",
        "tags": ["written-communication", "reporting", "update"],
        "evaluation_focus": ["clarity", "vocabulary"],
    },
    {
        "id": "wc_09",
        "track_id": "workplace_communication",
        "prompt": "How do you push back on a feature request you think is a bad idea without damaging the relationship?",
        "follow_up_prompts": [
            "What is your opening line?",
            "What if the stakeholder insists anyway?",
        ],
        "difficulty": "hard",
        "tags": ["pushback", "influence", "stakeholders"],
        "evaluation_focus": ["vocabulary", "confidence", "clarity"],
    },
    {
        "id": "wc_10",
        "track_id": "workplace_communication",
        "prompt": "Tell me how you would onboard a new engineer to a codebase you own.",
        "follow_up_prompts": [
            "What documentation would you prepare?",
            "How would you pace the ramp-up?",
        ],
        "difficulty": "medium",
        "tags": ["onboarding", "knowledge-transfer", "mentoring"],
        "evaluation_focus": ["vocabulary", "clarity"],
    },
    {
        "id": "wc_11",
        "track_id": "workplace_communication",
        "prompt": "Describe how you would request additional resources or headcount for your team.",
        "follow_up_prompts": [
            "What data or evidence would you use?",
            "How do you frame the business case?",
        ],
        "difficulty": "hard",
        "tags": ["stakeholders", "negotiation", "business-case"],
        "evaluation_focus": ["vocabulary", "clarity", "confidence"],
    },
    {
        "id": "wc_12",
        "track_id": "workplace_communication",
        "prompt": "How do you make sure your async updates — Slack messages, PRs, tickets — keep the team unblocked?",
        "follow_up_prompts": [
            "What do you include in a good PR description?",
            "How do you handle no responses in a timely manner?",
        ],
        "difficulty": "medium",
        "tags": ["async-communication", "async-work", "PR-culture"],
        "evaluation_focus": ["vocabulary", "clarity"],
    },
    {
        "id": "wc_13",
        "track_id": "workplace_communication",
        "prompt": "Tell me about a time you successfully advocated for a technical approach in a meeting.",
        "follow_up_prompts": [
            "How did you prepare your argument?",
            "What objections did you face?",
        ],
        "difficulty": "hard",
        "tags": ["advocacy", "technical-decision", "meeting"],
        "evaluation_focus": ["confidence", "vocabulary", "structure"],
    },
    {
        "id": "wc_14",
        "track_id": "workplace_communication",
        "prompt": "How do you keep a project status clear to everyone involved when things are uncertain?",
        "follow_up_prompts": [
            "How often do you send updates?",
            "What format works best in your experience?",
        ],
        "difficulty": "medium",
        "tags": ["project-status", "transparency", "communication"],
        "evaluation_focus": ["clarity", "vocabulary"],
    },
    {
        "id": "wc_15",
        "track_id": "workplace_communication",
        "prompt": "Describe a time when you had to coordinate work across multiple teams with different priorities.",
        "follow_up_prompts": [
            "How did you align on a shared timeline?",
            "What communication patterns kept things moving?",
        ],
        "difficulty": "hard",
        "tags": ["cross-team", "coordination", "alignment"],
        "evaluation_focus": ["vocabulary", "structure", "clarity"],
    },
]

_TRACK_QUESTION_INDEX: dict[str, list[dict[str, Any]]] = {}
for _q in INTERVIEW_QUESTIONS:
    _TRACK_QUESTION_INDEX.setdefault(_q["track_id"], []).append(_q)


def select_questions_for_track(
    track_id: str,
    limit: int = 4,
    skip_ids: list[str] | None = None,
    session_seed: str | None = None,
) -> list[dict[str, Any]]:
    """Select questions for a session, starting easy and progressing to harder.

    Args:
        track_id: Interview track identifier.
        limit: Maximum number of questions to return.
        skip_ids: Question IDs to skip (used recently — encourage rotation).
        session_seed: String seed for deterministic shuffle within a session.

    Returns:
        Ordered list of question dicts (easy → medium → hard).
    """
    all_questions = _TRACK_QUESTION_INDEX.get(track_id, [])
    if not all_questions:
        return []

    candidates = all_questions
    if skip_ids:
        filtered = [q for q in candidates if q["id"] not in skip_ids]
        if len(filtered) >= limit:
            candidates = filtered
        # else fall back to full set to avoid empty result

    rng = random.Random()
    if session_seed:
        seed_int = int(hashlib.md5(session_seed.encode()).hexdigest(), 16) % (2 ** 31)
        rng.seed(seed_int)

    by_difficulty: dict[str, list[dict[str, Any]]] = {"easy": [], "medium": [], "hard": []}
    for q in candidates:
        by_difficulty.setdefault(q.get("difficulty", "medium"), []).append(q)

    for group in by_difficulty.values():
        rng.shuffle(group)

    selected: list[dict[str, Any]] = []
    for diff in ("easy", "medium", "hard"):
        for q in by_difficulty.get(diff, []):
            if len(selected) >= limit:
                break
            selected.append(q)
        if len(selected) >= limit:
            break

    return selected
