import json
import asyncio
import os
import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.data.ml_technical_questions import ML_TECHNICAL_QUESTIONS
from app.core.config import settings
from app.mcp.ml_technical_server import (
    _require_admin_write,
    _require_curator_write,
)
from app.models.ml_technical import (
    MlQuestionReview,
    MlQuestionRevision,
    MlTechnicalAttempt,
    MlTechnicalSessionItem,
    MlTechnicalSession,
)
from app.models.core_tables import User
from app.services.ml_question_bank_service import (
    MlQuestionBankConflictError,
    MlQuestionBankPermissionError,
    MlQuestionBankService,
    normalize_question_payload,
    question_content_hash,
    validate_question_payload,
)
from app.services.ml_technical_service import (
    ANSWER_KIND_DONT_KNOW,
    MlTechnicalService,
    compute_question_progress,
    select_daily_queue,
)


ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.getenv("ML_TECHNICAL_PG_TEST_URL")


def _valid_payload(question_index: int = 0) -> dict:
    question = deepcopy(ML_TECHNICAL_QUESTIONS[question_index])
    return {
        **question,
        "source_kind": "owner_authored",
        "source_label": "Founder interview preparation notes",
        "source_uri_public": None,
        "source_fingerprint": "a" * 64,
        "derivation_kind": "original",
        "publication_scope": "internal_only",
        "license_note": "Owner-authored preparation material.",
        "model_id": None,
        "prompt_version": None,
    }


def test_checked_in_pack_is_only_the_exact_15_row_migration_fixture():
    sql = (
        ROOT / "db" / "migrations" / "postgres" / "014_ml_question_bank.sql"
    ).read_text(encoding="utf-8")
    match = re.search(
        r"values \(\$fixture\$(\[.*?\])\$fixture\$::jsonb\);", sql, re.DOTALL
    )
    assert match is not None
    fixture = json.loads(match.group(1))
    assert len(fixture) == len(ML_TECHNICAL_QUESTIONS) == 15
    assert [item["question_key"] for item in fixture] == [
        question["id"] for question in ML_TECHNICAL_QUESTIONS
    ]
    for item, source_question in zip(fixture, ML_TECHNICAL_QUESTIONS, strict=True):
        for field in (
            "question_ru",
            "topic_id",
            "difficulty",
            "tags",
            "rubric_points",
            "reference_explanation_ru",
            "follow_ups",
            "rubric_version",
        ):
            assert item[field] == source_question[field]
        assert item["content_hash"] == question_content_hash(item)


def test_validator_accepts_complete_owner_authored_question():
    assert validate_question_payload(_valid_payload()) == []


def test_validator_rejects_private_source_leak_and_public_scope():
    payload = _valid_payload()
    payload.update(
        {
            "source_kind": "private_corpus",
            "source_uri_public": "https://t.me/private-channel/42",
            "publication_scope": "public_verbatim",
        }
    )
    codes = {issue["code"] for issue in validate_question_payload(payload)}
    assert {"private_source_scope", "private_source_uri", "private_locator"} <= codes


def test_content_hash_uses_canonical_whitespace_and_case_for_identifiers():
    payload = _valid_payload()
    variant = deepcopy(payload)
    variant["id"] = f"  {payload['id']}  "
    variant["difficulty"] = payload["difficulty"].upper()
    variant["tags"] = [f"  {tag.upper()}  " for tag in payload["tags"]]
    assert normalize_question_payload(variant) == normalize_question_payload(payload)
    assert question_content_hash(variant) == question_content_hash(payload)


def test_runtime_queue_uses_supplied_db_snapshot_not_static_pack():
    question = _valid_payload()
    question.update(
        {
            "id": "mltech_db_only",
            "question_revision_id": "00000000-0000-0000-0000-000000000001",
        }
    )
    assert select_daily_queue(
        [], session_seed="founder:2026-07-21", questions=[question]
    ) == ["mltech_db_only"]


def test_revision_foreign_keys_exist_on_session_items_and_attempts():
    assert "question_revision_id" in MlTechnicalSessionItem.__table__.columns
    assert "question_revision_id" in MlTechnicalAttempt.__table__.columns
    assert MlQuestionRevision.__tablename__ == "ml_question_revisions"
    assert MlQuestionReview.__tablename__ == "ml_question_reviews"


def test_mcp_write_capabilities_are_environment_gated(monkeypatch):
    monkeypatch.setattr(settings, "ml_question_curator_enabled", False)
    monkeypatch.setattr(settings, "ml_question_admin_enabled", False)
    with pytest.raises(MlQuestionBankPermissionError):
        _require_curator_write()
    with pytest.raises(MlQuestionBankPermissionError):
        _require_admin_write()

    monkeypatch.setattr(settings, "ml_question_curator_enabled", True)
    monkeypatch.setattr(settings, "ml_question_admin_enabled", True)
    _require_curator_write()
    _require_admin_write()


@pytest_asyncio.fixture(scope="function")
async def isolated_pg_session_maker():
    """Clone the designated disposable DB so append-only tests leave no debris."""
    if not TEST_DATABASE_URL or "postgresql" not in TEST_DATABASE_URL:
        pytest.skip("ML_TECHNICAL_PG_TEST_URL is not configured for PostgreSQL")

    source_url = make_url(TEST_DATABASE_URL)
    source_db = source_url.database
    if not source_db:
        pytest.skip("PostgreSQL test URL has no source database")
    isolated_db = f"ef_mlq_{uuid4().hex[:16]}"
    admin_engine = create_async_engine(
        source_url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        async with admin_engine.connect() as conn:
            await conn.execute(
                text(f'create database "{isolated_db}" template "{source_db}"')
            )
    except (OperationalError, ProgrammingError) as exc:
        await admin_engine.dispose()
        pytest.skip(f"cannot create isolated PostgreSQL clone: {exc}")

    engine = create_async_engine(source_url.set(database=isolated_db), echo=False)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield maker
    finally:
        await engine.dispose()
        async with admin_engine.connect() as conn:
            await conn.execute(
                text(
                    "select pg_terminate_backend(pid) from pg_stat_activity "
                    "where datname = :database and pid <> pg_backend_pid()"
                ),
                {"database": isolated_db},
            )
            await conn.execute(text(f'drop database if exists "{isolated_db}"'))
        await admin_engine.dispose()


def _unique_payload() -> dict:
    payload = _valid_payload()
    payload["id"] = f"mlq_test_{uuid4().hex[:20]}"
    return payload


async def _append_required_passes(
    service: MlQuestionBankService, revision: dict
) -> None:
    revision_id = revision["id"]
    content_hash = revision["content_hash"]
    await service.validate_draft(revision_id, expected_content_hash=content_hash)
    for kind in ("technical", "source_ip"):
        await service.append_qa_review(
            revision_id,
            expected_content_hash=content_hash,
            review_kind=kind,
            verdict="pass",
            findings=[],
            reviewer_type="human",
            reviewer_id="test-owner",
        )


async def _create_approved_revision(
    maker,
    payload: dict,
    *,
    supersedes_id: str | None = None,
) -> dict:
    async with maker() as db:
        service = MlQuestionBankService(db)
        draft = await service.create_draft(
            payload,
            idempotency_key=f"test:{payload['id']}:{uuid4().hex}",
            created_by="test-curator",
            supersedes_id=supersedes_id,
        )
        await _append_required_passes(service, draft)
        return await service.approve(
            draft["id"],
            expected_content_hash=draft["content_hash"],
            approved_by="test-owner",
            admin_enabled=True,
        )


@pytest.mark.integration
async def test_postgres_question_lifecycle_is_idempotent_append_only_and_gated(
    isolated_pg_session_maker,
):
    payload = _unique_payload()
    key = f"lifecycle:{uuid4().hex}"
    async with isolated_pg_session_maker() as db:
        service = MlQuestionBankService(db)
        draft = await service.create_draft(
            payload,
            idempotency_key=key,
            created_by="test-curator",
        )
        replay = await service.create_draft(
            deepcopy(payload),
            idempotency_key=key,
            created_by="test-curator",
        )
        assert replay["id"] == draft["id"]

        changed = deepcopy(payload)
        changed["question_ru"] += " Измененная формулировка."
        with pytest.raises(MlQuestionBankConflictError):
            await service.create_draft(
                changed,
                idempotency_key=key,
                created_by="test-curator",
            )
        with pytest.raises(MlQuestionBankConflictError, match="stale content_hash"):
            await service.validate_draft(draft["id"], expected_content_hash="0" * 64)

        schema_review = await service.validate_draft(
            draft["id"], expected_content_hash=draft["content_hash"]
        )
        assert schema_review["verdict"] == "pass"
        await service.append_qa_review(
            draft["id"],
            expected_content_hash=draft["content_hash"],
            review_kind="technical",
            verdict="pass",
            findings=[],
            reviewer_type="human",
            reviewer_id="reviewer-1",
        )
        await service.append_qa_review(
            draft["id"],
            expected_content_hash=draft["content_hash"],
            review_kind="technical",
            verdict="needs_changes",
            findings=[{"code": "clarify"}],
            reviewer_type="human",
            reviewer_id="reviewer-2",
        )
        await service.append_qa_review(
            draft["id"],
            expected_content_hash=draft["content_hash"],
            review_kind="source_ip",
            verdict="pass",
            findings=[],
            reviewer_type="human",
            reviewer_id="reviewer-1",
        )
        with pytest.raises(MlQuestionBankConflictError, match="technical"):
            await service.approve(
                draft["id"],
                expected_content_hash=draft["content_hash"],
                approved_by="test-owner",
                admin_enabled=True,
            )

        final_technical = await service.append_qa_review(
            draft["id"],
            expected_content_hash=draft["content_hash"],
            review_kind="technical",
            verdict="pass",
            findings=[],
            reviewer_type="human",
            reviewer_id="reviewer-3",
        )
        approved = await service.approve(
            draft["id"],
            expected_content_hash=draft["content_hash"],
            approved_by="test-owner",
            admin_enabled=True,
        )
        assert approved["status"] == "approved"

        stored_reviews = await db.scalars(
            select(MlQuestionReview).where(
                MlQuestionReview.question_revision_id == draft["id"]
            )
        )
        assert len(stored_reviews.all()) == 5

        with pytest.raises(DBAPIError):
            await db.execute(
                update(MlQuestionReview)
                .where(MlQuestionReview.id == final_technical["id"])
                .values(verdict="fail")
            )
            await db.commit()
        await db.rollback()
        with pytest.raises(DBAPIError):
            await db.execute(
                delete(MlQuestionReview).where(
                    MlQuestionReview.id == final_technical["id"]
                )
            )
            await db.commit()
        await db.rollback()

        with pytest.raises(DBAPIError):
            await db.execute(
                update(MlQuestionRevision)
                .where(MlQuestionRevision.id == draft["id"])
                .values(question_ru="illegal content mutation")
            )
            await db.commit()
        await db.rollback()
        with pytest.raises(DBAPIError):
            await db.execute(
                delete(MlQuestionRevision).where(MlQuestionRevision.id == draft["id"])
            )
            await db.commit()
        await db.rollback()


@pytest.mark.integration
async def test_revision_branching_atomic_approval_and_concurrent_approval(
    isolated_pg_session_maker,
):
    payload = _unique_payload()
    revision_1 = await _create_approved_revision(isolated_pg_session_maker, payload)

    payload_2 = deepcopy(payload)
    payload_2["question_ru"] += " Вторая редакция."
    async with isolated_pg_session_maker() as db:
        service = MlQuestionBankService(db)
        with pytest.raises(MlQuestionBankConflictError, match="supersedes_id"):
            await service.create_draft(
                payload_2,
                idempotency_key=f"test:no-parent:{uuid4().hex}",
                created_by="test-curator",
            )
        draft_2 = await service.create_draft(
            payload_2,
            idempotency_key=f"test:r2:{uuid4().hex}",
            created_by="test-curator",
            supersedes_id=revision_1["id"],
        )
        await _append_required_passes(service, draft_2)

    async def approve_once(actor: str):
        async with isolated_pg_session_maker() as db:
            return await MlQuestionBankService(db).approve(
                draft_2["id"],
                expected_content_hash=draft_2["content_hash"],
                approved_by=actor,
                admin_enabled=True,
            )

    outcomes = await asyncio.gather(
        approve_once("approver-a"),
        approve_once("approver-b"),
        return_exceptions=True,
    )
    assert sum(isinstance(value, dict) for value in outcomes) == 1
    assert (
        sum(isinstance(value, MlQuestionBankConflictError) for value in outcomes) == 1
    )

    async with isolated_pg_session_maker() as db:
        rows = (
            await db.scalars(
                select(MlQuestionRevision)
                .where(MlQuestionRevision.question_key == payload["id"])
                .order_by(MlQuestionRevision.revision_no)
            )
        ).all()
        assert [row.status for row in rows] == ["retired", "approved"]
        assert str(rows[1].supersedes_id) == str(rows[0].id)
        assert rows[0].retired_at is not None
        assert rows[1].approved_at is not None

        with pytest.raises(DBAPIError):
            await db.execute(
                update(MlQuestionRevision)
                .where(MlQuestionRevision.id == rows[1].id)
                .values(approved_by="rewritten-auditor")
            )
            await db.commit()
        await db.rollback()


@pytest.mark.integration
async def test_progress_and_old_active_session_are_bound_to_exact_revision(
    isolated_pg_session_maker,
):
    payload = _unique_payload()
    revision_1 = await _create_approved_revision(isolated_pg_session_maker, payload)
    answered_at = datetime.now(timezone.utc) - timedelta(days=5)

    async with isolated_pg_session_maker() as db:
        user_id = await db.scalar(
            insert(User)
            .values(username=f"mlq_revision_user_{uuid4().hex}")
            .returning(User.id)
        )
        passed_session_id = str(uuid4())
        old_active_session_id = str(uuid4())
        for session_id, status in (
            (passed_session_id, "completed"),
            (old_active_session_id, "active"),
        ):
            await db.execute(
                insert(MlTechnicalSession).values(
                    id=session_id,
                    user_id=user_id,
                    mode="topic",
                    channel="web",
                    topic_id=payload["topic_id"],
                    status=status,
                    created_at=answered_at,
                    closed_at=answered_at if status == "completed" else None,
                )
            )
            await db.execute(
                insert(MlTechnicalSessionItem).values(
                    id=str(uuid4()),
                    user_id=user_id,
                    session_id=session_id,
                    question_id=payload["id"],
                    question_revision_id=revision_1["id"],
                    position=1,
                    status="answered" if status == "completed" else "pending",
                    created_at=answered_at,
                    updated_at=answered_at,
                )
            )
        await db.execute(
            insert(MlTechnicalAttempt).values(
                id=str(uuid4()),
                user_id=user_id,
                session_id=passed_session_id,
                question_id=payload["id"],
                question_revision_id=revision_1["id"],
                topic_id=payload["topic_id"],
                answer_kind="normal",
                answer_language="ru_knowledge",
                raw_answer="Полный ответ для первой редакции.",
                source_channel="web",
                answered_at=answered_at,
                provenance_id=f"ml-question-revision:{revision_1['id']}",
                review={"status": "graded", "score_percent": 100.0},
            )
        )
        await db.commit()

    payload_2 = deepcopy(payload)
    payload_2["question_ru"] += " Новая проверяемая редакция."
    revision_2 = await _create_approved_revision(
        isolated_pg_session_maker,
        payload_2,
        supersedes_id=revision_1["id"],
    )

    async with isolated_pg_session_maker() as db:
        progress = await MlTechnicalService(db).get_progress(int(user_id))
        question_progress = next(
            question
            for topic in progress["topics"]
            for question in topic["questions"]
            if question["question_id"] == payload["id"]
        )
        assert question_progress == {
            **question_progress,
            "question_revision_id": revision_2["id"],
            "unseen": True,
            "attempted": False,
            "attempt_count": 0,
            "latest_pass": False,
            "due_for_repetition": False,
        }
        # submit_answer manages its own short-lived transaction and rejects
        # sessions with an active caller-owned transaction, so use a fresh
        # session from the same isolated pool rather than reusing `db`.
        pass

    async with isolated_pg_session_maker() as fresh_db:
        result = await MlTechnicalService(fresh_db).submit_answer(
            int(user_id),
            session_id=old_active_session_id,
            question_id=payload["id"],
            answer_text="",
            answer_kind=ANSWER_KIND_DONT_KNOW,
            source_channel="web",
        )
        assert result["question_progress"]["question_revision_id"] == revision_2["id"]
        assert result["question_progress"]["unseen"] is True
        assert result["question_progress"]["latest_pass"] is False
        assert result["question_progress"]["due_for_repetition"] is False

    async with isolated_pg_session_maker() as db:
        old_session_attempt = await db.scalar(
            select(MlTechnicalAttempt).where(
                MlTechnicalAttempt.session_id == old_active_session_id
            )
        )
        assert str(old_session_attempt.question_revision_id) == revision_1["id"]
        assert revision_1["id"] != revision_2["id"]
        assert result["question_progress"]["question_revision_id"] == revision_2["id"]
        assert result["question_progress"]["unseen"] is True
        assert result["question_progress"]["latest_pass"] is False
        assert result["question_progress"]["due_for_repetition"] is False

        old_session_attempt = await db.scalar(
            select(MlTechnicalAttempt).where(
                MlTechnicalAttempt.session_id == old_active_session_id
            )
        )
        assert str(old_session_attempt.question_revision_id) == revision_1["id"]
        assert revision_1["id"] != revision_2["id"]


def test_exact_revision_pure_progress_ignores_historical_attempts():
    question = _valid_payload()
    question.update(
        {
            "id": "mltech_revision_scope",
            "question_revision_id": "00000000-0000-0000-0000-000000000002",
        }
    )
    attempts = [
        {
            "question_id": question["id"],
            "question_revision_id": "00000000-0000-0000-0000-000000000001",
            "answered_at": "2026-07-01T00:00:00+00:00",
            "review": {"status": "graded", "score_percent": 100.0},
        }
    ]
    progress = compute_question_progress(question["id"], attempts, [question])
    assert progress["question_revision_id"] == question["question_revision_id"]
    assert progress["unseen"] is True
    assert progress["attempted"] is False
    assert progress["latest_pass"] is False
    assert progress["due_for_repetition"] is False
