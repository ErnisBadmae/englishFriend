# Анализ JEPA, World Models и Voice AI для Language Learning

**Дата**: 2026-01-13
**Цель**: Оценить применимость передовых AI-технологий для голосового ассистента обучения английскому

---

## TL;DR

| Технология | Инновационность | Применимость к English Mentor | Реалистичность |
|------------|-----------------|------------------------------|----------------|
| **JEPA** | ⭐⭐⭐⭐⭐ Cutting-edge | ⚠️ Косвенная (LLM-JEPA для NLP) | 6-12 мес R&D |
| **World Models** | ⭐⭐⭐⭐⭐ Frontier AI | ❌ Не для education | Академический research |
| **Moshi (Kyutai)** | ⭐⭐⭐⭐ Production-ready | ✅ Прямая замена текущего стека | 1-2 месяца |
| **OpenAI Realtime** | ⭐⭐⭐⭐ Best-in-class | ✅ Plug & play | 1-2 недели |
| **LiveKit + Deepgram** | ⭐⭐⭐ Mature | ✅ Гибкий стек | 2-4 недели |

---

## Часть 1: JEPA (Joint Embedding Predictive Architecture)

### Что это?
JEPA — архитектура self-supervised learning, предложенная Яном ЛеКуном (Meta) в 2022 году как альтернатива генеративным моделям (GPT). Ключевое отличие:

```
Генеративные модели: Предсказывают пиксели/токены напрямую
JEPA: Предсказывает в пространстве эмбеддингов (абстрактных представлений)
```

### Эволюция JEPA (2023-2025)

| Модель | Год | Модальность | Ключевые результаты |
|--------|-----|-------------|---------------------|
| **I-JEPA** | 2023 | Изображения | ViT-Huge за 72 часа на 16 A100 |
| **V-JEPA** | 2024 | Видео | 2M+ unlabeled видео, предсказание masked частей |
| **V-JEPA 2** | 2025 | Видео + Robotics | World model для планирования роботов |
| **VL-JEPA** | Dec 2025 | Vision-Language | 50% меньше параметров vs классический VLM, лучше CLIP |
| **LLM-JEPA** | Sep 2025 | Текст/LLM | Fine-tuning LLM, превосходит стандартные objectives |

### Почему JEPA инновационна?

1. **Энергоэффективность**: Не генерирует все детали, работает с абстракциями
2. **Robustness**: Более устойчива к шуму и irrelevant деталям
3. **Sample efficiency**: Меньше данных для обучения
4. **Path to AGI**: LeCun считает JEPA фундаментом для human-level AI

### Применимость к English Mentor

| Вариант JEPA | Применимо? | Почему |
|--------------|------------|--------|
| I-JEPA | ❌ | Только vision |
| V-JEPA | ❌ | Видео, не audio |
| VL-JEPA | ⚠️ | Потенциально для multimodal (видео+текст lessons) |
| **LLM-JEPA** | ✅ | Fine-tuning на диалогах, устойчивость к overfitting |

**Реальное применение LLM-JEPA:**
```python
# Возможный use case: fine-tune модель на education диалогах
# LLM-JEPA показывает лучшую устойчивость к overfitting
# Особенно полезно при малом количестве данных
```

### Честная оценка
- **Audio-JEPA не существует в open-source** — Perplexity выдумал "Voice JEPA"
- LLM-JEPA реально может помочь с fine-tuning, но это research-level работа
- Для MVP лучше использовать готовые решения (OpenAI, Deepgram)

---

## Часть 2: World Models

### Что это?
World Models — AI-системы, которые строят внутреннюю модель мира для предсказания и планирования.

```
Традиционный RL: Действие → Наблюдение реального мира → Feedback
World Model: Действие → Симуляция в "воображении" → Планирование → Действие
```

### Ключевые игроки (2024-2025)

| Компания | Продукт | Фокус | Funding |
|----------|---------|-------|---------|
| **Google DeepMind** | Genie 2 | 3D миры из одного изображения | Internal |
| **NVIDIA** | Cosmos | Robotics + Omniverse | N/A |
| **World Labs** (Fei-Fei Li) | Marble | 3D миры из prompt | $230M |
| **Physical Intelligence** | Robotics | Physical AI | $400M @ $2.4B |
| **Figure AI** | Humanoid robots | Physical AI | $675M |
| **General Intuition** | Spatial reasoning | Agents | $134M seed |

### Рынок World Models

- **$7.5B+ привлечено в Physical AI в 2024**
- **Gaming**: $1.2B (2022-2025) → $276B к 2030 (прогноз PitchBook)
- **Yann LeCun** ушел из Meta основывать стартап по World Models

### Почему World Models НЕ подходят для English Mentor

```
World Models оптимизированы для:
├── Robotics (физическое взаимодействие)
├── Autonomous vehicles (навигация)
├── Gaming (генерация 3D миров)
└── Simulation (предсказание физики)

English Mentor требует:
├── Понимание речи (ASR/STT)
├── Генерация речи (TTS)
├── Педагогическую логику
└── Персонализацию обучения

Пересечение: ~5%
```

### Что Perplexity назвал "World Model ученика"
Это **не** World Model в академическом смысле. Это:
- User modeling (профиль ученика)
- Learning trajectory prediction (FSRS, Bayesian Knowledge Tracing)
- Adaptive learning systems

Такие системы существуют давно и не требуют World Models архитектуры.

---

## Часть 3: Реальные инструменты для Voice AI Language Learning

### Топ-решения 2025

#### 1. OpenAI Realtime API
```
Latency: ~200-300ms
Pricing: $0.06/min input, $0.24/min output
Качество: Best-in-class
Особенности: Native speech-to-speech, без цепочки STT→LLM→TTS
```
**Плюсы**: Минимум кода, отличное качество
**Минусы**: Дорого при масштабе ($2.40 за 10 мин output)

#### 2. Moshi (Kyutai) - Open Source
```
Latency: 160-200ms (лучший в классе)
Pricing: Self-hosted (GPU costs only)
Модель: 7B параметров, full-duplex
Лицензия: Apache 2.0 (код), CC-BY 4.0 (веса)
```
**Плюсы**: Open-source, self-hosted, 92 интонации, эмоции
**Минусы**: Требует GPU (L4 минимум), сложнее интеграция

**GitHub**: https://github.com/kyutai-labs/moshi

#### 3. LiveKit + Deepgram + ElevenLabs
```
Архитектура: STT (Deepgram) → LLM → TTS (ElevenLabs)
Latency: ~300-500ms (сумма компонентов)
Pricing: ~$0.01/min combined (без LLM)
```
**Плюсы**: Гибкость, можно менять компоненты
**Минусы**: Больше latency, сложнее interruption handling

#### 4. Vapi / Retell / Bland
```
Тип: Voice Agent Platforms (all-in-one)
Pricing: $0.05-0.10/min
Setup: Часы вместо недель
```
**Плюсы**: Быстрый старт, hosted solution
**Минусы**: Vendor lock-in, меньше контроля

### Сравнение для English Mentor

| Критерий | OpenAI Realtime | Moshi | LiveKit Stack | Vapi |
|----------|-----------------|-------|---------------|------|
| Time to MVP | 1-2 недели | 1-2 месяца | 2-4 недели | 1-3 дня |
| Стоимость/мин | $0.30 | ~$0.02 (GPU) | ~$0.05 | $0.05-0.10 |
| Latency | 200-300ms | 160-200ms | 300-500ms | 200-400ms |
| Кастомизация | Средняя | Высокая | Высокая | Низкая |
| Self-hosted | ❌ | ✅ | Частично | ❌ |
| Emotions/Tone | ✅ | ✅ (92 стиля) | Зависит от TTS | Зависит |

### Рекомендация для English Mentor

**Фаза 1 (MVP, 1-2 месяца):**
```
OpenAI Realtime API
├── Быстрый запуск
├── Отличное качество
└── Validate product-market fit
```

**Фаза 2 (Scale, 3-6 месяцев):**
```
Moshi self-hosted
├── Снижение costs 10-15x
├── Полный контроль
└── Кастомные эмоции для педагогики
```

---

## Часть 4: Конкуренты в Language Learning

### Duolingo (лидер рынка)
- **Video Call**: AI-персонаж Lily, OpenAI-powered
- **Адаптивность**: Подстраивается под уровень в real-time
- **Memory**: Помнит прошлые разговоры
- **Ограничение**: Только Duolingo Max ($30/мес)

### Gliglish
- **Исследования**: +75% improvement в speaking (Gualán & Ramírez, 2024)
- **Фокус**: Чистый conversation practice

### Langotalk / Talkpal / Pronounce
- **Подход**: AI tutors с real-time feedback
- **Особенности**: Pronunciation analysis, grammar correction

### Что отличает English Mentor (твой проект)

| Фича | Duolingo | Gliglish | English Mentor |
|------|----------|----------|----------------|
| Goal-based learning | ❌ | ❌ | ✅ (ML interview, etc) |
| Spaced repetition для vocab | ❌ | ❌ | ✅ (FSRS) |
| Voice-first | Частично | ✅ | ✅ |
| Open-source | ❌ | ❌ | ✅ |
| Self-hosted | ❌ | ❌ | ✅ |
| Custom curriculum | ❌ | ❌ | ✅ |

---

## Часть 5: Перспективные стартап-идеи

### На основе JEPA (Research-heavy, 12-24 месяца)

#### Идея 1: "Pronunciation Predictor"
```
Концепт: Модель предсказывает ошибки произношения ДО того, как ученик их сделает
Технология: Audio embeddings + JEPA-like prediction
Проблема: Audio-JEPA не существует, нужно создавать с нуля
Рынок: B2B для language schools
Сложность: ⭐⭐⭐⭐⭐
```

#### Идея 2: "LLM-JEPA Educational Fine-tuning"
```
Концепт: Платформа fine-tuning LLM для education с LLM-JEPA
Преимущество: Устойчивость к overfitting на малых датасетах
Рынок: EdTech компании, корпоративное обучение
Сложность: ⭐⭐⭐⭐
```

### На основе World Models (Очень долгосрочно)

#### Идея 3: "Learning Trajectory Simulator"
```
Концепт: World Model для симуляции прогресса ученика
Применение: Оптимизация учебных программ без A/B тестов на людях
Реальность: Существующие BKT модели проще и эффективнее
Сложность: ⭐⭐⭐⭐⭐ (и не факт что нужно)
```

### На основе Voice AI (Реалистичные, 3-6 месяцев)

#### Идея 4: "Domain-Specific Voice Tutor" ⭐ РЕКОМЕНДУЮ
```
Концепт: Голосовой репетитор для узких доменов
Примеры:
├── ML Interview Prep (твой English Mentor)
├── Medical English для врачей
├── Legal English для юристов
├── Aviation English для пилотов
Технология: OpenAI Realtime + RAG с domain knowledge
Monetization: B2B, $50-200/user/month
Сложность: ⭐⭐⭐
```

#### Идея 5: "Moshi-based Language School Platform"
```
Концепт: White-label voice AI для языковых школ
Преимущество: Self-hosted = низкие costs, data privacy
Рынок: Языковые школы, корпоративные тренинги
Monetization: SaaS $500-2000/school/month
Сложность: ⭐⭐⭐
```

#### Идея 6: "Emotional Adaptive Tutor"
```
Концепт: Репетитор, который адаптируется к эмоциям ученика
Технология: Emotion detection (Hume AI) + adaptive pacing
Фичи:
├── Замедляется при фрустрации
├── Поддерживает при неуверенности
├── Челленджит при скуке
Сложность: ⭐⭐⭐⭐
```

### Матрица "Инновационность vs Реалистичность"

```
Инновационность
     ▲
     │  [JEPA Audio]        [World Model Education]
  5  │       ●                      ●
     │
  4  │  [LLM-JEPA Tutor]  [Emotional Adaptive]
     │       ●                   ●
  3  │              [Domain Voice Tutor] ⭐
     │                     ●
  2  │        [Moshi White-label]
     │              ●
  1  │  [Basic Voice Bot]
     │       ●
     └──────────────────────────────────► Реалистичность
         1    2    3    4    5
```

---

## Часть 6: Технический роадмап для English Mentor

### Текущий стек (по CLAUDE_SESSION_LOG.md)
```
STT: Vosk (browser) + накопление partial results
LLM: Groq (Llama)
TTS: Silero / Edge TTS
Педагогика: Mode selector (4 режима), FSRS
```

### Рекомендуемая эволюция

#### Phase 1: Стабилизация MVP (текущий)
```
Задачи:
├── Исправить баг vocabulary cards (SQLAlchemy JSON)
├── Протестировать End Session flow
├── Валидировать product-market fit
Timeline: 2-4 недели
```

#### Phase 2: Voice Quality Upgrade
```
Опция A (быстро, дорого):
└── OpenAI Realtime API
    ├── Заменяет весь voice pipeline
    ├── ~$0.30/min
    └── 1-2 недели интеграции

Опция B (дольше, дешевле):
└── Moshi self-hosted
    ├── Требует GPU (RTX 3090 или L4)
    ├── ~$0.02/min
    └── 4-6 недель интеграции
```

#### Phase 3: Differentiation
```
Уникальные фичи:
├── Goal-based curriculum generation
├── FSRS vocabulary с voice drilling
├── Domain-specific knowledge (ML interviews)
└── Progress analytics
```

#### Phase 4: Scale (если PMF подтвержден)
```
├── Multi-language support
├── B2B white-label
├── Mobile apps
└── Возможно: LLM-JEPA fine-tuning на education данных
```

---

## Выводы

### Что Perplexity сказал правильно:
- ✅ JEPA и World Models — передовые технологии
- ✅ Персонализация — ключ к retention
- ✅ Предиктивный подход лучше реактивного

### Что Perplexity выдумал:
- ❌ "Voice JEPA" — не существует
- ❌ World Models для "модели ученика" — overkill
- ❌ "3 месяца до MVP" с этими технологиями — нереально

### Практические рекомендации:

1. **Для English Mentor сейчас**: OpenAI Realtime или Moshi
2. **JEPA**: Следить за LLM-JEPA, возможно применить через 6-12 мес
3. **World Models**: Не для этого проекта, это для robotics
4. **Стартап-идея**: Domain-specific voice tutor (ML interviews) — уже делаешь правильно

---

## Источники

### JEPA & World Models
- [Meta AI: I-JEPA](https://ai.meta.com/blog/yann-lecun-ai-model-i-jepa/)
- [Meta AI: V-JEPA](https://ai.meta.com/blog/v-jepa-yann-lecun-ai-model-video-joint-embedding-predictive-architecture/)
- [VL-JEPA Paper (Dec 2025)](https://arxiv.org/abs/2512.10942)
- [LLM-JEPA Paper (Sep 2025)](https://arxiv.org/abs/2509.14252)
- [World Models Survey](https://arxiv.org/html/2510.16732v1)
- [Built In: World Models Explained](https://builtin.com/articles/ai-world-models-explained)

### Voice AI Platforms
- [Moshi GitHub](https://github.com/kyutai-labs/moshi)
- [Kyutai: Meet Moshi](https://kyutai.org/blog/2024-07-03-meet-moshi)
- [OpenAI Realtime API](https://openai.com/index/introducing-the-realtime-api/)
- [Voice Agent Platforms Comparison](https://softcery.com/lab/choosing-the-right-voice-agent-platform-in-2025)
- [Deepgram vs ElevenLabs](https://deepgram.com/learn/deepgram-vs-elevenlabs)

### Language Learning AI
- [Duolingo AI Innovations 2024](https://investors.duolingo.com/news-releases/news-release-details/duolingo-introduces-ai-powered-innovations-duocon-2024)
- [Gliglish](https://gliglish.com/)
- [AI Language Learning Apps 2025](https://www.unite.ai/best-ai-language-learning-apps/)

### Market & Investment
- [ElevenLabs Developer Trends 2025](https://elevenlabs.io/blog/voice-agents-and-conversational-ai-new-developer-trends-2025)
- [NVIDIA Physical AI](https://nvidianews.nvidia.com/news/nvidia-releases-new-physical-ai-models-as-global-partners-unveil-next-generation-robots)

---

*Документ создан: 2026-01-13*
*Последнее обновление: 2026-01-13*
