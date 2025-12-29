# Анализ реализации голосового взаимодействия для English Friend

## Executive Summary

**Рекомендация:** Гибридный подход с приоритетом на классический pipeline (Whisper + GPT-4o + Azure TTS)

**Почему:**
- Экономически жизнеспособно: $0.62 за сессию против $0.81
- Доступно сразу (не нужен beta-доступ к Realtime API)
- Достаточное качество для MVP
- Возможность перехода на Realtime API позже

---

## Сравнительный анализ подходов

### Подход 1: OpenAI Realtime API

#### Технические характеристики

```
User Audio → WebRTC → OpenAI Realtime API → Audio Response
                            ↓
                    Universal Prompt (динамически)
```

**Стек:**
- OpenAI Realtime API (gpt-4o-realtime-preview)
- WebRTC (aiortc на бэкенде)
- Azure Speech Service (только для пост-анализа)
- FastAPI WebSockets

#### Плюсы

 **Низкая латентность:** 300-500ms (как с человеком)  
 **Естественность:** Может перебивать, паузы, эмоции в голосе  
 **Простота интеграции:** Один API решает STT + LLM + TTS  
 **Качество голоса:** Естественный эмоциональный голос  
 **Прерывания:** Пользователь может перебить AI  

#### Минусы

 **Стоимость:** $0.81 за сессию 2.5 мин (дороже на 30%)  
 **Beta-доступ:** Нужен запрос на доступ (неопределённость)  
 **Сложность WebRTC:** Больше инфраструктуры  
 **Меньше контроля:** Нельзя выбрать голос, параметры  
 **Зависимость:** Один vendor для всего  

#### Экономика (2.5 мин сессия)

| Компонент | Стоимость |
|-----------|-----------|
| Audio Input | $0.06/мин × 2.5 = **$0.15** |
| Audio Output | $0.24/мин × 2.5 = **$0.60** |
| Azure Pronunciation | $1.50/час × 0.042ч = **$0.06** |
| **ИТОГО** | **$0.81/сессия** |

**Freemium модель:**
- 5 бесплатных сессий/неделю = $4.05/неделю (~$16/месяц на пользователя)
- При 1000 активных пользователей = **$16,000/месяц**

---

### Подход 2: Классический Pipeline (РЕКОМЕНДУЕТСЯ)

#### Технические характеристики

```
User Audio → WebRTC → Whisper API (STT)
                           ↓
                      GPT-4o + Universal Prompt
                           ↓
                    Azure TTS (или ElevenLabs)
                           ↓
                      Audio Response
```

**Стек:**
- Whisper API (STT)
- GPT-4o (text generation)
- Azure Neural TTS (голос)
- WebRTC или простой audio recording
- FastAPI

#### Плюсы

 **Экономичность:** $0.62 за сессию (на 23% дешевле)  
 **Доступность:** Все API доступны сразу  
 **Гибкость:** Выбор голоса, скорости, языка  
 **Контроль:** Полный контроль над промптами и параметрами  
 **Надёжность:** Каждый компонент работает независимо  
 **Простота отладки:** Легче найти проблему  

#### Минусы

 **Латентность:** 2-3 секунды (заметная пауза)  
 **Сложность:** Три API вместо одного  
 **Нет прерываний:** Пользователь не может перебить  
 **Менее естественно:** Ощущается как бот  

#### Экономика (2.5 мин сессия)

| Компонент | Стоимость |
|-----------|-----------|
| Whisper API | $0.006/мин × 2.5 = **$0.015** |
| GPT-4o | ~2000 токенов × $0.000075 = **$0.15** |
| Azure TTS | $16/1M chars, ~500 chars = **$0.008** |
| Azure Pronunciation | $1.50/час × 0.042ч = **$0.06** |
| Буфер (инфраструктура) | **$0.02** |
| **ИТОГО** | **$0.62/сессия** |

**Альтернатива (ElevenLabs TTS):**
- ElevenLabs: $0.18/мин × 2.5 = $0.45
- Итого: **$0.67/сессия** (лучший голос, но дороже)

**Freemium модель:**
- 5 бесплатных сессий/неделю = $3.10/неделю (~$12/месяц на пользователя)
- При 1000 активных пользователей = **$12,000/месяц**

**Экономия:** $4,000/месяц на 1000 пользователей

---

## Детальное сравнение

### 1. Качество пользовательского опыта

| Параметр | Realtime API | Классический Pipeline |
|----------|--------------|----------------------|
| Латентность | 300-500ms ⭐⭐⭐⭐⭐ | 2-3 сек ⭐⭐⭐ |
| Естественность голоса | Очень высокая ⭐⭐⭐⭐⭐ | Высокая ⭐⭐⭐⭐ |
| Прерывания | Да ⭐⭐⭐⭐⭐ | Нет ⭐ |
| Эмоции в голосе | Встроены ⭐⭐⭐⭐⭐ | Ограничены ⭐⭐⭐ |
| Ощущение диалога | Как с человеком ⭐⭐⭐⭐⭐ | Как с ботом ⭐⭐⭐ |

**Вывод:** Realtime API даёт значительно лучший UX

### 2. Техническая сложность

| Параметр | Realtime API | Классический Pipeline |
|----------|--------------|----------------------|
| Количество API | 1 (+ 1 для анализа) | 3 (+ 1 для анализа) |
| WebRTC обязателен | Да ⭐⭐ | Нет ⭐⭐⭐⭐ |
| Сложность отладки | Средняя ⭐⭐⭐ | Низкая ⭐⭐⭐⭐⭐ |
| Время разработки | 4-6 недель | 2-3 недели |
| Доступность | Beta (неопределённость) | Сразу ⭐⭐⭐⭐⭐ |

**Вывод:** Классический pipeline проще и быстрее запустить

### 3. Экономика и масштабируемость

| Параметр | Realtime API | Классический Pipeline |
|----------|--------------|----------------------|
| Стоимость сессии | $0.81 | $0.62 ⭐⭐⭐⭐⭐ |
| 1K активных юзеров/мес | $16,000 | $12,000 ⭐⭐⭐⭐ |
| 10K активных юзеров/мес | $160,000 | $120,000 ⭐⭐⭐⭐ |
| Freemium viable | Маржинально ⭐⭐⭐ | Да ⭐⭐⭐⭐⭐ |
| Оптимизация возможна | Ограничена ⭐⭐ | Высокая ⭐⭐⭐⭐⭐ |

**Вывод:** Классический pipeline экономичнее на 25-30%

---

## Рекомендуемый стек (Гибридный подход)

### Фаза 1: MVP (3 месяца) — Классический Pipeline

**Почему начать с классики:**
1. Быстрее запуск (не нужен beta-доступ)
2. Дешевле ($0.62 vs $0.81)
3. Проще отладка
4. Доказать product-market fit

**Стек MVP:**

```python
# STT
Whisper API
- Стоимость: $0.006/мин
- Качество: Отличное
- Латентность: ~1 сек

# LLM
GPT-4o
- Universal Prompt (compact mode для 2-3 мин)
- Стоимость: ~$0.15/сессия
- Контекст из PostgreSQL

# TTS
Azure Neural TTS (начать)
- Стоимость: $0.008/сессия
- Качество: Хорошее
- Голоса: en-US-JennyNeural (женский), en-US-GuyNeural (мужской)

Опционально: ElevenLabs для premium ($0.45/сессия)
- Качество: Отличное
- Эмоциональность: Высокая

# Pronunciation Analysis
Azure Speech Service
- Pronunciation Assessment API
- Стоимость: $0.06/сессия
- Метрики: accuracy, fluency, completeness, phoneme-level
```

**Архитектура MVP:**

```
[Telegram Mini App / Web]
        ↓
[FastAPI WebSocket] ← Простая аудио запись
        ↓
[Whisper API] → Транскрипция
        ↓
[ContextBuilder] → Данные из PostgreSQL
        ↓
[UniversalPromptBuilder (compact)] → Промпт
        ↓
[GPT-4o] → Текстовый ответ
        ↓
[Azure TTS] → Аудио ответ
        ↓
[User] ← Воспроизведение
        
После сессии:
[Azure Pronunciation Assessment] → Анализ
        ↓
[PostgreSQL] → Сохранение feedback
        ↓
[Telegram Notification] → Уведомление
```

### Фаза 2: Premium Upgrade (6 месяцев) — Realtime API

**Когда переходить:**
- PMF доказан (retention >40%, NPS >50)
- 1000+ активных пользователей
- Есть платящие пользователи
- Получен доступ к Realtime API

**Стратегия:**
```
Free tier: Классический pipeline ($0.62/сессия)
Premium tier ($15/мес): Realtime API ($0.81/сессия)
```

**Дифференциация:**
- Free: 2-3 сек латентность, 5 сессий/неделю
- Premium: <500ms латентность, безлимит, прерывания, лучший голос

---

## Детальная имплементация MVP

### 1. Backend Architecture

```
app/
├── api/
│   ├── voice_session.py      # Эндпоинты для голосовых сессий
│   └── pronunciation.py       # Анализ произношения
├── services/
│   ├── speech_to_text.py     # Whisper API integration
│   ├── text_to_speech.py     # Azure TTS integration
│   ├── pronunciation_analyzer.py  # Azure Pronunciation
│   ├── feedback_generator.py # Генерация обратной связи
│   └── context_builder.py    # Уже есть
├── prompts/
│   └── universal.py          # Уже есть (compact mode)
└── models/
    └── core_tables.py        # Уже есть
```

### 2. API Flow

**Старт сессии:**
```python
POST /api/v1/voice/session/start
{
    "user_id": 123,
    "language_level": "B1"
}

Response:
{
    "session_id": "uuid",
    "max_duration_seconds": 180,  # 3 минуты
    "upload_url": "wss://api/voice/stream"
}
```

**Стриминг аудио:**
```python
WebSocket /api/v1/voice/stream/{session_id}

# Client отправляет audio chunks
→ {"audio": "base64_chunk"}

# Server отвечает текстом + аудио
← {
    "type": "transcription",
    "text": "Hello, how are you?",
    "speaker": "user"
}
← {
    "type": "response_text", 
    "text": "I'm great! What's on your mind?",
    "speaker": "assistant"
}
← {
    "type": "response_audio",
    "audio": "base64_audio_chunk",
    "final": false
}
```

**Завершение сессии:**
```python
POST /api/v1/voice/session/{session_id}/end

Response:
{
    "duration_seconds": 147,
    "utterance_count": 8,
    "processing_started": true
}

# Асинхронно:
# 1. Анализ произношения
# 2. Генерация feedback
# 3. Уведомление в Telegram
```


## Оптимизации для снижения стоимости

### 1. Промпт-оптимизации

**Используем Compact Mode по умолчанию:**
- Full mode: ~2,300 токенов → первая сессия дня
- Compact mode: ~1,500 токенов → все остальные
- Экономия: ~800 токенов × $0.000075 = **$0.06 на сессию**

### 2. TTS оптимизации

**Azure TTS вместо ElevenLabs для free tier:**
- Azure: $0.008/сессия
- ElevenLabs: $0.45/сессия
- Экономия: **$0.44 на сессию**

**Кэширование общих фраз:**
```python
# Кэш для частых ответов
CACHED_AUDIO = {
    "greeting": "pre-generated-audio-base64",
    "goodbye": "pre-generated-audio-base64",
    "great_job": "pre-generated-audio-base64"
}

# Сэкономить ~20% TTS запросов
```

### 3. Whisper оптимизации

**Использовать language hint:**
```python
whisper.transcribe(
    audio,
    language="en",  # Снижает latency и errors
    prompt="English learning conversation"  # Context hint
)
```

### 4. Batch Processing

**Анализ произношения батчами:**
```python
# Не анализировать каждую реплику
# Анализировать только реплики пользователя после сессии
# Экономия: 50% вызовов Azure Speech
```

---

## Timeline и Milestones

### MVP (12 недель)

**Неделя 1-2: Audio Infrastructure**
- [ ] FastAPI WebSocket endpoint
- [ ] Audio recording на фронтенде
- [ ] Базовая передача аудио

**Неделя 3-4: STT + LLM Integration**
- [ ] Whisper API integration
- [ ] GPT-4o с Universal Prompt
- [ ] Сохранение utterances в PostgreSQL

**Неделя 5-6: TTS Integration**
- [ ] Azure TTS integration
- [ ] Audio playback на фронтенде
- [ ] End-to-end тест диалога

**Неделя 7-8: Pronunciation Analysis**
- [ ] Azure Pronunciation Assessment
- [ ] Feedback generation
- [ ] Corrections в PostgreSQL

**Неделя 9-10: Telegram Integration**
- [ ] Telegram Mini App UI
- [ ] WebApp button
- [ ] Notifications после сессии

**Неделя 11-12: Polish & Testing**
- [ ] UX improvements
- [ ] Error handling
- [ ] Load testing
- [ ] Beta launch

---

## Рекомендации по запуску

### 1. Начать с Whisper + GPT-4o + Azure TTS

**Аргументы:**
- Доступно сразу
- $0.62 за сессию (жизнеспособная экономика)
- Проще отладка
- Быстрее MVP

### 2. Доказать product-market fit

**Метрики успеха:**
- Retention D7 > 40%
- Retention D30 > 20%
- NPS > 50
- 1000+ активных пользователей
- Conversion free→paid > 5%

### 3. Затем мигрировать Premium на Realtime API

**Когда:**
- PMF доказан
- Есть revenue
- Получен beta-доступ

**Стратегия:**
- Free tier: классический pipeline
- Premium tier: Realtime API
- A/B тест влияния на retention

---

## Итоговая рекомендация

### Стек для MVP

```
STT:     Whisper API ($0.015/сессия)
LLM:     GPT-4o + Universal Prompt compact ($0.15/сессия)
TTS:     Azure Neural TTS ($0.008/сессия)
Анализ:  Azure Pronunciation Assessment ($0.06/сессия)

ИТОГО:   $0.62 за сессию 2.5 минуты
```

### Экономика

**Freemium:**
- 5 сессий/неделю бесплатно
- Стоимость: $3.10/неделю = **$12/месяц на активного пользователя**

**Premium ($10/месяц):**
- 20 сессий/месяц
- Стоимость: $12.40
- Маржа: **-$2.40** (окупается данными + LTV)

**Premium Pro ($20/месяц):**
- Безлимит (лимит 60 сессий)
- Стоимость: $37
- Маржа: **-$17** (окупается LTV + возможностью upsell)

### Переход на Realtime API (Phase 2)

**Когда:** PMF доказан + revenue + beta-доступ

**Модель:**
- Free: Классический ($0.62)
- Premium: Realtime API ($0.81) + улучшенный UX

---

## Заключение


**Короткие сессии (2-3 мин) — ключевое решение:**
- Снижает стоимость в 4 раза
- Улучшает retention
- Позволяет freemium модель
- Педагогически эффективнее



