#!/usr/bin/env python3
"""Read-only: что сказал гейт против того, что решил владелец, по одной карточке.

Метки берутся из живой работы в боте (`owner_verdict` + закрытый список
`owner_reason`), а не из синтетического набора. Ценность даёт именно СШИВКА: сама
по себе метка говорит «карточка не подошла», а вместе с сохранённым `gates` этой
же карточки — «gate X сказал pass, и ошибся».

Что этот отчёт измеряет:
  precision — из ПОКАЗАННОГО сколько оказалось мусором и по чьей вине.

Чего он не измеряет, и это не мелочь:
  recall — сколько нужного система выбросила ДО показа. Владелец физически не
  может разметить то, чего не видел. Ложные отказы ловятся только выборкой из
  отсеянного (telegram-digest/vacancy_replay.py --sample), и это отдельная работа.

Использование:
  venv\\Scripts\\python.exe scripts/career_gate_calibration.py --telegram-id 123456789
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter, defaultdict

from sqlalchemy import select

from app.core.database import get_async_session
from app.models.career import CareerInboxItem
from app.models.core_tables import User

# Причины, которые называют ошибшийся gate (см. _SKIP_REASONS в боте).
GATE_REASONS = ("role_scope", "legal_hire_from_rf", "comp_threshold", "language_path")

# Отказы, которые НЕ являются ошибкой гейта: гейт был прав, когда пост писался,
# либо решение чисто личное. В матрицу ошибок они попадать не должны.
NON_GATE_REASONS = ("vacancy_closed", "other")

ACCEPTED_VERDICTS = ("prepare", "applied")

# Ниже этого числа проценты не печатаем: "3 из 8" честно, "37.5%" — нет.
MIN_N_FOR_SHARE = 30


def _fraction(part: int, whole: int) -> str:
    if whole == 0:
        return "нет данных"
    if whole < MIN_N_FOR_SHARE:
        return f"{part} из {whole}"
    return f"{part} из {whole} ({100 * part / whole:.0f}%)"


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
                    CareerInboxItem.gates,
                    CareerInboxItem.company,
                    CareerInboxItem.role_title,
                ).where(CareerInboxItem.user_id == user_id)
            )
        ).all()

    decided = [r for r in rows if r.owner_verdict is not None]
    accepted = [r for r in decided if r.owner_verdict in ACCEPTED_VERDICTS]
    blamed = [r for r in decided if r.owner_reason in GATE_REASONS]
    not_gate = [r for r in decided if r.owner_reason in NON_GATE_REASONS]
    unlabelled = [
        r
        for r in decided
        if r.owner_verdict not in ACCEPTED_VERDICTS
        and r.owner_reason not in GATE_REASONS + NON_GATE_REASONS
    ]

    print(f"карточек всего:            {len(rows)}")
    print(f"с решением владельца:      {len(decided)}")
    print(f"  взято в работу:          {len(accepted)}")
    print(f"  отклонено с меткой гейта:{len(blamed):>4}")
    print(f"  отклонено не по вине гейта: {len(not_gate)}  (закрыта / другое)")
    print(f"  отклонено без метки:     {len(unlabelled)}  (до появления причин)")

    if not blamed and not accepted:
        print(
            "\nСшивать пока нечего. Метки появляются, когда вы жмёте «Не подходит» "
            "и выбираете причину."
        )
        return 0

    # ─── главная таблица: что сказал гейт там, где владелец его обвинил ───
    print("\n=== gate сказал X — владелец обвинил этот gate ===")
    print("Показывает, где гейт был УВЕРЕН и ошибся (status=pass) — это худший класс.\n")

    said = defaultdict(Counter)
    for row in blamed:
        gate = (row.gates or {}).get(row.owner_reason) or {}
        said[row.owner_reason][gate.get("status") or "нет данных"] += 1

    print(f"{'gate':<22}{'обвинён':>9}{'сказал pass':>13}{'unknown':>10}{'fail':>7}")
    for gate in GATE_REASONS:
        counter = said.get(gate)
        if not counter:
            continue
        total = sum(counter.values())
        print(
            f"{gate:<22}{total:>9}{counter['pass']:>13}"
            f"{counter['unknown']:>10}{counter['fail']:>7}"
        )
        if counter["fail"]:
            print(
                f"  ! {counter['fail']} карточка(и) со status=fail не должны были "
                "показываться вообще — проверить маршрутизацию"
            )

    # ─── контекст: как часто pass этого гейта переживал решение владельца ───
    print("\n=== надёжность status=pass по каждому гейту ===")
    print("Из карточек, где gate сказал pass и владелец вынес решение —")
    print("сколько раз владелец обвинил именно его.\n")

    for gate in GATE_REASONS:
        passed = [
            r
            for r in decided
            if ((r.gates or {}).get(gate) or {}).get("status") == "pass"
        ]
        wrong = [r for r in passed if r.owner_reason == gate]
        print(f"  {gate:<22} ошибся {_fraction(len(wrong), len(passed))}")

    # ─── по маршруту, которым карточка пришла ───
    print("\n=== по маршруту ===")
    per_route: dict[str, Counter] = defaultdict(Counter)
    for row in decided:
        bucket = (
            "взято"
            if row.owner_verdict in ACCEPTED_VERDICTS
            else "ошибка гейта"
            if row.owner_reason in GATE_REASONS
            else "прочее"
        )
        per_route[row.route or "manual"][bucket] += 1
    for route in sorted(per_route):
        counter = per_route[route]
        total = sum(counter.values())
        print(
            f"  {route:<16} решений={total:<4} взято={counter['взято']:<4} "
            f"ошибка гейта={counter['ошибка гейта']:<4} прочее={counter['прочее']}"
        )

    if len(blamed) < MIN_N_FOR_SHARE:
        print(
            f"\nВыборка мала ({len(blamed)} размеченных отказов): читайте как сырые "
            "доли, не как метрику. Ориентир для первых выводов — 20-30."
        )
    print(
        "\nЛожные ОТКАЗЫ здесь не видны: владелец не может разметить то, чего ему не "
        "показали. Их ловит telegram-digest/vacancy_replay.py --sample."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--telegram-id", type=int, required=True)
    args = parser.parse_args()
    return asyncio.run(_run(args.telegram_id))


if __name__ == "__main__":
    sys.exit(main())
