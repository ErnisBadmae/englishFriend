#!/usr/bin/env python3
"""Read-only: что говорят гейты против того, что решил владелец.

Метки берутся из живой работы в боте (`owner_verdict` + закрытый список
`owner_reason`), а не из синтетического набора. Это отвечает ровно на один
вопрос: как часто гейт пропустил к владельцу то, что владельцу не подошло, и
какой именно гейт при этом ошибся.

ЧЕГО ЭТОТ ОТЧЁТ НЕ ИЗМЕРЯЕТ, и это не мелочь: владелец видит только то, что
система ему показала. Всё, что ушло в `skip` на стороне telegram-digest, до
бота не доезжает, поэтому ложные ОТКАЗЫ здесь невидимы в принципе - а именно
они и стоили 196 потерянных вакансий. Их можно поймать только выборкой из
skip, размеченной отдельно.

Использование:
  venv\\Scripts\\python.exe scripts/career_gate_calibration.py --telegram-id 123456789
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter

from sqlalchemy import select

from app.core.database import get_async_session
from app.models.career import CareerInboxItem
from app.models.core_tables import User

# Причины, которые называют ошибшийся gate (см. _SKIP_REASONS в боте).
GATE_REASONS = (
    "role_scope",
    "legal_hire_from_rf",
    "comp_threshold",
    "language_path",
)
NON_GATE_REASONS = ("vacancy_closed", "other")


async def _run(telegram_id: int) -> int:
    session_factory = get_async_session()
    async with session_factory() as db:
        user_id = await db.scalar(
            select(User.id).where(
                User.telegram_id == telegram_id, User.deleted_at.is_(None)
            )
        )
        if user_id is None:
            print(f"[ERR] no user linked to telegram_id={telegram_id}")
            return 1

        rows = (
            await db.execute(
                select(
                    CareerInboxItem.route,
                    CareerInboxItem.owner_verdict,
                    CareerInboxItem.owner_reason,
                ).where(CareerInboxItem.user_id == user_id)
            )
        ).all()

    decided = [r for r in rows if r.owner_verdict is not None]
    labelled = [r for r in decided if r.owner_reason in GATE_REASONS + NON_GATE_REASONS]

    print(f"карточек всего:        {len(rows)}")
    print(f"с решением владельца:  {len(decided)}")
    print(f"из них с меткой:       {len(labelled)}")
    if not labelled:
        print(
            "\nМеток пока нет. Они появляются, когда вы жмёте «Не подходит» и "
            "выбираете причину - данные копятся с первого дня использования."
        )
        return 0

    print("\n=== какой gate ошибся (по мнению владельца) ===")
    by_gate = Counter(r.owner_reason for r in labelled if r.owner_reason in GATE_REASONS)
    for reason, count in by_gate.most_common():
        share = 100 * count / len(labelled)
        print(f"  {reason:<22} {count:>4}  ({share:.0f}% помеченных)")

    other = Counter(
        r.owner_reason for r in labelled if r.owner_reason in NON_GATE_REASONS
    )
    if other:
        print("\n=== не ошибка гейта ===")
        for reason, count in other.most_common():
            print(f"  {reason:<22} {count:>4}")

    print("\n=== по маршруту, которым карточка пришла ===")
    per_route: dict[str, Counter] = {}
    for r in labelled:
        per_route.setdefault(r.route or "manual", Counter())[
            "gate_error" if r.owner_reason in GATE_REASONS else "not_a_gate_error"
        ] += 1
    for route, counter in sorted(per_route.items()):
        total = sum(counter.values())
        errors = counter["gate_error"]
        print(f"  {route:<16} помечено={total:<4} ошибка гейта={errors}")

    print(
        "\nНапоминание: ложные отказы (нужное, выброшенное в skip) здесь не видны "
        "и требуют отдельной выборки."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--telegram-id", type=int, required=True)
    args = parser.parse_args()
    return asyncio.run(_run(args.telegram_id))


if __name__ == "__main__":
    sys.exit(main())
