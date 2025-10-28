# Универсальный динамический промпт - Руководство по использованию

## Обзор

Вместо сложной агентной архитектуры (LangGraph с множеством агентов) мы используем **один универсальный промпт** с динамической подстановкой данных из PostgreSQL.

## Преимущества подхода

✅ **Простота**: Один промпт вместо оркестрации  
✅ **Производительность**: Один вызов LLM вместо нескольких  
✅ **Стоимость**: Меньше токенов  
✅ **Гибкость**: Легко добавлять новые поля из БД  
✅ **Отладка**: Проще понять, что происходит  

## Архитектура

```
User Message
    ↓
FastAPI Endpoint (/api/v1/chat/send)
    ↓
ContextBuilder → Извлекает данные из PostgreSQL
    ↓
UniversalPromptBuilder → Подставляет данные в промпт
    ↓
OpenAI API → Генерирует ответ
    ↓
PostgreSQL → Сохраняет utterance
```

## Компоненты

### 1. UniversalPromptBuilder (`app/prompts/universal.py`)

Строит промпт из динамических данных:

```python
from app.prompts.universal import build_universal_prompt

prompt = build_universal_prompt(
    user_profile=user_profile,
    interests=interests,
    memories=memories,
    recent_utterances=utterances,
    progress=progress,
    session_context=session_context
)
```

### 2. ContextBuilder (`app/services/context_builder.py`)

Извлекает данные из PostgreSQL:

```python
from app.services.context_builder import ContextBuilder

builder = ContextBuilder(db)
context = await builder.build_full_context(
    user_id=123,
    session_id="session-uuid"
)
```

### 3. Chat API (`app/api/chat.py`)

Endpoint для отправки сообщений:

```python
POST /api/v1/chat/send
{
    "user_id": 123,
    "session_id": "uuid",
    "message": "Hello!"
}
```

## Что подставляется в промпт

### Из PostgreSQL:

1. **User Profile**
   - ID, username, language level (CEFR)
   - Session count, created date
   - Accent preference

2. **User Interests**
   - Topics с весами (0.0-1.0)
   - Last mentioned date
   - Сортировка по популярности

3. **Memories**
   - Fact, preference, goal, achievement
   - Salience score (0.0-1.0)
   - Created timestamp

4. **Recent Utterances**
   - Последние 10 реплик из сессии
   - Speaker (user/assistant)
   - Emotion code, grammar score

5. **Learning Progress**
   - Total XP points
   - Recent achievements
   - Learning plan

6. **Session Context**
   - Session ID, start time
   - Utterance count
   - Topics discussed
   - Dominant emotion

## Структура промпта

Промпт состоит из секций:

1. **Role & Identity** - Кто ты (Anna, English Friend)
2. **User Context** - Профиль, интересы, прогресс (динамически)
3. **Current Session** - Последние реплики, темы (динамически)
4. **Memory & History** - Воспоминания из БД (динамически)
5. **Adaptive Behavior** - Адаптация под CEFR level
6. **Output Guidelines** - Как отвечать, исправлять, поддерживать

## Пример использования

### Полный пример

```python
from app.services.context_builder import ContextBuilder
from app.prompts.universal import build_universal_prompt
import openai

# 1. Собрать контекст из БД
builder = ContextBuilder(db)
context = await builder.build_full_context(
    user_id=123,
    session_id="session-uuid"
)

# 2. Построить промпт
system_prompt = build_universal_prompt(
    user_profile=context['user_profile'],
    interests=context['interests'],
    memories=context['memories'],
    recent_utterances=context['recent_utterances'],
    progress=context['progress'],
    session_context=context['session_context']
)

# 3. Вызвать OpenAI API
response = await openai.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Hello!"}
    ]
)
```

### Быстрый старт с API

```bash
# 1. Запустить приложение
python main.py

# 2. Предпросмотр промпта для пользователя
curl http://localhost:8000/api/v1/chat/prompt-preview/123

# 3. Отправить сообщение
curl -X POST http://localhost:8000/api/v1/chat/send \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 123,
    "session_id": "session-uuid",
    "message": "Hello, how are you?"
  }'
```

## Адаптация под CEFR уровни

Промпт автоматически адаптируется под уровень пользователя:

- **A1**: Простые предложения, базовый словарь
- **A2**: Основные времена, повседневные темы
- **B1**: Разнообразные времена, мнения
- **B2**: Сложные структуры, абстрактные темы
- **C1**: Естественный язык, нюансы
- **C2**: Уровень носителя

Описания уровней находятся в `CEFR_LEVELS` в `UniversalPromptBuilder`.

## Отладка

### Просмотр промпта

Используйте endpoint `/api/v1/chat/prompt-preview/{user_id}` для просмотра того, что будет отправлено в LLM:

```bash
curl http://localhost:8000/api/v1/chat/prompt-preview/123
```

Ответ включает:
- Полный промпт
- Длину промпта
- Оценку токенов
- Сводку контекста

### Логирование

Промпт можно логировать для отладки:

```python
import logging

logger = logging.getLogger(__name__)
logger.info(f"Generated prompt: {system_prompt}")
```

## Что дальше

### Интеграция с OpenAI Realtime API

Когда будете готовы интегрировать голосовые звонки:

1. Замените `generate_ai_response()` в `app/api/chat.py`
2. Используйте OpenAI Realtime API для streaming
3. Добавьте WebRTC для передачи аудио

### Добавление новых полей

Чтобы добавить новые данные в промпт:

1. Добавьте поле в датакласс (например, `UserProfile`)
2. Извлеките данные в `ContextBuilder`
3. Добавьте секцию в `UniversalPromptBuilder._add_*_context()`

### Qdrant интеграция

Для векторной памяти:

1. Добавьте метод в `ContextBuilder.get_vector_memories()`
2. Используйте embeddings для семантического поиска
3. Добавьте секцию "Vector Memories" в промпт

## FAQ

**Q: Почему не используем LangGraph?**  
A: Для нашего use case одного промпта достаточно. LangGraph нужен для сложных агентных взаимодействий.

**Q: Как часто обновлять контекст?**  
A: После каждого utterance обновляйте промпт, чтобы AI видел актуальный контекст.

**Q: Что если промпт слишком длинный?**  
A: Ограничьте количество memories и utterances в `ContextBuilder`.

**Q: Можно ли использовать этот промпт для других задач?**  
A: Да, промпт универсальный. Можно адаптировать для обратной связи, анализа прогресса и т.д.

## Связанные файлы

- `app/prompts/universal.py` - Builder промпта
- `app/services/context_builder.py` - Извлечение данных из БД
- `app/api/chat.py` - API endpoint
- `app/models/core_tables.py` - SQLAlchemy модели

