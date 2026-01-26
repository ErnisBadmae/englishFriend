"""
Базовый агент English Friend для текстового чата
"""

import logging

from agents import Agent, Runner
from sqlalchemy.ext.asyncio import AsyncSession

# Импорт автоматически настроит прокси
from app.agents import proxy  # noqa: F401

from app.services.context_builder import ContextBuilder
from app.prompts.universal import build_universal_prompt, determine_prompt_mode

logger = logging.getLogger(__name__)


async def create_simple_agent() -> Agent:
    """
    Создать простого агента для тестирования.
    
    Returns:
        Agent: Настроенный агент
    """
    agent = Agent(
        name="English_Friend_Test",
        instructions=(
            "You are a friendly English learning assistant. "
            "Help users practice English in a natural, conversational way. "
            "Be encouraging and supportive."
        ),
        model="gpt-4o-mini",
    )
    
    return agent


async def create_english_friend_agent(
    user_id: int,
    session_id: str,
    db: AsyncSession,
    use_universal_prompt: bool = True
) -> Agent:
    """
    Создать агента с полным контекстом из БД.
    
    Args:
        user_id: ID пользователя
        session_id: ID сессии
        db: Сессия базы данных
        use_universal_prompt: Использовать Universal Prompt (по умолчанию True)
    
    Returns:
        Agent: Настроенный агент
    """
    if not use_universal_prompt:
        return await create_simple_agent()
    
    try:
        # Собрать контекст из БД
        context_builder = ContextBuilder(db)
        context = await context_builder.build_full_context(
            user_id=user_id,
            session_id=session_id
        )
        
        # Определить режим промпта
        from app.prompts.universal import PromptMode
        mode = determine_prompt_mode(
            context["session_context"],
            context["user_profile"] or None
        )
        
        # Построить универсальный промпт
        system_prompt = build_universal_prompt(
            user_profile=context["user_profile"],
            interests=context["interests"],
            memories=context["memories"],
            recent_utterances=context["recent_utterances"],
            progress=context["progress"],
            session_context=context["session_context"],
            mode=mode
        )
        
        # Создать агента с динамическим промптом
        agent = Agent(
            name="English_Friend",
            instructions=system_prompt,
            model="gpt-4o-mini",
        )
        
        return agent
        
    except Exception as e:
        # Если что-то пошло не так - возвращаем простого агента
        logger.warning(f"Failed to build universal prompt: {e}")
        return await create_simple_agent()

