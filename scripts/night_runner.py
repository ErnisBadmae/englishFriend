#!/usr/bin/env python3
"""Minimal overnight task runner — proving harness, NOT a framework.

Ключевая идея против переполнения контекста: СВЕЖИЙ контекст на каждую задачу.
Runner — тупой цикл. Состояние живёт в git + отчёте, не в окне модели.
Каждая задача гоняется в одноразовом git worktree — executor НИКОГДА не трогает
основную рабочую копию. На красном — revert + удаление worktree, переход к следующей.

Сегодня = ПРОВЕРОЧНЫЙ прогон на крошечной очереди, не 8-часовой grind.
Morning-review архитектором обязателен (отчёт содержит сырой вывод).

Канонический источник — репозиторий expert-agent; в другие репозитории копируется
как есть, сверка версий по VERSION ниже.
При копировании можно менять только репо-настройки:
  REPO / WORKTREE_ROOT / QUEUE / OPENCODE / AUTO_APPROVE_EDITS.
Changelog:
  1.0 — базовый runner.
  1.1 — копирование .env в worktree + sh_logged full-log + LOG_TAIL_CHARS.
Запуск:
  python scripts/night_runner.py --dry-run   # проверить plumbing без executor (безопасно)
  python scripts/night_runner.py             # реальный прогон

Ограничения (честно):
- Сервисы (локальный Qwen + API) должны быть подняты всю ночь — acceptance гоняет gate.
- Подходят только задачи, чей acceptance читает файлы worktree В ПРОЦЕССЕ (gate/pytest/YAML/config).
  Задачи, требующие, чтобы API отдавал НОВЫЙ код, сюда не годятся (нужен рестарт против worktree).
"""
from __future__ import annotations

import argparse
import datetime
import fnmatch
import json
import pathlib
import shutil
import subprocess
import sys

VERSION = "1.1"

REPO = pathlib.Path(__file__).resolve().parents[1]
WORKTREE_ROOT = pathlib.Path("C:/tmp/englishfriend-qwen-runs")
QUEUE = REPO / "scripts" / "night_queue.json"
BASE_REF = "HEAD"
LOG_TAIL_CHARS = 3000
_VENV_PY = next((p for p in REPO.glob("*venv*/Scripts/python.exe")), None)
PY = str(_VENV_PY) if _VENV_PY else "python"

OPENCODE = shutil.which("opencode") or "opencode"
AUTO_APPROVE_EDITS = True
_PY_POSIX = _VENV_PY.as_posix() if _VENV_PY else "python"
SELF_VERIFY = (
    f"\n\n---\nСначала ВЫПОЛНИ задачу выше (внеси правки в файлы). ПОТОМ, перед финишем, self-check "
    f"(python НЕ на PATH — только полный путь к venv):\n"
    f"1) тесты: `{_PY_POSIX} -m pytest <нужные_файлы> -q` → rc=0;\n"
    f"2) lint изменённых .py: `{_PY_POSIX} -m flake8 <files>` и `{_PY_POSIX} -m black <files>`.\n"
    f"Исправь всё красное. НЕ финишируй, пока правки НЕ внесены и тесты/lint НЕ зелёные."
)


def sh_full(cmd: list[str], cwd: pathlib.Path, timeout: int = 1800) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def sh(cmd: list[str], cwd: pathlib.Path, timeout: int = 1800) -> tuple[int, str]:
    rc, out = sh_full(cmd, cwd, timeout)
    return rc, out[-LOG_TAIL_CHARS:]


def _write_full_log(log_dir: pathlib.Path, name: str, content: str) -> str:
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / f"{name}.log"
        path.write_text(content, encoding="utf-8")
        return str(path)
    except OSError as exc:
        return f"<full log unavailable: {exc}>"


def sh_logged(
    cmd: list[str],
    cwd: pathlib.Path,
    timeout: int,
    log_dir: pathlib.Path,
    name: str,
) -> tuple[int, str, str]:
    rc, out = sh_full(cmd, cwd, timeout)
    log_path = _write_full_log(log_dir, name, out)
    return rc, out[-LOG_TAIL_CHARS:], log_path


def _changed_files(wt: pathlib.Path) -> tuple[int, list[str], str]:
    try:
        p = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(wt),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return 124, [], "TIMEOUT"
    out = (p.stdout or "") + (p.stderr or "")
    if p.returncode != 0:
        return p.returncode, [], out
    files: list[str] = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        files.append(path.replace("\\", "/"))
    return 0, files, out


def _check_files_allowed(t: dict, wt: pathlib.Path) -> tuple[bool, str]:
    patterns = t.get("files_allowed")
    if patterns is None:
        return True, ""
    rc, files, out = _changed_files(wt)
    if rc != 0:
        return False, f"files_allowed guard failed to read git status\n```\n{out}\n```\n"
    forbidden = [
        path for path in files if not any(fnmatch.fnmatch(path, pattern) for pattern in patterns)
    ]
    if forbidden:
        return (
            False,
            "files_allowed guard violation\n" f"allowed={patterns}\n" f"forbidden={forbidden}\n",
        )
    return True, ""


def run_task(t: dict, wt: pathlib.Path, dry: bool, log_dir: pathlib.Path) -> tuple[str, str]:
    detail = ""
    if not dry and t.get("prompt"):
        cmd = [OPENCODE, "run", "--format", "json", "--dir", str(wt)]
        if AUTO_APPROVE_EDITS:
            cmd.append("--dangerously-skip-permissions")
        cmd.append(t["prompt"] + SELF_VERIFY)
        erc, eout, log_path = sh_logged(cmd, wt, t.get("timeout", 1800), log_dir, "executor")
        detail += f"executor rc={erc}\nFull log: {log_path}\n```\n{eout}\n```\n"
        ok, guard_detail = _check_files_allowed(t, wt)
        if not ok:
            return "RED", detail + guard_detail
    status = "GREEN"
    for idx, cmd in enumerate(t["acceptance"], start=1):
        argv = [PY if a == "{PY}" else a for a in cmd]
        rc, out, log_path = sh_logged(
            argv,
            wt,
            t.get("timeout", 1800),
            log_dir,
            f"acceptance-{idx:02d}",
        )
        detail += f"$ {' '.join(cmd)}\nrc={rc}\nFull log: {log_path}\n```\n{out}\n```\n"
        if rc == 124:
            return "BLOCKED", detail
        if rc != 0:
            status = "RED"
            break
    if status == "GREEN":
        ok, guard_detail = _check_files_allowed(t, wt)
        if not ok:
            return "RED", detail + guard_detail
    return status, detail


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="skip executor, test plumbing")
    args = ap.parse_args()

    tasks = json.loads(QUEUE.read_text(encoding="utf-8"))
    date = datetime.date.today().isoformat()
    run_id = datetime.datetime.now().strftime("%H%M%S")
    out_dir = WORKTREE_ROOT / date
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"# night_runner {date}-{run_id} ({'DRY' if args.dry_run else 'LIVE'})\n"]
    sh(["git", "worktree", "prune"], REPO, 60)

    for t in tasks:
        tid = t["id"]
        branch = f"auto/{date}-{run_id}/{tid}"
        wt = out_dir / f"{tid}-{run_id}"
        rc, wout = sh(["git", "worktree", "add", "-b", branch, str(wt), BASE_REF], REPO, 120)
        if rc != 0:
            lines.append(f"## {tid} — BLOCKED (worktree add)\n```\n{wout}\n```\n")
            continue
        env_file = REPO / ".env"
        if env_file.exists():
            shutil.copy2(env_file, wt / ".env")
        log_dir = out_dir / "logs" / f"{tid}-{run_id}"
        status, detail = run_task(t, wt, args.dry_run, log_dir)
        committed = False
        if status == "GREEN" and not args.dry_run:
            sh(["git", "add", "-A"], wt)
            diff_rc, diff_out = sh(["git", "diff", "--cached", "--quiet"], wt, 60)
            if diff_rc == 1:
                commit_rc, commit_out = sh(
                    ["git", "commit", "-m", f"auto: {tid}", "--no-verify"],
                    wt,
                    120,
                )
                detail += (
                    f"$ git commit -m auto: {tid} --no-verify\n"
                    f"rc={commit_rc}\n```\n{commit_out}\n```\n"
                )
                committed = commit_rc == 0
                if commit_rc != 0:
                    status = "RED"
            elif diff_rc == 0:
                detail += "no staged changes to commit\n"
            else:
                status = "RED"
                detail += f"git diff --cached --quiet failed\n```\n{diff_out}\n```\n"
        if not (status == "GREEN" and not args.dry_run and committed):
            sh(["git", "worktree", "remove", "--force", str(wt)], REPO)
            sh(["git", "branch", "-D", branch], REPO)
        lines.append(f"## {tid} — {status} (branch {branch})\n{detail}\n")
        if status != "GREEN":
            break

    report = out_dir / "report.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"[night_runner] done -> {report}")
    for ln in lines:
        if ln.startswith("## "):
            print(ln.strip())


if __name__ == "__main__":
    main()
