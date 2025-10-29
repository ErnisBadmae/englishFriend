# English Friend - System Overview

## Архитектура системы

English Friend - это многослойная система для изучения английского языка, построенная на микросервисной архитектуре с использованием различных типов баз данных для разных задач.

### Основные компоненты

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL   │    │     Kafka       │    │     Neo4j       │
│   (Primary DB) │───▶│   (Message Bus) │───▶│   (Graph DB)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Debezium      │    │  sync-vector    │    │  sync-graph     │
│   (CDC)         │    │  (Vector Sync)  │    │  (Graph Sync)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Kafka Topics  │    │    Qdrant       │    │   Neo4j Graph   │
│   (Events)      │    │  (Vector DB)    │    │   (Relations)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Слои системы

### 1. **PostgreSQL (Основная база данных)**
- **Назначение**: Хранение всех пользовательских данных, сессий, высказываний, воспоминаний
- **Особенности**: 
  - Партиционированные таблицы (`sessions`, `utterances`, `xp_events`)
  - Row-Level Security (RLS) для изоляции данных пользователей
  - Материализованные представления для аналитики
  - Логическая репликация для CDC

**Основные таблицы**:
- `users` - пользователи системы
- `sessions` - сессии изучения (партиционированы по месяцам)
- `utterances` - высказывания в сессиях (партиционированы по хэшу)
- `memories` - воспоминания пользователей
- `learning_plan` - планы обучения
- `xp_events` - события опыта (партиционированы по дате)

### 2. **Kafka + Debezium (CDC слой)**
- **Назначение**: Захват изменений данных (Change Data Capture) и передача в другие системы
- **Компоненты**:
  - **Debezium Connectors**: Отслеживают изменения в PostgreSQL
  - **Kafka Topics**: Хранят события изменений
  - **Publications**: PostgreSQL публикации для логической репликации

**Топики**:
- `graph.public.sessions` - события сессий для графа
- `graph.public.utterances` - события высказываний
- `memories.public.memories` - события воспоминаний

### 3. **Neo4j (Графовая база данных)**
- **Назначение**: Хранение отношений между пользователями, темами, эмоциями
- **Особенности**:
  - Граф интересов пользователей
  - Рекомендации тем для изучения
  - Эмоциональная память
  - Контекстные связи

**Основные узлы**:
- `User` - пользователи
- `Session` - сессии
- `Topic` - темы изучения
- `Emotion` - эмоции
- `Utterance` - высказывания

**Основные связи**:
- `PARTICIPATED_IN` - пользователь участвует в сессии
- `INTEREST_IN` - интерес пользователя к теме
- `EXPRESSES` - выражение эмоции в высказывании
- `RELATED_TO` - связи между темами

### 4. **Qdrant (Векторная база данных)**
- **Назначение**: Семантический поиск по воспоминаниям пользователей
- **Особенности**:
  - Векторные представления воспоминаний
  - Поиск по смыслу, а не по ключевым словам
  - Рекомендации на основе семантического сходства

### 5. **Синхронизационные сервисы**

#### sync-graph
- **Назначение**: Синхронизация данных из Kafka в Neo4j
- **Функции**:
  - Обработка событий CDC
  - Создание узлов и связей в графе
  - Нормализация данных Debezium
  - Обработка ошибок и DLQ

#### sync-vector
- **Назначение**: Синхронизация воспоминаний в Qdrant
- **Функции**:
  - Векторизация воспоминаний
  - Индексация в Qdrant
  - Обновление векторных представлений

## Поток данных

### 1. **Пользователь создает сессию**
```
User → PostgreSQL (sessions table) → Debezium → Kafka → sync-graph → Neo4j
```

### 2. **Пользователь делает высказывание**
```
User → PostgreSQL (utterances table) → Debezium → Kafka → sync-graph → Neo4j
```

### 3. **Система создает воспоминание**
```
System → PostgreSQL (memories table) → Debezium → Kafka → sync-vector → Qdrant
```

### 4. **Рекомендации**
```
Neo4j (граф интересов) → Рекомендации тем
Qdrant (семантический поиск) → Рекомендации контента
```

## Технические особенности

### Партиционирование
- **sessions**: По месяцам (`sessions_2025_10`, `sessions_2025_11`)
- **utterances**: По хэшу (`utterances_p0`, `utterances_p1`, ...)
- **xp_events**: По дате (`xp_events_2025_10`)

### Безопасность
- **Row-Level Security (RLS)**: Каждый пользователь видит только свои данные
- **Политики доступа**: На уровне PostgreSQL и Neo4j

### Производительность
- **Индексы**: B-tree, GIN для JSONB, составные индексы
- **Материализованные представления**: Для аналитики
- **Партиционирование**: Для больших объемов данных

### Надежность
- **CDC**: Гарантированная доставка изменений
- **DLQ (Dead Letter Queue)**: Обработка ошибок
- **Health checks**: Мониторинг состояния сервисов

## Развертывание

### Docker Compose
- **docker-compose.yml**: Основная PostgreSQL база
- **docker-compose.cdc.yml**: Полный стек с CDC
- **docker-compose.vector.yml**: Векторный стек
- **docker-compose.graph.yml**: Графовый стек

### Миграции
- **Flyway/Liquibase**: Управление схемой базы данных
- **pgTAP**: Тестирование базы данных
- **Cypher**: Тестирование графа

## Мониторинг и тестирование

### Тестирование
- **pgTAP**: Тесты для PostgreSQL
- **Cypher**: Тесты для Neo4j
- **Integration tests**: End-to-end тесты

### Мониторинг

#### Prometheus и Grafana
- **Prometheus**: Сбор метрик временных рядов (порт 9090)
- **Grafana**: Визуализация метрик (порт 3000)
- **Health checks**: HTTP endpoints для проверки состояния (`/health`)
- **Metrics endpoints**: Prometheus метрики (`/metrics`)

#### Собираемые метрики

**FastAPI:**
- HTTP метрики (requests, latency, size)
- Метрики базы данных (query duration, connections)
- Метрики OpenAI API (calls, duration, tokens)

**Sync-Vector:**
- Upsert латентность
- Queue lag (Kafka)
- Failures и success rates
- Timestamp последней обработки

**Sync-Graph:**
- Batch processing duration
- DLQ метрики
- Created nodes и relationships
- Timestamp последней обработки

#### Запуск мониторинга

```bash
# Запуск Prometheus и Grafana
docker-compose -f docker-compose.monitoring.yml up -d

# Доступ к интерфейсам
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin)
```

Подробная документация: `monitoring/README.md`

## Использование

### Запуск системы
```bash
# Полный стек
docker compose -f docker-compose.cdc.yml up -d

# Только база данных
docker compose up -d postgres
```

### Тестирование
```bash
# Тесты базы данных
docker compose exec postgres psql -U postgres -d englishfriend_dev -f db/tests/010_users_channel_identity.sql

# Тесты графа
docker compose exec neo4j cypher-shell -u neo4j -p password -f graph/tests/schema_checks.cypher
```

### Генерация тестовых данных
```bash
# Генерация сессий
python scripts/cdc_batch_sessions.py --events 100

# Загрузка демо данных
docker compose -f docker-compose.cdc.yml up load-postgres-demo load-neo4j-demo load-qdrant-demo
```

## Заключение

English Friend представляет собой современную многослойную архитектуру, которая использует различные типы баз данных для решения разных задач:

- **PostgreSQL** - надежное хранение и транзакции
- **Neo4j** - графовые отношения и рекомендации  
- **Qdrant** - семантический поиск и векторизация
- **Kafka** - надежная передача событий
- **Debezium** - автоматический CDC

Такая архитектура обеспечивает масштабируемость, производительность и гибкость системы для изучения английского языка.
