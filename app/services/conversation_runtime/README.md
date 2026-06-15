# Conversation Runtime — Local Architecture

## Summary
Transport-neutral session loop: receives normalized client events, runs agent
turns (`graph_v2.run_agent_turn_v2`), emits transcript/feedback/completion
events. Text-first; audio (TTS) is opt-in via the explicit `text_only` flag.
Formerly `voice_runtime` — renamed because the loop is not voice-specific.

## Responsibilities (exactly three)

1. Receive user input through a `TransportAdapter`.
2. Call the agent with server-owned context (bootstrap via
   `voice_session.SessionBootstrapService`).
3. Emit events; persist on completion/disconnect
   (`voice_session.SessionPersistenceService`).

It must NOT own: mission selection, career state transitions, evidence rules.
Those live in `app/services/` (see global map).

## Pieces

| File | Role |
| --- | --- |
| `controller.py` | `ConversationController` — the session loop |
| `base.py` | ports: `TransportAdapter`, `STTProvider`, `TTSProvider`, `TurnDetector`; dataclasses `ControllerOutcome`, `RuntimeResult` |
| `transport.py` | `WebSocketTransport` |
| `stt.py` | `PassthroughTextSTTProvider` (text/composer), `ParakeetSTTProvider` (backend audio) |
| `tts.py` | `EdgeTTSTTSProvider` |
| `turn_detection.py` | `ExplicitMessageTurnDetector` (commit/end/ignore) |

## Modality Contract

- The API boundary (`app/api/voice.py`) translates the client's
  `stt_provider` label into `text_only` (composer ⇒ `text_only=True`).
- The controller never inspects provider names to decide whether to speak;
  it acts only on `text_only`. When `text_only`, TTS is skipped entirely.

## Entry Points

- `WS /api/v1/voice/chat/v2` — mainline (composer/text-first today)
- `WS /api/v1/voice/realtime` — feature-flagged (`REALTIME_RUNTIME_ENABLED`)

## Testing

```bash
pytest tests/test_conversation_runtime.py -q
```

## Related Documentation

- **Implements**: [!DOC/ARCHITECTURE.md](../../../!DOC/ARCHITECTURE.md) — layer boundaries
- **Depends-On**: [app/agent/README.md](../../agent/README.md) — the engine this loop drives
- **Related-To**: `app/services/voice_session/` — bootstrap/persistence services
- **Related-To**: `app/services/voice_observability.py` — event envelopes/logging

## Last Updated
2026-06-12: created with the voice_runtime → conversation_runtime rename
(explicit `text_only` modality, neutral controller naming).
