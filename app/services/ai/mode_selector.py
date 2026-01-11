"""Логика выбора режима обучения.

Определяет оптимальный режим сессии на основе:
- Наличия assessment (если нет - сначала оценка)
- Количества слов для повторения (FSRS)
- Цели обучения (interview → MOCK_INTERVIEW)
- Предпочтений пользователя
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

from app.services.ai.mode_prompts import LearningMode


@dataclass
class SessionContext:
    """Контекст для выбора режима сессии."""
    user_id: int
    username: str
    language_level: str = "B1"

    # Learning plan
    goal: Optional[str] = None
    focus_areas: list[str] | None = None
    preferred_mode: Optional[str] = None

    # Assessment status
    last_assessment_date: Optional[datetime] = None
    assessed_level: Optional[str] = None

    # Vocabulary
    due_vocabulary_count: int = 0
    due_vocabulary_words: list[str] | None = None

    # Session history
    total_sessions: int = 0
    sessions_since_assessment: int = 0

    # User request (explicit mode choice)
    requested_mode: Optional[LearningMode] = None


def select_learning_mode(context: SessionContext) -> LearningMode:
    """Выбрать режим обучения на основе контекста.

    Приоритеты:
    1. Явный запрос пользователя
    2. Нужен assessment (нет оценки или > 30 дней)
    3. Много слов для повторения (> 10)
    4. Цель = interview → MOCK_INTERVIEW
    5. Default → FREE_CONVERSATION

    Args:
        context: Контекст сессии

    Returns:
        Выбранный режим обучения
    """
    # 1. Явный запрос пользователя
    if context.requested_mode:
        return context.requested_mode

    # 2. Нужен assessment?
    if needs_assessment(context):
        return LearningMode.ASSESSMENT

    # 3. Много слов для повторения?
    if context.due_vocabulary_count >= 10:
        return LearningMode.VOCABULARY_DRILL

    # 4. Цель связана с interview?
    if is_interview_goal(context.goal):
        # Чередуем mock interview и vocabulary
        if context.due_vocabulary_count >= 5:
            # Каждую третью сессию - vocabulary drill
            if context.sessions_since_assessment % 3 == 2:
                return LearningMode.VOCABULARY_DRILL
        return LearningMode.MOCK_INTERVIEW

    # 5. Default - свободный разговор
    return LearningMode.FREE_CONVERSATION


def needs_assessment(context: SessionContext) -> bool:
    """Проверить, нужна ли оценка уровня.

    Criteria:
    - Никогда не проходил assessment
    - Прошло > 30 дней с последнего assessment
    - Первые 3 сессии нового пользователя (если нет assessment)
    """
    # Никогда не проходил
    if context.last_assessment_date is None:
        # Для совсем новых пользователей - сразу assessment
        if context.total_sessions < 1:
            return True
        # Если уже были сессии без assessment - напомнить
        return context.total_sessions % 5 == 0  # Каждые 5 сессий

    # Прошло > 30 дней
    days_since = (datetime.now() - context.last_assessment_date).days
    if days_since > 30:
        return True

    return False


def is_interview_goal(goal: Optional[str]) -> bool:
    """Проверить, связана ли цель с собеседованием."""
    if not goal:
        return False

    goal_lower = goal.lower()
    interview_keywords = [
        "interview", "интервью",
        "job", "работа", "работу",
        "ml", "machine learning",
        "data science", "data scientist",
        "software engineer", "developer", "разработчик",
        "ielts", "toefl", "экзамен",
    ]

    return any(kw in goal_lower for kw in interview_keywords)


def get_focus_area_for_mode(
    mode: LearningMode,
    context: SessionContext,
) -> str:
    """Определить фокус сессии для режима.

    Args:
        mode: Выбранный режим
        context: Контекст сессии

    Returns:
        Описание фокуса сессии
    """
    if mode == LearningMode.ASSESSMENT:
        return "general level assessment"

    if mode == LearningMode.MOCK_INTERVIEW:
        # Определяем фокус на основе focus_areas или goal
        if context.focus_areas:
            # Чередуем разные области
            idx = context.sessions_since_assessment % len(context.focus_areas)
            return context.focus_areas[idx]

        # По умолчанию на основе goal
        if context.goal:
            if "ml" in context.goal.lower() or "data" in context.goal.lower():
                focus_options = [
                    "technical ML concepts",
                    "behavioral questions",
                    "explaining your projects",
                    "system design discussion",
                ]
            else:
                focus_options = [
                    "tell me about yourself",
                    "behavioral questions",
                    "technical discussion",
                    "problem-solving scenarios",
                ]
            return focus_options[context.sessions_since_assessment % len(focus_options)]

        return "general interview skills"

    if mode == LearningMode.VOCABULARY_DRILL:
        return "vocabulary review"

    return "conversation practice"


def suggest_next_mode(
    current_mode: LearningMode,
    context: SessionContext,
) -> tuple[LearningMode, str]:
    """Предложить режим для следующей сессии.

    Args:
        current_mode: Текущий режим
        context: Контекст

    Returns:
        Tuple (рекомендуемый режим, причина)
    """
    # После assessment - рекомендовать режим под цель
    if current_mode == LearningMode.ASSESSMENT:
        if is_interview_goal(context.goal):
            return (
                LearningMode.MOCK_INTERVIEW,
                "Let's start practicing with mock interviews!"
            )
        return (
            LearningMode.FREE_CONVERSATION,
            "Let's practice with some free conversation."
        )

    # После vocabulary drill - mock interview или conversation
    if current_mode == LearningMode.VOCABULARY_DRILL:
        if is_interview_goal(context.goal):
            return (
                LearningMode.MOCK_INTERVIEW,
                "Great vocabulary work! Ready for some interview practice?"
            )
        return (
            LearningMode.FREE_CONVERSATION,
            "Nice job with the vocabulary! Let's use those words in conversation."
        )

    # После mock interview - vocabulary или ещё interview
    if current_mode == LearningMode.MOCK_INTERVIEW:
        if context.due_vocabulary_count >= 5:
            return (
                LearningMode.VOCABULARY_DRILL,
                "Good interview practice! Let's review some vocabulary before the next one."
            )
        return (
            LearningMode.MOCK_INTERVIEW,
            "Ready for another interview round?"
        )

    # После free conversation
    if context.due_vocabulary_count >= 10:
        return (
            LearningMode.VOCABULARY_DRILL,
            "You have some words to review. Let's do a quick vocabulary session!"
        )

    return (
        LearningMode.FREE_CONVERSATION,
        "Let's continue chatting!"
    )


def parse_user_mode_request(message: str) -> Optional[LearningMode]:
    """Распознать запрос пользователя на конкретный режим.

    Args:
        message: Сообщение пользователя

    Returns:
        Режим, если распознан, иначе None
    """
    message_lower = message.lower()

    # Assessment keywords
    if any(kw in message_lower for kw in [
        "check my level", "assess", "оценить уровень", "какой у меня уровень",
        "test my english", "проверить мой",
    ]):
        return LearningMode.ASSESSMENT

    # Mock interview keywords
    if any(kw in message_lower for kw in [
        "mock interview", "practice interview", "simulate interview",
        "собеседование", "интервью", "interview practice",
    ]):
        return LearningMode.MOCK_INTERVIEW

    # Vocabulary keywords
    if any(kw in message_lower for kw in [
        "vocabulary", "words", "повторить слова", "слова",
        "review words", "vocab", "drill",
    ]):
        return LearningMode.VOCABULARY_DRILL

    # Free conversation keywords
    if any(kw in message_lower for kw in [
        "just chat", "free talk", "просто поговорить",
        "conversation", "разговор",
    ]):
        return LearningMode.FREE_CONVERSATION

    return None
