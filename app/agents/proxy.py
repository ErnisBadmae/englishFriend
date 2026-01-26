"""
Настройка прокси для библиотеки agents
Автоматически применяет monkey-patch для всех запросов к OpenAI
"""

import logging
import httpx
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def setup_proxy():
    """
    Настраивает прокси для библиотеки agents

    Returns:
        str: URL прокси или None
    """
    load_dotenv()
    PROXY_URL = os.getenv("PROXY_URL")

    if not PROXY_URL:
        logger.debug("PROXY_URL not found in .env")
        return None

    logger.debug(f"Setting up proxy for Agents: {PROXY_URL[:40]}...")

    from agents.models import openai_provider

    if not hasattr(openai_provider.OpenAIProvider._get_client, '_proxy_patched'):
        _original_get_client = openai_provider.OpenAIProvider._get_client
        
        def patched_get_client(self):
            client = _original_get_client(self)
            
            http_client = httpx.AsyncClient(
                proxy=PROXY_URL,
                timeout=httpx.Timeout(60.0, connect=15.0)
            )
            
            client = AsyncOpenAI(
                api_key=client.api_key,
                base_url=client.base_url,
                http_client=http_client
            )
            logger.debug("Proxy connected to OpenAI client")
            return client

        patched_get_client._proxy_patched = True
        openai_provider.OpenAIProvider._get_client = patched_get_client
        logger.debug("Monkey-patch applied")

    logger.debug("Proxy configured")
    return PROXY_URL

# Автоматически настраиваем при импорте
setup_proxy()

