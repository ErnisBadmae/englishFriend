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

