#!/usr/bin/env python3
"""Idempotent CLI import of a telegram-digest Career Inbox JSONL export
(career/CAREER_TELEGRAM_COCKPIT_SPEC.md Slice B).

The file is passed explicitly via ``--file`` - no sibling-repo reads at
runtime, no shared database, no HTTP/broker. Repeated import of the same file
creates no duplicate rows; a changed ``content_hash`` for the same
``external_id`` adds a new immutable snapshot without touching any existing
application (see ``CareerInboxService.import_snapshot``). This script makes
no network or LLM call and does not send anything - it only writes bounded,
owner-reviewable rows to this owner's Career Inbox.

Usage:
  venv\\Scripts\\python.exe scripts/import_career_inbox.py \
      --file data/career_inbox_export.jsonl --telegram-id 123456789
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from judge_gate.totals import TotalsContract, check_run
from sqlalchemy import select

from app.core.database import get_async_session
from app.models.core_tables import User
from app.services.career_inbox_service import (
    INBOX_DISPLAY_LIMIT,
    CareerInboxError,
    CareerInboxService,
    validate_import_envelope,
)


# Каждый конверт обязан получить ровно один исход. `over_limit` — единственная
# санкционированная дыра: усечение по --limit это решение вызывающего, и оно
# должно быть названо и посчитано, а не молча съедено срезом списка.
IMPORT_CONTRACT = TotalsContract(
    routes=("imported", "duplicate", "rejected"),
    exclusion_reasons=("over_limit",),
)


async def _run(args: argparse.Namespace) -> int:
    lines = Path(args.file).read_text(encoding="utf-8").splitlines()
    envelopes = [json.loads(line) for line in lines if line.strip()]

    session_factory = get_async_session()
    async with session_factory() as db:
        user_id = await db.scalar(
            select(User.id).where(
                User.telegram_id == args.telegram_id, User.deleted_at.is_(None)
            )
        )
        if user_id is None:
            print(
                f"[ERR] no EnglishFriend user linked to telegram_id={args.telegram_id}"
            )
            return 1

        service = CareerInboxService(db)
        imported = skipped_duplicate = rejected = 0
        outcomes: list[tuple[str, str | None]] = []
        for envelope in envelopes[: args.limit]:
            error = validate_import_envelope(envelope)
            if error:
                rejected += 1
                outcomes.append(("rejected", None))
                print(f"[REJECT] {envelope.get('external_id')}: {error}")
                continue
            try:
                result = await service.import_snapshot(
                    user_id,
                    external_id=envelope["external_id"],
                    content_hash=envelope["content_hash"],
                    company=envelope.get("company"),
                    role_title=envelope.get("role_title"),
                    location=envelope.get("location"),
                    url=envelope.get("url"),
                    route=envelope["route"],
                    gates=envelope["gates"],
                    questions_for_recruiter=envelope.get("questions_for_recruiter")
                    or [],
                )
            except CareerInboxError as exc:
                rejected += 1
                outcomes.append(("rejected", None))
                print(f"[REJECT] {envelope.get('external_id')}: {exc}")
                continue
            if result["created"]:
                imported += 1
                outcomes.append(("imported", None))
            else:
                skipped_duplicate += 1
                outcomes.append(("duplicate", None))

    truncated = max(0, len(envelopes) - args.limit)
    print(
        f"DONE. imported={imported} skipped_duplicate={skipped_duplicate} "
        f"rejected={rejected} over_limit={truncated} total_read={len(envelopes)}"
    )

    violations = check_run(
        outcomes,
        IMPORT_CONTRACT,
        expected_count=len(envelopes),
        exclusions={"over_limit": truncated},
    )
    if violations:
        print("\nFAIL conservation: не каждый конверт получил исход")
        for violation in violations:
            print(f"  {violation}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--file", required=True, help="path to the telegram-digest JSONL export"
    )
    parser.add_argument(
        "--telegram-id", type=int, required=True, help="owner's allowed Telegram ID"
    )
    parser.add_argument("--limit", type=int, default=INBOX_DISPLAY_LIMIT)
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
