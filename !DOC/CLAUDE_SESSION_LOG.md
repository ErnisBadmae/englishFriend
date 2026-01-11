# Claude Session Log

Этот файл ведётся AI-агентами для отслеживания прогресса между сессиями.
При обрыве сессии - читай этот файл чтобы понять контекст и продолжить работу.

---

## Последнее обновление: 2026-01-11 02:45

### Текущий статус проекта
**MVP Ready**: ~90%
**Backend**: FastAPI на порту 8000
**Frontend**: React/Vite на порту 5173
**База данных**: PostgreSQL (контейнер `englishfriend-postgres-1`)

---

## Активные задачи

### 1. Баг: Vocabulary cards не создаются при определении цели
**Статус**: В процессе исправления
**Проблема**: При автоматическом определении цели из сообщения пользователя, `recommended_vocabulary` возвращает пустой список
**Причина**: SQLAlchemy не отслеживает изменения вложенных JSON объектов
**Что сделано**:
- Добавлен `flag_modified(plan, 'roadmap')` в `learning_plan_service.py:171`
- Добавлена отладочная печать в `voice.py:323-328`
**Что нужно сделать**:
- Сбросить roadmap в БД: `docker exec -i englishfriend-postgres-1 psql -U postgres -d english_friend -c "UPDATE learning_plan SET roadmap = '{}' WHERE user_id = 1;"`
- Перезапустить backend
- Протестировать голосовой чат, сказав "I want to prepare for ML interview"
- Проверить логи: должно быть `[DEBUG] recommended_vocabulary: ['implementation', ...]`

### 2. Кнопка End Session
**Статус**: Реализовано, требует тестирования
**Что сделано**:
- Добавлена кнопка "End Session & See Summary" в `VoiceChatV2.tsx:267-274`
- При нажатии отправляется `{"type": "end"}` через WebSocket
- Backend вызывает `PostSessionService` для генерации flashcards
**CSS**: `VoiceChat.css:359-386`

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
