"""
Middleware для автоматического сбора HTTP метрик Prometheus
"""

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

