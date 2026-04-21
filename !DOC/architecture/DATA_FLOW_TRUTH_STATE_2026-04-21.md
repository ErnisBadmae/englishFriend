# Data Flow Truth State

Last updated: 2026-04-21
Status: short architecture truth-state for current code

## Зачем этот файл

Этот файл фиксирует не target vision, а то, как данные реально ходят в коде сейчас.

Нужен, чтобы не смешивать:

- `hot path` пользовательской сессии
- `async/materialization` контур
- роль `PostgreSQL`, `Qdrant`, `Neo4j`, `Kafka`, `Debezium`

## 1. Hot Path: что происходит в живой сессии

```text
Пользователь
  ->
Frontend
  ->
Backend session bootstrap
  ->
PostgreSQL
  - LearningPlan / Goal / roadmap / vocabulary
  - memories / session_evidence
  ->
best-effort Qdrant retrieval (optional, timeout-safe)
  ->
prompt assembly
  ->
guided session
  ->
PostgreSQL writes on session end
  - session state
  - evidence
  - memories
  - XP / product artifacts
```

Ключевой факт:

- текущий bootstrap опирается прежде всего на `PostgreSQL`
- `Qdrant` используется как дополнительный semantic enricher
- `Neo4j` не участвует в session bootstrap

## 2. Формула prompt/bootstrap на старт сессии

Упрощённо текущий стартовый контекст собирается так:

```text
Session prompt
  =
base coach / mode prompt
  +
LearnerProfileSummary из PostgreSQL
  +
mission context из PostgreSQL
  +
relevant memories из Qdrant, если retrieval успел и вернул полезный контекст
```

Практический смысл:

- если `Qdrant` недоступен, сессия всё равно стартует
- если `Neo4j` недоступен, сессия тоже стартует
- канонический product state живёт в `PostgreSQL`

## 3. Write Path: что считается канонической записью

Сейчас truth-state такой:

```text
Backend write
  ->
PostgreSQL commit
  ->
best-effort background vector sync
```

Это означает:

- запись сначала считается успешной в `PostgreSQL`
- векторная синхронизация не должна тормозить пользовательский request path
- `Qdrant` не является authoritative storage для product state

## 4. Async / Materialization Contour

```text
PostgreSQL
  ->
background / infra sync layers
  ->
Qdrant / Neo4j / analytics projections
```

Более подробно:

```text
PostgreSQL
  ->
Debezium CDC
  ->
Kafka
  ->
sync services
  ->
specialized stores and projections
```

Важно:

- этот контур нужен для обогащения, индексации и аналитики
- он не должен быть обязательным условием старта пользовательской сессии
- он не должен определять каноническое состояние продукта

## 5. Роли хранилищ

| Layer | Реальная роль сейчас | Hot path | Каноничность |
|------|-----------------------|----------|--------------|
| `PostgreSQL` | основной product state: roadmap, evidence, artifacts, memories, XP | да | да |
| `Qdrant` | semantic retrieval для relevant context | да, но best-effort | нет |
| `Neo4j` | graph/materialized insights, future analytics | нет | нет |
| `Kafka` | транспорт событий и async materialization | нет | нет |
| `Debezium` | CDC-слой для репликации изменений | нет | нет |

## 6. Почему это правильно для продукта

Такая схема нужна не ради архитектурной красоты, а ради продукта:

- пользователь получает быстрый старт сессии без зависимости от тяжёлой инфраструктуры
- продукт всё равно накапливает память и длинный контекст
- moat строится на `career state + evidence + adaptive routing`, а не на том, чтобы тащить весь infra stack в каждый запрос

## 7. Что уже подтверждено кодом

- session bootstrap читает `PostgreSQL` как основной источник состояния
- `Qdrant` подключается как optional retrieval layer
- `Neo4j` не участвует в bootstrap mainline
- vector sync больше не должен висеть на пользовательском request path

## 8. Что отложено сознательно

- graph digest materialization в session bootstrap
- зависимость start-of-session от `Neo4j`
- превращение `Qdrant` или `Neo4j` в primary source of truth

Следующий шаг не в re-analysis, а в спокойном наращивании moat-слоя поверх этой схемы:

- stronger STT
- evidence loop
- richer adaptive missions
