"""Local, project-specific MCP server for independent review of the
`ml_technical` interview track.

Purpose: let Sonnet/Codex read the same backend truth a founder session
produces (progress, attempts, question pack) and append an independent
review as new evidence, without ever mutating or deleting the original
Qwen review or writing raw SQL. Every tool below goes through
`MlTechnicalService` / `app.services.database.UserService` — the same
service layer the FastAPI app uses.

Transport: stdio only (see `.mcp.json`). Not exposed over HTTP/SSE, no
general CRUD, no arbitrary SQL — intentionally narrow per the task's MCP
scope limits.

Run standalone for a manual check:
    venv\\Scripts\\python.exe -m app.mcp.ml_technical_server
Normally launched by the MCP client (Claude Code) via `.mcp.json`.
"""

from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.config import settings
from app.data.ml_technical_questions import ML_TECHNICAL_TOPICS
from app.services.database import UserService
from app.services.ml_question_bank_service import (
    MlQuestionBankPermissionError,
    MlQuestionBankService,
)
from app.services.ml_progress_review_service import (
    MlProgressReviewError,
    MlProgressReviewService,
    read_career_brief,
)
from app.services.ml_technical_service import MlTechnicalService
from app.services.career_ledger_service import CareerLedgerService

mcp = FastMCP("englishfriend-ml-technical")


def _require_curator_write() -> None:
    if not settings.ml_question_curator_enabled:
        raise MlQuestionBankPermissionError("question curator writes are disabled")


def _require_admin_write() -> None:
    if not settings.ml_question_admin_enabled:
        raise MlQuestionBankPermissionError("question admin writes are disabled")


def _require_progress_review_append() -> None:
    if not settings.ml_progress_review_append_enabled:
        raise MlProgressReviewError("progress review appends are disabled")


async def _resolve_user_id(
    db: AsyncSession, user_id: Optional[int], telegram_id: Optional[int]
) -> int:
    if user_id is not None:
        return user_id
    if telegram_id is not None:
        user = await UserService(db).get_user_by_telegram_id(telegram_id)
        if user is None:
            raise ValueError(f"no user found for telegram_id={telegram_id}")
        return user.id
    raise ValueError("either user_id or telegram_id must be provided")


@mcp.tool()
async def get_ml_technical_progress(
    user_id: Optional[int] = None,
    telegram_id: Optional[int] = None,
) -> dict[str, Any]:
    """Read ml_technical track and topic progress for a user or Telegram ID.

    Returns the same track/topic/question progress the Mini App renders:
    totals, unseen, attempted, passed, needs_review, due_for_repetition,
    and per-topic/per-question breakdowns.
    """
    session_maker = get_async_session()
    async with session_maker() as db:
        resolved_user_id = await _resolve_user_id(db, user_id, telegram_id)
        service = MlTechnicalService(db)
        return await service.get_progress(resolved_user_id)


@mcp.tool()
async def get_ml_technical_attempts(
    user_id: Optional[int] = None,
    telegram_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Read recent (or needs_review) technical attempts for independent review.

    Each item includes the question text, the founder's raw answer, the
    authoritative rubric points, the reference explanation, the Qwen review
    (model id, prompt/rubric version, score, gaps, feedback), and provenance.
    Pass status="needs_review" to see only attempts that failed closed.
    """
    session_maker = get_async_session()
    async with session_maker() as db:
        resolved_user_id = await _resolve_user_id(db, user_id, telegram_id)
        service = MlTechnicalService(db)
        return await service.get_recent_attempts(
            resolved_user_id, status=status, limit=limit
        )


@mcp.tool()
async def append_ml_technical_external_review(
    attempt_id: str,
    reviewer: str,
    verdict: str,
    notes: Optional[str] = None,
    user_id: Optional[int] = None,
    telegram_id: Optional[int] = None,
) -> dict[str, Any]:
    """Append a Sonnet/Codex technical review as new evidence for one attempt.

    This never mutates or deletes the original Qwen review — it appends a
    separate, timestamped external_review record referencing `attempt_id`.
    `reviewer` should identify the reviewing agent (e.g. "sonnet", "codex").
    `verdict` is a short independent judgment (e.g. "agree", "disagree",
    "score_too_high", "score_too_low").
    """
    session_maker = get_async_session()
    async with session_maker() as db:
        resolved_user_id = await _resolve_user_id(db, user_id, telegram_id)
        service = MlTechnicalService(db)
        return await service.append_external_review(
            resolved_user_id,
            attempt_id=attempt_id,
            reviewer=reviewer,
            verdict=verdict,
            notes=notes,
        )


@mcp.tool()
async def list_ml_technical_question_pack() -> dict[str, Any]:
    """List approved PostgreSQL questions, rubrics and explanations."""
    session_maker = get_async_session()
    async with session_maker() as db:
        questions = await MlQuestionBankService(db).list_approved_questions()
        return {"topics": ML_TECHNICAL_TOPICS, "questions": questions}


@mcp.tool()
async def get_ml_question_bank_coverage() -> dict[str, Any]:
    """Read approved/draft/retired counts by ML topic."""
    session_maker = get_async_session()
    async with session_maker() as db:
        return await MlQuestionBankService(db).coverage()


@mcp.tool()
async def list_ml_question_drafts(
    topic_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Read draft revisions, optionally filtered by topic."""
    session_maker = get_async_session()
    async with session_maker() as db:
        return await MlQuestionBankService(db).list_drafts(topic_id)


@mcp.tool()
async def get_ml_question_revision(
    revision_id: str,
    include_authority: bool = True,
) -> dict[str, Any]:
    """Read one immutable revision and its append-only QA evidence."""
    session_maker = get_async_session()
    async with session_maker() as db:
        return await MlQuestionBankService(db).get_revision(
            revision_id, include_authority=include_authority
        )


@mcp.tool()
async def create_ml_question_draft(
    payload: dict[str, Any],
    idempotency_key: str,
    created_by: str,
    supersedes_id: Optional[str] = None,
) -> dict[str, Any]:
    """Create an immutable draft. Requires the curator capability flag."""
    _require_curator_write()
    session_maker = get_async_session()
    async with session_maker() as db:
        return await MlQuestionBankService(db).create_draft(
            payload,
            idempotency_key=idempotency_key,
            created_by=created_by,
            supersedes_id=supersedes_id,
        )


@mcp.tool()
async def validate_ml_question_draft(
    revision_id: str,
    expected_content_hash: str,
) -> dict[str, Any]:
    """Append deterministic schema/provenance validation evidence."""
    _require_curator_write()
    session_maker = get_async_session()
    async with session_maker() as db:
        return await MlQuestionBankService(db).validate_draft(
            revision_id, expected_content_hash=expected_content_hash
        )


@mcp.tool()
async def append_ml_question_qa_review(
    revision_id: str,
    expected_content_hash: str,
    review_kind: str,
    verdict: str,
    findings: list[dict[str, Any]],
    reviewer_type: str,
    reviewer_id: str,
    model_id: Optional[str] = None,
    prompt_version: Optional[str] = None,
) -> dict[str, Any]:
    """Append technical or source/IP review evidence to a draft."""
    _require_curator_write()
    session_maker = get_async_session()
    async with session_maker() as db:
        return await MlQuestionBankService(db).append_qa_review(
            revision_id,
            expected_content_hash=expected_content_hash,
            review_kind=review_kind,
            verdict=verdict,
            findings=findings,
            reviewer_type=reviewer_type,
            reviewer_id=reviewer_id,
            model_id=model_id,
            prompt_version=prompt_version,
        )


@mcp.tool()
async def approve_ml_question(
    revision_id: str,
    expected_content_hash: str,
    approved_by: str,
) -> dict[str, Any]:
    """Approve a fully reviewed draft. Requires the admin capability flag."""
    _require_admin_write()
    session_maker = get_async_session()
    async with session_maker() as db:
        return await MlQuestionBankService(db).approve(
            revision_id,
            expected_content_hash=expected_content_hash,
            approved_by=approved_by,
            admin_enabled=True,
        )


@mcp.tool()
async def retire_ml_question(
    revision_id: str,
    expected_content_hash: str,
    retired_by: str,
    reason: str,
) -> dict[str, Any]:
    """Retire an exact revision. Requires the admin capability flag."""
    _require_admin_write()
    session_maker = get_async_session()
    async with session_maker() as db:
        return await MlQuestionBankService(db).retire(
            revision_id,
            expected_content_hash=expected_content_hash,
            retired_by=retired_by,
            reason=reason,
            admin_enabled=True,
        )


@mcp.tool()
async def get_ml_progress_review_context(
    user_id: Optional[int] = None,
    telegram_id: Optional[int] = None,
) -> dict[str, Any]:
    """Return bounded PostgreSQL facts and their stable SHA-256 context hash."""
    session_maker = get_async_session()
    async with session_maker() as db:
        resolved_user_id = await _resolve_user_id(db, user_id, telegram_id)
        return await MlProgressReviewService(db).get_context(resolved_user_id)


@mcp.tool()
async def append_ml_progress_review(
    expected_context_hash: str,
    findings: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    reviewer_type: str,
    reviewer_id: str,
    prompt_version: str,
    model_id: Optional[str] = None,
    user_id: Optional[int] = None,
    telegram_id: Optional[int] = None,
) -> dict[str, Any]:
    """Append analysis only if the PostgreSQL evidence hash is still current."""
    _require_progress_review_append()
    session_maker = get_async_session()
    async with session_maker() as db:
        resolved_user_id = await _resolve_user_id(db, user_id, telegram_id)
        return await MlProgressReviewService(db).append_review(
            resolved_user_id,
            expected_context_hash=expected_context_hash,
            findings=findings,
            recommendations=recommendations,
            reviewer_type=reviewer_type,
            reviewer_id=reviewer_id,
            model_id=model_id,
            prompt_version=prompt_version,
        )


@mcp.tool()
async def get_career_pipeline_summary(
    user_id: Optional[int] = None,
    telegram_id: Optional[int] = None,
) -> dict[str, Any]:
    """Read bounded application counts by status and nearest next actions.

    Read-only: this tool has no write path for application status, applications
    or vacancy facts. Owner Telegram commands are the only write path.
    """
    session_maker = get_async_session()
    async with session_maker() as db:
        resolved_user_id = await _resolve_user_id(db, user_id, telegram_id)
        return await CareerLedgerService(db).get_pipeline_summary(resolved_user_id)


@mcp.tool()
async def get_career_pipeline_review_context(
    user_id: Optional[int] = None,
    telegram_id: Optional[int] = None,
) -> dict[str, Any]:
    """Read bounded career ledger facts and their stable SHA-256 context hash.

    A senior model reads this alongside `get_career_brief` and reasons over
    both; it cannot write either source.
    """
    session_maker = get_async_session()
    async with session_maker() as db:
        resolved_user_id = await _resolve_user_id(db, user_id, telegram_id)
        return await CareerLedgerService(db).get_review_context(resolved_user_id)


@mcp.tool()
async def get_career_brief() -> dict[str, Any]:
    """Read the marked YAML brief from the canonical root strategy document."""
    return read_career_brief()


if __name__ == "__main__":
    mcp.run()
