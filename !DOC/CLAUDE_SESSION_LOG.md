# Claude Session Log

Этот файл ведётся AI-агентами для отслеживания прогресса между сессиями.
При обрыве сессии - читай этот файл чтобы понять контекст и продолжить работу.

---

## Последнее обновление: 2026-01-19 13:15

### Текущий статус проекта
**MVP Ready**: ~90%
**Backend**: FastAPI на порту 8000
**Frontend**: React/Vite на порту 5173
**База данных**: PostgreSQL (Docker CDC stack)
**Мониторинг**: Prometheus (9090) + Grafana (3000) - **РАБОТАЕТ!**

---

## Активные задачи

### 1. Backend Monitoring - ✅ ПОЛНОСТЬЮ РАБОТАЕТ
**Цель**: Сделать бекенд полностью прозрачным для отладки
**Статус**: Voice метрики работают и видны в Prometheus/Grafana!

**Проверено 2026-01-19**:
- `curl localhost:8000/metrics | grep voice_` → показывает все метрики
- `curl localhost:9090/api/v1/query?query=voice_sessions_total` → Prometheus видит данные
- 1 сессия завершена успешно (mode=assessment, status=completed)
- LLM latency: ~1.03 сек
- TTS latency: ~1.3 сек
- Total turn: ~2.37 сек

**Что сделано**:
- Добавлены Voice метрики в `app/core/metrics.py`:
  - `voice_sessions_active` - активные WebSocket сессии
  - `voice_sessions_total` - счётчик по mode/status
  - `voice_llm_latency_seconds` - latency Groq LLM
  - `voice_tts_latency_seconds` - latency edge-tts
  - `voice_turn_total_seconds` - полный turn (LLM+TTS)
  - `voice_messages_total` - inbound/outbound счётчики
  - `voice_errors_total` - ошибки по стадиям (llm/tts/db/websocket)
- Инструментирован `app/api/voice.py` метриками
- Создан Grafana dashboard `monitoring/grafana/dashboards/voice-backend.json`
- Все `print()` заменены на `logger`

**Проверка метрик**:
```bash
curl http://localhost:8000/metrics | grep voice_
# Показывает: voice_sessions_total, voice_llm_latency_seconds, etc.
```

**Grafana**: http://localhost:3000 (admin/admin)
- Dashboard: "Voice Backend Monitor"

### 2. PostgreSQL Auth Issue - ✅ ИСПРАВЛЕНО
**Было**: `password authentication failed for user "postgres"`
**Причина**: Разные пароли в `.env` и docker-compose.cdc.yml
**Решение**: Исправлен `.env`:
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/englishfriend_dev
```

### 3. Баг: Vocabulary cards не создаются при определении цели
**Статус**: В процессе (отложено из-за DB auth)
**Проблема**: `recommended_vocabulary` возвращает пустой список
**Причина**: SQLAlchemy не отслеживает изменения вложенных JSON

---

## Недавно выполненные задачи

### Рефакторинг LLM (8 пунктов) - ✅ ВЫПОЛНЕНО
Все 8 пунктов из STRATEGY.md уже реализованы:
1. ✅ Удалён `groq_llm.py`
2. ✅ `groq_model` в config.py:38
3. ✅ `llm_temperature` в config.py:47
4. ✅ Timeouts в config.py:39,44
5. ✅ `import re` в voice.py:18
6. ✅ Retry логика (tenacity) в llm_provider.py:23
7. ✅ `sanitize_user_input()` в llm_provider.py:54
8. ✅ Тесты в tests/test_llm_provider.py

### Data Flow Logger - ✅ ВЫПОЛНЕНО
**Файл**: `app/services/data_flow_logger.py`
Логирует все записи в БД с цветными тегами `[DATA-FLOW]`

### Goal Detection - ✅ ВЫПОЛНЕНО
**Файл**: `app/services/learning_plan_service.py:394-457`
Функция `detect_goal_from_message()` с fuzzy matching для STT искажений

### Gamification (Streaks + XP) - ✅ ВЫПОЛНЕНО
**Файлы**:
- `app/services/gamification/xp_service.py`
- `app/services/gamification/streak_service.py`
- `db/migrations/postgres/010_streaks_gamification.sql`

---

## Известные проблемы

### 1. OpenAI API Key для Embeddings
```
ERROR: Incorrect API key provided: dummy
```
**Файл**: `app/services/ai/embedding_service.py`
**Решение**: Установить корректный `OPENAI_API_KEY` в `.env` или отключить RAG memory

### 2. Vosk STT фрагментация
**Статус**: Исправлено в `useVoskWithVAD.ts`
Добавлен аккумулятор для накопления partial results

---

## Архитектурные заметки

### Педагогические режимы
4 режима в `app/services/ai/mode_selector.py`:
- ASSESSMENT - оценка уровня
- MOCK_INTERVIEW - симуляция собеседования
- VOCABULARY_DRILL - повторение слов (FSRS)
- FREE_CONVERSATION - свободный разговор

### Выбор режима
```python
if no_recent_assessment: return ASSESSMENT
if due_vocabulary >= 10: return VOCABULARY_DRILL
if goal == "interview": return MOCK_INTERVIEW
return FREE_CONVERSATION
```

### Multi-Agent Research
Добавлена секция в STRATEGY.md о LangGraph + Gradient Boosting архитектуре.
Это для будущего рассмотрения, не для текущей реализации.

---

## Команды для быстрого старта

```bash
# Запуск PostgreSQL
docker compose up -d postgres

# Запуск backend
cd /Users/macbook/Desktop/englishFriend
source venv/bin/activate
python main.py

# Запуск frontend
cd frontend
npm run dev

# Проверка health
curl --noproxy localhost http://localhost:8000/health

# Сброс learning_plan для тестов
docker exec -i englishfriend-postgres-1 psql -U postgres -d english_friend -c "UPDATE learning_plan SET roadmap = '{}' WHERE user_id = 1;"
```

---

## История сессий

### 2026-01-11 (текущая)
- Обнаружено что все 8 пунктов рефакторинга уже выполнены
- Добавлена секция Multi-Agent + ML Scoring в STRATEGY.md
- Работа над багом vocabulary cards (SQLAlchemy JSON mutation)
- Добавлена кнопка End Session
- Создан этот файл для трекинга между сессиями

### 2026-01-10 (предыдущая)
- Реализован Data Flow Logger
- Реализован Goal Detection с fuzzy matching
- Добавлен PostSessionService для генерации flashcards
- Исправлена фрагментация Vosk STT
