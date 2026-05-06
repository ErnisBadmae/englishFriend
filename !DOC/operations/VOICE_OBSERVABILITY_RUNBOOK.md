# Voice Observability Runbook

Last updated: 2026-05-06
Scope: instrumented live smoke for `/api/v1/voice/chat/v2` and `/api/v1/voice/realtime`

## Purpose

Используй этот runbook, когда нужен один повторяемый способ разбирать live voice behavior через:

- browser STT / composer input
- websocket flow
- agent и pedagogy routing
- LLM compatibility / fallback behavior
- memory bootstrap and save
- post-session persistence

Нужна одна коррелированная картина по:

- `session_id`
- `turn_id`
- `runtime`

Operator replay artifact:

- `venv\Scripts\python.exe scripts/replay_session.py --session-id <uuid>`

## What Exists Now

Backend уже пишет structured voice events с:

- `runtime`
- `session_id`
- `turn_id`
- `turn_index`
- `phase`
- `mode`
- `mission_task_type`

Frontend dev mode уже показывает debug panel с:

- session metadata
- normalized client-side event list
- copy/download JSON export

## Capture Checklist

Для каждого live run собирай все 4 артефакта:

1. Frontend debug export JSON из dev panel.
2. Backend logs, отфильтрованные по `session_id`.
3. `/metrics` snapshot до и после run.
4. Replay bundle из `scripts/replay_session.py`.

Если одного из 4 артефактов нет, run не считается полностью instrumented.

## Replay Workflow

Минимальная команда:

`venv\Scripts\python.exe scripts/replay_session.py --session-id <uuid>`

Опционально можно сохранить bundle в файл:

`venv\Scripts\python.exe scripts/replay_session.py --session-id <uuid> --output replay.json`

Replay bundle должен включать:

- session metadata
- transcript по utterances
- corrections
- feedback
- matching `roadmap_session_evidence`
- `snapshot_excerpt`
- trace note для дальнейшей корреляции логов

Любой pilot debrief должен ссылаться на конкретный `session_id` и прилагать replay bundle.

## Smoke Set

### 1. First-run setup

Цель:

- проверить `goal -> first useful mission -> session_complete -> return home`

Успех:

- нет пустого assistant turn
- reasoning text не утек пользователю
- setup session завершается чисто
- Home показывает next mission после handoff

### 2. Noisy foundation

Цель:

- проверить low-signal handling и mission anchoring

Успех:

- нет topic drift
- noisy input не превращается в hallucinated topic
- coach просит shorter answer или recovery через composer
- session остается внутри mission anchors

### 3. Clean foundation

Цель:

- проверить нормальный guided loop на clean input

Успех:

- короткие guided follow-ups
- корректное завершение session
- evidence и persistence остаются целыми

## What To Inspect By Layer

### Frontend

Смотри:

- `model_loading_started` / `model_loaded`
- `listening_started` / `listening_stopped`
- `transcript_partial` / `transcript_accumulated`
- `silence_detected`
- `ws_connecting` / `ws_connected_payload`
- `ws_text_sent`
- `ws_transcript`
- `ws_audio`
- `ws_session_complete`

Вопросы:

- Браузер действительно захватил нужный текст?
- Клиент отправил его как `browser_vosk` или `composer`?
- WebSocket неожиданно переподключился или закрылся?

### Backend bootstrap and memory

Смотри:

- `session_bootstrap_started`
- `session_bootstrap_ready`
- `memory_context_loaded`
- `agent_session_ready`

Вопросы:

- Загрузился правильный `mission_task_type`?
- Был ли learner profile?
- Runtime стартовал как `chat_v2` или `realtime`?

### Turn processing

Смотри:

- `turn_received`
- `stt_completed`
- `agent_turn_completed`
- `tts_completed` или `tts_failed`

Вопросы:

- Какой `turn_id` сломался?
- Проблема в transcript quality, pedagogy или TTS?
- `phase` или `mode` сдвинулись неожиданно?

### Persistence

Смотри:

- `persistence_started`
- `memory_saved`
- `persistence_completed`
- `session_completed`
- `session_disconnected`

Вопросы:

- Persistence отработал один раз или два?
- Setup handoff случился корректно?
- Session сохранил evidence и memory безопасно?

## Metrics To Snapshot

Минимальный набор:

- `voice_stage_latency_seconds`
- `voice_turn_events_total`
- `voice_persistence_total`
- `voice_turn_total_seconds`
- `voice_tts_latency_seconds`
- `voice_errors_total`
- `llm_response_anomalies_total`

Для comparison runs храни:

- raw `/metrics` text
- короткую человеческую заметку со сценарием и `session_id`

## Triage Rules

Если проблема такая:

- неверный transcript с самого начала: сначала смотри frontend STT и source tag
- transcript верный, но follow-up неправильный: смотри `agent_turn_completed`
- пустой или silent assistant turn: смотри `llm_response_anomalies_total` и LLM logs
- turn хороший, но state сохранился неверно: смотри `persistence_*` и `memory_saved`
- есть drift между Home и live mission: смотри mission contract во время bootstrap

## Non-Goals

Этот runbook пока не покрывает:

- PersonaPlex premium path
- `/chat-legacy`
- server-side storage of frontend debug events
- full production tracing UX

После того как run полностью собран по этому runbook, можно переходить к:

- [STT_BENCHMARK_RUNBOOK.md](./STT_BENCHMARK_RUNBOOK.md)
