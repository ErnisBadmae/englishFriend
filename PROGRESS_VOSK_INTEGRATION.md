# Voice Recognition Integration Progress

**Дата**: 2025-12-30
**Задача**: Интеграция Vosk STT (браузерное распознавание речи) с WebSocket бэкендом для голосового чата

---

## Текущий статус: 90% готовности

### ✅ Что работает:

1. **WebSocket подключение** - стабильно, без бесконечных переподключений
2. **Vosk модель** - загружается и инициализируется (46MB, vosk-model-small-en-us-0.15)
3. **Микрофон** - разрешения работают, аудио захватывается
4. **AudioContext** - создаётся с правильным sample rate (16000Hz)
5. **KaldiRecognizer** - создаётся успешно
6. **acceptWaveform** - принимает аудио буферы без ошибок
7. **Partial/Final results** - события приходят от Vosk

### ❌ Проблема (последний шаг):

**Vosk не распознаёт речь** - все результаты пустые (`partial: ''`, `text: ''`)

**Симптомы**:
```javascript
[Vosk] Partial result: {partial: '', length: 0}
[Vosk] Final result: {text: ''}
```

**Возможные причины** (в порядке вероятности):
1. Несоответствие sample rate между AudioContext (16000Hz запрошено, но браузер может использовать 48000Hz)
2. Недостаточный уровень громкости микрофона
3. Проблема с форматом передачи аудио в acceptWaveform
4. Неправильная модель (нужна другая версия)

---

## Архитектура решения

```
[Микрофон]
    → [MediaStream]
    → [AudioContext 16000Hz]
    → [ScriptProcessorNode 4096 samples]
    → [recognizer.acceptWaveform(inputBuffer)]
    → [Vosk WebAssembly]
    → [partialresult/result events]
    → [WebSocket → Backend]
    → [vLLM/Groq]
    → [edge-tts]
    → [Audio playback]
```

---

## Файлы с изменениями

### Frontend (React + TypeScript)

1. **`frontend/src/hooks/useVosk.ts`** - основной хук для Vosk STT
   - Загрузка модели с проверкой готовности
   - Создание KaldiRecognizer
   - Обработка аудио через ScriptProcessorNode
   - События: `result`, `partialresult`
   - **Текущие логи**: sample rate, amplitude, chunk count

2. **`frontend/src/hooks/useWebSocket.ts`** - WebSocket соединение
   - Автоматические переподключения (макс 3 попытки)
   - Обработка сообщений: `connected`, `transcript`, `audio`, `error`
   - Отправка текста: `sendText(text)`

3. **`frontend/src/components/VoiceChat.tsx`** - главный компонент
   - Интеграция useVosk + useWebSocket
   - Обработчик `onResult` для транскриптов
   - При остановке записи → отправка текста на сервер

4. **`frontend/public/vosk-model-small-en-us-0.15.zip`** - модель Vosk (46MB)

### Backend (Python FastAPI)

5. **`app/api/voice.py`** - WebSocket endpoint `/api/v1/voice/chat`
   - **ИСПРАВЛЕНО**: AttributeError с `user.channel_id` → `user.username`
   - **ИСПРАВЛЕНО**: Graceful error handling с proper close codes
   - Интеграция с vLLM/Groq + edge-tts

6. **`app/services/memory_and_interests.py:102-113`**
   - **ИСПРАВЛЕНО**: PostgreSQL enum comparison (используем `.value`)

7. **`app/models/enums_and_dimensions.py:21-27`**
   - **ИСПРАВЛЕНО**: MemoryKind enum синхронизирован с БД
   - Добавлен `ERROR_PATTERN = "error_pattern"`

8. **`db/migrations/postgres/008_extend_memory_kind.sql`** - НОВЫЙ файл
   - Расширяет enum `memory_kind` для поддержки error_pattern

---

## Что нужно сделать на новом компьютере

### 1. Клонировать репозиторий

```bash
git clone <your-repo-url>
cd englishFriend
git checkout main  # или ваша ветка
```

### 2. Установить зависимости

**Backend:**
```bash
# Создать venv с Python 3.12
py -3.12 -m venv venv
venv/Scripts/activate

# Установить зависимости
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
npm install
```

### 3. Настроить окружение

**Скопировать `.env` файл:**
```bash
cp .env.example .env
```

**Важные переменные в `.env`:**
```bash
# vLLM (локальный сервер)
VLLM_API_BASE=http://192.168.0.88:8000/v1
VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct-AWQ
TRUST_REMOTE_CODE=false

# Groq (альтернатива)
GROQ_API_KEY=<your-key>

# TTS
TTS_PROVIDER=edge

# База данных
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/english_friend
```

### 4. Запустить инфраструктуру

**PostgreSQL через Docker:**
```bash
docker-compose up -d postgres
```

**Применить миграции:**
```bash
# Миграция 008 критична!
docker exec english_friend_postgres psql -U postgres -d english_friend -f /docker-entrypoint-initdb.d/008_extend_memory_kind.sql
```

### 5. Запустить приложение

**Backend:**
```bash
venv/Scripts/python.exe main.py
# Слушает на http://localhost:8000
```

**Frontend:**
```bash
cd frontend
npm run dev
# Слушает на http://localhost:5173
```

### 6. Проверить Vosk модель

Убедитесь что модель на месте:
```bash
ls -la frontend/public/vosk-model-small-en-us-0.15.zip
# Должен быть ~46MB
```

Если нет, скачайте:
```bash
cd frontend/public
curl -LO https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
```

---

## Debugging команды

**Проверить логи браузера:**
```
[Vosk] AudioContext created with sample rate: 16000Hz
[Vosk] KaldiRecognizer created with sample rate: 16000Hz
[Vosk] Processed 50 chunks | Max amplitude: 0.XXXX | Buffer SR: 16000Hz
[Vosk] Partial result: {partial: '', length: 0}
```

**Ключевые метрики:**
- `Max amplitude` должна быть > 0.01 при громкой речи
- `Buffer SR` должна быть 16000Hz (может быть 48000Hz - это проблема!)
- `partial` должна содержать распознанный текст

**Если amplitude близко к 0:**
→ Проверить разрешения микрофона в браузере
→ Проверить уровень записи в Windows Sound Settings

**Если Buffer SR != 16000Hz:**
→ Нужен resampler (добавить Web Audio API resampler)

---

## План исправления (следующие шаги)

### Вариант 1: Проверить sample rate mismatch

```typescript
// В useVosk.ts после создания AudioContext
console.log(`Requested: 16000Hz, Actual: ${audioContext.sampleRate}Hz`);

if (audioContext.sampleRate !== 16000) {
  console.warn('Sample rate mismatch! Need to add resampler');
  // TODO: Добавить OfflineAudioContext для resample 48000→16000
}
```

### Вариант 2: Увеличить чувствительность микрофона

```typescript
// Добавить gain node для усиления сигнала
const gainNode = audioContext.createGain();
gainNode.gain.value = 2.0; // Увеличить громкость в 2 раза

source.connect(gainNode);
gainNode.connect(processor);
```

### Вариант 3: Попробовать другую модель

Скачать более качественную модель:
```bash
# vosk-model-en-us-0.22 (1.8GB) - лучшее качество
curl -LO https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip
```

### Вариант 4: Переход на AudioWorklet (вместо ScriptProcessorNode)

ScriptProcessorNode deprecated, AudioWorklet более современный:
```typescript
// Создать worklet processor
await audioContext.audioWorklet.addModule('/vosk-processor.js');
const workletNode = new AudioWorkletNode(audioContext, 'vosk-processor');
```

---

## Полезные ссылки

- **Vosk Browser docs**: https://www.npmjs.com/package/vosk-browser
- **Vosk models**: https://alphacephei.com/vosk/models
- **Issue tracker**: https://github.com/ccoreilly/vosk-browser/issues
- **Web Audio API**: https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API

---

## Контекст для Claude (на новом компьютере)

**Промпт для продолжения работы:**

> Я работаю над интеграцией Vosk STT в браузерное приложение. WebSocket работает, модель загружается, микрофон захватывается, но Vosk возвращает пустые результаты распознавания (`partial: ''`, `text: ''`).
>
> Прочитай файл `PROGRESS_VOSK_INTEGRATION.md` в корне проекта - там полный контекст проблемы.
>
> Текущие логи показывают:
> - AudioContext: 16000Hz
> - Max amplitude: [проверь значение - должно быть > 0.01]
> - Buffer SR: [проверь - должно быть 16000Hz]
>
> Нужно исправить проблему с пустыми результатами распознавания. Начни с проверки sample rate mismatch.

**Важные файлы для анализа:**
1. `frontend/src/hooks/useVosk.ts` - основная логика
2. `frontend/src/components/VoiceChat.tsx` - интеграция
3. Логи браузера (Console)

**Критические изменения в бэкенде (уже сделаны):**
- `app/api/voice.py:62` - используем `user.username` вместо `user.channel_id`
- `app/services/memory_and_interests.py:107` - используем `kind.value` для PostgreSQL enum
- `db/migrations/postgres/008_extend_memory_kind.sql` - новая миграция для ERROR_PATTERN

---

## Версии зависимостей

**Frontend:**
- React 18.3.1
- TypeScript 5.6.2
- vosk-browser 0.0.8
- vite 6.0.3

**Backend:**
- Python 3.12.10
- FastAPI 0.115.6
- SQLAlchemy 2.0.36
- asyncpg 0.30.0
- edge-tts 6.1.18

**Инфраструктура:**
- PostgreSQL 15
- Docker 24.x
- Node.js 18+

---

## Известные ограничения

1. **ScriptProcessorNode deprecated** - работает, но браузер показывает warning
2. **Sample rate constraints** - браузеры могут игнорировать запрошенный SR
3. **CORS** - модель должна быть на том же домене (используем `/public/`)
4. **HTTPS required** - микрофон работает только на localhost или https://

---

**Последнее обновление**: 2025-12-30 12:30 UTC+3
**Автор**: Claude Sonnet 4.5 via Claude Code
