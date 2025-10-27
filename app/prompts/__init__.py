"""
Модуль системных промптов для English Friend.

Используется универсальный динамический промпт с подстановкой данных из PostgreSQL.
"""

from app.prompts.universal import (
    UserProfile,
    UserInterest,
    Memory,
    RecentUtterance,
    LearningProgress,
    SessionContext,
    UniversalPromptBuilder,
    build_universal_prompt
)

__all__ = [
    "UserProfile",
    "UserInterest",
    "Memory",
    "RecentUtterance",
    "LearningProgress",
    "SessionContext",
    "UniversalPromptBuilder",
    "build_universal_prompt",
]
