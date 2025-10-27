### Документация проекта  
**ИИ‑репетитор‑компаньон по английскому языку в Telegram, мобильном приложении и веб-клиенте**

***

## 1. Концепция проекта

Цель: создать **интерактивного ИИ‑репетитора‑компаньона**, который комбинирует функции преподавателя, собеседника и эмоционально вовлечённого друга.  
Он ведёт **реальные голосовые звонки**, анализирует речь и грамматику, формирует **портрет личности и интересов пользователя**, хранящийся в векторной памяти, и развивает общение на уровне человеческих отношений.

Главные свойства:  
- Реальные звонки (через Telegram Mini App, мобильное приложение и веб-клиент на WebRTC).  
- Мультиканальный доступ (телеграм, мобильное приложение, веб) с единым профилем.  
- Эмоциональный голос и поддержка диалога в реальном времени.  
- Анализ произношения и грамматики после разговора.  
- Гибридная память (PostgreSQL + Vector DB + Graph).  
- Профиль личности и интересов пользователя.  
- Персонализированные темы общения и траектории обучения.

***

## 2. Общая архитектура системы

```
[ Telegram MiniApp / Mobile App / Web Voice UI ]
          ↓
[ WebRTC Gateway + Realtime Session Manager ]
          ↓
[ OpenAI Realtime API (gpt‑4o‑realtime) ]
          ↓
[ LangGraph Orchestrator ]
 ├─ GrammarCoach
 ├─ EmotionCompanion
 ├─ ProgressPlanner
 ├─ MemoryKeeper
          ↓
[ Hybrid Storage Layer ]
 ├─ PostgreSQL (users, sessions, feedback)
 ├─ VectorDB (Qdrant или Pinecone)
 ├─ GraphDB (Neo4j или Memgraph)
          ↓
[ Analytics Dashboard / Streamlit ]
```

### Ключевые модули

| Модуль | Описание |
|---------|-----------|
| **SpeechAgent** | передача аудио через WebRTC в OpenAI Realtime API и генерация ответов с эмоциями |
| **GrammarCoach** | анализ синтаксиса, ошибок, выдача обратной связи |
| **EmotionCompanion** | отслеживание тональности, пауз, ритма и эмоционального состояния |
| **ProgressPlanner** | планирование новых тем и адаптивных заданий |
| **MemoryKeeper** | управление векторной памятью, поиск прошлых тем, напоминание фактов о пользователе |

***

## 3. Структура базы данных (PostgreSQL)

### Таблица `users`
| Поле | Тип | Описание |
|------|-----|-----------|
| `id` | BIGSERIAL PK | Уникальный ID |
| `telegram_id` | BIGINT UNIQUE | Telegram ID (если используется канал Telegram) |
| `username` | VARCHAR (255) | Имя пользователя |
| `language_level` | VARCHAR (10) | Уровень (A2–C1) |
| `primary_channel` | VARCHAR (20) | Основной канал (telegram / mobile_app / web) |
| `personality_vector_ref` | UUID | ID в VectorDB |
| `created_at` | TIMESTAMP | регистрация |

### Таблица `user_channel_identity`
| Поле | Тип | Описание |
|------|-----|-----------|
| `id` | UUID PK | Идентификатор записи |
| `user_id` | BIGINT FK → users | Пользователь |
| `channel` | VARCHAR (20) | `telegram`, `mobile_app`, `web` |
| `external_id` | TEXT | ID пользователя в канале |
| `auth_payload` | JSONB | Токены, данные устройства |
| `linked_at` | TIMESTAMP | Дата привязки |

### Таблица `sessions`
| Поле | Тип | Описание |
|------|-----|-----------|
| `id` | UUID PK | ID сессии |
| `user_id` | BIGINT FK → users |
| `start_time` | TIMESTAMP | Начало звонка |
| `audio_url` | TEXT | Ссылка на запись |
| `transcript_text` | TEXT | Расшифровка |
| `topics_detected` | JSONB | Темы разговора |
| `emotion_detected` | VARCHAR (50) | Основная эмоция |
| `grammar_score` | FLOAT | Балл грамматики |
| `pronunciation_score` | FLOAT | Балл произношения |

### Таблица `feedback`
| Поле | Тип | Описание |
|------|-----|-----------|
| `session_id` | UUID FK | Сессия |
| `corrected_phrases` | JSONB | Исправления |
| `grammar_tips` | TEXT | Объяснения |
| `pronunciation_tips` | TEXT | Замечания |
| `vocabulary_suggestions` | JSONB | Новые слова |

### Таблица `user_interests`
| Поле | Тип | Описание |
|------|-----|-----------|
| `user_id` | BIGINT FK | Пользователь |
| `interest` | VARCHAR (255) | Тематика |
| `weight` | FLOAT | Значимость |
| `last_mentioned` | TIMESTAMP | Последнее упоминание |

### Таблица `emotional_state_log`
| Поле | Тип | Описание |
|------|-----|-----------|
| `user_id` | BIGINT FK | Пользователь |
| `session_id` | UUID | Сессия |
| `emotion` | VARCHAR (50) | Эмоция |
| `intensity` | FLOAT | Сила |
| `context` | TEXT | Контекст события |

***

## 4. Структура графа (Graph DB)

**Узлы:**  
`User`, `Interest`, `Topic`, `Session`, `Emotion`, `Memory`, `Persona`  

**Связи:**  
- `INTEREST_IN` — интерес пользователя.  
- `TALKED_ABOUT` — тема обсуждения.  
- `EVOKES` — эмоция, вызванная темой.  
- `HAS_MEMORY` — запись в воспоминании.  
- `RELATED_TO` — связи тем.  
- `HAS_TRAIT` — психолингвистические характеристики (Big Five).

**Пример:**  
`(User:Anna)-[:INTEREST_IN]->(Topic:design)-[:EVOKES]->(Emotion:joy)`

***

## 5. Векторная память (Vector DB)

### Коллекция `user_memories`
| Поле | Тип | Описание |
|------|-----|-----------|
| `id` | UUID | Уникальный ID |
| `user_id` | BIGINT | Пользователь |
| `embedding` | VECTOR(1536) | Вектор эмбеддинга |
| `content` | TEXT | Фраза или воспоминание |
| `metadata` | JSON | эмоции, темы, дата |
| `timestamp` | TIMESTAMP | время записи |

***

## 6. Эмоционально‑когнитивная модель

| Слой | Назначение |
|------|-------------|
| **State Variables** | текущие эмоции из тона речи (tone, pitch) |
| **Mood State** | сводное настроение за сессию |
| **Personality Traits** | стабильные черты (например, доброжелательность) |
| **Emotion Policy** | определяет стиль реакции: поддержать, пошутить, переключить тему |

***

## 7. Поток данных (Pipeline)

1. Пользователь инициирует звонок через Telegram Mini App, мобильное приложение или веб‑клиент.  
2. WebRTC‑поток направляется в Realtime API.  
3. Модель gpt‑4o‑realtime транскрибирует, отвечает голосом и фиксирует эмоции.  
4. По завершении сессии создаются:  
   - транскрипт и анализ речи;  
   - векторные воспоминания;  
   - обновления в графе интересов и эмоций.  
5. Результаты выводятся в Telegram‑чате, мобильном приложении и веб‑кабинете:  
   - Your pronunciation of “work” was very clear today.  
   - You mixed up “say” and “tell”. Here’s an easy rule to remember.  

***

## 8. Персонализационный и игровой уровень

- **Adaptive Learning:** модель регулирует сложность тем и предлагает повторение трудных случаев.  
- **Gamification:** миссии, награды, уровни (“Fluency XP”, “Grammar Streak”).  
- **Reflection Module:** еженедельный отчёт с анализом прогресса и эмоций.

***

## 9. Технологический стек

| Компонент | Инструменты |
|------------|-------------|
| Бот / Клиент | Telegram Bot API, Mini Apps, мобильное приложение (React Native/Flutter), веб‑клиент (Next.js) |
| Realtime модель | OpenAI gpt‑4o‑realtime |
| Оркестрация | LangGraph / LangChain |
| Анализ речи | Whisper API, SpeechSuper, Azure Speech |
| Базы данных | PostgreSQL, Qdrant / Pinecone, Neo4j |
| Бэкенд | Python FastAPI / Node.js (grammY / aiogram) |
| Аналитика | Grafana / Streamlit |

***

## 10. Безопасность и приватность

- Изоляция данных пользователей по ID в PostgreSQL и VectorDB.  
- Минимизация хранимых аудио — только ссылки на зашифрованное хранилище (MinIO/S3).  
- Шифрование API‑ключей и личной информации (AES‑256).  
- Опциональная очистка памяти по запросу («забыть разговор»).  

***

## 11. Дополнительные перспективы

- **Multimodal апгрейд:** анализ мимики и текста одновременно при видео‑звонках.  
- **Характерные роли:** выбор “персональности” преподавателя (энергичный, спокойный, британский, американский акцент).  
- **Социальный режим:** групповые занятия с несколькими пользователями.  

***

**Формат итоговой системы** — гибридная платформа с живыми голосовыми диалогами, эмоциональной и когнитивной памятью, которая обучает, мотивирует и формирует настоящие отношения между человеком и ИИ.
