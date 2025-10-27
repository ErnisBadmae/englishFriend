# Синхронизация FastAPI с архитектурой коллеги

## Принципы

**Коллега является ключевым разработчиком** - его SQL миграции (`db/migrations/postgres/`) являются источником истины для схемы БД.

## Соответствие схем

### ✅ Полностью синхронизировано

1. **Users** (`002_users.sql`)
   - Строго по SQL схеме
   - Поддержка partitioning отсутствует (PostgreSQL управляет это автоматически)

2. **Sessions** (`003_sessions_utterances.sql`)
   - Partitioning по `started_at` (PostgreSQL управляет автоматически)
   - Поля: id, user_id, started_at, ended_at, audio_url, lang_code, call_quality
   - **Нет поля `status`** в SQL - это добавочное поле FastAPI для удобства

3. **Utterances** (`003_sessions_utterances.sql`)
   - Partitioning по hash(session_id) на 8 частей
   - Все поля соответствуют SQL схеме
   - Эмоции хранятся в `emotion_code` и `emotion_score` (не отдельная таблица)

4. **Feedback** (`003_sessions_utterances.sql`)
   - **Только 4 поля**: overall_grammar, overall_pronunciation, summary_md, tips_md
   - Удалены лишние поля: corrected_phrases, grammar_tips, pronunciation_tips, vocabulary_suggestions

5. **Corrections** (`003_sessions_utterances.sql`)
   - Все поля соответствуют SQL схеме

6. **Memories** (`005_memories_learning_plan.sql`)
   - Опциональное поле `embedding` для vector extension
   - Поля salience, last_refreshed соответствуют SQL

7. **LearningPlan** (`005_memories_learning_plan.sql`)
   - Все поля соответствуют SQL схеме

8. **XPEvents** (`005_memories_learning_plan.sql`)
   - Partitioning по happened_at (PostgreSQL управляет автоматически)

9. **Справочники** (`001_reference_tables.sql`)
   - DimEmotion, DimTopic, DimAccent - полностью соответствуют

### ❌ Отличия от SQL (с обоснованием)

1. **Session.status** - добавлено в FastAPI для удобства управления статусами сессий
   - В SQL статус вычисляется через ended_at IS NULL
   - FastAPI требует явного статуса для API

2. **Партиционирование** - управляется PostgreSQL автоматически
   - SQLAlchemy модели не требуют явного объявления партиций
   - PostgreSQL создает партиции по SQL миграциям

3. **RLS Policies** - не реализованы в SQLAlchemy
   - Управляются на уровне PostgreSQL через SQL миграции
   - FastAPI не требует явной реализации RLS

## Интеграция с компонентами коллеги

### sync-vector (CDC -> Qdrant)
- Слушает Kafka события из PostgreSQL CDC
- Синхронизирует memories в Qdrant
- FastAPI не изменяет данные в memories напрямую - только читает

### sync-graph (CDC -> Neo4j)
- Слушает Kafka события из PostgreSQL CDC
- Синхронизирует sessions в Neo4j
- FastAPI создает sessions в PostgreSQL - CDC автоматически синхронизирует в Neo4j

## Правила разработки

1. **SQL миграции коллеги - источник истины**
   - Все изменения схемы БД сначала в SQL миграциях
   - Потом синхронизация SQLAlchemy моделей

2. **Дополнительные поля FastAPI - с пометкой**
   - Любое поле, которого нет в SQL - должно быть четко документировано
   - Пример: `Session.status` - вычисляется из ended_at, но удобно для API

3. **Партиционирование через PostgreSQL**
   - Не пытаться управлять партициями в SQLAlchemy
   - Доверить PostgreSQL автоматическое создание по SQL миграциям

4. **CDC синхронизация прозрачна**
   - FastAPI работает только с PostgreSQL
   - Qdrant и Neo4j синхронизируются автоматически через CDC

## Проверка соответствия

Запустить SQL миграции коллеги:
```bash
# Запуск миграций через Liquibase или psql
psql $DATABASE_URL -f db/migrations/postgres/000_init.sql
psql $DATABASE_URL -f db/migrations/postgres/001_reference_tables.sql
psql $DATABASE_URL -f db/migrations/postgres/002_users.sql
psql $DATABASE_URL -f db/migrations/postgres/003_sessions_utterances.sql
psql $DATABASE_URL -f db/migrations/postgres/004_partition_management.sql
psql $DATABASE_URL -f db/migrations/postgres/005_memories_learning_plan.sql
```

Запустить FastAPI с тестовыми данными:
```bash
make seed-users
make start-app
```

Проверить endpoints:
```bash
curl http://localhost:8000/api/v1/users/
curl http://localhost:8000/api/v1/sessions/
curl http://localhost:8000/docs
```
