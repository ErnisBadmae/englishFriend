# Voice Observability Runbook

Last updated: 2026-04-09
Scope: instrumented live smoke for `/api/v1/voice/chat/v2` and `/api/v1/voice/realtime`

## Purpose

Use this runbook when you need one repeatable way to debug live voice behavior across:

- browser STT / composer input
- websocket flow
- agent and pedagogy routing
- LLM compatibility / fallback behavior
- memory bootstrap and save
- post-session persistence

The target is one correlated view by:

- `session_id`
- `turn_id`
- `runtime`

## What Exists Now

Backend now emits structured voice events with:

- `runtime`
- `session_id`
- `turn_id`
- `turn_index`
- `phase`
- `mode`
- `mission_task_type`

Frontend dev mode now exposes a debug panel with:

- session metadata
- normalized client-side event list
- copy/download JSON export

## Capture Checklist

For every live run, collect all 3 artifacts:

1. Frontend debug export JSON from the dev panel.
2. Backend logs filtered by `session_id`.
3. `/metrics` snapshot before and after the run.

If one of the 3 is missing, the run is not considered fully instrumented.

## Smoke Set

### 1. First-run setup

Goal:

- validate `goal -> first useful mission -> session_complete -> return home`

Success:

- no empty assistant turn
- no reasoning text leaked to the user
- setup session ends cleanly
- Home shows the next mission after handoff

### 2. Noisy foundation

Goal:

- validate low-signal handling and mission anchoring

Success:

- no topic drift
- noisy input does not become a hallucinated topic
- coach asks for shorter answer or composer recovery
- session stays inside mission anchors

### 3. Clean foundation

Goal:

- validate the normal guided loop with clean speech

Success:

- short guided follow-ups
- correct session completion
- evidence and persistence remain intact

## What To Inspect By Layer

### Frontend

Look for:

- `model_loading_started` / `model_loaded`
- `listening_started` / `listening_stopped`
- `transcript_partial` / `transcript_accumulated`
- `silence_detected`
- `ws_connecting` / `ws_connected_payload`
- `ws_text_sent`
- `ws_transcript`
- `ws_audio`
- `ws_session_complete`

Questions:

- Did the browser capture the intended text?
- Did the client send it as `browser_vosk` or `composer`?
- Did the websocket reconnect or close unexpectedly?

### Backend bootstrap and memory

Look for:

- `session_bootstrap_started`
- `session_bootstrap_ready`
- `memory_context_loaded`
- `agent_session_ready`

Questions:

- Was the right `mission_task_type` loaded?
- Was learner profile present?
- Did the runtime start as `chat_v2` or `realtime`?

### Turn processing

Look for:

- `turn_received`
- `stt_completed`
- `agent_turn_completed`
- `tts_completed` or `tts_failed`

Questions:

- Which `turn_id` failed?
- Was the issue in transcript quality, pedagogy, or TTS?
- Did `phase` or `mode` shift unexpectedly?

### Persistence

Look for:

- `persistence_started`
- `memory_saved`
- `persistence_completed`
- `session_completed`
- `session_disconnected`

Questions:

- Was persistence run once or twice?
- Did setup handoff happen?
- Did the session save evidence and memory safely?

## Metrics To Snapshot

Minimum metrics to inspect:

- `voice_stage_latency_seconds`
- `voice_turn_events_total`
- `voice_persistence_total`
- `voice_turn_total_seconds`
- `voice_tts_latency_seconds`
- `voice_errors_total`
- `llm_response_anomalies_total`

For comparison runs, keep both:

- raw `/metrics` text
- a short human note with the scenario and `session_id`

## Triage Rules

If the problem is:

- wrong transcript from the start: inspect frontend STT and source tag first
- correct transcript but wrong question/follow-up: inspect `agent_turn_completed`
- empty or silent assistant turn: inspect `llm_response_anomalies_total` and LLM logs
- good turn but wrong saved state: inspect `persistence_*` and `memory_saved`
- drift between Home and live mission: inspect mission contract in bootstrap

## Non-Goals

This runbook does not yet cover:

- PersonaPlex premium path
- `/chat-legacy`
- server-side storage of frontend debug events
- full production tracing UX

After a run is fully captured here, move to:

- [STT_BENCHMARK_RUNBOOK.md](./STT_BENCHMARK_RUNBOOK.md)
