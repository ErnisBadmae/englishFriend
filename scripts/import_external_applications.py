#!/usr/bin/env python3
"""Записывает отклики, отправленные вне бота, — с внешних площадок.

Зачем. В боте владелец нажимает «Я уже откликнулся» на карточке. Но отклик на
getmatch, hh или сайте компании фиксировать негде, и такие отклики выпадали из
статистики целиком: очередь выглядит необработанной, а сколько на самом деле
отправлено — неизвестно. Незаписанный исход и есть тот сигнал, ради которого
вся калибровка и затевалась.

Вход — TSV без заголовка, по одной вакансии в строке:

    url<TAB>компания<TAB>должность[<TAB>заметка]

Идемпотентность по url: повторный запуск не задваивает. Строка, для которой
отклик уже записан, попадает в `duplicate`, а не тихо пропускается.

Использование:
    python scripts/import_external_applications.py --file career/external_applications.tsv \
        --telegram-id 1682176470
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from judge_gate.totals import TotalsContract, check_run  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.database import get_async_session  # noqa: E402
from app.models.core_tables import User  # noqa: E402
from app.services.career_inbox_service import (  # noqa: E402
    CareerInboxError,
    CareerInboxService,
)

# Тот же приём, что в import_career_inbox: у каждой строки обязан быть исход,
# иначе ссылка исчезает бесследно — ровно та потеря, против которой контракт.
# Причина — ИМЕНОВАННЫЙ код, а не текст исключения. Свободный текст пришлось бы
# кем-то категоризировать, чтобы посчитать, и контракт такой строки не принимает —
# он поймал ровно эту мою ошибку на первом запуске.
REASON_SERVICE_ERROR = "service_error"
IMPORT_CONTRACT = TotalsContract(
    routes=("applied", "duplicate", "rejected"),
    reasons=(REASON_SERVICE_ERROR,),
)


def parse_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("\t")]
        if len(parts) < 3:
            raise ValueError(f"нужно минимум url, компания, должность: {line[:80]!r}")
        rows.append(
            {
                "url": parts[0],
                "company": parts[1],
                "role_title": parts[2],
                "note": parts[3] if len(parts) > 3 else "",
            }
        )
    return rows


async def _run(args: argparse.Namespace) -> int:
    rows = parse_rows(Path(args.file))
    print(f"строк на вход: {len(rows)}")

    observations: list[tuple[str, str | None]] = []
    session_factory = get_async_session()
    async with session_factory() as db:
        user_id = await db.scalar(
            select(User.id).where(User.telegram_id == args.telegram_id)
        )
        if user_id is None:
            print(f"[ERR] нет пользователя с telegram_id={args.telegram_id}")
            return 1
        service = CareerInboxService(db)

        for row in rows:
            # Ключ от url, а не от времени: повторный запуск обязан быть безопасным.
            key = hashlib.sha256(row["url"].encode("utf-8")).hexdigest()[:32]
            raw_text = f"{row['company']} — {row['role_title']}\n{row['url']}"
            if row["note"]:
                raw_text += f"\n{row['note']}"
            try:
                lead = await service.confirm_manual_lead(
                    user_id,
                    source=args.source,
                    raw_text=raw_text,
                    company=row["company"],
                    role_title=row["role_title"],
                    url=row["url"],
                    idempotency_key=f"external:{key}",
                    actor_id=str(args.telegram_id),
                )
                inbox_item_id = lead["inbox_item"]["inbox_item_id"]
                result = await service.confirm_applied(
                    user_id,
                    inbox_item_id=inbox_item_id,
                    idempotency_key=f"external_applied:{key}",
                    actor_id=str(args.telegram_id),
                )
            except CareerInboxError as exc:
                print(f"  [ОТКАЗ] {row['company']} — {row['role_title']}: {exc}")
                observations.append(("rejected", REASON_SERVICE_ERROR))
                continue

            verb = "записан" if result.get("created") else "уже был"
            observations.append(("applied" if result.get("created") else "duplicate", None))
            print(f"  [{verb}] {row['company']} — {row['role_title']}")

    violations = check_run(observations, IMPORT_CONTRACT, expected_count=len(rows))
    counts = {r: sum(1 for route, _ in observations if route == r) for r in IMPORT_CONTRACT.routes}
    print(
        f"\nDONE. записано={counts['applied']} уже было={counts['duplicate']} "
        f"отказов={counts['rejected']} строк на входе={len(rows)}"
    )
    if violations:
        print("FAIL conservation: не каждая ссылка получила исход")
        for violation in violations:
            print(f"  {violation}")
        return 1
    print("PASS conservation: каждая ссылка получила исход")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="TSV: url, компания, должность[, заметка]")
    parser.add_argument("--telegram-id", type=int, required=True)
    parser.add_argument("--source", default="manual", help="источник из закрытого словаря MANUAL_LEAD_SOURCES")
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
