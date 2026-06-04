"""Guard test: the AgentState schema must describe every key the agent writes.

AgentState is ``total=False``, so writing an undeclared key never fails at
runtime — the schema can silently drift away from reality (this is exactly how
the fallback/telemetry keys ended up undeclared). This test scans the agent
layer for ``state["..."] = ...`` assignments and asserts each key is declared,
keeping the type the single source of truth for what the state holds.
"""

import re
from pathlib import Path

from app.agent.state import AgentState

_AGENT_DIR = Path(__file__).resolve().parent.parent / "app" / "agent"
# Match `state["key"] =` assignments but not comparisons (`==`).
_ASSIGN_RE = re.compile(r'\bstate\["([a-zA-Z_][a-zA-Z0-9_]*)"\]\s*=(?!=)')


def test_all_agent_state_writes_are_declared():
    declared = set(AgentState.__annotations__)
    offenders: dict[str, set[str]] = {}

    for path in _AGENT_DIR.rglob("*.py"):
        for key in _ASSIGN_RE.findall(path.read_text(encoding="utf-8")):
            if key not in declared:
                offenders.setdefault(str(path.relative_to(_AGENT_DIR)), set()).add(key)

    assert not offenders, (
        "AgentState keys written but not declared in app/agent/state.py "
        f"(add them to the TypedDict): {offenders}"
    )
