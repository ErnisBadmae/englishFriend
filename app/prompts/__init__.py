"""
Модуль системных промптов для English Friend.

Используется универсальный динамический промпт с подстановкой данных из PostgreSQL.
"""

from app.prompts.universal import (
    PromptMode,
    UserProfile,
    UserInterest,
    Memory,
    RecentUtterance,
    LearningProgress,
    SessionContext,
    UniversalPromptBuilder,
    determine_prompt_mode,
    build_universal_prompt
)

__all__ = [
    "PromptMode",
    "UserProfile",
    "UserInterest",
    "Memory",
    "RecentUtterance",
    "LearningProgress",
    "SessionContext",
    "UniversalPromptBuilder",
    "determine_prompt_mode",
    "build_universal_prompt",
]
