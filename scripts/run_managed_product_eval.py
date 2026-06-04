"""Run product synthetic eval with a managed local API process.

This is a thin operator helper for repeatable self-dogfood checks:

1. Reuse an already healthy API at --base-url, or start uvicorn locally.
2. Wait for /health.
3. Run scripts/run_product_synthetic_eval.py with the provided eval args.
4. Stop the managed API process.

Examples:
    python scripts/run_managed_product_eval.py --scenario interview_self_intro_gap
    python scripts/run_managed_product_eval.py --scenario-set mainline
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _health_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/health"


def _is_healthy(base_url: str, timeout_s: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(_health_url(base_url), timeout=timeout_s) as response:
            return 200 <= response.status < 300
    except (OSError, urllib.error.URLError):
        return False


def _wait_for_health(
    *,
    base_url: str,
    process: subprocess.Popen[str] | None,
    startup_timeout_s: float,
    log_path: Path | None,
) -> None:
    deadline = time.monotonic() + startup_timeout_s
    while time.monotonic() < deadline:
        if _is_healthy(base_url):
            return
        if process is not None and process.poll() is not None:
            detail = ""
            if log_path and log_path.exists():
                detail = "\nAPI log tail:\n" + "\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:])
            raise RuntimeError(f"Managed API exited before /health became ready.{detail}")
        time.sleep(0.5)

    detail = ""
    if log_path and log_path.exists():
        detail = "\nAPI log tail:\n" + "\n".join(log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:])
    raise RuntimeError(f"API did not become healthy within {startup_timeout_s:.0f}s.{detail}")


def _start_api(host: str, port: int) -> tuple[subprocess.Popen[str], Path]:
    log_file = tempfile.NamedTemporaryFile(
        prefix="englishfriend-api-",
        suffix=".log",
        delete=False,
        mode="w",
        encoding="utf-8",
    )
    log_path = Path(log_file.name)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            host,
            "--port",
            str(port),
        ],
        cwd=ROOT,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )
    log_file.close()
    return process, log_path


def _parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Start local API if needed, then run product synthetic eval.",
        add_help=True,
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--startup-timeout", type=float, default=45.0)
    parser.add_argument(
        "--force-managed-api",
        action="store_true",
        help="Start a managed API process even if --base-url is already healthy.",
    )
    return parser.parse_known_args()


def main() -> int:
    args, eval_args = _parse_args()
    process: subprocess.Popen[str] | None = None
    log_path: Path | None = None
    managed = False

    try:
        if not args.force_managed_api and _is_healthy(args.base_url):
            print(f"Reusing healthy API at {args.base_url}", flush=True)
        else:
            process, log_path = _start_api(args.host, args.port)
            managed = True
            print(f"Started managed API pid={process.pid}; log={log_path}", flush=True)
            _wait_for_health(
                base_url=args.base_url,
                process=process,
                startup_timeout_s=args.startup_timeout,
                log_path=log_path,
            )
            print(f"API healthy at {args.base_url}", flush=True)

        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "run_product_synthetic_eval.py"),
            "--base-url",
            args.base_url,
            *eval_args,
        ]
        return subprocess.run(cmd, cwd=ROOT).returncode
    finally:
        if managed and process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
