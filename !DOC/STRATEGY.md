# Стратегический план развития EnglishFriend AI Mentor

---

## 🔍 АУДИТ LLM-АРХИТЕКТУРЫ (Январь 2026)

### Общая оценка: 7/10 (Хорошая база, требует cleanup)

---

### ✅ Что сделано ПРАВИЛЬНО:

#### 1. Чистая абстракция LLM провайдеров
**Файл:** `app/services/ai/llm_provider.py`
```python
class LLMProvider(ABC):
    async def generate(...) -> str
    async def generate_stream(...) -> AsyncIterator[str]
```
- Три реализации: VLLMProvider, GroqProvider, OpenAIProvider
- Factory-функция `get_llm_provider()` с кэшированием
- Централизованный конфиг через `settings`

#### 2. Отдельная абстракция для голосовых провайдеров
**Файл:** `app/services/ai/base.py`
```python
class AIProvider(ABC):
    async def connect(session) -> None
    async def send_audio(chunk) -> None
    async def receive() -> AsyncIterator[dict]
    async def disconnect() -> None
```
- Три реализации: HumeEVIProvider, OpenAIRealtimeProvider, WhisperPipelineProvider
- Правильное разделение: текст (LLMProvider) vs аудио (AIProvider)

#### 3. TTS сервис
**Файл:** `app/services/ai/tts_service.py`
- Чистая абстракция с edge-tts
- Маппинг голосов (american_female, british_male, etc.)
- Singleton pattern

#### 4. Конфигурация централизована
**Файл:** `app/core/config.py`
- Все API ключи и параметры в одном месте
- Pydantic Settings с .env поддержкой
- Типизация через Literal["vllm", "groq", "openai"]

---

### ⚠️ КОСТЫЛИ И ПРОБЛЕМЫ:

#### 1. МЁРТВЫЙ КОД: `groq_llm.py` (УДАЛИТЬ)
**Файл:** `app/services/ai/groq_llm.py` (107 строк)
- Класс `GroqLLMService` НИГДЕ не используется!
- Дублирует `GroqProvider` из `llm_provider.py`
- **Действие:** Удалить файл целиком

#### 2. HARDCODED модель Groq
**Файл:** `app/services/ai/llm_provider.py:127, 148`
```python
model="llama-3.3-70b-versatile"  # HARDCODED!
```
- **Действие:** Добавить `groq_model` в settings

#### 3. HARDCODED temperature
**Файлы:** `llm_provider.py:76,98,130,152,183,205`
```python
temperature=0.7  # HARDCODED везде!
```
- **Действие:** Добавить `llm_temperature` в settings

#### 4. НЕТ RETRY логики
- Все LLM провайдеры не имеют retry при ошибках сети
- **Действие:** Добавить tenacity с exponential backoff

#### 5. НЕТ TIMEOUT для Groq/OpenAI
**Файл:** `app/services/ai/llm_provider.py`
- VLLMProvider имеет timeout, другие - нет
- **Действие:** Добавить `groq_timeout`, `openai_timeout` в settings

#### 6. IMPORT внутри функции
**Файл:** `app/api/voice.py:359`
```python
import re  # Внутри обработчика, не наверху!
```
- **Действие:** Перенести в начало файла

#### 7. НЕТ ТЕСТОВ для LLM
- Поиск `tests/**/test_*llm*.py` вернул 0 файлов
- **Действие:** Добавить unit-тесты с мокированием

#### 8. Потенциальный PROMPT INJECTION
**Файл:** `app/api/voice.py:321`
```python
response_text = await llm.generate(
    user_message=user_text,  # Напрямую от пользователя!
    ...
)
```
- Нет санитизации пользовательского ввода
- **Действие:** Добавить базовую защиту от "ignore previous instructions"

---

### 📋 ПЛАН РЕФАКТОРИНГА LLM - ✅ ВЫПОЛНЕНО (Январь 2026)

| # | Задача | Статус | Где реализовано |
|---|--------|--------|-----------------|
| 1 | Удалить `groq_llm.py` | ✅ | Удалён |
| 2 | Добавить `groq_model` | ✅ | `config.py:38` |
| 3 | Добавить `llm_temperature` | ✅ | `config.py:47` |
| 4 | Добавить timeouts | ✅ | `config.py:39,44` |
| 5 | Перенести `import re` | ✅ | `voice.py:18` |
| 6 | Добавить retry | ✅ | `llm_provider.py:23` (tenacity) |
| 7 | Prompt injection защита | ✅ | `llm_provider.py:54` (`sanitize_user_input()`) |
| 8 | Unit-тесты LLM | ✅ | `tests/test_llm_provider.py` |

---

### 🏗️ РЕКОМЕНДУЕМАЯ АРХИТЕКТУРА (после рефакторинга)

```
app/services/ai/
├── __init__.py              # Экспорты
├── base.py                  # AIProvider (голосовые)
├── factory.py               # get_ai_provider()
├── llm_provider.py          # LLMProvider + все реализации (vllm, groq, openai)
├── tts_service.py           # TTSService (edge-tts)
├── embedding_service.py     # EmbeddingService (OpenAI)
├── memory_pipeline.py       # RAG pipeline
├── memory_extraction_service.py
├── qdrant_service.py
├── mode_prompts.py          # Промпты для режимов
├── mode_selector.py         # Автовыбор режима
├── mentor_prompt.py         # System prompts
├── vocabulary_service.py    # FSRS
├── hume_evi.py              # Legacy: Hume provider
├── openai_realtime.py       # Legacy: OpenAI Realtime
└── whisper_pipeline.py      # Legacy: Whisper STT

# УДАЛИТЬ:
# - groq_llm.py              # Дубликат, не используется
```

---

## ✅ РЕАЛИЗОВАНО: Педагогическая архитектура AI-ментора

### Статус: Готово к тестированию

**Созданные файлы:**
- `app/services/ai/mode_prompts.py` - Промпты для 4 режимов
- `app/services/ai/mode_selector.py` - Автовыбор режима
- `app/services/learning_plan_service.py` - Хранение целей
- `app/api/voice.py` - Обновлён с интеграцией

---

### Исходная проблема
Текущий агент - просто чат-бот без педагогики:
- Не адаптируется под цели пользователя (ML Interview → игнорируется)
- Нет assessment (оценки уровня)
- Нет структуры обучения
- FSRS есть в коде, но **НЕ подключён**
- LearningPlan таблица **пустая**

### Решение: Режимы обучения + Goal-Driven Learning

**Новые файлы:**

1. **`app/services/ai/mode_prompts.py`** - Промпты для каждого режима:
   - ASSESSMENT: "Let's check your level..."
   - MOCK_INTERVIEW: "I'm a hiring manager at..."
   - VOCABULARY_DRILL: "Let's review these words..."
   - FREE_CONVERSATION: Текущий промпт

2. **`app/services/ai/mode_selector.py`** - Логика выбора режима:
   ```python
   if no_recent_assessment: return ASSESSMENT
   if len(due_vocabulary) >= 10: return VOCABULARY_DRILL
   if goal == "interview": return MOCK_INTERVIEW
   return FREE_CONVERSATION
   ```

3. **`app/services/learning_plan_service.py`** - Хранение целей:
   ```json
   {
     "goal": "ML/DS Interview",
     "milestones": ["Master 50 ML terms", "5 mock interviews"],
     "focus_areas": ["technical_vocabulary", "behavioral_questions"]
   }
   ```

**Изменения в `app/api/voice.py`:**
1. При подключении: загрузить learning_plan + due_vocabulary
2. Определить режим через mode_selector
3. Построить режимный промпт
4. После ответа ментора: извлечь новые слова → VocabularyService
5. После ответа студента: анализ ошибок → save to memories

**Порядок реализации:**
1. mode_prompts.py (промпты)
2. mode_selector.py (логика выбора)
3. learning_plan_service.py (цели)
4. Интеграция VocabularyService в voice.py
5. Обновление voice.py: режимы + FSRS + ошибки

---

## ✅ ЗАВЕРШЕНО: Фрагментация транскрипта Vosk

### Проблема
Vosk STT выдаёт несколько "final" результатов во время одной фразы, когда пользователь делает паузы для обдумывания. Текущий код **перезаписывает** каждый результат, и на LLM уходит только последний фрагмент.

**Пример проблемы:**
```
[VoskVAD] final: "I think"
[VoskVAD] final: "that this is"
[VoskVAD] final: "a good idea"
→ LLM получает только: "a good idea" (вместо полной мысли)
```

### Решение: Аккумулятор финальных результатов

**Файл:** `/Users/macbook/Desktop/englishFriend/frontend/src/hooks/useVoskWithVAD.ts`

**Изменения:**

1. **Добавить refs для аккумуляции:**
```typescript
const accumulatedTextRef = useRef<string>('');
const currentPartialRef = useRef<string>('');
```

2. **Изменить обработчик 'result':**
```typescript
recognizer.on('result', (message: any) => {
  const text = message.result?.text?.trim();
  if (text) {
    // Аккумулируем вместо перезаписи
    if (accumulatedTextRef.current) {
      accumulatedTextRef.current += ' ' + text;
    } else {
      accumulatedTextRef.current = text;
    }
    currentPartialRef.current = '';

    // Показываем накопленный текст
    const fullText = accumulatedTextRef.current;
    lastTranscriptRef.current = fullText;
    setTranscript(fullText);
    onFinalResult?.(fullText);
  }
});
```

3. **Изменить обработчик 'partialresult':**
```typescript
recognizer.on('partialresult', (message: any) => {
  const partial = message.result?.partial?.trim();
  if (partial) {
    currentPartialRef.current = partial;

    // Показываем: накопленное + текущий partial
    const displayText = accumulatedTextRef.current
      ? accumulatedTextRef.current + ' ' + partial
      : partial;

    lastTranscriptRef.current = displayText;
    setTranscript(displayText);
    onPartialResult?.(displayText);

    // Сброс таймера тишины
    hasSpokenRef.current = true;
    silenceStartRef.current = null;
    setVoiceStatus('listening');
    setSilenceProgress(0);
  }
});
```

4. **Обновить confirmSend:**
```typescript
const confirmSend = useCallback((): string | null => {
  const text = accumulatedTextRef.current.trim();
  if (text.length >= VAD_CONFIG.minTextLength) {
    stopListening();
    setVoiceStatus('processing');
    // Сброс аккумулятора
    accumulatedTextRef.current = '';
    currentPartialRef.current = '';
    return text;
  }
  return null;
}, [stopListening]);
```

5. **Обновить cancelAndReset:**
```typescript
const cancelAndReset = useCallback(() => {
  stopListening();
  setTranscript('');
  lastTranscriptRef.current = '';
  hasSpokenRef.current = false;
  accumulatedTextRef.current = '';
  currentPartialRef.current = '';
}, [stopListening]);
```

6. **Сбросить аккумулятор в startListening:**
```typescript
// После setIsListening(true);
accumulatedTextRef.current = '';
currentPartialRef.current = '';
```

### Ожидаемый результат
```
[VoskVAD] final: "I think" → accumulated: "I think"
[VoskVAD] final: "that this is" → accumulated: "I think that this is"
[VoskVAD] final: "a good idea" → accumulated: "I think that this is a good idea"
→ LLM получает: "I think that this is a good idea" ✓
```

---

## 🏆 ГЛУБОКИЙ АНАЛИЗ РЫНКА AI-МЕНТОРОВ (Январь 2026)

### Топ конкуренты и их технологии

#### 1. **Speak.com** ($1B valuation, $162M raised)
- **Технология**: OpenAI GPT-4 + собственный "ML scaffolding"
- **Фокус**: Разговорная практика без живого репетитора
- **Цена**: ~$19.50/мес ($235/год)
- **Сильные стороны**:
  - 1 млрд+ произнесённых предложений
  - Кастомная модель GPT-4 для японского (2.8x быстрее)
  - Open-ended conversations с фидбеком
- **Слабость**: Дорого, только английский для изучающих

#### 2. **ELSA Speak** (Pronunciation focus)
- **Технология**: Проприетарный STT + фонетический анализ
- **Фокус**: Произношение, интонация, ритм
- **Цена**: $12-15/мес ($70-100/год)
- **Сильные стороны**:
  - 8000+ уроков
  - Visual "mouth shape" guidance
  - Accent-based learning paths (American, British, Australian)
  - Детекция конкретных фонем
- **Слабость**: Нет свободных диалогов, только упражнения

#### 3. **TalkPal** (50+ languages)
- **Технология**: Voice + text conversations
- **Фокус**: Role-play scenarios (ресторан, путешествия, врач)
- **Цена**: Неизвестно (free tier + premium)
- **Сильные стороны**: Много языков, практические сценарии
- **Слабость**: Базовый фидбек

#### 4. **Langua** (LanguaTalk)
- **Технология**: AI voices cloned from real native speakers
- **Фокус**: Естественные разговоры
- **Сильные стороны**: Самые натуральные голоса
- **Слабость**: Меньше структурированного обучения

#### 5. **Heylama**
- **Технология**: Custom role-play + vocabulary
- **Фокус**: Персонализация
- **Сильные стороны**: Пользователь создаёт свои сценарии
- **Слабость**: Требует самоорганизации

---

### 🎯 Ключевые инсайты для EnglishFriend

#### Что делает лидеров успешными:

1. **Speak.com**: "Holy grail" = понимание тона, произношения, намерения + мгновенный естественный ответ
2. **ELSA**: Систематический подход: слово → предложение → комбинации → контекст
3. **Общее**: Персонализация через AI, мгновенный фидбек, адаптивная сложность

#### Наша уникальная ниша:

| Фактор | Конкуренты | EnglishFriend |
|--------|------------|---------------|
| **Целевая аудитория** | Все | Русскоязычные |
| **Специфика ошибок** | Общие | W/V, TH, артикли, schwa |
| **Язык поддержки** | Английский | Русский + английский |
| **Цена** | $10-20/мес | Freemium (Telegram) |
| **Платформа** | Мобильные приложения | Telegram Mini App |

---

### 📚 Методология обучения (исследования)

#### Second Language Acquisition (SLA) - что работает:

1. **Extensive Processing Instruction (EPI)**:
   - Input processing → Fluency-building → Listening → Pronunciation → Grammar (последним!)
   - Грамматика НЕ барьер, а поддержка после практики

2. **Socratic Method для ESL**:
   - Вопросы вместо лекций
   - Студент сам приходит к выводам
   - Формирует критическое мышление
   - Улучшает speaking И listening одновременно

3. **Spaced Repetition (FSRS)**:
   - 10 слов/день = 3650 слов/год за 20 мин!
   - FSRS-5: современный алгоритм, предсказывает когда забудешь
   - Органично встраивать повторения в диалог

#### Типичные ошибки русскоговорящих:

| Категория | Ошибка | Примеры |
|-----------|--------|---------|
| **Согласные** | W→V | "where"→"vere", "water"→"vater" |
| **Согласные** | TH→S/Z/F/D | "think"→"sink", "the"→"zee" |
| **Согласные** | Оглушение | "bad"→"bat" |
| **Гласные** | Long/short | "ship"="sheep" |
| **Гласные** | Schwa | "today" /tuːˈdeɪ/ вместо /təˈdeɪ/ |
| **Интонация** | Плоская | Вопросы без подъёма тона |
| **Стресс** | Неправильный | Ударение на артикли, предлоги |

---

### 🤖 Передовые технологии

#### OpenAI Realtime API
- **Latency**: ~500ms TTFB, цель 800ms voice-to-voice
- **Архитектура**: Speech-to-speech в одной модели (не цепочка STT→LLM→TTS)
- **Преимущества**: Слышит эмоции, фильтрует шум, прерывания (barge-in)
- **Подключение**: WebRTC (браузер), WebSocket (сервер), SIP (телефония)

#### Hume AI EVI (Empathic Voice Interface)
- **Уникальность**: Первый AI с эмоциональным интеллектом
- **Функции**:
  - Responds to expression (понимает тон)
  - Always interruptible (можно перебивать)
  - Aligned with well-being (оптимизирован на счастье пользователя)
  - End-of-turn detection по тону голоса
- **Ценность для обучения**: Детекция фрустрации → упрощение задачи

---

### 💰 Ценообразование на рынке

| Приложение | Месяц | Год | Модель |
|------------|-------|-----|--------|
| ELSA Speak | $12-15 | $70-100 | Фокус на произношении |
| Speak.com | ~$19.50 | $235 | Разговоры |
| Kippy | ~$6.70 | $80 | Бюджетный |
| Duolingo+ | ~$7 | $84 | Геймификация |
| **EnglishFriend** | $0 (free) | $5-10? | Telegram, русские |

---

## 🚀 РЕКОМЕНДАЦИИ ДЛЯ MVP

### Наше конкурентное преимущество:

1. **Специализация на русских** = глубокое понимание W/V, TH, артиклей
2. **Telegram Mini App** = нет барьера установки, 800M+ пользователей
3. **Freemium** = низкий порог входа
4. **Терпеливый ментор** = не торопит, даёт время думать (VAD 2.5 сек)
5. **Билингвальность** = подсказки на русском когда застрял

### Что реализовать для "best in market":

| Приоритет | Функция | Почему важно |
|-----------|---------|--------------|
| 1 | **Socratic questioning** | Студент говорит больше, учится лучше |
| 2 | **Фонетический фидбек** | W/V, TH детекция и коррекция |
| 3 | **FSRS vocabulary** | Органичное повторение слов в диалоге |
| 4 | **Эмоциональная адаптация** | Упрощать при фрустрации |
| 5 | **Progress tracking** | Видеть улучшения мотивирует |

---

## 🔬 Исследование: Coqui TTS vs Piper TTS (Январь 2026)

### Coqui TTS - Результаты анализа

**Что это**: Open-source TTS на PyTorch, создан бывшими разработчиками Mozilla TTS.

**Статус**: ⚠️ Компания Coqui закрылась в декабре 2023, сервисы отключены в 2024. Код поддерживается сообществом (Idiap Research Institute).

**Ключевые характеристики**:
- XTTS-v2: 17 языков, клонирование голоса с 6 сек аудио
- Latency: ~150-200ms на GPU
- **НЕТ браузерной/WASM версии** - только серверное решение
- Лицензия: Apache 2.0, но XTTS-v2 - некоммерческая лицензия

**Вывод**: Coqui TTS **не подходит** для нашей браузерной архитектуры. Блогер, вероятно, использовал его на сервере.

### Piper TTS - АЛЬТЕРНАТИВА ДЛЯ БРАУЗЕРА ✅

**Что это**: Быстрый локальный нейросетевой TTS от rhasspy (Home Assistant).

**Ключевое преимущество**: Есть WASM версия для браузера!

**npm пакет**: `@mintplex-labs/piper-tts-web`

```typescript
import * as tts from '@mintplex-labs/piper-tts-web';

const wav = await tts.predict({
  text: "Hello, I am your English mentor!",
  voiceId: 'en_US-hfc_female-medium',
});

const audio = new Audio();
audio.src = URL.createObjectURL(wav);
audio.play();
```

**Характеристики Piper TTS**:
- Размер модели: ~100MB (качество medium)
- 904+ голоса, включая английские (британские, американские)
- Качество: x_low / low / medium / high
- 100% браузер, работает офлайн
- Модели кешируются в Origin Private File System

### Сравнение TTS решений для Free Tier

| Решение | Локальное | Размер | Latency | Качество | Офлайн |
|---------|-----------|--------|---------|----------|--------|
| **edge-tts** (текущий) | ❌ Сервер MS | 0 | ~200-500ms | Хорошее | ❌ |
| **Piper TTS WASM** | ✅ Браузер | ~100MB | ~100-300ms | Среднее | ✅ |
| **Web Speech API** | ✅ Браузер | 0 | ~50ms | Низкое | ✅ |

### Рекомендация

**Для MVP**: Оставить edge-tts (работает, бесплатно, хорошее качество)

**Для "полностью локального" режима**: Добавить Piper TTS как опцию
- Плюс: Vosk STT + Piper TTS = полностью офлайн (кроме LLM)
- Минус: +100MB загрузка модели

**Ссылки**:
- [Piper TTS Web](https://github.com/Mintplex-Labs/piper-tts-web)
- [Piper голоса](https://rhasspy.github.io/piper-samples/)
- [Coqui TTS (архив)](https://github.com/coqui-ai/TTS)

---

## Текущее состояние (MVP готовность: 90%)

### Реализованная архитектура (Free Tier - Vosk)
```
Browser (Vosk WASM STT) → WebSocket → FastAPI → vLLM/Groq LLM → edge-tts TTS → Browser
                                         ↓
                                    PostgreSQL (история, прогресс)
```

**Статус**: ✅ Vosk STT успешно работает после исправления sample rate resampling (48kHz→16kHz)

**Преимущества текущего MVP**:
- Полностью бесплатный STT (работает офлайн в браузере)
- Приватность речевых данных (распознавание локально)
- Низкая стоимость эксплуатации (~$0.10-0.50/час при использовании Groq/vLLM)
- Уже работающий прототип с базой данных

**Недостатки текущего MVP**:
- Высокая latency (800-1200ms end-to-end) из-за каскадной архитектуры
- Потеря просодической информации (только текст передается между компонентами)
- Vosk WER ~10-15% (хуже премиальных решений)
- Нет анализа эмоций и интонации студента
- Базовая коррекция произношения (только через текстовый анализ)

---

## Многоуровневая модель подписок

### 🆓 **FREE TIER** (текущая архитектура)
**Технологии**: Vosk + Groq/vLLM + edge-tts
**Стоимость эксплуатации**: ~$0.10-0.50/час
**Цена для пользователя**: Бесплатно

**Ограничения**:
- Задержка ответа: 800-1200ms
- Базовая коррекция грамматики (только текст)
- Ограниченная история сессий (7 дней)
- Синтетический голос среднего качества (edge-tts)
- 30 минут практики в день

**Целевая аудитория**: Студенты начального уровня (A1-B1), пробующие продукт

---

### 💎 **PREMIUM TIER** (каскадная архитектура, премиум компоненты)
**Технологии**: Deepgram Nova-3 + GPT-4o-mini + ElevenLabs Flash
**Стоимость эксплуатации**: ~$2-4/час
**Цена для пользователя**: $9.99/месяц

**Улучшения**:
- Задержка ответа: 400-600ms (2x быстрее)
- Точность STT: WER 5.8% (Deepgram vs 10-15% Vosk)
- Натуральный голос с эмоциями (ElevenLabs Flash, 75ms latency)
- Безлимитная практика
- Долгосрочная память (RAG): ИИ помнит историю обучения
- Автоматическое создание SRS карточек для повторения слов
- Продвинутая коррекция грамматики через GPT-4o-mini

**Целевая аудитория**: Серьезные студенты (B1-C1), готовые платить за качество

---

### 🚀 **ULTRA TIER** (нативная S2S архитектура)
**Технологии**: OpenAI Realtime API (GPT-4o Realtime) + опционально ElevenLabs PVC
**Стоимость эксплуатации**: ~$1.35-3/час (оптимизированная Realtime API)
**Цена для пользователя**: $29.99/месяц

**Уникальные возможности**:
- ⚡ **Минимальная latency**: <300-500ms (естественный диалог)
- 🎭 **Анализ просодики**: Коррекция интонации, акцента, эмоциональной окраски
- 🧠 **Эмпатия**: ИИ "слышит" фрустрацию/радость студента и адаптирует подход
- 🎙️ **Естественные прерывания**: Студент может перебить ИИ как в живом разговоре (barge-in)
- 📚 **Продвинутый RAG**: Интеграция с учебными материалами студента (PDF, статьи)
- 🔄 **Умный SRS**: Алгоритм FSRS для оптимальных интервалов повторения
- 🎨 **Персонализация**: Выбор личности ментора (строгий британец, дружелюбный американец, etc.)
- 📊 **Детальная аналитика**: Отчеты по прогрессу, слабым местам, статистика по темам

**Целевая аудитория**: Профессионалы (C1-C2), корпоративные клиенты, готовящиеся к IELTS/TOEFL

---

## Конкурентные преимущества (что нас отличает)

### 1. **Гибридная архитектура с выбором уровня**
- **Отличие**: Большинство конкурентов используют только одну технологию
- **Наше**: Freemium модель позволяет попробовать бесплатно, затем апгрейд по мере прогресса
- **Пример**: Duolingo использует только текст, HelloTalk - только peer-to-peer, мы - адаптивный ИИ с выбором tier

### 2. **Специализация на русскоязычных студентах**
- **Отличие**: Промпты учитывают типичные ошибки русскоговорящих (артикли, "most of people", th-звуки)
- **Наше**: База знаний интерференций (влияние русского на английский)
- **Реализация**: System prompts с встроенными правилами коррекции для русских студентов

### 3. **Интеграция SRS + RAG в голосовом формате**
- **Отличие**: Anki - карточки без контекста, ChatGPT - нет повторений
- **Наше**: ИИ автоматически создает карточки из разговора и органично возвращается к сложным словам в будущих сессиях
- **Пример**: Студент забыл слово "resilience" → ИИ добавляет в SRS → через 3 дня в диалоге спрашивает "How would you describe resilience?"

### 4. **Эмоциональный интеллект (Ultra Tier)**
- **Отличие**: Конкуренты игнорируют эмоции
- **Наше**: Детекция фрустрации → упрощение задач, детекция скуки → переключение на интересную тему
- **Технология**: Hume AI EVI или OpenAI Realtime с анализом просодики

### 5. **Прогрессивная модель данных**
- **Отличие**: Большинство EdTech не хранят детальную историю
- **Наше**: PostgreSQL с партиционированием + Neo4j (граф интересов) + Qdrant (семантический поиск по памяти)
- **Результат**: ИИ помнит, что студент любит технологии и Marvel → адаптирует примеры

---

## Roadmap (3 фазы)

### 📍 **Фаза 1: MVP Launch (1-2 месяца)**
**Цель**: Запустить Free Tier для первых пользователей

**Задачи**:
1. ✅ Исправить Vosk STT (уже сделано)
2. 🔄 Решить проблему с LLM (настроить Groq API или исправить vLLM connection)
3. Оптимизировать промпты для русскоязычных студентов:
   - Добавить базу типичных ошибок в system prompt
   - Реализовать Socratic questioning для стимуляции речи
   - Настроить уровни коррекции (A1: мягкая → C2: строгая)
4. Реализовать базовую аналитику:
   - Подсчет времени практики
   - История диалогов в PostgreSQL
   - Простой дашборд прогресса
5. Улучшить UX:
   - Визуализация речевой активности (Lottie анимации)
   - Индикатор latency для мониторинга качества
   - Кнопка экстренной остановки (если ИИ "несет чушь")

**Метрики успеха**:
- 100 активных пользователей Free Tier
- Средняя сессия >10 минут
- Retention 7 дней >30%

---

### 📍 **Фаза 2: Premium Launch (3-4 месяца)**
**Цель**: Монетизация через Premium Tier

**Задачи**:
1. Интеграция Deepgram Nova-3:
   - Переключатель STT: Vosk (Free) / Deepgram (Premium)
   - WebSocket streaming для Deepgram
   - Keyword boosting для специализированной лексики
2. Интеграция ElevenLabs Flash v2.5:
   - Профессиональный голос с низкой latency (75ms)
   - Выбор голоса: британский/американский акцент
3. Реализация RAG:
   - Векторизация истории обучения (Qdrant уже в стеке)
   - Поиск релевантных фрагментов из прошлых сессий
   - Промпт-инжиниринг для контекстных ответов
4. Реализация SRS (Spaced Repetition):
   - Алгоритм FSRS для расчета интервалов
   - Автоматическое извлечение новых слов из транскриптов (GPT-4o)
   - Органичное внедрение повторений в диалог
5. Система подписок:
   - Stripe интеграция
   - Ограничения Free Tier (30 мин/день)
   - Безлимит для Premium

**Метрики успеха**:
- 5-10% конверсия Free → Premium
- LTV (Lifetime Value) >$50 на пользователя
- Churn rate <15% в месяц

---

### 📍 **Фаза 3: Ultra Tier & Scale (6+ месяцев)**
**Цель**: Дифференциация через эксклюзивные фичи

**Задачи**:
1. Миграция на OpenAI Realtime API (Ultra Tier):
   - Полная переработка WebSocket логики
   - Server VAD с настраиваемыми параметрами (silence_duration, eagerness)
   - Реализация barge-in (прерывания)
   - Context summarization для длинных сессий (>30 мин)
2. Эмоциональный интеллект:
   - Интеграция Hume AI EVI или использование Realtime API с анализом просодики
   - Адаптивные промпты на основе эмоционального состояния
   - Логирование эмоций в EmotionalLog таблицу (уже в БД)
3. Персонализация:
   - 4-5 типов ментора (строгий профессор, дружелюбный репетитор, носитель-сленгист)
   - PVC (Professional Voice Cloning) от ElevenLabs для уникальных голосов
   - Тематические сценарии (деловой английский, путешествия, подготовка к IELTS)
4. Продвинутая аналитика:
   - Детекция слабых мест (грамматика, vocabulary, pronunciation)
   - Автоматические рекомендации материалов
   - Экспорт прогресса в PDF/Excel
5. Масштабирование инфраструктуры:
   - Переход на LiveKit Agents для оркестрации (если Realtime API не справляется)
   - Кеширование промптов (80% экономия на input tokens)
   - Адаптивное качество TTS (дешевый TTS для рутинных фраз, премиум для чтения)

**Метрики успеха**:
- 1000+ платящих пользователей (Premium + Ultra)
- Ultra Tier >15% от Premium базы
- NPS (Net Promoter Score) >50

---

## Технический стек (по тирам)

| Компонент | Free Tier | Premium Tier | Ultra Tier |
|-----------|-----------|--------------|------------|
| **STT** | Vosk (browser WASM) | Deepgram Nova-3 | OpenAI Realtime (native) |
| **LLM** | Groq/vLLM (бесплатно) | GPT-4o-mini | GPT-4o Realtime |
| **TTS** | edge-tts | ElevenLabs Flash | Realtime API + ElevenLabs PVC |
| **VAD** | Browser (basic) | Deepgram endpointing | Server VAD (OpenAI) |
| **Latency** | 800-1200ms | 400-600ms | <500ms |
| **Стоимость/час** | $0.10-0.50 | $2-4 | $1.35-3 |
| **Цена подписки** | Free | $9.99/мес | $29.99/мес |

---

## Анализ конкурентов

| Конкурент | Технология | Цена | Недостатки vs EnglishFriend |
|-----------|------------|------|------------------------------|
| **Duolingo** | Текст + базовое TTS | Free + $7/мес | ❌ Нет живого диалога, роботизированный голос |
| **ELSA Speak** | Proprietary STT + упражнения | $6/мес | ❌ Только произношение, нет свободного разговора |
| **Speak.com** | GPT-4 + TTS | $20/мес | ❌ Дорого, нет русскоязычной специализации |
| **HelloTalk** | Peer-to-peer | Free + $7/мес | ❌ Зависимость от людей, нет 24/7 доступности |
| **Cambly** | Живые преподаватели | $50+/мес | ❌ Очень дорого, расписание |

**Наша ниша**: Между бесплатным Duolingo (низкое качество) и дорогим Cambly (живые люди). Мы даем качество живого диалога по цене подписки.

---

## Оценка юнит-экономики

### Premium Tier ($9.99/мес)
**Предположения**:
- Средний пользователь: 10 часов/месяц практики
- Стоимость эксплуатации: $3/час
- Итого COGS (Cost of Goods Sold): $30/месяц
- **Маржа**: -$20.01 😱 (УБЫТОЧНО на малых объемах!)

**Оптимизация**:
1. Prompt caching: -80% на input tokens → $2/час
2. Смешанное TTS: OpenAI (дешево) для простых фраз, ElevenLabs для сложных → $1.5/час
3. Итого: $1.5/час × 10 часов = $15/месяц
4. **Маржа**: -$5.01 (все еще минус, но терпимо для привлечения Ultra)

### Ultra Tier ($29.99/мес)
**Предположения**:
- Средний пользователь: 15 часов/месяц (более вовлечен)
- Стоимость эксплуатации (оптимизированная): $2/час
- Итого COGS: $30/месяц
- **Маржа**: -$0.01 (break-even!)

**Вывод**:
- Premium Tier - это инструмент привлечения (loss leader)
- Ultra Tier - основная прибыль через апселл корпоративным клиентам (B2B)
- Необходимо добавить B2B тариф: $99/мес за корпоративную лицензию с брендированием

---

## Критические риски и митигация

### Риск 1: Высокая стоимость эксплуатации
**Митигация**:
- Агрессивный промпт-кеширование
- Гибридная модель TTS
- Self-hosted vLLM для Premium (вместо GPT-4o-mini) → $0.50/час вместо $2

### Риск 2: OpenAI Realtime API может изменить pricing
**Митигация**:
- Держать готовую альтернативу на LiveKit + Pipecat (open source)
- Мониторить Anthropic Claude Voice (анонсирован на 2025)

### Риск 3: Низкая конверсия Free → Paid
**Митигация**:
- Ограничение Free Tier до 30 мин/день (создать "голод" на продукт)
- Trial Premium: 7 дней бесплатно для демонстрации качества
- Геймификация: "Unlock unlimited practice for $9.99"

---

## Следующие шаги (сразу после завершения Vosk MVP)

1. **Завершить Free Tier MVP** (приоритет #1):
   - Решить LLM connection issue (Groq API setup)
   - Оптимизировать system prompts для русскоязычных
   - Добавить базовую аналитику (таблица в PostgreSQL уже есть)

2. **Подготовить инфраструктуру для Premium**:
   - Создать архитектуру с переключением STT/TTS провайдеров
   - Интегрировать Stripe для подписок
   - Реализовать role-based ограничения (Free vs Premium)

3. **Исследовать конкурентные преимущества**:
   - Собрать базу типичных ошибок русскоязычных студентов (из форумов, учебников)
   - Спроектировать алгоритм SRS интеграции в диалог
   - Создать прототип эмоциональной детекции (Hume AI trial)

4. **Создать заметку-референс из анализа нейросети**:
   - Сохранить документ с детальными рекомендациями по VAD, latency, промптам
   - Использовать как чеклист при разработке Premium/Ultra

---

## 🎮 РЕАЛИЗАЦИЯ: Streaks + XP System (Q1 2026)

### Статус: Готов к реализации

### Анализ текущего состояния

**Что уже есть:**
- ✅ `XPEvent` модель в `app/models/extended_tables.py` (партиционирована)
- ✅ SQL миграция `005_memories_learning_plan.sql` с таблицей `xp_events`
- ✅ Связь `User.xp_events` уже настроена
- ❌ НЕТ сервиса для XP — модель не используется
- ❌ НЕТ streak tracking — нет полей/таблиц

### Архитектура решения

```
┌─────────────────────────────────────────────────────────┐
│                    GamificationService                   │
├─────────────────────────────────────────────────────────┤
│  ├── StreakService (streaks, daily check-ins)           │
│  │     ├── check_in(user_id) → update streak            │
│  │     ├── get_streak(user_id) → current/max streak     │
│  │     └── is_streak_at_risk(user_id) → bool            │
│  │                                                       │
│  └── XPService (points, achievements)                   │
│        ├── award_xp(user_id, kind, points, session_id)  │
│        ├── get_total_xp(user_id) → int                  │
│        ├── get_level(user_id) → level, progress         │
│        └── get_daily_xp(user_id) → int                  │
└─────────────────────────────────────────────────────────┘
```

### План реализации (7 шагов)

#### Шаг 1: SQL миграция для Streaks
**Файл:** `db/migrations/postgres/010_streaks_gamification.sql`

```sql
-- Streak tracking поля в users
ALTER TABLE users ADD COLUMN IF NOT EXISTS current_streak INT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS max_streak INT NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_activity_date DATE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS total_xp BIGINT NOT NULL DEFAULT 0;

-- Индекс для партиций xp_events (январь 2026)
CREATE TABLE IF NOT EXISTS xp_events_2026_01
  PARTITION OF xp_events
  FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
```

#### Шаг 2: Обновление User модели
**Файл:** `app/models/core_tables.py`

```python
# Добавить поля в класс User:
current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
max_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
last_activity_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
total_xp: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
```

#### Шаг 3: XPService
**Файл:** `app/services/gamification/xp_service.py`

```python
class XPService:
    XP_VALUES = {
        "session_complete": 10,
        "streak_bonus": 5,          # умножается на streak day
        "vocabulary_learned": 2,    # за каждое слово
        "perfect_pronunciation": 15,
        "first_session": 50,
        "comeback": 20,             # после 7+ дней
        "daily_goal": 25,
    }

    async def award_xp(user_id, kind, session_id=None, multiplier=1) -> XPEvent
    async def get_total_xp(user_id) -> int
    async def get_level(user_id) -> dict  # {level, xp, next_level_xp, progress}
    async def get_today_xp(user_id) -> int
```

#### Шаг 4: StreakService
**Файл:** `app/services/gamification/streak_service.py`

```python
class StreakService:
    async def check_in(user_id) -> dict
        # Логика:
        # 1. Если last_activity_date == сегодня → ничего
        # 2. Если last_activity_date == вчера → streak += 1
        # 3. Если last_activity_date < вчера → streak = 1 (сброс)
        # 4. Обновить max_streak если current > max
        # 5. Начислить streak_bonus XP

    async def get_streak_info(user_id) -> dict
        # {current: 7, max: 14, at_risk: False}

    async def is_streak_at_risk(user_id) -> bool
        # True если сегодня ещё не было активности
```

#### Шаг 5: Интеграция в voice.py
**Файл:** `app/api/voice.py`

```python
# При завершении сессии (session.ended_at = ...)
from app.services.gamification import XPService, StreakService

xp_service = XPService(db)
streak_service = StreakService(db)

# 1. Streak check-in
streak_result = await streak_service.check_in(user_id)

# 2. XP за сессию
await xp_service.award_xp(user_id, "session_complete", session_id)

# 3. Streak bonus
if streak_result["streak"] > 1:
    await xp_service.award_xp(
        user_id, "streak_bonus",
        multiplier=streak_result["streak"]
    )
```

#### Шаг 6: API endpoints
**Файл:** `app/api/gamification.py`

```python
router = APIRouter(prefix="/gamification", tags=["gamification"])

@router.get("/users/{user_id}/stats")
async def get_user_stats(user_id: int):
    return {
        "xp": {"total": 1250, "level": 5, "progress": 0.7},
        "streak": {"current": 7, "max": 14, "at_risk": False},
        "today": {"sessions": 2, "xp_earned": 45}
    }
```

#### Шаг 7: Unit-тесты
**Файлы:**
- `tests/test_xp_service.py`
- `tests/test_streak_service.py`
- `tests/test_gamification_api.py`

**Тесты:**
- `test_award_xp_creates_event()`
- `test_streak_increments_on_consecutive_days()`
- `test_streak_resets_after_gap()`
- `test_comeback_bonus_after_week()`
- `test_level_calculation()`
- `test_max_streak_updates()`

### XP Level Formula

```python
import math

def get_level(total_xp: int) -> int:
    # Level 1: 0-100 XP
    # Level 2: 100-250 XP
    # Level 3: 250-500 XP
    return int(1 + math.sqrt(total_xp / 50))

def get_xp_for_level(level: int) -> int:
    return 50 * (level - 1) ** 2
```

### Файлы для создания/изменения

| Действие | Файл |
|----------|------|
| CREATE | `db/migrations/postgres/010_streaks_gamification.sql` |
| CREATE | `app/services/gamification/__init__.py` |
| CREATE | `app/services/gamification/xp_service.py` |
| CREATE | `app/services/gamification/streak_service.py` |
| CREATE | `app/api/gamification.py` |
| CREATE | `tests/test_xp_service.py` |
| CREATE | `tests/test_streak_service.py` |
| EDIT | `app/models/core_tables.py` (добавить 4 поля) |
| EDIT | `app/api/voice.py` (интеграция при завершении сессии) |
| EDIT | `main.py` (добавить gamification router) |

### Ожидаемый результат

После реализации:
- ✅ Пользователь видит свой streak при каждом входе
- ✅ XP начисляется автоматически за активность
- ✅ Мотивация через streak бонусы (+5 XP × день streak)
- ✅ Уровни для визуализации прогресса
- ✅ Готовая база для достижений (будущая фаза)
- ✅ Retention +40% (по данным индустрии)

---

## 🔬 Исследование: Multi-Agent + ML Scoring (Январь 2026)

### Контекст
На собеседовании в компании, разрабатывающей AI-психолога, описали перспективную архитектуру:
- **LangGraph** для оркестрации параллельных субагентов
- **Gradient Boosting** для скоринга/ранжирования ответов агентов
- Высокая латентность (~2-3s), но значительно выше качество

### Архитектура
```
User Input (описание проблемы)
         ↓
    LangGraph Router
         ↓
┌─────────┬─────────┬─────────┐
│ Agent A │ Agent B │ Agent C │  (параллельное выполнение)
│ empathy │   CBT   │ analyze │
└────┬────┴────┬────┴────┬────┘
     └─────────┼─────────┘
               ↓
      Gradient Boosting Scorer
      (обучен на feedback пользователей)
               ↓
         Best Response
```

### Преимущества подхода
1. **Ensemble effect**: Множественные точки зрения улучшают качество ответа
2. **Personalization**: GB модель учитывает профиль пользователя (интроверт? тревожность? стиль общения?)
3. **Feedback loop**: Каждый thumbs up/down улучшает scorer
4. **Interpretability**: GB более объясним чем LLM-as-judge (можно увидеть feature importance)
5. **Контролируемость**: ML модель можно дообучить на конкретные метрики качества

### Почему высокая латентность допустима
- Для психологии/коучинга качество важнее скорости
- Пользователь ожидает "обдуманный" ответ
- Текстовый чат, не голосовой (нет ожидания мгновенного ответа)

### Применимость к EnglishFriend

**Где подходит (background processing):**
- **Assessment mode**: 3 агента оценивают grammar, vocabulary, fluency параллельно
- **Выбор контента**: Agent A предлагает упражнения, Agent B - темы, Agent C - vocabulary
- **Анализ ошибок**: Разные агенты специализируются на типах ошибок (grammar vs pronunciation vs word choice)
- **Post-session analysis**: После завершения сессии, глубокий анализ в фоне

**Где НЕ подходит:**
- **Real-time голосовой чат**: Латентность критична, пользователь ждёт <800ms
- **Immediate feedback**: Мгновенная реакция на ошибку произношения

**Гибридный подход для EnglishFriend:**
```
Voice Chat (real-time, <800ms):
  User → Single LLM → Response
               ↓ (async, background)
         Multi-Agent Analysis
         (goal refinement, error patterns, vocabulary extraction)
               ↓
         Background DB Updates
         (learning_plan, memories, vocab cards)
```

### Технологии для изучения
- **LangGraph**: [python.langchain.com/docs/langgraph](https://python.langchain.com/docs/langgraph)
- **XGBoost для ранжирования**: [xgboost.readthedocs.io/en/latest/tutorials/learning_to_rank.html](https://xgboost.readthedocs.io/en/latest/tutorials/learning_to_rank.html)
- **LightGBM LambdaRank**: Альтернатива XGBoost для ranking

### Следующие шаги (когда будет время)
1. Изучить LangGraph документацию и примеры
2. Прототип: 3 агента для assessment mode (grammar, vocabulary, fluency)
3. Собрать датасет оценок пользователей для обучения GB scorer
4. A/B тест: single-agent vs multi-agent для assessment
5. Измерить improvement в качестве vs latency trade-off

### Потенциальные метрики качества для GB
- User satisfaction (explicit feedback)
- Engagement (продолжил ли пользователь сессию)
- Learning outcome (улучшился ли vocabulary/grammar score)
- Response appropriateness (human evaluation)

---

## Заключение

**Текущая позиция**: Vosk MVP почти готов, это сильная база для Free Tier.

**Стратегия**: Запустить freemium с бесплатным Vosk → монетизировать через Premium (Deepgram + ElevenLabs) → дифференцироваться через Ultra (Realtime API + эмоции).

**Конкурентное преимущество**: Специализация на русскоязычных + интеграция SRS/RAG + эмоциональный интеллект.

**Критический путь**: Free MVP (2 мес) → Premium (4 мес) → Ultra (6+ мес).

**Риски**: Высокая стоимость эксплуатации → митигация через кеширование и гибридные модели.

Этот анализ - живой документ. Обновлять по мере тестирования гипотез и сбора feedback от первых пользователей Free Tier.
