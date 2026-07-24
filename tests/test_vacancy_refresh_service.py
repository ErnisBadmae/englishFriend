from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from app.services import vacancy_refresh_service as svc


_REAL_VENV_ROOT = Path(sys.executable).resolve().parents[1]


def _fake_digest_repo(tmp_path: Path) -> Path:
    digest_repo = tmp_path / "telegram-digest"
    python_dir = digest_repo / "venv" / "Scripts"
    python_dir.mkdir(parents=True)
    shutil.copy(sys.executable, python_dir / "python.exe")
    # The venv launcher stub needs pyvenv.cfg (absolute `home` path) next to
    # it to resolve the base interpreter - copy it so the fake venv works.
    shutil.copy(_REAL_VENV_ROOT / "pyvenv.cfg", digest_repo / "venv" / "pyvenv.cfg")
    return digest_repo


@pytest.mark.asyncio
async def test_missing_repo_path_config_fails_closed():
    result = await svc.refresh_vacancies(digest_repo_path="", telegram_id=1)
    assert result.ok is False
    assert "not configured" in result.message


@pytest.mark.asyncio
async def test_missing_digest_venv_fails_closed(tmp_path):
    digest_repo = tmp_path / "no-venv-here"
    digest_repo.mkdir()
    result = await svc.refresh_vacancies(digest_repo_path=str(digest_repo), telegram_id=1)
    assert result.ok is False
    assert "venv not found" in result.message


@pytest.mark.asyncio
async def test_pipeline_step_failure_surfaces_tail(tmp_path):
    digest_repo = _fake_digest_repo(tmp_path)
    (digest_repo / "refresh_vacancies.py").write_text(
        "import sys\nprint('boom')\nsys.exit(3)\n", encoding="utf-8"
    )
    result = await svc.refresh_vacancies(
        digest_repo_path=str(digest_repo), telegram_id=1
    )
    assert result.ok is False
    assert "Парсер вакансий упал" in result.message
    assert "boom" in result.message


@pytest.mark.asyncio
async def test_pipeline_ok_but_no_export_file_fails_closed(tmp_path):
    digest_repo = _fake_digest_repo(tmp_path)
    (digest_repo / "refresh_vacancies.py").write_text(
        "import sys\nsys.exit(0)\n", encoding="utf-8"
    )
    result = await svc.refresh_vacancies(
        digest_repo_path=str(digest_repo), telegram_id=1
    )
    assert result.ok is False
    assert "Файл экспорта не был создан" in result.message


@pytest.mark.asyncio
async def test_import_step_failure_surfaces_tail(tmp_path, monkeypatch):
    digest_repo = _fake_digest_repo(tmp_path)
    (digest_repo / "refresh_vacancies.py").write_text(
        "import sys\nsys.exit(0)\n", encoding="utf-8"
    )
    (digest_repo / "data").mkdir()
    (digest_repo / "data" / "career_inbox_export.jsonl").write_text("", encoding="utf-8")

    fake_import_script = tmp_path / "fake_import.py"
    fake_import_script.write_text(
        "import sys\nprint('import failed')\nsys.exit(2)\n", encoding="utf-8"
    )
    monkeypatch.setattr(svc, "PYTHON", Path(sys.executable))
    monkeypatch.setattr(svc, "IMPORT_SCRIPT", fake_import_script)

    result = await svc.refresh_vacancies(
        digest_repo_path=str(digest_repo), telegram_id=1
    )
    assert result.ok is False
    assert "Импорт в инбокс упал" in result.message
    assert "import failed" in result.message


@pytest.mark.asyncio
async def test_full_pipeline_success_returns_last_output_line(tmp_path, monkeypatch):
    digest_repo = _fake_digest_repo(tmp_path)
    (digest_repo / "refresh_vacancies.py").write_text(
        "import sys\nsys.exit(0)\n", encoding="utf-8"
    )
    (digest_repo / "data").mkdir()
    (digest_repo / "data" / "career_inbox_export.jsonl").write_text("", encoding="utf-8")

    fake_import_script = tmp_path / "fake_import.py"
    fake_import_script.write_text(
        "print('DONE. imported=2 skipped_duplicate=0 rejected=0 total_read=2')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "PYTHON", Path(sys.executable))
    monkeypatch.setattr(svc, "IMPORT_SCRIPT", fake_import_script)

    result = await svc.refresh_vacancies(
        digest_repo_path=str(digest_repo), telegram_id=1
    )
    assert result.ok is True
    assert result.message == "DONE. imported=2 skipped_duplicate=0 rejected=0 total_read=2"
