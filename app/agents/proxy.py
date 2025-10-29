"""
Настройка прокси для библиотеки agents
Автоматически применяет monkey-patch для всех запросов к OpenAI
"""

import httpx
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

def setup_proxy():
    """
    Настраивает прокси для библиотеки agents
    
    Returns:
        str: URL прокси или None
    """
    load_dotenv()
    PROXY_URL = os.getenv("PROXY_URL")
    
    if not PROXY_URL:
        print("[WARNING] PROXY_URL not found in .env")
        return None
    
    print("=" * 60)
    print("[INFO] Setting up proxy for Agents")
    print(f"Proxy: {PROXY_URL[:40]}...")
    print("=" * 60)

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
            print("[OK] Proxy connected to OpenAI client")
            return client
        
        patched_get_client._proxy_patched = True
        openai_provider.OpenAIProvider._get_client = patched_get_client
        print("[OK] Monkey-patch applied")
    
    print("[OK] Proxy configured!")
    print("=" * 60)
    return PROXY_URL

# Автоматически настраиваем при импорте
setup_proxy()

