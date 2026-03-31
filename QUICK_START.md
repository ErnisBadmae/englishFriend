# 🚀 Quick Start - Быстрый старт

Универсальная инструкция для запуска EnglishFriend на Windows, Linux и Mac.

---

## 📋 Предварительные требования

- Python 3.12
- Node.js 18+ (для фронтенда)
- Docker и Docker Compose (для базы данных и инфраструктуры)
- Git

---

## 🎯 Быстрый запуск за 5 минут

### 1. Запуск инфраструктуры (1 мин)

```bash
# Запустить все сервисы (PostgreSQL + Kafka + Neo4j + Qdrant + sync services)
docker-compose -f docker-compose.cdc.yml up -d

# Проверить что PostgreSQL запущен
docker exec englishfriend-postgres-1 pg_isready -U postgres
# Ожидаемый вывод: /var/run/postgresql:5432 - accepting connections
```

**Что запустилось:**
- PostgreSQL (порт 5432)
- Kafka + Zookeeper (порт 9092)
- Debezium (порт 8083)
- Neo4j (порт 7474, 7687)
- Qdrant (порт 6333)
- sync-vector и sync-graph сервисы

---

### 2. Запуск API сервера (1 мин)

#### Windows (PowerShell)

```powershell
# Активировать виртуальное окружение
venv\Scripts\activate

# Проверить, что FastAPI установлен
python -c "import fastapi; print(fastapi.__version__)"
# Должно вывести: 0.128.0

# Запустить сервер
python main.py
```

**Альтернатива (если venv не активируется):**
```powershell
# Прямой запуск через полный путь к Python в venv
venv\Scripts\python.exe main.py
```

#### Linux / Mac

```bash
# Активировать виртуальное окружение
source venv/bin/activate

# Проверить, что FastAPI установлен
python -c "import fastapi; print(fastapi.__version__)"

# Запустить сервер
python main.py
```

**Сервер будет доступен на:** http://localhost:8000

---

### 3. Запуск фронтенда (30 сек)

Откройте **новый терминал** (не закрывая сервер):

#### Windows (PowerShell)

```powershell
cd frontend
npm run dev
```

#### Linux / Mac

```bash
cd frontend
npm run dev
```

**Фронтенд будет доступен на:** http://localhost:5173

---

### 4. Проверка работы (30 сек)

#### Windows

```powershell
# Проверка health
curl http://localhost:8000/health

# Открыть Swagger UI
start http://localhost:8000/docs
```

#### Linux / Mac

```bash
# Проверка health
curl http://localhost:8000/health

# Открыть Swagger UI
open http://localhost:8000/docs
```

**Ожидаемый ответ:**
```json
{"status": "healthy"}
```

---

## 🔧 Первоначальная настройка (для нового компьютера)

### 1. Клонирование репозитория

```bash
git clone https://github.com/ErnisBadmae/englishFriend.git
cd englishFriend
git checkout main  # или dev, в зависимости от ветки
```

---

### 2. Настройка бэкенда (Python 3.12)

#### Windows

```powershell
# Создать виртуальное окружение
py -3.12 -m venv venv

# Активировать venv
venv\Scripts\activate

# Установить зависимости
pip install -r requirements.txt

# Скопировать файл окружения
copy .env.example .env

# Отредактировать .env: выбрать LLM_PROVIDER и настроить VLLM_/LLAMA_CPP_/OPENAI_ переменные
```

#### Linux / Mac

```bash
# Создать виртуальное окружение
python3.12 -m venv venv

# Активировать venv
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Скопировать файл окружения
cp .env.example .env

# Отредактировать .env: выбрать LLM_PROVIDER и настроить VLLM_/LLAMA_CPP_/OPENAI_ переменные
```

---

### 3. Настройка фронтенда

```bash
cd frontend
npm install
cd ..
```

---

### 3.1. Настройка LLM backend

Для тестов через корпоративный кластер по умолчанию используется `LLM_PROVIDER=vllm`.

#### GPU vLLM (Qwen 32B)

```env
LLM_PROVIDER=vllm
VLLM_BASE_URL=http://192.168.0.27:8000/v1
VLLM_API_KEY=token-abc123
VLLM_MODEL=qwen32b-32k
```

#### CPU llama.cpp (Qwen 3.5 35B, большой контекст)

```env
LLM_PROVIDER=llama_cpp
LLAMA_CPP_BASE_URL=http://192.168.0.18:8001/v1
LLAMA_CPP_MODEL=qwen3.5-35b
```

#### OpenAI fallback

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_CHAT_MODEL=gpt-4o-mini
```

#### PersonaPlex speech-to-speech

```env
PERSONAPLEX_ENABLED=true
PERSONAPLEX_HOST=192.168.0.18
PERSONAPLEX_PORT=8998
PERSONAPLEX_DEFAULT_VOICE=NATM0
PERSONAPLEX_QUANTIZATION=int8
```

- Health check: `curl http://192.168.0.18:8998/health`
- Voice WebSocket: `ws://192.168.0.18:8998/api/chat`
- Node3 already runs `Open WebUI`, `Docling`, and `llama.cpp`, so if GPU pressure appears reduce PersonaPlex concurrency first.

#### Важно про embeddings / RAG

- Чат и voice path могут работать через корпоративный кластер без OpenAI.
- Векторная память и embeddings по-прежнему используют `OPENAI_API_KEY`.
- Если `OPENAI_API_KEY` не задан или `VECTOR_MEMORY_ENABLED=false`, приложение переходит в DB-only режим для памяти и не должно ломать основной chat flow.

---

### 4. Настройка базы данных

```bash
# Запустить PostgreSQL (и всю инфраструктуру)
docker-compose -f docker-compose.cdc.yml up -d

# Проверить статус
docker ps
```

**Примечание:** Миграции применяются автоматически через SQLAlchemy при старте приложения.

---

### 5. Проверка Vosk модели (для STT)

```bash
# Проверить наличие Vosk модели
ls -la frontend/public/vosk-model-small-en-us-0.15.zip
# Должен быть ~46MB
```

**Если модель отсутствует:**

#### Windows
```powershell
cd frontend\public
curl -LO https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
cd ..\..
```

#### Linux / Mac
```bash
cd frontend/public
curl -LO https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
cd ../..
```

---

## 📚 Основные команды

### Остановка сервисов

```bash
# Остановить все Docker контейнеры
docker-compose -f docker-compose.cdc.yml down

# Остановить только PostgreSQL
docker-compose down
```

### Перезапуск API сервера

#### Windows
```powershell
# Найти процесс и убить
tasklist | findstr python
taskkill /F /PID <PID>

# Или просто Ctrl+C в терминале, где запущен сервер
# Потом запустить снова
python main.py
```

#### Linux / Mac
```bash
# Убить процесс
pkill -f "python main.py"

# Запустить снова
python main.py
```

### Просмотр логов

```bash
# Логи PostgreSQL
docker-compose -f docker-compose.cdc.yml logs -f postgres

# Логи Kafka
docker-compose -f docker-compose.cdc.yml logs -f kafka

# Логи sync-vector
docker-compose -f docker-compose.cdc.yml logs -f sync-vector

# Логи sync-graph
docker-compose -f docker-compose.cdc.yml logs -f sync-graph
```

---

## 🌐 Эндпоинты API

### Документация
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

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

### WebSocket
- `ws://localhost:8000/ws/voice/{user_id}` - WebSocket для голосового взаимодействия

---

## 🧪 Тестирование

### Запуск всех тестов

```bash
pytest tests/ -v
```

### Запуск конкретных тестов

```bash
# Unit тесты
pytest tests/ -m unit -v

# Integration тесты
pytest tests/ -m integration -v

# Тесты API
pytest tests/test_api/ -v

# Тесты helpers (после code simplification)
pytest tests/test_voice_helpers.py -v
pytest tests/test_response_mappers.py -v
pytest tests/test_logger_helpers.py -v
pytest tests/test_query_helpers.py -v
```

---

## ⚠️ Типичные проблемы и решения

### 1. ModuleNotFoundError: No module named 'fastapi'

**Причина:** Запускаете глобальный Python вместо venv.

**Решение:**
- Windows: `venv\Scripts\activate` затем `python main.py`
- Linux/Mac: `source venv/bin/activate` затем `python main.py`
- Или используйте полный путь: `venv\Scripts\python.exe main.py` (Windows) / `venv/bin/python main.py` (Linux/Mac)

### 2. Database connection error

**Причина:** PostgreSQL не запущен.

**Решение:**
```bash
docker-compose -f docker-compose.cdc.yml up -d postgres
docker exec englishfriend-postgres-1 pg_isready -U postgres
```

### 3. Frontend не запускается

**Причина:** Зависимости не установлены.

**Решение:**
```bash
cd frontend
npm install
npm run dev
```

### 4. Vosk model not found

**Причина:** Модель не загружена.

**Решение:**
```bash
cd frontend/public
curl -LO https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
```

---

## 📁 Структура проекта

```
englishFriend/
├── app/                    # Backend (FastAPI)
│   ├── api/               # API routers
│   ├── core/              # Config and database
│   ├── models/            # SQLAlchemy models
│   ├── schemas/           # Pydantic schemas
│   └── services/          # Business logic
├── frontend/              # Frontend (Vue.js/Vite)
│   ├── src/              # Source code
│   └── public/           # Static files (включая Vosk модель)
├── db/                    # Database migrations and seeds
├── tests/                 # Тесты
├── docker-compose.yml     # Docker конфигурация (PostgreSQL only)
├── docker-compose.cdc.yml # Full CDC stack
├── main.py               # FastAPI entry point
├── requirements.txt      # Python dependencies
└── .env                  # Environment configuration
```

---

## 📖 Дополнительная документация

- **Система управления документацией**: [!DOC/DOCUMENTATION_SYSTEM.md](!DOC/DOCUMENTATION_SYSTEM.md) - Как агенты поддерживают документацию
- **Полная документация системы**: [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)
- **Стратегия развития**: [!DOC/STRATEGY.md](!DOC/STRATEGY.md)
- **Интеграция CDC**: [cdc/README.md](cdc/README.md)
- **Упрощение кода**: [SIMPLIFICATION_PROGRESS.md](SIMPLIFICATION_PROGRESS.md)
- **База данных**: [db/README.md](db/README.md)
- **Graph layer (Neo4j)**: [graph/README.md](graph/README.md)

---

## ✅ Чеклист готовности

Перед началом разработки убедитесь:

- [ ] Python 3.12 установлен
- [ ] Node.js 18+ установлен
- [ ] Docker и Docker Compose установлены
- [ ] Git установлен
- [ ] Репозиторий склонирован
- [ ] Virtual environment создан и активирован
- [ ] Python зависимости установлены (`pip install -r requirements.txt`)
- [ ] Frontend зависимости установлены (`npm install` в папке frontend)
- [ ] Файл `.env` создан и настроен (выбран `LLM_PROVIDER`, cluster/OpenAI переменные заполнены по сценарию)
- [ ] Docker контейнеры запущены (`docker-compose -f docker-compose.cdc.yml up -d`)
- [ ] PostgreSQL работает (`docker exec englishfriend-postgres-1 pg_isready`)
- [ ] Vosk модель загружена (`frontend/public/vosk-model-small-en-us-0.15.zip`)
- [ ] Backend запущен (http://localhost:8000/health возвращает `{"status": "healthy"}`)
- [ ] Frontend запущен (http://localhost:5173 открывается в браузере)

---

## 🚀 Готово!

После выполнения всех шагов у вас должны быть:
- ✅ Backend API на http://localhost:8000
- ✅ Frontend UI на http://localhost:5173
- ✅ Swagger docs на http://localhost:8000/docs
- ✅ PostgreSQL, Kafka, Neo4j, Qdrant работают в Docker

**Можно начинать разработку!** 🎉
