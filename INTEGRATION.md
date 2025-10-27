# Интеграция FastAPI с SQL миграциями

## Архитектура

Проект использует **гибридный подход**:

1. **SQL миграции** (`db/migrations/postgres/`) - источник истины для схемы БД
2. **SQLAlchemy модели** (`app/models/`) - для работы FastAPI API
3. **Синхронизация** - модели обновлены согласно миграциям

## Структура

```
englishFriend/
├── db/                     # SQL миграции (источник истины)
│   ├── migrations/postgres/ # Чистые SQL миграции
│   ├── seed/               # Тестовые данные
│   └── tests/              # pgTAP тесты
├── app/                    # FastAPI приложение
│   ├── models/            # SQLAlchemy модели (синхронизированы с db/)
│   ├── api/               # API endpoints
│   ├── schemas/           # Pydantic схемы
│   └── services/          # Бизнес-логика
├── sync-vector/           # Синхронизация с Qdrant
├── sync-graph/            # Синхронизация с Neo4j
└── scripts/               # Вспомогательные скрипты
```

## Использование

### 1. Инициализация БД через SQL миграции

```bash
# Запустить PostgreSQL
docker-compose up -d postgres

# Применить миграции
psql $DATABASE_URL -f db/migrations/postgres/000_init.sql
psql $DATABASE_URL -f db/migrations/postgres/001_reference_tables.sql
psql $DATABASE_URL -f db/migrations/postgres/002_users.sql
psql $DATABASE_URL -f db/migrations/postgres/003_sessions_utterances.sql
psql $DATABASE_URL -f db/migrations/postgres/004_partition_management.sql
psql $DATABASE_URL -f db/migrations/postgres/005_memories_learning_plan.sql
psql $DATABASE_URL -f db/migrations/postgres/006_materialized_views.sql

# Заполнить справочники
psql $DATABASE_URL -f db/seed/001_reference_seed.sql
```

### 2. Запуск FastAPI

```bash
# Запустить FastAPI сервер
python main.py

# Или через Makefile
make start
```

FastAPI будет использовать существующую схему БД, созданную через SQL миграции.

**⚠️ ВАЖНО:** SQLAlchemy модели НЕ создают таблицы автоматически в production. Они используются только для:
- Валидации запросов через Pydantic
- Типизации кода
- ORM операции (CRUD)

Таблицы создаются через SQL миграции, которые являются источником истины.

