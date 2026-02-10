"""
API для текстового чата с агентом
"""

import logging
import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
import os

from app.core.database import get_db
from app.agents.base_agent import create_english_friend_agent

logger = logging.getLogger(__name__)
from app.models.core_tables import Utterance

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


class AgentChatRequest(BaseModel):
    user_id: int
    session_id: str
    message: str
    @field_validator('session_id')
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError(f"session_id must be a valid UUID, got: {v}")

class AgentChatResponse(BaseModel):
    response: str
    session_id: str
    user_id: int


@router.get("/health")
async def agent_health():
    """Проверка доступности OpenAI API через прокси"""
    from openai import AsyncOpenAI
    import httpx
    
    api_key = os.getenv("OPENAI_API_KEY")
    proxy_url = os.getenv("PROXY_URL")
    
    if not api_key:
        return {"status": "error", "message": "OPENAI_API_KEY not set"}
    
    if not proxy_url:
        return {"status": "error", "message": "PROXY_URL not set"}
    
    try:
        # Тест с прокси
        http_client = httpx.AsyncClient(
            proxy=proxy_url,
            timeout=httpx.Timeout(60.0, connect=15.0)
        )
        
        client = AsyncOpenAI(
            api_key=api_key,
            http_client=http_client
        )
        
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Test"}],
            max_tokens=5
        )
        
        return {
            "status": "ok",
            "message": "OpenAI API connected via proxy",
            "model": response.model,
            "proxy": proxy_url[:40] + "..."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"OpenAI API error: {str(e)}"
        }


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    request: AgentChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Текстовый чат с агентом English Friend.
    """
    from agents import Runner
    
    try:
        # 2. Сохранить сообщение пользователя
        user_utterance = Utterance(
            session_id=request.session_id,
            speaker="user",
            text=request.message,
            t_start_ms=0,
            t_end_ms=0
        )
        db.add(user_utterance)
        await db.flush()
        
        # 3. Создать агента
        agent = await create_english_friend_agent(
            user_id=request.user_id,
            session_id=request.session_id,
            db=db
        )
        
        # 4. Запустить агента
        result = await Runner.run(agent, request.message)
        ai_response = result.final_output
        
        # 5. Сохранить ответ AI
        ai_utterance = Utterance(
            session_id=request.session_id,
            speaker="assistant",
            text=ai_response,
            t_start_ms=0,
            t_end_ms=0
        )
        db.add(ai_utterance)
        await db.commit()
        
        return AgentChatResponse(
            response=ai_response,
            session_id=request.session_id,
            user_id=request.user_id
        )
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Agent chat error for user {request.user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

