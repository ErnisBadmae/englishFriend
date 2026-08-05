"""Owner-triggered vacancy refresh: runs the telegram-digest fetch/triage/export
pipeline as a subprocess, then imports the resulting export into this owner's
Career Inbox (career/CAREER_TELEGRAM_COCKPIT_SPEC.md Slice B).

Button trigger only - never a scheduler (see telegram-digest/CLAUDE.md: "no
schedulers without a separate accepted decision"). Two separate repos/venvs,
so both steps run as subprocesses rather than in-process imports.
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
IMPORT_SCRIPT = REPO_ROOT / "scripts" / "import_career_inbox.py"
PYTHON = REPO_ROOT / "venv" / "Scripts" / "python.exe"

REFRESH_TIMEOUT_SECONDS = 900
IMPORT_TIMEOUT_SECONDS = 60
OUTPUT_TAIL_LINES = 15
CHANNELS_CONFIG_FILENAME = "vacancy_telegram_channels.json"
SOURCE_ENTRY_MAX_LEN = 64
RESOLVE_NAMES_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class RefreshResult:
    ok: bool
    message: str


async def _run_subprocess(
    args: list[str], *, cwd: Path, timeout: float, env: Optional[dict[str, str]] = None
) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 1, "timed out"
    return proc.returncode, stdout.decode("utf-8", errors="replace")


def _tail(output: str) -> str:
    lines = output.strip().splitlines()
    return "\n".join(lines[-OUTPUT_TAIL_LINES:])


async def refresh_vacancies(*, digest_repo_path: str, telegram_id: int) -> RefreshResult:
    if not digest_repo_path:
        return RefreshResult(False, "vacancy_refresh_repo_path is not configured")
    digest_repo = Path(digest_repo_path)
    digest_python = digest_repo / "venv" / "Scripts" / "python.exe"
    if not digest_python.exists():
        return RefreshResult(False, f"telegram-digest venv not found at {digest_python}")

    returncode, output = await _run_subprocess(
        [str(digest_python), "refresh_vacancies.py"],
        cwd=digest_repo,
        timeout=REFRESH_TIMEOUT_SECONDS,
    )
    if returncode != 0:
        return RefreshResult(False, f"Парсер вакансий упал:\n{_tail(output)}")

    export_file = digest_repo / "data" / "career_inbox_export.jsonl"
    if not export_file.exists():
        return RefreshResult(False, "Файл экспорта не был создан")

    import_env = dict(os.environ)
    import_env["PYTHONPATH"] = str(REPO_ROOT)
    returncode, output = await _run_subprocess(
        [
            str(PYTHON),
            str(IMPORT_SCRIPT),
            "--file",
            str(export_file),
            "--telegram-id",
            str(telegram_id),
        ],
        cwd=REPO_ROOT,
        timeout=IMPORT_TIMEOUT_SECONDS,
        env=import_env,
    )
    if returncode != 0:
        return RefreshResult(False, f"Импорт в инбокс упал:\n{_tail(output)}")

    last_line = output.strip().splitlines()[-1] if output.strip() else "Готово"
    return RefreshResult(True, last_line)


def _channels_config_path(digest_repo_path: str) -> Path:
    return Path(digest_repo_path) / CHANNELS_CONFIG_FILENAME


def list_vacancy_channels(digest_repo_path: str) -> list[str]:
    """Read-only: current whitelist entries from telegram-digest's channel
    config, as display strings. Just reads the JSON file - no network call,
    no membership/liveness check."""
    if not digest_repo_path:
        return []
    path = _channels_config_path(digest_repo_path)
    if not path.exists():
        return []
    cfg = json.loads(path.read_text(encoding="utf-8"))
    return [str(c) for c in cfg.get("channels", [])]


def add_vacancy_channel(digest_repo_path: str, entry: str) -> tuple[bool, str]:
    """Append one channel (chat_id or @username) to telegram-digest's
    whitelist config. Deliberately no liveness/membership check here - the
    owner confirms the source themselves on the next manual fetch run."""
    if not digest_repo_path:
        return False, "vacancy_refresh_repo_path не настроен"
    path = _channels_config_path(digest_repo_path)
    if not path.exists():
        return False, f"конфиг не найден: {path}"

    cfg = json.loads(path.read_text(encoding="utf-8"))
    channels = cfg.get("channels", [])
    if entry.lstrip("-").isdigit():
        value: object = int(entry)
    else:
        # existing entries are always stored with a leading "@" - match that.
        value = entry if entry.startswith("@") else f"@{entry}"
    if value in channels:
        return False, f"{value} уже есть в списке"

    channels.append(value)
    cfg["channels"] = channels
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True, str(value)


async def resolve_vacancy_channel_names(digest_repo_path: str) -> dict[str, str]:
    """Live lookup (via telegram-digest's userbot session) of a display name
    per configured channel - only for entries already in the whitelist, not
    the owner's full dialog list. Best-effort: any failure (session not
    logged in, timeout, missing venv) returns an empty mapping and the
    caller falls back to showing the raw channel value."""
    if not digest_repo_path:
        return {}
    digest_repo = Path(digest_repo_path)
    digest_python = digest_repo / "venv" / "Scripts" / "python.exe"
    if not digest_python.exists():
        return {}

    returncode, output = await _run_subprocess(
        [
            str(digest_python),
            "fetch_telegram_channels.py",
            "--config",
            CHANNELS_CONFIG_FILENAME,
            "--resolve-names",
        ],
        cwd=digest_repo,
        timeout=RESOLVE_NAMES_TIMEOUT_SECONDS,
    )
    if returncode != 0:
        return {}

    names: dict[str, str] = {}
    for line in output.splitlines():
        channel, _, name = line.partition("\t")
        if name:
            names[channel.strip()] = name.strip()
    return names
