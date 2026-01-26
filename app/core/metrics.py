"""
Метрики Prometheus для мониторинга FastAPI приложения
"""

from prometheus_client import Counter, Histogram, Gauge
from typing import Optional

# HTTP метрики
http_requests_total = Counter(
    'http_requests_total',
    'Общее количество HTTP запросов',
    ['method', 'endpoint', 'status_code']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'Время обработки HTTP запросов в секундах',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0]
)

http_request_size_bytes = Histogram(
    'http_request_size_bytes',
    'Размер входящих HTTP запросов в байтах',
    ['method', 'endpoint'],
    buckets=[100, 500, 1000, 5000, 10000, 50000, 100000]
)

http_response_size_bytes = Histogram(
    'http_response_size_bytes',
    'Размер HTTP ответов в байтах',
    ['method', 'endpoint'],
    buckets=[100, 500, 1000, 5000, 10000, 50000, 100000]
)

# Метрики базы данных
database_query_duration_seconds = Histogram(
    'database_query_duration_seconds',
    'Время выполнения SQL запросов в секундах',
    ['operation', 'table'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
)

database_connections_active = Gauge(
    'database_connections_active',
    'Количество активных подключений к базе данных'
)

# Метрики OpenAI API
openai_api_calls_total = Counter(
    'openai_api_calls_total',
    'Общее количество вызовов OpenAI API',
    ['operation', 'model', 'status']
)

openai_api_duration_seconds = Histogram(
    'openai_api_duration_seconds',
    'Время ответа OpenAI API в секундах',
    ['operation', 'model'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0]
)

openai_api_tokens_total = Counter(
    'openai_api_tokens_total',
    'Общее количество токенов использованных в OpenAI API',
    ['type']  # 'prompt' или 'completion'
)

# Метрики агента
agent_chat_sessions_total = Counter(
    'agent_chat_sessions_total',
    'Общее количество чат-сессий с агентом'
)

agent_chat_messages_total = Counter(
    'agent_chat_messages_total',
    'Общее количество сообщений в чате',
    ['speaker']  # 'user' или 'assistant'
)

# ============ VOICE WEBSOCKET METRICS ============

# Активные сессии
voice_sessions_active = Gauge(
    'voice_sessions_active',
    'Количество активных WebSocket голосовых сессий'
)

voice_sessions_total = Counter(
    'voice_sessions_total',
    'Общее количество голосовых сессий',
    ['mode', 'status']  # mode: FREE_CONVERSATION, status: completed/disconnected/error
)

# Latency метрики (ключевые для диагностики!)
voice_turn_total_seconds = Histogram(
    'voice_turn_total_seconds',
    'Полное время обработки turn (LLM + TTS)',
    ['mode'],
    buckets=[0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0]
)

voice_llm_latency_seconds = Histogram(
    'voice_llm_latency_seconds',
    'Время ответа LLM (Groq)',
    ['mode'],
    buckets=[0.3, 0.5, 1.0, 2.0, 5.0, 10.0]
)

voice_tts_latency_seconds = Histogram(
    'voice_tts_latency_seconds',
    'Время синтеза TTS (edge-tts)',
    buckets=[0.1, 0.3, 0.5, 1.0, 2.0, 5.0]
)

# Счётчики сообщений
voice_messages_total = Counter(
    'voice_messages_total',
    'Количество сообщений в голосовых сессиях',
    ['direction', 'type']  # direction: inbound/outbound, type: text/audio/error
)

# Ошибки
voice_errors_total = Counter(
    'voice_errors_total',
    'Количество ошибок в голосовом pipeline',
    ['stage']  # stage: llm/tts/db/websocket
)


# ============ AGENT V2 METRICS (LLM-driven architecture) ============

# LLM latency by node
agent_v2_llm_latency = Histogram(
    'agent_v2_llm_latency_seconds',
    'LLM response time for agent v2 nodes',
    ['node'],  # node: onboarding, learning, session_end
    buckets=[0.3, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0]
)

# Parse success rate
agent_v2_parse_success = Counter(
    'agent_v2_parse_success_total',
    'JSON parse success/failure count for agent v2',
    ['node', 'success']  # success: true/false
)

# Goal detection
agent_v2_goal_detection = Counter(
    'agent_v2_goal_detection_total',
    'Goal detection events in onboarding',
    ['detected']  # detected: true/false
)

# Corrections made
agent_v2_corrections = Counter(
    'agent_v2_corrections_total',
    'Error corrections made by agent v2',
    ['type']  # type: grammar/vocabulary/pronunciation/total
)

# Session completion
agent_v2_session_complete = Counter(
    'agent_v2_session_complete_total',
    'Completed sessions by agent v2',
    ['goal', 'level']  # goal: goal slug, level: CEFR level
)

# A/B experiment tracking
agent_v2_ab_variant = Counter(
    'agent_v2_ab_variant_total',
    'A/B experiment variant assignments',
    ['experiment', 'variant']  # experiment name, variant: control/variant
)

# ============ AGENT VERSION COMPARISON METRICS ============

# Sessions by agent version (for v1 vs v2 comparison)
agent_version_sessions = Counter(
    'agent_version_sessions_total',
    'Sessions by agent version',
    ['version']  # v1 or v2
)

# Errors by agent version
agent_version_errors = Counter(
    'agent_version_errors_total',
    'Errors by agent version',
    ['version', 'error_type']  # version: v1/v2, error_type: parse/llm/validation/etc
)

# Successful onboarding completions by version
agent_version_onboarding_complete = Counter(
    'agent_version_onboarding_complete_total',
    'Successful onboarding completions by version',
    ['version']  # v1 or v2
)

# Guardrail violations
agent_guardrail_violations = Counter(
    'agent_guardrail_violations_total',
    'Guardrail validation failures',
    ['node', 'violation_type']  # node: onboarding/learning/session_end, violation_type: length/forbidden/missing_field/invalid_action
)

# Fallback applications
agent_guardrail_fallbacks = Counter(
    'agent_guardrail_fallbacks_total',
    'Times fallback response was applied',
    ['node']  # node: onboarding/learning/session_end
)

def normalize_endpoint(path: str) -> str:
    """
    Нормализует endpoint путь для метрик.
    Заменяет UUID и ID на универсальные плейсхолдеры.
    
    Args:
        path: Путь запроса
        
    Returns:
        Нормализованный путь
    """
    import re
    # Заменяем UUID на {uuid}
    path = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '{uuid}', path)
    # Заменяем числовые ID на {id}
    path = re.sub(r'/\d+(?=/|$)', '/{id}', path)
    return path

