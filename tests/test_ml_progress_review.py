from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.exc import DBAPIError, OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.mcp.ml_technical_server import _require_progress_review_append
from app.models.core_tables import User
from app.models.ml_technical import (
    MlProgressReview,
    MlQuestionRevision,
    MlTechnicalAttempt,
    MlTechnicalSession,
    MlTechnicalSessionItem,
)
from app.services.ml_progress_review_service import (
    DEFAULT_CAREER_STRATEGY_PATH,
    CareerBriefError,
    MlProgressContextStaleError,
    MlProgressReviewError,
    MlProgressReviewService,
    canonical_json,
    context_hash,
    read_career_brief,
)


TEST_DATABASE_URL = os.getenv("ML_TECHNICAL_PG_TEST_URL")


def test_canonical_context_hash_is_independent_of_mapping_order():
    first = {"b": 2, "a": {"y": 2, "x": 1}}
    second = {"a": {"x": 1, "y": 2}, "b": 2}
    assert canonical_json(first) == canonical_json(second)
    assert context_hash(first) == context_hash(second)


def test_career_brief_reads_only_marked_yaml_and_hashes_exact_block(tmp_path: Path):
    block = "\n```yaml\nschema_version: 1\ntarget_roles:\n  - role_a\n```\n"
    strategy = tmp_path / "PERSONAL_STRATEGY.md"
    strategy.write_text(
        f"ignored before\n<!-- career-brief:start -->{block}"
        "<!-- career-brief:end -->\nignored after",
        encoding="utf-8",
    )

    result = read_career_brief(strategy)

    assert result["data"] == {"schema_version": 1, "target_roles": ["role_a"]}
    assert result["block_sha256"] == hashlib.sha256(block.encode("utf-8")).hexdigest()
    assert "ignored" not in canonical_json(result["data"])


@pytest.mark.parametrize(
    "content",
    [
        "<!-- career-brief:start -->\n```yaml\na: 1\n```\n",
        (
            "<!-- career-brief:start -->\n```yaml\na: 1\na: 2\n```\n"
            "<!-- career-brief:end -->"
        ),
        ("<!-- career-brief:start -->\nnot-a-fence\n" "<!-- career-brief:end -->"),
        (
            "<!-- career-brief:start -->\n```yaml\na: 1\n```\n"
            "<!-- career-brief:end -->\n<!-- career-brief:end -->"
        ),
    ],
)
def test_career_brief_fails_closed_on_invalid_boundary(tmp_path: Path, content: str):
    strategy = tmp_path / "PERSONAL_STRATEGY.md"
    strategy.write_text(content, encoding="utf-8")
    with pytest.raises(CareerBriefError):
        read_career_brief(strategy)


def test_read_career_brief_zero_arg_resolves_shared_personal_strategy():
    assert DEFAULT_CAREER_STRATEGY_PATH.name == "PERSONAL_STRATEGY.md"
    repo_root = Path(__file__).resolve().parents[1]
    assert DEFAULT_CAREER_STRATEGY_PATH.parent == repo_root.parent

    result = read_career_brief()

    assert len(result["block_sha256"]) == 64
    assert "target_roles" in result["data"]


def test_progress_review_append_is_settings_gated(monkeypatch):
    monkeypatch.setattr(settings, "ml_progress_review_append_enabled", False)
    with pytest.raises(MlProgressReviewError):
        _require_progress_review_append()

    monkeypatch.setattr(settings, "ml_progress_review_append_enabled", True)
    _require_progress_review_append()


@pytest_asyncio.fixture()
async def pg_session_maker():
    if not TEST_DATABASE_URL or "postgresql" not in TEST_DATABASE_URL:
        pytest.skip("ML_TECHNICAL_PG_TEST_URL is not configured for PostgreSQL")
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1 from ml_progress_reviews limit 0"))
    except (OperationalError, ProgrammingError) as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL migration 015 unavailable: {exc.__class__.__name__}")
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


async def _create_user(db: AsyncSession) -> int:
    return int(
        await db.scalar(
            insert(User)
            .values(username=f"ml_progress_test_{uuid4().hex}")
            .returning(User.id)
        )
    )


async def _add_dont_know_attempt(db: AsyncSession, user_id: int) -> str:
    revision = await db.scalar(
        select(MlQuestionRevision).where(
            MlQuestionRevision.question_key == "mltech_001",
            MlQuestionRevision.status == "approved",
        )
    )
    assert revision is not None
    now = datetime.now(timezone.utc)
    session_id = str(uuid4())
    attempt_id = str(uuid4())
    db.add(
        MlTechnicalSession(
            id=session_id,
            user_id=user_id,
            mode="topic",
            channel="mcp",
            topic_id=revision.topic_id,
            status="completed",
            created_at=now,
            closed_at=now,
        )
    )
    db.add(
        MlTechnicalSessionItem(
            id=str(uuid4()),
            user_id=user_id,
            session_id=session_id,
            question_id=revision.question_key,
            question_revision_id=revision.id,
            position=1,
            status="answered",
            created_at=now,
            updated_at=now,
        )
    )
    db.add(
        MlTechnicalAttempt(
            id=attempt_id,
            user_id=user_id,
            session_id=session_id,
            question_id=revision.question_key,
            question_revision_id=revision.id,
            topic_id=revision.topic_id,
            answer_kind="dont_know",
            answer_language="ru_knowledge",
            raw_answer="",
            source_channel="mcp",
            answered_at=now,
            review={
                "status": "graded",
                "score_percent": 0.0,
                "covered_points": [],
                "missing_points": [item["id"] for item in revision.rubric_points],
            },
        )
    )
    await db.commit()
    return attempt_id


@pytest.mark.integration
async def test_context_is_stable_and_append_cannot_mutate_practice(pg_session_maker):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        await db.commit()
        await _add_dont_know_attempt(db, user_id)
        service = MlProgressReviewService(db)

        first = await service.get_context(user_id)
        second = await service.get_context(user_id)
        before_attempts = int(
            await db.scalar(
                select(func.count(MlTechnicalAttempt.id)).where(
                    MlTechnicalAttempt.user_id == user_id
                )
            )
            or 0
        )

        appended = await service.append_review(
            user_id,
            expected_context_hash=first["context_hash"],
            findings=[
                {
                    "code": "gap",
                    "evidence_attempt_ids": [
                        first["context"]["attempts"]["recent"][0]["attempt_id"]
                    ],
                }
            ],
            recommendations=[{"topic_id": "dl_training", "action": "repeat"}],
            reviewer_type="model",
            reviewer_id="sonnet",
            model_id="claude-sonnet",
            prompt_version="ml-progress-review-v1",
        )

        after_attempts = int(
            await db.scalar(
                select(func.count(MlTechnicalAttempt.id)).where(
                    MlTechnicalAttempt.user_id == user_id
                )
            )
            or 0
        )
        stored = await db.get(MlProgressReview, appended["review_id"])

        assert first == second
        assert appended["context_hash"] == first["context_hash"]
        assert before_attempts == after_attempts == 1
        assert stored is not None
        assert context_hash(stored.context_snapshot) == stored.context_hash

        with pytest.raises(DBAPIError):
            await db.execute(
                update(MlProgressReview)
                .where(MlProgressReview.id == appended["review_id"])
                .values(prompt_version="tampered")
            )
            await db.commit()
        await db.rollback()


@pytest.mark.integration
async def test_append_fails_closed_when_context_hash_is_stale(pg_session_maker):
    async with pg_session_maker() as db:
        user_id = await _create_user(db)
        await db.commit()
        service = MlProgressReviewService(db)
        old_context = await service.get_context(user_id)
        before_reviews = int(
            await db.scalar(
                select(func.count(MlProgressReview.id)).where(
                    MlProgressReview.user_id == user_id
                )
            )
            or 0
        )
        await _add_dont_know_attempt(db, user_id)

        with pytest.raises(MlProgressContextStaleError):
            await service.append_review(
                user_id,
                expected_context_hash=old_context["context_hash"],
                findings=[{"code": "stale"}],
                recommendations=[],
                reviewer_type="model",
                reviewer_id="sonnet",
                model_id="claude-sonnet",
                prompt_version="ml-progress-review-v1",
            )

        after_reviews = int(
            await db.scalar(
                select(func.count(MlProgressReview.id)).where(
                    MlProgressReview.user_id == user_id
                )
            )
            or 0
        )
        assert after_reviews == before_reviews
