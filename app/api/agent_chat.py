"""API для текстового чата с legacy OpenAI agent endpoint."""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base_agent import create_english_friend_agent
from app.core.config import settings
from app.core.database import get_db
from app.models.core_tables import Utterance

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


class AgentChatRequest(BaseModel):
    user_id: int
    session_id: str
    message: str

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        try:
            uuid.UUID(value)
            return value
        except ValueError as exc:
            raise ValueError(f"session_id must be a valid UUID, got: {value}") from exc


class AgentChatResponse(BaseModel):
    response: str
    session_id: str
    user_id: int


@router.get("/health")
async def agent_health():
    """Health check only for the legacy OpenAI Agents SDK path."""
    from openai import AsyncOpenAI
    import httpx

    base_payload = {
        "endpoint": "legacy_agents_sdk",
        "provider": "openai",
        "active_llm_provider": settings.llm_provider,
    }

    api_key = os.getenv("OPENAI_API_KEY")
    proxy_url = os.getenv("PROXY_URL")

    if not api_key:
        return {
            **base_payload,
            "status": "skipped",
            "message": "Legacy agent endpoint is OpenAI-only; OPENAI_API_KEY is not set",
        }

    if not proxy_url:
        return {
            **base_payload,
            "status": "skipped",
            "message": "Legacy agent endpoint is OpenAI-only; PROXY_URL is not set",
        }

    try:
        http_client = httpx.AsyncClient(
            proxy=proxy_url,
            timeout=httpx.Timeout(60.0, connect=15.0),
        )
        client = AsyncOpenAI(api_key=api_key, http_client=http_client)
        response = await client.chat.completions.create(
            model=settings.openai_chat_model,
            messages=[{"role": "user", "content": "Test"}],
            max_tokens=5,
        )
        return {
            **base_payload,
            "status": "ok",
            "message": "OpenAI API connected via proxy for legacy agent endpoint",
            "model": response.model,
            "proxy": proxy_url[:40] + "...",
        }
    except Exception as exc:
        logger.warning("Legacy agent health check failed: %s", exc)
        return {
            **base_payload,
            "status": "error",
            "message": f"OpenAI API error: {exc}",
        }


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    request: AgentChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """Текстовый чат с агентом English Friend."""
    from agents import Runner

    try:
        user_utterance = Utterance(
            session_id=request.session_id,
            speaker="user",
            text=request.message,
            t_start_ms=0,
            t_end_ms=0,
        )
        db.add(user_utterance)
        await db.flush()

        agent = await create_english_friend_agent(
            user_id=request.user_id,
            session_id=request.session_id,
            db=db,
        )

        result = await Runner.run(agent, request.message)
        ai_response = result.final_output

        ai_utterance = Utterance(
            session_id=request.session_id,
            speaker="assistant",
            text=ai_response,
            t_start_ms=0,
            t_end_ms=0,
        )
        db.add(ai_utterance)
        await db.commit()

        return AgentChatResponse(
            response=ai_response,
            session_id=request.session_id,
            user_id=request.user_id,
        )
    except Exception as exc:
        await db.rollback()
        logger.error("Agent chat error for user %s: %s", request.user_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from exc
