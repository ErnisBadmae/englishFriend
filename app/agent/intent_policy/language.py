"""Lightweight language hint helpers — no LLM, no external deps."""

from __future__ import annotations

import re

_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
_LETTER_RE = re.compile(r"[A-Za-zА-Яа-яЁё]")


def is_russian(text: str | None, threshold: float = 0.3) -> bool:
    """True when кириллица занимает ≥ threshold от всех букв."""
    if not text:
        return False
    letters = _LETTER_RE.findall(text)
    if not letters:
        return False
    cyrillic = _CYRILLIC_RE.findall(text)
    return (len(cyrillic) / len(letters)) >= threshold
