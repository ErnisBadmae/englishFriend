"""Rubric-based technical reviewer for the `ml_technical` interview track.

This is a narrow LLM analyzer, not a new provider: it calls the existing
`get_llm_provider()` boundary (same as onboarding's `turn_analyzer.py`) and
never invents rubric content — the question's checked-in `rubric_points` and
`reference_explanation_ru` (see `app/data/ml_technical_questions.py`) are the
only authority for what counts as covered/missing/incorrect.

Fail-closed contract: provider errors, timeouts, or schema violations must
never become a pass, a fail, or a zero-knowledge claim. They always produce
`ReviewOutcome(status="needs_review")` with no score.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.config import settings
from app.services.ai.llm_provider import get_llm_provider

logger = logging.getLogger(__name__)

PROMPT_VERSION = "ml-technical-review-v1"
REVIEW_TIMEOUT_SECONDS = 45
_JSON_BLOCK_RE = re.compile(
    r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE
)

REQUIRED_REVIEW_KEYS = (
    "score_percent",
    "covered_points",
    "missing_points",
    "incorrect_claims",
    "feedback",
    "follow_up_question",
    "confidence",
)


@dataclass(frozen=True)
class ReviewOutcome:
    status: str  # "graded" | "needs_review"
    model_id: str
    prompt_version: str = PROMPT_VERSION
    rubric_version: Optional[str] = None
    score_percent: Optional[float] = None
    covered_points: list[str] = field(default_factory=list)
    missing_points: list[str] = field(default_factory=list)
    incorrect_claims: list[str] = field(default_factory=list)
    feedback: Optional[str] = None
    follow_up_question: Optional[str] = None
    confidence: Optional[float] = None
    failure_reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "model_id": self.model_id,
            "prompt_version": self.prompt_version,
            "rubric_version": self.rubric_version,
            "score_percent": self.score_percent,
            "covered_points": list(self.covered_points),
            "missing_points": list(self.missing_points),
            "incorrect_claims": list(self.incorrect_claims),
            "feedback": self.feedback,
            "follow_up_question": self.follow_up_question,
            "confidence": self.confidence,
            "failure_reason": self.failure_reason,
        }


def _model_id() -> str:
    provider_name = settings.llm_provider
    if provider_name == "vllm":
        return settings.vllm_model
    return provider_name


def _needs_review(reason: str) -> ReviewOutcome:
    return ReviewOutcome(
        status="needs_review", model_id=_model_id(), failure_reason=reason
    )


async def review_technical_answer(
    *,
    question: dict[str, Any],
    answer_text: str,
    answer_language: str = "ru_knowledge",
    llm: Any = None,
) -> ReviewOutcome:
    """Grade one founder answer against the question's authoritative rubric.

    Never raises — every failure path returns a `needs_review` outcome.
    """
    model_id = _model_id()
    rubric_version = question.get("rubric_version")

    if not (answer_text or "").strip():
        return ReviewOutcome(
            status="needs_review",
            model_id=model_id,
            rubric_version=rubric_version,
            failure_reason="empty_answer",
        )

    system_prompt = _build_review_prompt(
        question=question, answer_language=answer_language
    )

    try:
        provider = llm or get_llm_provider()
        response = await asyncio.wait_for(
            provider.generate(
                user_message=answer_text,
                system_prompt=system_prompt,
                conversation_history=[],
                max_tokens=700,
            ),
            timeout=REVIEW_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "[MlTechnicalReviewer] provider timed out for question %s",
            question.get("id"),
        )
        return ReviewOutcome(
            status="needs_review",
            model_id=model_id,
            rubric_version=rubric_version,
            failure_reason="provider_timeout",
        )
    except Exception as exc:  # noqa: BLE001 - any provider failure must fail closed
        logger.warning(
            "[MlTechnicalReviewer] provider error for question %s: %s",
            question.get("id"),
            exc,
        )
        return ReviewOutcome(
            status="needs_review",
            model_id=model_id,
            rubric_version=rubric_version,
            failure_reason="provider_error",
        )

    try:
        payload = _extract_json_payload(response or "")
        outcome = _parse_review_payload(
            payload,
            question=question,
            model_id=model_id,
            rubric_version=rubric_version,
        )
    except (
        Exception
    ) as exc:  # noqa: BLE001 - schema violation must fail closed, never a score
        logger.warning(
            "[MlTechnicalReviewer] invalid review payload for question %s: %s",
            question.get("id"),
            exc,
        )
        return ReviewOutcome(
            status="needs_review",
            model_id=model_id,
            rubric_version=rubric_version,
            failure_reason="invalid_schema",
        )

    return outcome


def _build_review_prompt(*, question: dict[str, Any], answer_language: str) -> str:
    rubric_points = question.get("rubric_points") or []
    rubric_lines = "\n".join(
        f"- {point['id']}: {point['point_ru']}" for point in rubric_points
    )
    valid_ids = ", ".join(point["id"] for point in rubric_points)

    return f"""Ты — технический интервьюер по машинному обучению. Оцени ответ founder'а
на вопрос ниже строго по чек-листу обязательных технических пунктов (rubric).
Не придумывай новые критерии и не меняй формулировки пунктов — используй только
их id из списка ниже.

Режим ответа: {answer_language} (русское техническое знание, не оценивай английский язык).

Вопрос:
{question.get('question_ru')}

Обязательные технические пункты рубрики (id: описание):
{rubric_lines}

Эталонное объяснение (для твоей сверки, не показывай его целиком в feedback):
{question.get('reference_explanation_ru')}

Верни ТОЛЬКО компактный JSON без пояснений и без markdown-ограждений:
{{
  "score_percent": 0-100,
  "covered_points": ["<id из списка выше>", ...],
  "missing_points": ["<id из списка выше>", ...],
  "incorrect_claims": ["<короткое описание фактической ошибки на русском>", ...],
  "feedback": "<2-3 предложения на русском: что сильно, чего не хватает>",
  "follow_up_question": "<один уточняющий вопрос интервьюера на русском>",
  "confidence": 0.0-1.0
}}

Допустимые id для covered_points/missing_points: {valid_ids}.
covered_points и missing_points вместе должны покрывать все id рубрики без выдумывания новых id."""


def _extract_json_payload(text: str) -> dict[str, Any]:
    source = str(text or "").strip()
    if not source:
        raise ValueError("empty reviewer response")
    match = _JSON_BLOCK_RE.search(source)
    if match:
        source = match.group(1)
    else:
        start = source.find("{")
        end = source.rfind("}")
        if start != -1 and end != -1 and end > start:
            source = source[start : end + 1]
    return json.loads(source)


def _parse_review_payload(
    payload: dict[str, Any],
    *,
    question: dict[str, Any],
    model_id: str,
    rubric_version: Optional[str],
) -> ReviewOutcome:
    missing_keys = [key for key in REQUIRED_REVIEW_KEYS if key not in payload]
    if missing_keys:
        raise ValueError(f"missing required keys: {missing_keys}")

    valid_point_ids = {point["id"] for point in (question.get("rubric_points") or [])}
    total_points = len(valid_point_ids)

    raw_covered = payload.get("covered_points")
    raw_missing = payload.get("missing_points")

    if not isinstance(raw_covered, list):
        raise ValueError("covered_points must be a JSON array")
    if not isinstance(raw_missing, list):
        raise ValueError("missing_points must be a JSON array")

    # Coerce and validate point IDs — reject any unknown IDs and duplicates
    covered_points: list[str] = []
    for item in raw_covered:
        item_id = str(item).strip()
        if item_id not in valid_point_ids:
            raise ValueError(f"unknown covered_point id: {item_id}")
        if item_id in covered_points:
            raise ValueError(f"duplicate covered_point id: {item_id}")
        covered_points.append(item_id)

    missing_points: list[str] = []
    for item in raw_missing:
        item_id = str(item).strip()
        if item_id not in valid_point_ids:
            raise ValueError(f"unknown missing_point id: {item_id}")
        if item_id in missing_points:
            raise ValueError(f"duplicate missing_point id: {item_id}")
        missing_points.append(item_id)

    # Reject duplicates across covered and missing
    covered_set = set(covered_points)
    missing_set = set(missing_points)

    # Disjoint check: no overlap
    if covered_set & missing_set:
        raise ValueError(
            f"covered_points and missing_points share IDs: {covered_set & missing_set}"
        )

    # Union must equal all valid point IDs exactly
    union_set = covered_set | missing_set
    if union_set != valid_point_ids:
        missing_from_union = valid_point_ids - union_set
        extra_in_union = union_set - valid_point_ids
        details = []
        if missing_from_union:
            details.append(f"missing from partition: {sorted(missing_from_union)}")
        if extra_in_union:
            details.append(f"extra in partition: {sorted(extra_in_union)}")
        raise ValueError(f"rubric partition incomplete: {'; '.join(details)}")

    incorrect_claims = _coerce_string_list(payload.get("incorrect_claims"))
    feedback = str(payload.get("feedback") or "").strip()
    follow_up_question = str(payload.get("follow_up_question") or "").strip()
    raw_confidence = payload.get("confidence")
    if raw_confidence is None:
        confidence = None
    else:
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            raise ValueError("confidence is not a valid number")
        if not (0.0 <= confidence <= 1.0):
            raise ValueError(f"confidence out of range: {confidence}")
    score_percent = _coerce_score(payload.get("score_percent"))

    if score_percent is None:
        raise ValueError("score_percent is not a valid number")
    if not feedback:
        raise ValueError("feedback is empty")
    if not follow_up_question:
        raise ValueError("follow_up_question is empty")

    # Deterministic score: covered/total * 100
    deterministic_score = (
        round(covered_set.__len__() / total_points * 100, 1) if total_points else 0.0
    )

    # Incorrect claims cap: if non-empty, cap below pass threshold (60.0)
    INCORRECT_CLAIMS_CAP = 60.0
    if incorrect_claims:
        deterministic_score = min(deterministic_score, INCORRECT_CLAIMS_CAP - 0.1)

    # Confidence gate: below 0.6 → needs_review
    if confidence is not None and confidence < 0.6:
        return ReviewOutcome(
            status="needs_review",
            model_id=model_id,
            rubric_version=rubric_version,
            failure_reason="low_confidence",
            confidence=confidence,
        )

    return ReviewOutcome(
        status="graded",
        model_id=model_id,
        rubric_version=rubric_version,
        score_percent=deterministic_score,
        covered_points=covered_points,
        missing_points=missing_points,
        incorrect_claims=incorrect_claims,
        feedback=feedback,
        follow_up_question=follow_up_question,
        confidence=confidence,
    )


def _coerce_score(value: Any) -> Optional[float]:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return round(max(0.0, min(100.0, score)), 1)


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
