"""
API endpoint для голосового чата с пользователями.

Использует универсальный динамический промпт для генерации ответов.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.context_builder import ContextBuilder
from app.prompts.universal import build_universal_prompt
from app.models.core_tables import Utterance

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


class ChatMessage(BaseModel):
    """Модель входящего сообщения"""
    user_id: int
    session_id: str
    message: str
    speaker: str = "user"  # user или assistant


class ChatResponse(BaseModel):
    """Модель ответа"""
    response: str
    session_id: str
    user_id: int


class ChatRequest(BaseModel):
    """Модель запроса на чат"""
    user_id: int
    session_id: str
    message: str


@router.post("/send", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Отправить сообщение и получить ответ от AI.
    
    Процесс:
    1. Сохранить сообщение пользователя в БД
    2. Собрать контекст из БД (профиль, интересы, память, прогресс)
    3. Построить универсальный промпт с динамическими данными
    4. Вызвать OpenAI API с промптом (заглушка, т.к. нет интеграции)
    5. Сохранить ответ AI в БД
    6. Вернуть ответ пользователю
    """
    
    # 1. Сохранить сообщение пользователя
    user_utterance = Utterance(
        session_id=request.session_id,
        speaker="user",
        text=request.message,
        t_start_ms=0,  # В реальности нужно получать timestamp
        t_end_ms=0
    )
    db.add(user_utterance)
    await db.flush()
    
    # 2. Собрать контекст из БД
    context_builder = ContextBuilder(db)
    try:
        context = await context_builder.build_full_context(
            user_id=request.user_id,
            session_id=request.session_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    # 3. Построить универсальный промпт
    system_prompt = build_universal_prompt(
        user_profile=context['user_profile'],
        interests=context['interests'],
        memories=context['memories'],
        recent_utterances=context['recent_utterances'],
        progress=context['progress'],
        session_context=context['session_context']
    )
    
    # 4. Вызвать OpenAI API (заглушка - реальная интеграция будет позже)
    ai_response = await generate_ai_response(
        system_prompt=system_prompt,
        user_message=request.message
    )
    
    # 5. Сохранить ответ AI в БД
    ai_utterance = Utterance(
        session_id=request.session_id,
        speaker="assistant",
        text=ai_response,
        t_start_ms=0,
        t_end_ms=0
    )
    db.add(ai_utterance)
    await db.commit()
    
    # 6. Вернуть ответ
    return ChatResponse(
        response=ai_response,
        session_id=request.session_id,
        user_id=request.user_id
    )


async def generate_ai_response(system_prompt: str, user_message: str) -> str:
    """
    Генерация ответа от AI (заглушка).
    
    В реальной реализации здесь будет вызов OpenAI API:
    
    ```python
    import openai
    
    client = openai.AsyncOpenAI()
    
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=0.7,
        max_tokens=500
    )
    
    return response.choices[0].message.content
    ```
    
    Args:
        system_prompt: Системный промпт с динамическим контекстом
        user_message: Сообщение пользователя
    
    Returns:
        Ответ от AI
    """
    # Заглушка - возвращаем демо-ответ
    return f"Hi! I got your message: '{user_message}'. System prompt length: {len(system_prompt)} chars."


@router.get("/prompt-preview/{user_id}")
async def preview_prompt(
    user_id: int,
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Предпросмотр промпта для отладки.
    
    Полезно для проверки, какие данные подставляются в промпт.
    """
    context_builder = ContextBuilder(db)
    
    try:
        context = await context_builder.build_full_context(
            user_id=user_id,
            session_id=session_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    system_prompt = build_universal_prompt(
        user_profile=context['user_profile'],
        interests=context['interests'],
        memories=context['memories'],
        recent_utterances=context['recent_utterances'],
        progress=context['progress'],
        session_context=context['session_context']
    )
    
    return {
        "prompt": system_prompt,
        "prompt_length": len(system_prompt),
        "token_estimate": len(system_prompt) // 4,  # Примерная оценка токенов
        "context_summary": {
            "user_id": user_id,
            "session_id": session_id,
            "interests_count": len(context['interests']),
            "memories_count": len(context['memories']),
            "utterances_count": len(context['recent_utterances']),
            "session_exists": context['session_context'] is not None
        }
    }

