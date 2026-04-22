"""Markdown-backed internal skill registry.

This is an internal control plane for the coach. It is not a user-facing plugin
system and it is not a second source of truth for product state.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillManifest:
    """Parsed internal skill manifest."""

    id: str
    title: str
    description: str
    kind: str
    trigger_modes: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    instructions: str = ""
    greeting_template: Optional[str] = None
    path: Optional[Path] = None


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse a very small YAML-frontmatter subset.

    Supported:
    - scalar values: ``key: value``
    - block lists:
      key:
        - item
        - item
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break
    if end_index is None:
        return {}, text

    metadata: dict[str, Any] = {}
    current_list_key: Optional[str] = None
    for line in lines[1:end_index]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            if current_list_key:
                metadata.setdefault(current_list_key, []).append(_strip_quotes(stripped[2:].strip()))
            continue
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value:
            metadata[key] = _strip_quotes(value)
            current_list_key = None
        else:
            metadata[key] = []
            current_list_key = key

    body = "\n".join(lines[end_index + 1:]).strip()
    return metadata, body


def render_skill_template(template: Optional[str], context: dict[str, Any]) -> Optional[str]:
    """Render ``{{variable}}`` placeholders without using Python format()."""
    if not template:
        return None

    rendered = template
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value or ""))
    return rendered


def render_skill_instructions(skill: SkillManifest, context: dict[str, Any]) -> str:
    """Render a loaded skill body with the supplied context."""
    return render_skill_template(skill.instructions, context) or ""


class SkillRegistry:
    """Load internal markdown skills from ``app/skills``."""

    def __init__(self, base_path: Optional[Path] = None) -> None:
        self.base_path = base_path or Path(__file__).resolve().parents[2] / "skills"
        self._skills: Optional[dict[str, SkillManifest]] = None

    def _load_skill(self, path: Path) -> Optional[SkillManifest]:
        try:
            raw_text = path.read_text(encoding="utf-8")
            metadata, body = _parse_frontmatter(raw_text)
            skill_id = metadata.get("id") or path.parent.name
            title = metadata.get("title") or skill_id.replace("_", " ").title()
            description = metadata.get("description", "")
            kind = metadata.get("kind", "career_loop_skill")
            trigger_modes = tuple(metadata.get("trigger_modes", []))
            inputs = tuple(metadata.get("inputs", []))
            outputs = tuple(metadata.get("outputs", []))
            greeting_template = metadata.get("greeting_template") or None
            return SkillManifest(
                id=skill_id,
                title=title,
                description=description,
                kind=kind,
                trigger_modes=trigger_modes,
                inputs=inputs,
                outputs=outputs,
                instructions=body,
                greeting_template=greeting_template,
                path=path,
            )
        except Exception as exc:
            logger.warning("Failed to load internal skill from %s: %s", path, exc)
            return None

    def load_all(self) -> dict[str, SkillManifest]:
        if self._skills is not None:
            return self._skills

        skills: dict[str, SkillManifest] = {}
        if not self.base_path.exists():
            logger.info("Internal skills directory does not exist: %s", self.base_path)
            self._skills = skills
            return skills

        for path in sorted(self.base_path.glob("*/SKILL.md")):
            skill = self._load_skill(path)
            if skill:
                skills[skill.id] = skill

        self._skills = skills
        return skills

    def get(self, skill_id: str) -> Optional[SkillManifest]:
        return self.load_all().get(skill_id)

    def get_for_mode(self, mode: str) -> Optional[SkillManifest]:
        for skill in self.load_all().values():
            if mode in skill.trigger_modes:
                return skill
        return None

    def list(self) -> tuple[SkillManifest, ...]:
        return tuple(self.load_all().values())


@lru_cache(maxsize=1)
def get_skill_registry() -> SkillRegistry:
    return SkillRegistry()
