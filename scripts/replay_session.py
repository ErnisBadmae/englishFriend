r"""Build an operator-friendly replay bundle for one session_id.

Usage:
    venv\Scripts\python.exe scripts/replay_session.py --session-id <uuid>
    venv\Scripts\python.exe scripts/replay_session.py --session-id <uuid> --output replay.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_async_session
from app.models.core_tables import Session
from app.models.extended_tables import LearningPlan
from app.services.program_snapshot_service import ProgramSnapshotService


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def select_session_evidence(
    session_id: str,
    evidence_items: list[dict[str, Any]] | None,
) -> Optional[dict[str, Any]]:
    for item in evidence_items or []:
        if isinstance(item, dict) and str(item.get("session_id") or "") == session_id:
            return item
    return None


def build_snapshot_excerpt(snapshot: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not snapshot:
        return {}

    mission = snapshot.get("mission") or {}
    setup = snapshot.get("setup") or {}
    product_signals = snapshot.get("product_signals") or {}
    monetization = snapshot.get("monetization") or {}
    latest_evidence = ((snapshot.get("session_evidence") or {}).get("latest")) or {}

    return {
        "mission": {
            "mode": mission.get("mode"),
            "task_type": mission.get("task_type"),
            "title": mission.get("title"),
            "reason": mission.get("reason"),
            "adaptation_reason": mission.get("adaptation_reason"),
            "repeat_vs_advance": mission.get("repeat_vs_advance"),
        },
        "setup": {
            "state": setup.get("state"),
            "scope_status": setup.get("scope_status"),
            "progress": setup.get("progress"),
        },
        "product_signals": {
            "activation_stage": product_signals.get("activation_stage"),
            "value_stage": product_signals.get("value_stage"),
            "conversion_stage": product_signals.get("conversion_stage"),
            "retention_stage": product_signals.get("retention_stage"),
        },
        "monetization": {
            "value_visible": monetization.get("value_visible"),
            "value_signals": monetization.get("value_signals"),
            "cta_reason": monetization.get("cta_reason"),
        },
        "latest_session_evidence": latest_evidence,
    }


async def build_replay_bundle(session_id: str) -> dict[str, Any]:
    session_factory = get_async_session()
    async with session_factory() as db:
        stmt = (
            select(Session)
            .options(
                selectinload(Session.user),
                selectinload(Session.utterances),
                selectinload(Session.feedback),
                selectinload(Session.corrections),
            )
            .where(Session.id == session_id)
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        if session is None:
            raise ValueError(f"Session not found: {session_id}")

        plan_stmt = (
            select(LearningPlan)
            .where(LearningPlan.user_id == session.user_id)
            .order_by(LearningPlan.updated_at.desc())
        )
        plan_result = await db.execute(plan_stmt)
        plan = plan_result.scalars().first()
        roadmap = (plan.roadmap or {}) if plan else {}
        session_evidence_items = list(roadmap.get("session_evidence") or [])
        matching_evidence = select_session_evidence(session_id, session_evidence_items)

        snapshot_service = ProgramSnapshotService(db)
        snapshot = await snapshot_service.get_snapshot(session.user_id)

        utterances = sorted(
            session.utterances or [],
            key=lambda item: (item.t_start_ms, item.t_end_ms, str(item.id)),
        )

        return {
            "session": {
                "id": str(session.id),
                "user_id": session.user_id,
                "started_at": session.started_at,
                "ended_at": session.ended_at,
                "duration_minutes": getattr(session, "duration_minutes", None),
                "lang_code": session.lang_code,
                "audio_url": session.audio_url,
                "call_quality": session.call_quality,
            },
            "user": {
                "id": session.user.id if session.user else session.user_id,
                "telegram_id": session.user.telegram_id if session.user else None,
                "username": session.user.username if session.user else None,
                "language_level": session.user.language_level if session.user else None,
            },
            "transcript": [
                {
                    "id": str(item.id),
                    "speaker": item.speaker,
                    "text": item.text,
                    "t_start_ms": item.t_start_ms,
                    "t_end_ms": item.t_end_ms,
                    "grammar_score": item.grammar_score,
                    "pronunciation_score": item.pronunciation_score,
                }
                for item in utterances
            ],
            "feedback": (
                {
                    "overall_grammar": session.feedback.overall_grammar,
                    "overall_pronunciation": session.feedback.overall_pronunciation,
                    "summary_md": session.feedback.summary_md,
                    "tips_md": session.feedback.tips_md,
                }
                if session.feedback
                else None
            ),
            "corrections": [
                {
                    "id": str(item.id),
                    "utterance_id": str(item.utterance_id) if item.utterance_id else None,
                    "user_text": item.user_text,
                    "corrected_text": item.corrected_text,
                    "rule_tag": item.rule_tag,
                    "explanation_md": item.explanation_md,
                }
                for item in (session.corrections or [])
            ],
            "roadmap_session_evidence": matching_evidence,
            "snapshot_excerpt": build_snapshot_excerpt(snapshot),
            "trace_context": {
                "session_id": str(session.id),
                "runtime": "unknown",
                "note": "Use session_id to correlate structured voice logs and Langfuse traces.",
            },
        }


async def _async_main(args: argparse.Namespace) -> int:
    bundle = await build_replay_bundle(args.session_id)
    payload = json.dumps(bundle, ensure_ascii=False, indent=2, default=_json_default)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an operator replay bundle for a session.")
    parser.add_argument("--session-id", required=True, help="Session UUID to inspect")
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()
    return asyncio.run(_async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
