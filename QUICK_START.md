# 🚀 Quick Start - Быстрый старт

## Быстрый запуск за 5 минут

### 1. Запуск инфраструктуры (1 мин)

```bash
# Перейдите в директорию проекта
cd /Users/gp/projects/ernis/englishFriend

# Запустите все сервисы
docker-compose -f docker-compose.cdc.yml up -d

# Проверьте что PostgreSQL запущен
docker exec englishfriend-postgres-1 pg_isready -U postgres
```

### 2. Запуск API сервера (1 мин)

```bash
# Активация виртуального окружения
source .venv/bin/activate

# Запуск сервера
python main.py
```

Сервер будет доступен на: http://localhost:8000

### 3. Проверка работы (30 сек)

```bash
# Проверка health
curl http://localhost:8000/health

# Открыть Swagger UI
open http://localhost:8000/docs
```

### 4. Тестирование (2 мин)

```bash
# Полный lifecycle тест
python test_user_lifecycle.py
```

## Основные команды

```bash
# Остановить все
docker-compose -f docker-compose.cdc.yml down

# Перезапустить API
pkill -f "python main.py" && python main.py &

# Посмотреть логи API
tail -f /tmp/api.log

# Посмотреть логи PostgreSQL
docker-compose -f docker-compose.cdc.yml logs -f postgres
```

## Эндпоинты API

### Пользователи
- `GET /api/v1/users/` - список пользователей
- `POST /api/v1/users/` - создать пользователя
- `GET /api/v1/users/{id}` - получить пользователя
- `PUT /api/v1/users/{id}` - обновить пользователя
- `DELETE /api/v1/users/{id}` - удалить пользователя

### Сессии
- `POST /api/v1/sessions/` - создать сессию
- `GET /api/v1/sessions/{id}` - получить сессию
- `GET /api/v1/sessions/user/{user_id}` - сессии пользователя

### Интересы
- `POST /api/v1/users/{user_id}/interests` - добавить интерес
- `GET /api/v1/users/{user_id}/interests` - список интересов

### XP события
- `POST /api/v1/xp-events/` - создать XP событие
- `GET /api/v1/users/{user_id}/xp-events` - события пользователя
- `GET /api/v1/users/{user_id}/xp-total` - общий XP

## Документация

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Помощь

Полная документация: см. `INTEGRATION_SUMMARY.md`

