# Quick Start Guide - Mac Setup

Этот файл содержит все команды для быстрого старта проекта на новом Mac после клонирования репозитория.

## Статус проекта

**90% -> 95% готовности** - Исправлена критическая проблема с Vosk STT (sample rate mismatch)

## Что было сделано

### Setup (выполнено)
- ✅ Установлен Python 3.12.12 через Homebrew
- ✅ Установлен Node.js 20.19.6 через Homebrew
- ✅ Запущен Colima (Docker runtime для Mac)
- ✅ Создан Python venv и установлены зависимости
- ✅ Установлены frontend зависимости (npm)
- ✅ Скачана Vosk модель (39MB)
- ✅ Запущен PostgreSQL через Docker Compose

### Исправлена проблема с Vosk STT
**Проблема**: Vosk возвращал пустые результаты распознавания (`partial: ''`, `text: ''`)

**Причина**: Sample rate mismatch - браузер использовал 48000Hz, а Vosk ожидал 16000Hz

**Решение**: Добавлен audio resampling в `frontend/src/hooks/useVosk.ts`
- Recognizer теперь всегда создается с 16000Hz (не с audioContext.sampleRate)
- Добавлена функция `resampleAudio()` с linear interpolation
- Если браузер использует 48000Hz, аудио автоматически ресэмплируется в 16000Hz перед отправкой в Vosk

## Команды для запуска

### 1. Установка зависимостей (если еще не установлено)

```bash
# Homebrew (если не установлен)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Python 3.12
brew install python@3.12

# Node.js 20
brew install node@20
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"
echo 'export PATH="/opt/homebrew/opt/node@20/bin:$PATH"' >> ~/.zshrc

# Colima (Docker для Mac)
brew install colima
colima start --cpu 4 --memory 8
```

### 2. Backend setup

```bash
# Создать venv
/opt/homebrew/bin/python3.12 -m venv venv

# Активировать venv
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt
```

### 3. Frontend setup

```bash
cd frontend
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"
npm install
cd ..
```

### 4. Vosk модель

Модель уже скачана в `frontend/public/vosk-model-small-en-us-0.15.zip` (39MB).

Если нужно скачать заново:
```bash
cd frontend/public
curl -LO https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
cd ../..
```

### 5. Запуск инфраструктуры

```bash
# PostgreSQL
docker-compose up -d postgres

# Проверить что PostgreSQL запущен
docker ps | grep postgres
```

### 6. Запуск приложения

**Terminal 1 - Backend:**
```bash
source venv/bin/activate
python main.py
# Слушает на http://localhost:8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"
npm run dev
# Слушает на http://localhost:5173
```

### 7. Тестирование Vosk

1. Открыть http://localhost:5173 в браузере
2. Открыть DevTools (Cmd+Opt+I) → Console
3. Разрешить доступ к микрофону
4. Начать запись и говорить на английском

**Что проверить в логах браузера:**
```
[Vosk] AudioContext created. Requested: 16000Hz, Actual: 48000Hz  ← ожидаем 48000Hz
[Vosk] KaldiRecognizer created with sample rate: 16000Hz          ← всегда 16000Hz
[Vosk] Processed 50 chunks | Max amplitude: 0.XXXX | Input SR: 48000Hz -> Vosk SR: 16000Hz
[Vosk] Partial result: {partial: 'hello world', ...}              ← должен быть текст!
```

**Ключевые метрики:**
- `Max amplitude` должна быть > 0.01 при громкой речи
- `Input SR: 48000Hz -> Vosk SR: 16000Hz` - resampling работает
- `partial` должна содержать распознанный текст (не пустая строка)

## Troubleshooting

### Node.js версия не та
```bash
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"
node --version  # должно быть v20.19.6
```

### Docker не работает
```bash
# Проверить Colima
colima status

# Перезапустить
colima stop
colima start --cpu 4 --memory 8
```

### npm install ошибка SSL
```bash
cd frontend
npm config set strict-ssl false
npm install
npm config set strict-ssl true
```

### Vosk все еще возвращает пустые результаты
1. Проверить логи в Console - есть ли resampling?
2. Проверить `Max amplitude` - если близко к 0, проблема с микрофоном
3. Попробовать другую модель:
```bash
cd frontend/public
# Скачать более качественную модель (1.8GB)
curl -LO https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip
# Обновить modelUrl в useVosk.ts
```

## Следующие шаги

1. ✅ Протестировать Vosk распознавание в браузере
2. Проверить интеграцию с WebSocket backend
3. Тестировать полный flow: Vosk → WebSocket → vLLM/Groq → edge-tts → Audio playback
4. (Опционально) Перейти на AudioWorklet вместо deprecated ScriptProcessorNode

## Полезные ссылки

- **Vosk Browser docs**: https://www.npmjs.com/package/vosk-browser
- **Vosk models**: https://alphacephei.com/vosk/models
- **Web Audio API**: https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API
- **Progress file**: PROGRESS_VOSK_INTEGRATION.md

---

**Последнее обновление**: 2026-01-02 03:00 UTC+3
**Автор**: Claude Sonnet 4.5 via Claude Code
