#!/usr/bin/env python3
"""Обслуживание документации !DOC/: audit / archive / report.

Единственный скрипт обслуживания документации (заменил archive_session_logs.py).
Канонический источник — репозиторий expert-agent; в другие репозитории копируется
как есть, сверка версий по VERSION ниже.

Режимы:
  audit   — отчёт о состоянии документации (человекочитаемый)
  archive — архивация старых записей SESSION_LOG.md по ISO-неделям
  report  — audit в JSON для CI / night runner

Настройка: секция [tool.docs-maintenance] в pyproject.toml (читается на Python 3.11+),
поверх неё env-переменные DM_* (работают на любом Python 3.10+). Без конфига
действуют дефолты под layout `!DOC/operations/`.

Правила — !DOC/DOC_GUIDELINES.md.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

VERSION = "1.2 (2026-07-03)"

# Windows-консоль/пайпы часто не utf-8 — иначе кириллица в логах превращается в кракозябры
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# Автогенерируемые каталоги — не документация, audit их не трогает
GENERATED_DIRS = {"graphify-out"}

DEFAULTS: dict = {
    "doc_dir": "!DOC",
    "session_log": "!DOC/operations/SESSION_LOG.md",
    "archive_dir": "!DOC/operations/archive",
    "keep_last": 10,
    "keep_days": 7,
    "max_file_lines": 300,
    "max_archive_files": 50,
    "max_nav_depth": 4,
    "tier0_files": [],
    "context_budget_lines": 2000,
}

# Заголовок записи: "## 2026-07-01 - Title" или "## 2026-07-01 — Title" (оба разделителя в ходу)
ENTRY_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*[-—]\s*(.+?)\s*$", re.MULTILINE)
# Служебные секции в хвосте SESSION_LOG — не записи, при парсинге отрезаются
TAIL_MARKERS = ("\n## [Следующая сессия]", "\n## Архив")


@dataclass
class Cfg:
    root: Path
    doc_dir: Path
    session_log: Path
    archive_dir: Path
    keep_last: int
    keep_days: int
    max_file_lines: int
    max_archive_files: int
    max_nav_depth: int
    tier0_files: list[Path] = field(default_factory=list)
    context_budget_lines: int = 2000


def load_cfg(root: Path) -> Cfg:
    raw = dict(DEFAULTS)

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib

            section = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            raw.update(section.get("tool", {}).get("docs-maintenance", {}))
        except ImportError:  # Python < 3.11 — работаем на env/defaults
            log("WARN", "tomllib недоступен (Python < 3.11) — pyproject-конфиг пропущен")
        except (OSError, ValueError) as e:
            log("WARN", f"pyproject.toml не прочитан: {e}")

    for key in ("keep_last", "keep_days", "max_file_lines", "max_archive_files", "max_nav_depth"):
        env = os.environ.get(f"DM_{key.upper()}")
        if env:
            raw[key] = int(env)

    return Cfg(
        root=root,
        doc_dir=root / raw["doc_dir"],
        session_log=root / raw["session_log"],
        archive_dir=root / raw["archive_dir"],
        keep_last=int(raw["keep_last"]),
        keep_days=int(raw["keep_days"]),
        max_file_lines=int(raw["max_file_lines"]),
        max_archive_files=int(raw["max_archive_files"]),
        max_nav_depth=int(raw["max_nav_depth"]),
        tier0_files=[root / f for f in raw["tier0_files"]],
        context_budget_lines=int(raw["context_budget_lines"]),
    )


def log(level: str, msg: str) -> None:
    prefix = {
        "OK": "\033[32m[OK]\033[0m",
        "WARN": "\033[33m[WARN]\033[0m",
        "ERR": "\033[31m[ERR]\033[0m",
        "INFO": "\033[36m[INFO]\033[0m",
    }.get(level, f"[{level}]")
    # диагностика в stderr: stdout остаётся чистым для JSON (режим report)
    print(f"{prefix} {msg}", file=sys.stderr)


def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


def count_lines(path: Path) -> int:
    content = read_file(path)
    return len(content.splitlines()) if content else 0


def get_iso_week(date_str: str) -> str:
    iso = datetime.strptime(date_str, "%Y-%m-%d").isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


# ─── audit ───────────────────────────────────────────────────────────────────


def audit(cfg: Cfg) -> dict:
    if not cfg.doc_dir.exists():
        log("WARN", f"{cfg.doc_dir} не найден — нечего проверять")
        return {"error": "no doc dir"}

    report: dict = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "version": VERSION,
        "stats": {},
        "issues": [],
    }
    issues: list[dict] = report["issues"]

    total_files = 0
    total_lines = 0
    oversized: list[dict] = []
    deep_dirs: set[str] = set()

    # --- doc_dir scan ---
    if cfg.doc_dir.exists():
        for fp in sorted(cfg.doc_dir.rglob("*")):
            if not fp.is_file() or fp.suffix in (".pyc", ".cache"):
                continue
            rel = fp.relative_to(cfg.doc_dir)
            if GENERATED_DIRS.intersection(rel.parts):
                continue
            in_archive = "archive" in rel.parts

            total_files += 1
            lines = count_lines(fp)
            total_lines += lines

            if fp.suffix == ".md" and not in_archive and lines > cfg.max_file_lines:
                oversized.append({"file": rel.as_posix(), "lines": lines})

            if len(rel.parts) - 1 > cfg.max_nav_depth:
                deep_dirs.add(rel.parent.as_posix())

    # --- archive overflow: count from archive_dir directly, not via doc_dir ---
    archive_count = 0
    if cfg.archive_dir.exists():
        archive_count = sum(1 for _ in cfg.archive_dir.glob("*.md"))

    for item in oversized:
        issues.append({"type": "oversized_file", **item, "max": cfg.max_file_lines})
    for d in sorted(deep_dirs):
        issues.append({"type": "deep_path", "dir": d, "max_depth": cfg.max_nav_depth})
    if archive_count > cfg.max_archive_files:
        issues.append(
            {
                "type": "archive_overflow",
                "count": archive_count,
                "max": cfg.max_archive_files,
                "suggestion": "слить старые архивные файлы или удалить неактуальные",
            }
        )

    # Дубликаты H1 между living-файлами
    titles: dict[str, list[str]] = {}
    for fp in cfg.doc_dir.rglob("*.md"):
        rel = fp.relative_to(cfg.doc_dir)
        if "archive" in rel.parts or GENERATED_DIRS.intersection(rel.parts):
            continue
        m = re.search(r"^#\s+(.+)", read_file(fp), re.MULTILINE)
        if m:
            titles.setdefault(m.group(1).strip(), []).append(rel.as_posix())
    for title, paths in titles.items():
        if len(paths) > 1:
            issues.append({"type": "duplicate_title", "title": title, "files": paths})

    # SESSION_LOG
    if cfg.session_log.exists():
        entries = parse_entries(read_file(cfg.session_log))
        report["session_log"] = {
            "entries": len(entries),
            "lines": count_lines(cfg.session_log),
            "newest": entries[0]["date"] if entries else None,
            "oldest": entries[-1]["date"] if entries else None,
        }
        if len(entries) > cfg.keep_last + 5:
            issues.append(
                {
                    "type": "session_log_too_long",
                    "entries": len(entries),
                    "keep": cfg.keep_last,
                    "suggestion": "python scripts/docs_maintenance.py archive",
                }
            )

    # Last updated для всех living tier-0 файлов (README, ACTIVE_TASK и т.д.)
    # SESSION_LOG не проверяем — его состояние определяется через session_log_too_long
    # Ищем и "last updated" (EN), и "обновлено" (RU)
    for fp in cfg.tier0_files:
        if not fp.exists() or not fp.suffix == ".md":
            continue
        if fp == cfg.session_log:
            continue
        content = read_file(fp)
        content_lower = content.lower()
        if "last updated" not in content_lower and "обновлено" not in content_lower:
            rel = fp.relative_to(cfg.root)
            issues.append(
                {
                    "type": "missing_last_updated",
                    "file": rel.as_posix(),
                    "suggestion": "добавить 'Last updated: YYYY-MM-DD'",
                }
            )

    # Root-level oversized для tier-0 файлов вне doc_dir (README, ACTIVE_TASK и т.д.)
    for fp in cfg.tier0_files:
        if not fp.exists() or fp.is_relative_to(cfg.doc_dir):
            continue
        rel = fp.relative_to(cfg.root)
        lines = count_lines(fp)
        if fp.suffix == ".md" and lines > cfg.max_file_lines:
            # проверяем, что ещё не добавлено через doc_dir scan
            already = any(o["file"] == rel.as_posix() for o in oversized)
            if not already:
                oversized.append({"file": rel.as_posix(), "lines": lines})

    # Контекстный бюджет: сколько строк агент обязан прочитать на старте сессии
    if cfg.tier0_files:
        budget_files = []
        budget_total = 0
        for fp in cfg.tier0_files:
            lines = count_lines(fp)
            budget_files.append({"file": fp.relative_to(cfg.root).as_posix(), "lines": lines})
            budget_total += lines
            if not fp.exists():
                issues.append(
                    {"type": "tier0_missing", "file": fp.relative_to(cfg.root).as_posix()}
                )
        report["context_budget"] = {
            "total_lines": budget_total,
            "max_lines": cfg.context_budget_lines,
            "files": budget_files,
        }
        if budget_total > cfg.context_budget_lines:
            issues.append(
                {
                    "type": "context_budget_exceeded",
                    "total_lines": budget_total,
                    "max_lines": cfg.context_budget_lines,
                    "suggestion": "ужать tier-0 файлы: детали → tier-2 документы",
                }
            )

    report["stats"] = {
        "total_files": total_files,
        "total_lines": total_lines,
        "archive_files": archive_count,
        "oversized_files": len(oversized),
    }

    log("OK", f"Audit: {total_files} файлов, {total_lines} строк, {len(issues)} issues")
    for issue in issues:
        log("WARN", json.dumps(issue, ensure_ascii=False))
    if "context_budget" in report:
        cb = report["context_budget"]
        log("INFO", f"Контекстный бюджет (tier-0): {cb['total_lines']}/{cb['max_lines']} строк")
    return report


# ─── archive ─────────────────────────────────────────────────────────────────


def parse_entries(content: str) -> list[dict]:
    """Разбирает SESSION_LOG на датированные записи; служебный хвост отрезается."""
    for marker in TAIL_MARKERS:
        idx = content.find(marker)
        if idx != -1:
            content = content[:idx]

    matches = list(ENTRY_RE.finditer(content))
    entries = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = re.sub(r"\n-{3,}\s*$", "", content[m.end() : end].strip()).strip()
        entries.append(
            {
                "date": m.group(1),
                "title": m.group(2),
                "content": f"## {m.group(1)} - {m.group(2)}\n\n{body}",
            }
        )
    return entries


def _deduplicate(entries: list[dict]) -> tuple[list[dict], int]:
    seen: set[str] = set()
    unique = []
    dupes = 0
    for e in entries:
        normalized = re.sub(r"\n{3,}", "\n\n", e["content"]).strip()
        if normalized in seen:
            dupes += 1
            continue
        seen.add(normalized)
        unique.append(e)
    return unique, dupes


def _git_dirty(cfg: Cfg) -> bool:
    """True, если SESSION_LOG имеет незакоммиченные изменения. Нет git — считаем чистым."""
    try:
        p = subprocess.run(
            ["git", "status", "--porcelain", "--", str(cfg.session_log)],
            cwd=str(cfg.root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        log("WARN", "git недоступен — проверка чистоты SESSION_LOG пропущена")
        return False
    if p.returncode != 0:
        log("WARN", "git status не отработал — проверка чистоты пропущена")
        return False
    return bool(p.stdout.strip())


def archive(cfg: Cfg, force: bool = False) -> dict:
    result: dict = {"archived": 0, "kept": 0, "duplicates_removed": 0}

    if not cfg.session_log.exists():
        log("WARN", f"{cfg.session_log} не найден — нечего архивировать")
        return result

    # Перезапись living-файла должна быть diff-ревьюируемой: только от чистого git-состояния
    if not force and _git_dirty(cfg):
        log("ERR", "SESSION_LOG.md имеет незакоммиченные изменения — закоммить или --force")
        result["error"] = "session_log_dirty"
        return result

    entries = parse_entries(read_file(cfg.session_log))
    if not entries:
        log("INFO", "Датированных записей не найдено")
        return result

    entries, dupes = _deduplicate(entries)
    result["duplicates_removed"] = dupes
    if dupes:
        log("OK", f"Удалено дублей: {dupes}")

    cutoff = (datetime.now() - timedelta(days=cfg.keep_days)).strftime("%Y-%m-%d")
    kept = list(entries[: cfg.keep_last])
    kept_keys = {(e["date"], e["title"]) for e in kept}
    for e in entries:
        if e["date"] >= cutoff and (e["date"], e["title"]) not in kept_keys:
            kept.append(e)
            kept_keys.add((e["date"], e["title"]))

    to_archive = [e for e in entries if (e["date"], e["title"]) not in kept_keys]
    result["kept"] = len(kept)
    result["archived"] = len(to_archive)

    by_week: OrderedDict[str, list[dict]] = OrderedDict()
    for e in to_archive:
        by_week.setdefault(get_iso_week(e["date"]), []).append(e)

    cfg.archive_dir.mkdir(parents=True, exist_ok=True)
    for week, week_entries in by_week.items():
        af = cfg.archive_dir / f"SESSION_LOG_{week}.md"
        existing = read_file(af)
        new_entries = [e for e in week_entries if e["content"] not in existing]
        if not new_entries:
            continue
        blocks = "".join(f"\n---\n\n{e['content']}\n" for e in new_entries)
        if existing:
            af.write_text(existing.rstrip() + "\n" + blocks, encoding="utf-8")
        else:
            af.write_text(f"# Session Log Archive - {week}\n{blocks}", encoding="utf-8")
        log("OK", f"  -> {af.relative_to(cfg.root)} (+{len(new_entries)})")

    _write_clean_log(cfg, kept)
    log("OK", f"Архивировано {len(to_archive)}, оставлено {len(kept)}")
    return result


def _write_clean_log(cfg: Cfg, kept: list[dict]) -> None:
    parts = [
        "# Session Log\n\n"
        "Журнал рабочих сессий. Последние записи + текущая неделя.\n"
        "Старые недели — в `archive/SESSION_LOG_YYYY-Www.md`.\n\n---\n\n"
    ]
    for e in kept:
        clean = re.sub(r"\n{3,}", "\n\n", e["content"]).strip()
        parts.append(f"{clean}\n\n---\n\n")

    parts.append("## Архив\n\n| Неделя | Файл |\n|--------|------|\n")
    if cfg.archive_dir.exists():
        for af in sorted(cfg.archive_dir.glob("SESSION_LOG_*.md"), reverse=True):
            rel = Path(os.path.relpath(af, cfg.session_log.parent)).as_posix()
            parts.append(f"| {af.stem.removeprefix('SESSION_LOG_')} | [{af.name}]({rel}) |\n")

    cfg.session_log.write_text("".join(parts), encoding="utf-8")


# ─── entry point ─────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["audit", "archive", "report"])
    parser.add_argument(
        "--force", action="store_true", help="archive: игнорировать незакоммиченный SESSION_LOG"
    )
    parser.add_argument("--version", action="version", version=VERSION)
    args = parser.parse_args()

    cfg = load_cfg(Path.cwd())

    if args.mode == "audit":
        audit(cfg)
    elif args.mode == "archive":
        result = archive(cfg, force=args.force)
        if "error" in result:
            return 1
    elif args.mode == "report":
        print(json.dumps(audit(cfg), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
