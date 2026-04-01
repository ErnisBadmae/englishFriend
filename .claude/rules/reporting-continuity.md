---
description: Single-file reporting and continuity rule for active product work
last_updated: 2026-04-01
---

# Reporting Continuity Rule

Use one canonical file for active product continuity:

- `!DOC/operations/CURRENT_PRODUCT_STATE.md`

## Required behavior

- After a significant implementation or product decision, update that file.
- Keep updates short and operational.
- Do not create a new session log if the current-state file is enough.
- Do not duplicate the same report in multiple docs.

## Update format

Only touch these sections:

- `Current Wedge`
- `Golden Path`
- `What Works Now`
- `Known Issues`
- `Next Step`
- `Last Update`

## Style

- 3-7 bullets per update block
- current state only
- no long narratives
- no speculative essays
- make it easy for the next agent to resume work in under 2 minutes

## Legacy docs

- `!DOC/CLAUDE_SESSION_LOG.md` is legacy history
- use it only if older historical context is required
- do not keep appending normal progress there
