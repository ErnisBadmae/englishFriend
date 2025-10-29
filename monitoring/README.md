# Мониторинг системы English Friend

## Обзор

Система мониторинга построена на Prometheus и Grafana для сбора и визуализации метрик всех компонентов системы.

## Компоненты

### Prometheus
- **Порт**: 9090
- **Назначение**: Сбор и хранение метрик временных рядов
- **Интерфейс**: http://localhost:9090

### Grafana
- **Порт**: 3000
- **Назначение**: Визуализация метрик
- **Интерфейс**: http://localhost:3000
- **Логин**: admin
- **Пароль**: admin

## Запуск мониторинга

```bash
# Запуск Prometheus и Grafana
docker-compose -f docker-compose.monitoring.yml up -d

# Проверка статуса
docker-compose -f docker-compose.monitoring.yml ps

# Просмотр логов
docker-compose -f docker-compose.monitoring.yml logs -f
```

## Метрики

### FastAPI (Основной API)

Endpoints для метрик:
- `GET /metrics` - Prometheus метрики

Собираемые метрики:
- `http_requests_total` - Количество HTTP запросов по методам и endpoints
- `http_request_duration_seconds` - Время обработки запросов
- `http_request_size_bytes` - Размер входящих запросов
- `http_response_size_bytes` - Размер ответов
- `database_query_duration_seconds` - Время выполнения SQL запросов
- `openai_api_calls_total` - Количество вызовов OpenAI API
- `openai_api_duration_seconds` - Время ответа OpenAI API

### Sync-Vector

Endpoints для метрик:
- `GET /metrics` - Prometheus метрики (порт 8090)

Собираемые метрики:
- `sync_vector_upsert_latency_ms` - Латентность upsert операций
- `sync_vector_queue_lag` - Lag очереди Kafka
- `sync_vector_failures_total` - Количество ошибок по причинам
- `sync_vector_last_success_timestamp` - Timestamp последней успешной обработки
- `sync_vector_messages_processed_total` - Количество обработанных сообщений

### Sync-Graph

Endpoints для метрик:
- `GET /metrics` - Prometheus метрики (порт 8091)

Собираемые метрики:
- `sync_graph_batch_duration_ms` - Длительность обработки батча
- `sync_graph_dlq_total` - Количество сообщений в DLQ
- `sync_graph_last_success_timestamp` - Timestamp последней успешной обработки
- `sync_graph_nodes_created_total` - Количество созданных узлов
- `sync_graph_relationships_created_total` - Количество созданных связей

## Использование Grafana

### Доступ к дашбордам

1. Откройте http://localhost:3000
2. Войдите с учетными данными (admin/admin)
3. Перейдите в раздел Dashboards
4. Выберите "English Friend - System Overview"

### Создание собственных дашбордов

1. В Grafana выберите "Create" -> "Dashboard"
2. Добавьте панели с запросами к Prometheus
3. Используйте PromQL для запросов метрик

### Примеры PromQL запросов

```promql
# Requests per second
rate(http_requests_total[5m])

# 95th percentile latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status_code=~"5.."}[5m])

# Success rate
rate(sync_vector_messages_processed_total{status="success"}[5m])
```

## Конфигурация Prometheus

Конфигурация находится в `monitoring/prometheus/prometheus.yml`.

Для изменения targets (адресов сервисов для сбора метрик) отредактируйте файл и перезапустите Prometheus:

```bash
docker-compose -f docker-compose.monitoring.yml restart prometheus
```

## Интеграция с существующими сервисами

### Требования

Все сервисы должны быть запущены и доступны:
- FastAPI на порту 8000
- sync-vector на порту 8090
- sync-graph на порту 8091

### Проверка доступности метрик

```bash
# FastAPI
curl http://localhost:8000/metrics

# Sync-Vector
curl http://localhost:8090/metrics

# Sync-Graph
curl http://localhost:8091/metrics
```

## Остановка мониторинга

```bash
docker-compose -f docker-compose.monitoring.yml down

# С удалением данных
docker-compose -f docker-compose.monitoring.yml down -v
```

## Рекомендации

1. **Алертинг**: Настройте Alertmanager для получения уведомлений о проблемах
2. **Ретенция данных**: Настройте retention period в Prometheus (по умолчанию 30 дней)
3. **Бэкапы**: Настройте регулярные бэкапы конфигурации Grafana и Prometheus
4. **Безопасность**: Измените пароль по умолчанию в Grafana перед production

