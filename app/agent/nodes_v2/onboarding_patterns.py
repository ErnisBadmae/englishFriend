"""Static signal patterns and constants for the onboarding node.

Pure data only: substring/regex pattern tables, baseline assessment prompts,
and token sets used by onboarding goal-brief inference and baseline
assessment. No behavior lives here — see ``onboarding.py`` for the node logic.

The canonical 3-bucket signal patterns are sourced from
``app.services.routing.goal_routing`` so the onboarding layer and the
snapshot/mission layer agree on primary context.
"""

import re

from app.services.routing.goal_routing import (
    INTERVIEW_SIGNAL_PATTERNS as _ROUTING_INTERVIEW_PATTERNS,
    PROJECT_SIGNAL_PATTERNS as _ROUTING_PROJECT_PATTERNS,
    WORKPLACE_SIGNAL_PATTERNS as _ROUTING_WORKPLACE_PATTERNS,
)

_ML_SIGNAL_PATTERNS = (
    "machine learning",
    "ml",
    "artificial intelligence",
    " ai ",
    "model",
    "models",
    "dataset",
    "feature engineering",
    "neural",
)
_JOB_SIGNAL_PATTERNS = (
    "job",
    "work",
    "career",
    "abroad",
    "international",
    "western",
    "remote",
    "company",
)
# Canonical signal patterns live in app.services.routing.goal_routing so the
# onboarding layer and the snapshot/mission layer agree on primary context.
_INTERVIEW_SIGNAL_PATTERNS = _ROUTING_INTERVIEW_PATTERNS
_PROJECT_SIGNAL_PATTERNS = _ROUTING_PROJECT_PATTERNS
_WORKPLACE_SIGNAL_PATTERNS = _ROUTING_WORKPLACE_PATTERNS
_VOCAB_SIGNAL_PATTERNS = (
    "vocabulary",
    "words",
    "terminology",
)
_FLEXIBLE_COMPANY_CONTEXT_PATTERNS = (
    "doesnt matter",
    "does not matter",
    "dont care",
    "do not care",
    "whatever",
    "any company",
    "no matter",
)
_FORCE_ROUTE_AFTER_GOAL_TURNS = 3
_TURN_ANALYZER_MIN_CONFIDENCE = 0.7
_STT_NOISE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("intarview", "interview"),
    ("intarviews", "interviews"),
    ("practis", "practice"),
    ("practise", "practice"),
    ("prepear", "prepare"),
    ("preparashon", "preparation"),
    ("injineer", "engineer"),
    ("pozishon", "position"),
    ("abrod", "abroad"),
    ("jab", "job"),
    ("teknikal", "technical"),
    ("teknical", "technical"),
    ("internashenal", "international"),
    ("compny", "company"),
)
_CORRECTION_CUE_PATTERNS = (
    "actually",
    "instead",
    "change it",
    "change the draft",
    "change my goal",
    "not interviews",
    "not interview",
    "not project",
    "not project walkthrough",
    "not workplace",
    "not workplace communication",
    "rather than",
    "instead of",
)
_CONTEXT_NEGATION_PATTERNS: dict[str, tuple[str, ...]] = {
    "interviews": (
        "not interview",
        "not interviews",
        "instead of interview",
        "instead of interviews",
    ),
    "project_walkthrough": (
        "not project",
        "not projects",
        "not project walkthrough",
        "instead of project",
        "instead of projects",
    ),
    "workplace_communication": (
        "not workplace",
        "not workplace communication",
        "not team meetings",
        "instead of workplace",
        "instead of team meetings",
    ),
}
_ROLE_DOMAIN_PATTERNS: tuple[tuple[str, str, str], ...] = (
    ("applied scientist", "Applied Scientist", "machine_learning"),
    ("research scientist", "Research Scientist", "machine_learning"),
    ("phd student", "Researcher", "machine_learning"),
    ("researcher", "Researcher", "machine_learning"),
    ("data scientist", "Data Scientist", "data_science"),
    ("data science", "Data Scientist", "data_science"),
    ("data engineer", "Data Engineer", "data_engineering"),
    ("analytics engineer", "Analytics Engineer", "data_engineering"),
    ("mlops engineer", "MLOps Engineer", "mlops"),
    ("mlops", "MLOps Engineer", "mlops"),
    ("devops engineer", "DevOps Engineer", "devops"),
    ("devops", "DevOps Engineer", "devops"),
    ("sre", "SRE Engineer", "devops"),
    ("site reliability engineer", "SRE Engineer", "devops"),
    ("backend engineer", "Backend Engineer", "software_engineering"),
    ("frontend engineer", "Frontend Engineer", "software_engineering"),
    ("software engineer", "Software Engineer", "software_engineering"),
    ("team lead", "Team Lead", "software_engineering"),
    ("tech lead", "Tech Lead", "software_engineering"),
    ("product manager", "Product Manager", "product_management"),
    ("freelancer", "Freelancer", "professional_services"),
    ("machine learning engineer", "ML Engineer", "machine_learning"),
    ("ml engineer", "ML Engineer", "machine_learning"),
    ("ai engineer", "ML Engineer", "machine_learning"),
)
_PROCEED_PATTERNS = (
    "let's go",
    "lets go",
    "go on",
    "continue",
    "prepare my program",
    "build my program",
    "waiting that you",
    "just tell",
    "start now",
)
_LOW_SIGNAL_PATTERNS = (
    "i don't know",
    "i dont know",
    "my english is weak",
    "my english is bad",
    "hard for me",
    "i cannot say",
)
_BASELINE_PROMPTS: list[tuple[str, str]] = [
    ("current_role", "What do you do now? You can answer in simple English or mixed Russian and English."),
    ("target_role", "What role do you want next: ML engineer, data scientist, or software engineer?"),
    ("project_task", "Tell me about one ML or work task in simple words."),
]
_ASSESSMENT_FILLER_TOKENS = {
    "a",
    "ah",
    "an",
    "and",
    "as",
    "at",
    "eh",
    "erm",
    "hmm",
    "i",
    "im",
    "is",
    "just",
    "let",
    "lets",
    "like",
    "mean",
    "mm",
    "my",
    "no",
    "now",
    "of",
    "ok",
    "okay",
    "please",
    "say",
    "sorry",
    "test",
    "the",
    "to",
    "uh",
    "um",
    "well",
    "yeah",
    "yes",
    "you",
    "your",
}
_ASSESSMENT_NUMBER_WORDS = {
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
}
_CURRENT_ROLE_PATTERNS = (
    "i work",
    "i am",
    "my role",
    "data analyst",
    "data scientist",
    "ml engineer",
    "engineer",
    "scientist",
    "analyst",
    "developer",
    "researcher",
    "manager",
    "intern",
    "build",
    "built",
    "working on",
)
_NO_CURRENT_ROLE_PATTERNS = (
    "dont work now",
    "don't work now",
    "don t work now",
    "not working now",
    "i am not working",
    "im not working",
    "between jobs",
    "looking for my first role",
    "student now",
)
_TARGET_ROLE_PATTERNS = (
    "ml engineer",
    "machine learning engineer",
    "mlops engineer",
    "data engineer",
    "data scientist",
    "software engineer",
    "backend engineer",
    "frontend engineer",
    "devops engineer",
    "sre",
    "team lead",
    "tech lead",
    "product manager",
    "researcher",
    "freelancer",
    "developer",
    "scientist",
    "engineer",
    "analyst",
)
_PROJECT_TASK_PATTERNS = (
    "project",
    "task",
    "model",
    "models",
    "prediction",
    "recommendation",
    "recommender",
    "churn",
    "fraud",
    "pipeline",
    "dataset",
    "feature",
    "classification",
    "training",
    "recall",
    "precision",
    "e commerce",
    "ecommerce",
)
_FUTURE_ROLE_PATTERNS = (
    "want",
    "want to",
    "want next",
    "next role",
    "become",
    "looking for",
    "job abroad",
    "role abroad",
)
_ASSESSMENT_AFFIRMATION_PREFIX_RE = re.compile(r"^(yes|yeah|yep|ok|okay|sure)\b[\s,:.-]*")
