# English Friend API - Этап 3

FastAPI сервер с PostgreSQL интеграцией для проекта ИИ-репетитора по английскому языку.

## Что мы создали

- Полная интеграция с PostgreSQL через SQLAlchemy
- Async/await для работы с базой данных
- Docker Compose для PostgreSQL
- SQLAlchemy ORM модели (User, Session)
- Автоматическая инициализация БД при запуске
- Dependency injection для сессий БД

## Установка и запуск

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Запуск PostgreSQL

```bash
# Через Makefile (рекомендуется)
make start-db

# Или напрямую через Docker Compose
docker-compose up -d postgres
```

### 3. Запуск приложения

```bash
# Через Makefile
make start

# Или напрямую
python main.py
```

### 4. Тестирование

После запуска сервер будет доступен по адресу: http://localhost:8001

**Доступные endpoints:**

**Базовые:**
- `GET /health` - проверка здоровья сервера
- `GET /api/v1/hello` - приветственное сообщение
- `GET /api/v1/status` - статус всех компонентов системы

**Пользователи:**
- `POST /api/v1/users/` - создать пользователя
- `GET /api/v1/users/{user_id}` - получить пользователя по ID
- `GET /api/v1/users/` - список пользователей (с пагинацией)
- `PUT /api/v1/users/{user_id}` - обновить пользователя
- `DELETE /api/v1/users/{user_id}` - удалить пользователя
- `GET /api/v1/users/telegram/{telegram_id}` - получить по Telegram ID

**Сессии:**
- `POST /api/v1/sessions/` - создать сессию
- `GET /api/v1/sessions/{session_id}` - получить сессию
- `GET /api/v1/sessions/user/{user_id}` - сессии пользователя
- `PUT /api/v1/sessions/{session_id}` - обновить сессию
- `POST /api/v1/sessions/{session_id}/complete` - завершить сессию

**Автодокументация:**

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Что изучили

✅ **PostgreSQL интеграция**: подключение через SQLAlchemy и asyncpg  
✅ **Async/await**: асинхронная работа с базой данных  
✅ **SQLAlchemy ORM**: модели, отношения, запросы  
✅ **Dependency injection**: автоматическое управление сессиями БД  
✅ **Docker Compose**: контейнеризация PostgreSQL  
✅ **Lifespan events**: инициализация БД при запуске приложения  
✅ **Тестирование**: pytest, моки, тестирование API и схем  
✅ **Виртуальные окружения**: правильная изоляция зависимостей  

## Тестирование

Проект включает комплексную систему тестирования:

### Структура тестов
```
tests/
├── test_config.py      # Тесты конфигурации
├── test_schemas.py     # Тесты Pydantic схем
├── test_api.py         # Тесты API endpoints
└── test_services.py    # Тесты бизнес-логики
```

### Результаты тестирования
- **✅ Unit тесты**: 15/15 пройдено (конфигурация, схемы)
- **⚠️ Integration тесты**: требуют запущенной БД
- **📊 Покрытие**: основные компоненты покрыты тестами

### Запуск тестов
```bash
# Все тесты
pytest tests/ -v

# Только unit тесты (без БД)
pytest tests/test_config.py tests/test_schemas.py -v

# С покрытием
pytest --cov=app tests/

# Только failed тесты
pytest --lf
```

### Типы тестов
- **Unit тесты**: изолированные компоненты (схемы, конфигурация)
- **Integration тесты**: взаимодействие с БД (требуют PostgreSQL)
- **API тесты**: HTTP endpoints с моками
- **Service тесты**: бизнес-логика с моками БД

## Следующий этап

На этапе 4 мы добавим:
- Расширенную схему БД (utterances, feedback, memories)
- Справочники (emotions, topics, accents)
- JSONB поля для гибкого хранения данных
- Сложные отношения между таблицами

## Полезные команды

```bash
# Управление через Makefile
make help          # Показать все команды
make start-db       # Запустить только PostgreSQL
make start          # Запустить PostgreSQL + приложение
make stop           # Остановить все сервисы
make logs           # Показать логи PostgreSQL
make clean          # Очистить данные БД
make test-db         # Протестировать подключение к БД

# Тестирование
make test           # Запустить все тесты
make test-unit      # Запустить только unit тесты
make test-integration # Запустить integration тесты
make lint           # Проверить код линтерами
make format         # Форматировать код

# Прямые команды
docker-compose up -d postgres    # Запуск PostgreSQL
docker-compose down              # Остановка всех сервисов
python main.py                   # Запуск приложения
pytest tests/ -v                # Запуск тестов
```

## Структура проекта

```
englishFriend/
├── app/
│   ├── api/           # API endpoints (роутеры)
│   ├── core/          # Настройки и подключения
│   ├── models/        # SQLAlchemy модели
│   ├── schemas/       # Pydantic схемы
│   └── services/      # Бизнес-логика
├── docker-compose.yml # PostgreSQL контейнер
├── init.sql          # SQL скрипт инициализации
├── main.py           # Главный файл приложения
├── Makefile          # Команды управления
├── requirements.txt  # Зависимости
└── README.md        # Документация
```

## 🎯 Этап 4: Расширенная схема БД

### Новые возможности

**Справочники:**
- `GET /api/v1/dimensions/emotions/` - список эмоций
- `GET /api/v1/dimensions/topics/` - список тем  
- `GET /api/v1/dimensions/accents/` - список акцентов

**Реплики и обратная связь:**
- `POST /api/v1/utterances/` - создать реплику
- `GET /api/v1/sessions/{id}/utterances` - реплики сессии
- `POST /api/v1/feedback/` - создать обратную связь
- `GET /api/v1/sessions/{id}/feedback` - обратная связь сессии
- `POST /api/v1/corrections/` - создать исправление

**Память и интересы:**
- `POST /api/v1/memories/` - создать запись памяти
- `GET /api/v1/users/{id}/memories` - память пользователя
- `POST /api/v1/users/{id}/interests` - добавить интерес
- `GET /api/v1/users/{id}/interests` - интересы пользователя

**Обучение и XP:**
- `POST /api/v1/learning-plans/` - создать план обучения
- `GET /api/v1/users/{id}/learning-plan` - активный план
- `POST /api/v1/xp-events/` - создать событие XP
- `GET /api/v1/users/{id}/xp-total` - общий XP

**Эмоции:**
- `POST /api/v1/emotional-logs/` - записать эмоцию
- `GET /api/v1/users/{id}/emotional-logs` - лог эмоций

### Заполнение тестовыми данными

```bash
# Заполнить БД тестовыми данными
make seed-db

# Или полная переустановка с данными
make reset-with-data
```

### Структура БД

**Основные таблицы:**
- `users` - пользователи с предпочтениями
- `sessions` - сессии с анализом речи
- `utterances` - реплики с временными метками
- `feedback` - детальная обратная связь
- `corrections` - исправления с объяснениями

**Дополнительные таблицы:**
- `user_interest` - интересы пользователей
- `memories` - канонические записи памяти
- `learning_plan` - планы обучения
- `xp_events` - события и очки опыта
- `emotional_state_log` - лог эмоций

**Справочники:**
- `dim_emotion` - эмоции с валентностью/возбуждением
- `dim_topic` - темы с иерархией
- `dim_accent` - акценты английского языка

## 🔗 Интеграция с SQL миграциями

Проект интегрирован с SQL миграциями коллеги (`db/migrations/postgres/`):
- SQL миграции - источник истины для схемы БД
- SQLAlchemy модели синхронизированы с миграциями
- FastAPI использует существующую схему БД
- Интеграционные тесты проверяют совместимость моделей с SQL схемой

Подробности: см. [INTEGRATION.md](INTEGRATION.md)

## 🧪 Тестирование

Проект включает полное покрытие тестами:

**Unit тесты** (без БД):
- `tests/test_config.py` - тесты конфигурации
- `tests/test_schemas.py` - тесты Pydantic схем

**Интеграционные тесты** (с БД):
- `tests/test_integration_users.py` - Users CRUD с реальной БД
- `tests/test_integration_sessions.py` - Sessions CRUD с реальной БД
- `tests/test_integration_additional.py` - Utterances, Feedback, Dimensions
- `tests/test_model_schema_compatibility.py` - проверка совместимости моделей с SQL

**Запуск тестов:**
```bash
# Все тесты
pytest tests/ -v

# Только unit тесты
pytest tests/test_config.py tests/test_schemas.py -v

# Только интеграционные тесты (требуют PostgreSQL)
pytest tests/test_integration_*.py tests/test_model_*.py -v
```

## 🚀 Следующие этапы

- **Этап 5**: Интеграция с Qdrant (векторная БД) ✅ Уже есть в `sync-vector/`
- **Этап 6**: Интеграция с Neo4j (графовая БД) ✅ Уже есть в `sync-graph/`
- **Этап 7**: Endpoints для Telegram бота
- **Этап 8**: Docker-контейнеризация всего стека ✅ Частично готово