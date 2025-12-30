"""Генератор системных промптов для AI-ментора.

Создаёт персонализированный промпт на основе:
- Профиля пользователя
- Интересов (из PostgreSQL)
- Памяти прошлых разговоров
- Известных ошибок и проблем
"""

from dataclasses import dataclass
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.memory_and_interests import UserInterestService, MemoryService
from app.models.enums_and_dimensions import MemoryKind


@dataclass
class UserContext:
    """Контекст пользователя для промпта."""
    user_id: int
    username: str
    language_level: str = "B1"  # CEFR уровень
    interests: list[str] | None = None
    recent_memories: list[str] | None = None
    recent_errors: list[str] | None = None


MENTOR_SYSTEM_PROMPT = """You are English Friend - a warm and friendly AI English tutor in a Telegram voice chat.

## Student Profile
- Name: {username}
- Level: {language_level} (CEFR)
- Interests: {interests}
{memory_section}
{errors_section}

## Communication Rules
1. Keep responses SHORT (2-3 sentences max) - this is a voice conversation!
2. Speak naturally, like a friendly native speaker
3. Ask follow-up questions to keep the conversation going
4. Adapt vocabulary to the student's level

## Error Correction Style
- Minor errors: Note mentally, summarize corrections at the end of session
- Significant errors: Gently rephrase in your response
  Example: If student says "I goed to store", respond: "Oh, you WENT to the store! What did you buy?"
- NEVER interrupt or be pedantic - keep it natural and encouraging

## Conversation Starters (if student seems stuck)
- Ask about their day or weekend plans
- Discuss their interests: {interests}
- Ask about recent news or movies
{memory_prompts}

## Response Format
- Use contractions: "I'm", "you're", "don't"
- Include filler words naturally: "Well...", "So...", "Actually..."
- Express enthusiasm: "That's interesting!", "Oh really?"
- NEVER use bullet points or lists in speech

Remember: You're having a casual voice conversation, not writing an essay!
"""


async def build_mentor_prompt(
    db: AsyncSession,
    user_context: UserContext,
) -> str:
    """
    Построить персонализированный промпт для ментора.

    Args:
        db: Сессия базы данных
        user_context: Базовый контекст пользователя

    Returns:
        Готовый системный промпт
    """
    # Загружаем интересы из БД если не переданы
    if user_context.interests is None:
        interest_service = UserInterestService(db)
        interests = await interest_service.get_top_interests(user_context.user_id, limit=5)
        user_context.interests = [i.topic_id for i in interests] if interests else ["general topics"]

    # Загружаем недавние воспоминания
    if user_context.recent_memories is None:
        memory_service = MemoryService(db)
        memories = await memory_service.get_user_memories(
            user_context.user_id,
            kind=MemoryKind.FACT,
            limit=5
        )
        user_context.recent_memories = [m.content for m in memories] if memories else []

    # Загружаем недавние ошибки (используем SEMANTIC с metadata фильтром в будущем)
    if user_context.recent_errors is None:
        memory_service = MemoryService(db)
        errors = await memory_service.get_user_memories(
            user_context.user_id,
            kind=MemoryKind.ERROR_PATTERN,  # Будет добавлено в миграции 008
            limit=3
        )
        user_context.recent_errors = [e.content for e in errors] if errors else []

    # Форматируем секции промпта
    interests_str = ", ".join(user_context.interests) if user_context.interests else "general topics"

    memory_section = ""
    if user_context.recent_memories:
        memory_section = "\n## What you remember about this student\n"
        memory_section += "\n".join(f"- {m}" for m in user_context.recent_memories[:5])

    errors_section = ""
    if user_context.recent_errors:
        errors_section = "\n## Known issues to watch for\n"
        errors_section += "\n".join(f"- {e}" for e in user_context.recent_errors[:3])

    memory_prompts = ""
    if user_context.recent_memories:
        memory_prompts = "\n- Reference past conversations: " + user_context.recent_memories[0][:50] + "..."

    return MENTOR_SYSTEM_PROMPT.format(
        username=user_context.username,
        language_level=user_context.language_level,
        interests=interests_str,
        memory_section=memory_section,
        errors_section=errors_section,
        memory_prompts=memory_prompts,
    )


def build_simple_prompt(username: str = "Student", level: str = "B1") -> str:
    """
    Построить простой промпт без контекста из БД.

    Используется для быстрого старта или когда БД недоступна.
    """
    return MENTOR_SYSTEM_PROMPT.format(
        username=username,
        language_level=level,
        interests="general topics, travel, technology",
        memory_section="",
        errors_section="",
        memory_prompts="",
    )
