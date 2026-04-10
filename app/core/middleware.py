"""
Middleware для HTTP метрик и observability.

Includes:
- PrometheusMiddleware: Automatic HTTP metrics collection
- RequestIDMiddleware: Adds request ID for log correlation
- MetricsLogFilter: Filters /metrics spam from access logs
"""

import logging
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.metrics import (
    http_requests_total,
    http_request_duration_seconds,
    http_request_size_bytes,
    http_response_size_bytes,
    normalize_endpoint
)
from app.core.observability import (
    set_request_context,
    clear_request_context,
    get_request_id,
    get_session_id,
    get_turn_id,
    get_runtime,
)


# ============== Logging Filter ==============


class MetricsLogFilter(logging.Filter):
    """Filter to suppress /metrics and /health endpoint logs.

    These endpoints are called frequently by Prometheus scraper
    and health checks, creating noise in logs.
    """

    FILTERED_PATHS = {"/metrics", "/health", "/docs", "/redoc", "/openapi.json"}

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        # Filter uvicorn access logs for noisy endpoints
        for path in self.FILTERED_PATHS:
            if f'"{path}' in message or f" {path} " in message:
                return False
        return True


# ============== Request ID Middleware ==============


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns a unique request ID to each request.

    The request ID is:
    - Set in request context (accessible via get_request_id())
    - Added to response headers (X-Request-ID)
    - Used for log correlation

    Usage in logs:
        22:16:31 [abc12345] INFO router → onboarding
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate and set request ID
        request_id = set_request_context()

        # Store in request state for access in endpoints
        request.state.request_id = request_id

        try:
            response = await call_next(request)
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # Clear context after request completes
            clear_request_context()


# ============== Request ID Log Formatter ==============


class RequestIDFormatter(logging.Formatter):
    """Log formatter that includes request ID.

    Format: 22:16:31 [abc12345] INFO  message
    """

    def format(self, record: logging.LogRecord) -> str:
        request_id = get_request_id()
        session_id = get_session_id()
        turn_id = get_turn_id()
        runtime = get_runtime()

        parts: list[str] = [request_id] if request_id else []
        if session_id:
            parts.append(f"s={session_id[:8]}")
        if turn_id:
            parts.append(f"t={turn_id}")
        if runtime:
            parts.append(f"rt={runtime}")

        record.request_id = f"[{' '.join(parts)}]" if parts else "[-]"
        return super().format(record)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Middleware для автоматического сбора HTTP метрик.
    
    Собирает метрики:
    - Количество запросов по методам и endpoints
    - Время обработки запросов
    - Размер запросов и ответов
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Обработка запроса с сбором метрик.
        
        Args:
            request: HTTP запрос
            call_next: Следующий обработчик в цепочке
            
        Returns:
            HTTP ответ
        """
        # Игнорируем метрики и health checks в метриках
        if request.url.path in ['/metrics', '/health', '/docs', '/redoc', '/openapi.json']:
            return await call_next(request)
        
        # Нормализуем путь для метрик
        endpoint = normalize_endpoint(request.url.path)
        method = request.method
        
        # Измеряем размер запроса
        request_size = 0
        if hasattr(request, '_body'):
            request_size = len(getattr(request, '_body', b''))
        
        # Засекаем время начала обработки
        start_time = time.time()
        
        try:
            # Выполняем запрос
            response = await call_next(request)
            
            # Вычисляем время обработки
            duration = time.time() - start_time
            
            # Получаем статус код
            status_code = response.status_code
            
            # Измеряем размер ответа
            response_size = 0
            if hasattr(response, 'body'):
                response_body = getattr(response, 'body', b'')
                if isinstance(response_body, bytes):
                    response_size = len(response_body)
            
            # Записываем метрики
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).inc()
            
            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
            http_request_size_bytes.labels(
                method=method,
                endpoint=endpoint
            ).observe(request_size)
            
            http_response_size_bytes.labels(
                method=method,
                endpoint=endpoint
            ).observe(response_size)
            
            return response
            
        except Exception as e:
            # В случае ошибки тоже записываем метрики
            duration = time.time() - start_time
            
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status_code=500
            ).inc()
            
            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
            # Пробрасываем исключение дальше
            raise

