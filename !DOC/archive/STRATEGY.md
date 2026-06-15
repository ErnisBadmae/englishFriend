# Стратегический план развития EnglishFriend AI Mentor

---

## 🔍 АУДИТ LLM-АРХИТЕКТУРЫ (Январь 2026)

### Общая оценка: 7/10

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

## ✅ РЕАЛИЗОВАНО: Педагогическая архитектура AI-ментора

### Исходная проблема

Текущий агент - просто чат-бот без педагогики:

- Не адаптируется под цели пользователя (ML Interview → игнорируется)
- Нет assessment (оценки уровня)
- Нет структуры обучения
- FSRS есть в коде, но **НЕ подключён**
- LearningPlan таблица **пустая**

### Решение: Режимы обучения + Goal-Driven Learning

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

| Фактор                | Конкуренты           | EnglishFriend           |
| --------------------- | -------------------- | ----------------------- |
| **Целевая аудитория** | Все                  | Русскоязычные           |
| **Специфика ошибок**  | Общие                | W/V, TH, артикли, schwa |
| **Язык поддержки**    | Английский           | Русский + английский    |
| **Цена**              | $10-20/мес           | Freemium (Telegram)     |
| **Платформа**         | Мобильные приложения | Telegram Mini App       |

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

| Категория     | Ошибка       | Примеры                           |
| ------------- | ------------ | --------------------------------- |
| **Согласные** | W→V          | "where"→"vere", "water"→"vater"   |
| **Согласные** | TH→S/Z/F/D   | "think"→"sink", "the"→"zee"       |
| **Согласные** | Оглушение    | "bad"→"bat"                       |
| **Гласные**   | Long/short   | "ship"="sheep"                    |
| **Гласные**   | Schwa        | "today" /tuːˈdeɪ/ вместо /təˈdeɪ/ |
| **Интонация** | Плоская      | Вопросы без подъёма тона          |
| **Стресс**    | Неправильный | Ударение на артикли, предлоги     |

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

#### Moshi (Kyutai) - Open Source Voice AI ⭐ NEW 2025

- **Что это**: Первый open-source full-duplex voice AI от французской лаборатории Kyutai
- **GitHub**: https://github.com/kyutai-labs/moshi
- **Лицензия**: Apache 2.0 (код), CC-BY 4.0 (веса модели)

**Технические характеристики**:
- **Latency**: 160-200ms (лучший в классе!)
- **Модель**: 7B параметров, Helium base model
- **Архитектура**: Two-stream audio (user + AI одновременно)
- **Codec**: Mimi (300x compression)
- **Эмоции**: 92 различных интонации и стиля

**Преимущества для EnglishFriend**:
- Self-hosted = полный контроль над данными
- Стоимость ~$0.02/мин (только GPU) vs $0.30/мин OpenAI
- Можно fine-tune на education контент
- Работает на consumer GPU (RTX 3090, L4)

**Рекомендация**: Рассмотреть как альтернативу Ultra Tier для self-hosted deployment.

#### LiveKit Agents - Orchestration Layer

- **Что это**: Open-source фреймворк для voice agent orchestration
- **Роль**: Связывает STT + LLM + TTS в единый pipeline
- **Интеграции**: Deepgram, ElevenLabs, OpenAI, Cartesia
- **Преимущества**:
  - WebRTC из коробки
  - Turn detection и interruption handling
  - Self-hostable
- **Стоимость**: Open-source (MIT license)

**Применение**: Промежуточный вариант между текущим стеком и OpenAI Realtime.

#### Pipecat + Ultravox - Recommended Intermediate Option ⭐ NEW

**Pipecat** (https://github.com/pipecat-ai/pipecat):
- Open-source voice AI framework от Daily.co
- Модульная архитектура: plug любой STT/LLM/TTS
- Built-in interruption handling и VAD
- WebSocket и WebRTC support
- Active community, хорошая документация

**Ultravox** (https://ultravox.ai):
- Speech-native LLM (понимает аудио напрямую, без отдельного STT шага)
- Multimodal: текст + аудио в одной модели
- ~$0.05/min (сравнимо с OpenAI Realtime)
- API доступен, не нужен self-hosting

**Преимущества связки Pipecat + Ultravox**:
- Нет отдельного STT шага → меньше латентность
- Ultravox "слышит" интонацию (не теряется просодика)
- Pipecat даёт WebRTC из коробки
- Проще интеграция чем raw OpenAI Realtime
- Хорошая middle-ground между Vosk и OpenAI Realtime

**Стоимость**: ~$0.05/min = $3/час
**Latency**: ~400-600ms

**Рекомендация**: Рассмотреть как основной вариант для Premium Tier вместо Deepgram+GPT-4o+ElevenLabs.

---

### 🚫 Архитектурный анализ: Vosk vs Moshi (Январь 2026)

#### КЛЮЧЕВОЙ ВЫВОД: НЕ МЕНЯТЬ архитектуру сейчас

#### Почему сравнение "Vosk vs Moshi" некорректно

| Vosk | Moshi |
|------|-------|
| STT (Speech-to-Text) | End-to-end Speech-to-Speech |
| Только распознаёт речь | Заменяет **ВЕСЬ pipeline** (STT + LLM + TTS) |
| WASM в браузере, бесплатно | GPU сервер, $100-200/мес |
| Офлайн, приватно | Требует сеть |

**"Менять Vosk на Moshi" = полная перестройка архитектуры**, а не замена одного компонента.

#### Почему у Moshi нет широкого распространения

1. **Очень новый** - open-source веса с февраля 2025 (~11 мес)
2. **GPU требования** - RTX 4090 / A100 / L4 обязательно
3. **Нет коммерческой поддержки** - только research lab (Kyutai)
4. **Нет SDK** - нужно самим писать WebSocket, audio processing
5. **Только английский** - нет multi-language
6. **Нет function calling** - нельзя интегрировать с RAG/памятью

#### Риски перехода на Moshi для Free Tier

| Риск | Severity |
|------|----------|
| Потеря бесплатности Free Tier | CRITICAL |
| Потеря офлайн-работы (приватность) | HIGH |
| GPU инфраструктура ($5000+/мес при масштабе) | HIGH |
| Нет RAG/memory интеграции | HIGH |
| Потеря гибкости выбора LLM/TTS | MEDIUM |

#### Когда переходить на Moshi

| Условие | Статус |
|---------|--------|
| >1000 платящих пользователей | ❌ Не выполнено |
| OpenAI Realtime стоит >$5000/мес | ❌ Не релевантно |
| Moshi имеет stable API (v1.0+) | ❌ Не выполнено |
| Есть DevOps для GPU | ❌ Не выполнено |

**Ответ: Moshi рассмотреть через 12+ месяцев** для Ultra Tier как альтернативу OpenAI Realtime.

#### Сравнение альтернатив

| Инструмент | Тип | Стоимость | Когда использовать |
|------------|-----|-----------|-------------------|
| **Vosk + Groq + edge-tts** | Modular, free | ~$0 | Free Tier (NOW) |
| **Pipecat + Ultravox** | Modular pipeline | ~$0.05/min | Premium Tier (рекомендуется) |
| **Deepgram + GPT-4o + ElevenLabs** | Traditional cascade | ~$0.03/min | Premium Tier (альтернатива) |
| **Hume AI** | Emotional S2S | $14-500/мес | Если важны эмоции |
| **OpenAI Realtime** | Premium S2S | ~$0.05/min | Ultra Tier v1 |
| **Moshi self-hosted** | OSS S2S | GPU costs | Ultra Tier v2 (при scale) |

#### Стратегия выбора стека по фазам

```
NOW (MVP):
  ✅ Vosk + Groq + edge-tts
  ✅ Валидировать product-market fit
  ✅ Найти первых 100 пользователей

+3-4 месяца (Premium validation):
  □ Оценить спрос на premium features
  □ Прототип Pipecat + Ultravox ИЛИ Deepgram stack
  □ A/B тест latency improvements

+6-12 месяцев (Scale decision):
  □ Если >1000 платящих пользователей: внедрить Ultra tier
  □ Выбор между OpenAI Realtime vs Moshi
  □ Оценить экономику self-hosting
```

#### Файлы для будущей интеграции (когда придёт время)

| Файл | Назначение |
|------|------------|
| `app/api/voice.py` | Добавить `/premium` и `/ultra` endpoints |
| `app/services/ai/base.py` | Создать интерфейсы провайдеров |
| `app/services/ai/pipecat_provider.py` | Pipecat интеграция |
| `app/services/ai/moshi_provider.py` | Moshi интеграция |
| `app/core/config.py` | Tier-specific settings |
| `docker-compose.gpu.yml` | GPU service для Moshi |

---

### 💰 Ценообразование на рынке

| Приложение        | Месяц     | Год     | Модель                |
| ----------------- | --------- | ------- | --------------------- |
| ELSA Speak        | $12-15    | $70-100 | Фокус на произношении |
| Speak.com         | ~$19.50   | $235    | Разговоры             |
| Kippy             | ~$6.70    | $80     | Бюджетный             |
| Duolingo+         | ~$7       | $84     | Геймификация          |
| **EnglishFriend** | $0 (free) | $5-10?  | Telegram, русские     |

---

## 🚀 РЕКОМЕНДАЦИИ ДЛЯ MVP

### Наше конкурентное преимущество:

1. **Специализация на русских** = глубокое понимание W/V, TH, артиклей
2. **Telegram Mini App** = нет барьера установки, 800M+ пользователей
3. **Freemium** = низкий порог входа
4. **Терпеливый ментор** = не торопит, даёт время думать (VAD 2.5 сек)
5. **Билингвальность** = подсказки на русском когда застрял

### Что реализовать для "best in market":

| Приоритет | Функция                     | Почему важно                         |
| --------- | --------------------------- | ------------------------------------ |
| 1         | **Socratic questioning**    | Студент говорит больше, учится лучше |
| 2         | **Фонетический фидбек**     | W/V, TH детекция и коррекция         |
| 3         | **FSRS vocabulary**         | Органичное повторение слов в диалоге |
| 4         | **Эмоциональная адаптация** | Упрощать при фрустрации              |
| 5         | **Progress tracking**       | Видеть улучшения мотивирует          |

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
  text: 'Hello, I am your English mentor!',
  voiceId: 'en_US-hfc_female-medium'
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

| Решение                | Локальное    | Размер | Latency    | Качество | Офлайн |
| ---------------------- | ------------ | ------ | ---------- | -------- | ------ |
| **edge-tts** (текущий) | ❌ Сервер MS | 0      | ~200-500ms | Хорошее  | ❌     |
| **Piper TTS WASM**     | ✅ Браузер   | ~100MB | ~100-300ms | Среднее  | ✅     |
| **Web Speech API**     | ✅ Браузер   | 0      | ~50ms      | Низкое   | ✅     |

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

| Компонент         | Free Tier             | Premium Tier (Option A)   | Premium Tier (Option B)    | Ultra Tier                    |
| ----------------- | --------------------- | ------------------------- | -------------------------- | ----------------------------- |
| **Stack**         | Vosk + Groq + edge-tts| Deepgram + GPT-4o + EL    | **Pipecat + Ultravox** ⭐  | OpenAI Realtime / Moshi       |
| **STT**           | Vosk (browser WASM)   | Deepgram Nova-3           | Ultravox (native audio)    | Realtime (native) / Moshi     |
| **LLM**           | Groq/vLLM (бесплатно) | GPT-4o-mini               | Ultravox (built-in)        | GPT-4o Realtime / Moshi       |
| **TTS**           | edge-tts              | ElevenLabs Flash          | ElevenLabs / Cartesia      | Realtime API / Moshi          |
| **VAD**           | Browser (basic)       | Deepgram endpointing      | Pipecat VAD                | Server VAD (OpenAI)           |
| **Latency**       | 800-1200ms            | 400-600ms                 | **400-600ms**              | <500ms                        |
| **Стоимость/час** | $0.10-0.50            | $2-4                      | **~$3**                    | $1.35-3                       |
| **Цена подписки** | Free                  | $9.99/мес                 | $9.99/мес                  | $29.99/мес                    |
| **Рекомендация**  | ✅ MVP NOW            | Backup option             | **⭐ Recommended**         | After 1000+ users             |

---

## Анализ конкурентов (обновлено Январь 2026)

| Конкурент      | Технология                   | Цена          | Недостатки vs EnglishFriend                      |
| -------------- | ---------------------------- | ------------- | ------------------------------------------------ |
| **Duolingo**   | Video Call + OpenAI GPT-4    | Free + $30/мес (Max) | ⚠️ Теперь есть AI voice, но generic, не для русских |
| **ELSA Speak** | Proprietary STT + упражнения | $6/мес        | ❌ Только произношение, нет свободного разговора |
| **Speak.com**  | GPT-4 + TTS                  | $20/мес       | ❌ Дорого, нет русскоязычной специализации       |
| **Gliglish**   | AI voice conversations       | Free tier     | ⚠️ +75% improvement в исследованиях, но нет персонализации |
| **HelloTalk**  | Peer-to-peer                 | Free + $7/мес | ❌ Зависимость от людей, нет 24/7 доступности    |
| **Cambly**     | Живые преподаватели          | $50+/мес      | ❌ Очень дорого, расписание                      |

### ⚠️ Важное обновление: Duolingo Video Call (Сентябрь 2024)

Duolingo запустил AI Video Call с персонажем Lily:
- **Технология**: OpenAI-powered, адаптивная сложность
- **Фичи**: Помнит прошлые разговоры, адаптируется под уровень
- **Языки**: EN, ES, FR, DE, IT, PT, JP, KO
- **Цена**: Только Duolingo Max ($30/мес)

**Наше преимущество над Duolingo:**
- Специализация на русскоязычных (типичные ошибки W/V, TH, артикли)
- Goal-based learning (ML interview prep, IELTS, etc.)
- FSRS spaced repetition интегрирован в диалог
- Дешевле: $10-30/мес vs $30/мес
- Open-source возможность self-hosting

### Gliglish - Научно подтверждённая эффективность

Исследование Gualán & Ramírez (2024): **+75% improvement** в speaking scores
- Pre-test: 4.69 → Post-test: 8.24
- Особенно улучшение fluency (темп, паузы, hesitation)

**Вывод**: Voice AI для language learning работает. Вопрос в дифференциации.

**Наша ниша**: Между бесплатным Duolingo (низкое качество) и дорогим Cambly (живые люди). Мы даем качество живого диалога по цене подписки + специализация на русскоязычных + goal-based подход.

---

## Оценка юнит-экономики (обновлено Январь 2026)

### ⚡ Важное изменение: OpenAI Realtime API подешевел

В декабре 2024 OpenAI снизил цены:
- **Input audio**: -60% (было $0.06/мин → ~$0.024/мин)
- **Output audio**: -87.5% (было $0.24/мин → ~$0.03/мин)

**Новый расчёт Ultra Tier:**
- 10 мин диалога: ~$0.54 (было $3.00)
- Час практики: ~$3.24 (было $18.00)

### Premium Tier ($9.99/мес)

**Предположения**:

- Средний пользователь: 10 часов/месяц практики
- Стоимость эксплуатации: $3/час (Deepgram + GPT-4o-mini + ElevenLabs)
- Итого COGS (Cost of Goods Sold): $30/месяц
- **Маржа**: -$20.01 😱 (УБЫТОЧНО на малых объемах!)

**Оптимизация**:

1. Prompt caching: -80% на input tokens → $2/час
2. Смешанное TTS: OpenAI (дешево) для простых фраз, ElevenLabs для сложных → $1.5/час
3. Итого: $1.5/час × 10 часов = $15/месяц
4. **Маржа**: -$5.01 (все еще минус, но терпимо для привлечения Ultra)

### Ultra Tier ($29.99/мес) - OpenAI Realtime

**Обновлённые предположения** (после снижения цен):

- Средний пользователь: 15 часов/месяц (более вовлечен)
- Стоимость эксплуатации: ~$3.24/час (после снижения цен)
- Итого COGS: ~$48.60/месяц
- **Маржа**: -$18.61 (всё ещё минус, но лучше чем было -$0.01 при 15 часах)

### 🆕 Ultra Tier Alternative: Moshi Self-Hosted

**Расчёт для self-hosted Moshi:**

- GPU стоимость: L4 instance ~$0.50/час (при shared использовании)
- На пользователя при 10 concurrent users: ~$0.05/час
- 15 часов/месяц × $0.05 = **$0.75/месяц**
- **Маржа**: +$29.24 🎉

**Trade-offs Moshi vs OpenAI Realtime:**
| Фактор | OpenAI Realtime | Moshi Self-Hosted |
|--------|-----------------|-------------------|
| Latency | 200-300ms | 160-200ms ✅ |
| Quality | Best-in-class | Very good |
| Cost/hour | $3.24 | $0.05 ✅ |
| Setup complexity | Low ✅ | High |
| Maintenance | None ✅ | DevOps required |

**Вывод (обновлённый)**:

- Premium Tier - loss leader для привлечения
- Ultra Tier с OpenAI Realtime - для MVP и валидации (проще запустить)
- Ultra Tier с Moshi - для scale (после 1000+ пользователей)
- B2B тариф: $99/мес за корпоративную лицензию с Moshi self-hosted = маржа 95%+

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

| Действие | Файл                                                  |
| -------- | ----------------------------------------------------- |
| CREATE   | `db/migrations/postgres/010_streaks_gamification.sql` |
| CREATE   | `app/services/gamification/__init__.py`               |
| CREATE   | `app/services/gamification/xp_service.py`             |
| CREATE   | `app/services/gamification/streak_service.py`         |
| CREATE   | `app/api/gamification.py`                             |
| CREATE   | `tests/test_xp_service.py`                            |
| CREATE   | `tests/test_streak_service.py`                        |
| EDIT     | `app/models/core_tables.py` (добавить 4 поля)         |
| EDIT     | `app/api/voice.py` (интеграция при завершении сессии) |
| EDIT     | `main.py` (добавить gamification router)              |

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

## 🔬 Исследование: JEPA и World Models (Январь 2026)

### Контекст

Анализ передовых AI-архитектур от Meta (Yann LeCun) и galilai-group для потенциального применения в EnglishFriend.

### JEPA (Joint Embedding Predictive Architecture)

**Что это**: Архитектура self-supervised learning, альтернатива генеративным моделям (GPT).

**Ключевое отличие**:
```
Генеративные модели: Предсказывают пиксели/токены напрямую
JEPA: Предсказывает в пространстве эмбеддингов (абстракций)
```

**Эволюция JEPA (2023-2025)**:
| Модель | Год | Модальность | Статус |
|--------|-----|-------------|--------|
| I-JEPA | 2023 | Изображения | Production |
| V-JEPA | 2024 | Видео | Production |
| V-JEPA 2 | 2025 | Видео + Robotics | Production |
| VL-JEPA | Dec 2025 | Vision-Language | New |
| **LLM-JEPA** | Sep 2025 | Текст/LLM | **Применимо!** |

### LLM-JEPA - Применимость к EnglishFriend

**Что это**: JEPA-based fine-tuning для LLM.
**Paper**: https://arxiv.org/abs/2509.14252
**Repo**: https://github.com/galilai-group/llm-jepa

**Преимущества**:
- Устойчивость к overfitting (критично при малых education datasets)
- Лучше стандартных training objectives на GSM8K, Spider, etc.
- Работает с Llama3, Gemma2, OpenELM

**Потенциальное применение в EnglishFriend**:
1. Fine-tune модели на education диалогах
2. Специализация на коррекции ошибок русскоязычных
3. Улучшение Socratic questioning через обучение на примерах

**Статус**: R&D направление для Фазы 3+ (6-12 месяцев)

### World Models - НЕ применимо напрямую

**Что это**: AI-системы для предсказания и планирования в физическом мире.

**Рынок 2024-2025**:
- $7.5B+ инвестиций в Physical AI
- Google DeepMind (Genie 2), NVIDIA (Cosmos), World Labs ($230M)
- Yann LeCun ушёл из Meta основывать World Models стартап

**Почему НЕ подходит для EnglishFriend**:
- Оптимизированы для robotics, autonomous vehicles, gaming
- "World Model ученика" ≠ World Model в академическом смысле
- Для трекинга прогресса достаточно: FSRS, Bayesian Knowledge Tracing, простой ML

**Вывод**: Следить за развитием, но не инвестировать ресурсы сейчас.

### Практические рекомендации

| Технология | Применимость | Timeline | Действие |
|------------|--------------|----------|----------|
| LLM-JEPA | ✅ Высокая | 6-12 мес | R&D после MVP |
| World Models | ❌ Низкая | N/A | Мониторинг |
| JEPA для Audio | ⚠️ Не существует | 12-24 мес | Ждать open-source |

### Ссылки

- [Meta AI: I-JEPA](https://ai.meta.com/blog/yann-lecun-ai-model-i-jepa/)
- [LLM-JEPA Paper](https://arxiv.org/abs/2509.14252)
- [galilai-group GitHub](https://github.com/galilai-group)
- [World Models Survey](https://arxiv.org/html/2510.16732v1)

---

## Заключение (обновлено Январь 2026)

**Текущая позиция**: Vosk MVP почти готов, это сильная база для Free Tier.

**Стратегия**: Запустить freemium с бесплатным Vosk → монетизировать через Premium (Deepgram + ElevenLabs) → дифференцироваться через Ultra (Realtime API или Moshi).

**Конкурентное преимущество**:
- Специализация на русскоязычных + интеграция SRS/RAG
- Goal-based learning (ML interview, IELTS, etc.)
- Duolingo Video Call теперь конкурент, но мы дешевле и специализированнее

**Критический путь**:
- Free MVP (2 мес)
- Premium с LiveKit orchestration (4 мес)
- Ultra с OpenAI Realtime или Moshi self-hosted (6+ мес)

**Новые возможности (2025)**:
- Moshi для self-hosted Ultra tier = маржа 95%+ vs убыток на OpenAI
- LLM-JEPA для fine-tuning в Фазе 3+ (устойчивость к overfitting)
- OpenAI Realtime подешевел на 60-87%

**Риски**:
- Высокая стоимость эксплуатации → митигация через Moshi self-hosted
- Duolingo Video Call как конкурент → дифференциация через специализацию

**R&D направления** (не для MVP):
- LLM-JEPA для education fine-tuning
- Multi-Agent + ML Scoring для background analysis

Этот анализ - живой документ. Обновлять по мере тестирования гипотез и сбора feedback от первых пользователей Free Tier.

---

*Последнее обновление: 2026-01-20*
*Добавлено: Pipecat + Ultravox как альтернатива Premium Tier, архитектурный анализ Vosk vs Moshi, обновлённая таблица стеков*
*Предыдущее обновление (2026-01-13): Moshi, LiveKit, JEPA/World Models анализ, обновлённая юнит-экономика, Duolingo Video Call*
