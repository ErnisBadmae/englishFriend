---
description: Canonical local/team LLM truth-state for English Friend
last_updated: 2026-04-22
---

# Local LLM Truth-State

Use this as the canonical Claude Code rule for mainline local/team LLM work.

## Mainline defaults

- `LLM_PROVIDER=vllm`
- `VLLM_BASE_URL=http://192.168.0.18:8000/v1`
- `VLLM_API_KEY=token-abc123`

## Required behavior

- Treat the LAN-hosted Qwen/vLLM endpoint above as the default text inference backend for mainline product work.
- Before live product validation, run `venv\Scripts\python.exe scripts/test_voice_backend.py`.
- Do not silently switch active docs or tests back to stale hosts such as `192.168.0.27` or `192.168.0.88`.

## If the endpoint changes

Update all active sources of truth together:

- `.env`
- `.env.example`
- `CLAUDE.md`
- `QUICK_START.md`
- `!DOC/operations/CURRENT_PRODUCT_STATE.md`
- `tests/test_config.py`
- `tests/test_llm_provider.py`
