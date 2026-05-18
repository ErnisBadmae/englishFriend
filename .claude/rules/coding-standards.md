---
description: Global coding standards for English Friend
last_updated: 2026-05-05
---

# Coding Standards

Keep this file global and short. Put subsystem-specific guidance into scoped rule files.

## Baseline

- Python 3.12+ syntax only
- Black formatting, `isort`, and strict type hints where the codebase already expects them
- Use `logger`, never `print()`
- Prefer async-safe code paths in backend/runtime modules
- Keep service and routing behavior explicit; avoid hidden fallback branches

## Change Style

- Make the smallest product-coherent change that solves the task
- Reuse existing helpers and services before adding new abstractions
- Add or update targeted tests when changing routing, onboarding, persistence, snapshot, or session behavior
- Keep docs and continuity files short and current
