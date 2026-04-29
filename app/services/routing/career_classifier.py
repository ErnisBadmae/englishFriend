from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from app.core.config import settings
from app.core.metrics import (
    agent_career_routing_classifier_disagreements_total,
    agent_career_routing_classifier_latency_seconds,
    agent_career_routing_classifier_total,
)
from app.services.ai.llm_provider import LLMEmptyContentError, get_llm_provider
from app.services.routing.goal_routing import score_context_signals

logger = logging.getLogger(__name__)

PrimaryContext = Literal[
    "interviews",
    "workplace_communication",
    "project_walkthrough",
]
ClassifierMode = Literal["off", "shadow", "gate", "mainline"]

_SUPPORTED_PRIMARY_CONTEXTS: tuple[PrimaryContext, ...] = (
    "interviews",
    "workplace_communication",
    "project_walkthrough",
)
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class CareerRoutingSemanticValidation:
    safe: bool
    violations: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "safe": self.safe,
            "violations": list(self.violations),
        }


@dataclass(frozen=True)
class CareerRoutingClassifierResult:
    primary_context: Optional[str]
    secondary_contexts: tuple[str, ...] = ()
    confidence: float = 0.0
    requires_confirmation: bool = True
    explicit_correction_detected: bool = False
    negated_contexts: tuple[str, ...] = ()
    target_role: Optional[str] = None
    domain: Optional[str] = None
    target_market: Optional[str] = None
    intent_action: Optional[str] = None
    audience: Optional[str] = None
    artifact_focus: Optional[str] = None
    job_process_stage: Optional[str] = None
    domain_mentions: tuple[str, ...] = ()
    routing_rationale: Optional[str] = None
    reason_codes: tuple[str, ...] = ()
    evidence_spans: tuple[str, ...] = ()
    classifier_source: Literal["llm", "fallback"] = "llm"
    model_version: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)

    @property
    def ordered_contexts(self) -> tuple[str, ...]:
        values: list[str] = []
        if self.primary_context:
            values.append(self.primary_context)
        values.extend(self.secondary_contexts)
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            normalized = str(value or "").strip().lower()
            if not normalized or normalized in seen:
                continue
            if normalized not in _SUPPORTED_PRIMARY_CONTEXTS:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return tuple(ordered)

    @property
    def semantic_validation(self) -> CareerRoutingSemanticValidation:
        return validate_classifier_semantics(self)

    @property
    def semantic_safe(self) -> bool:
        return self.semantic_validation.safe

    def to_observability_payload(self) -> dict[str, Any]:
        semantic_validation = self.semantic_validation
        return {
            "primary_context": self.primary_context,
            "secondary_contexts": list(self.secondary_contexts),
            "confidence": round(float(self.confidence), 3),
            "requires_confirmation": bool(self.requires_confirmation),
            "explicit_correction_detected": bool(self.explicit_correction_detected),
            "negated_contexts": list(self.negated_contexts),
            "target_role": self.target_role,
            "domain": self.domain,
            "target_market": self.target_market,
            "intent_action": self.intent_action,
            "audience": self.audience,
            "artifact_focus": self.artifact_focus,
            "job_process_stage": self.job_process_stage,
            "domain_mentions": list(self.domain_mentions),
            "routing_rationale": self.routing_rationale,
            "reason_codes": list(self.reason_codes),
            "evidence_spans": list(self.evidence_spans),
            "semantic_validation": semantic_validation.to_payload(),
            "classifier_source": self.classifier_source,
            "model_version": self.model_version,
        }


@dataclass(frozen=True)
class CareerRoutingArbiterDecision:
    goal_brief_update: Optional[dict[str, Any]]
    classifier_result: Optional[CareerRoutingClassifierResult]
    lexical_goal_brief: Optional[dict[str, Any]]
    applied_source: Literal["legacy", "classifier", "fallback"]
    mode: ClassifierMode
    disagreement: bool
    ambiguous_legacy: bool
    applied_classifier: bool
    scope_status: Optional[str] = None
    scoped_gate_applied: bool = False

    def to_observability_payload(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "applied_source": self.applied_source,
            "disagreement": self.disagreement,
            "ambiguous_legacy": self.ambiguous_legacy,
            "applied_classifier": self.applied_classifier,
            "scope_status": self.scope_status,
            "scoped_gate_applied": self.scoped_gate_applied,
            "classifier_semantic_safe": (
                self.classifier_result.semantic_safe if self.classifier_result else None
            ),
            "classifier_semantic_violations": (
                list(self.classifier_result.semantic_validation.violations)
                if self.classifier_result
                else []
            ),
            "goal_brief_update": dict(self.goal_brief_update or {}),
            "classifier_result": (
                self.classifier_result.to_observability_payload()
                if self.classifier_result
                else None
            ),
            "lexical_goal_brief": dict(self.lexical_goal_brief or {}),
        }


def _normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(str(text).lower().split())


def _normalize_context_list(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        normalized = str(value or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        if normalized not in _SUPPORTED_PRIMARY_CONTEXTS:
            continue
        seen.add(normalized)
        out.append(normalized)
    return tuple(out)


def _coerce_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))


def _normalize_slot_value(value: Any) -> Optional[str]:
    text = str(value or "").strip().lower()
    if not text or text in {"null", "none", "unknown", "n/a"}:
        return None
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or None


def _normalize_slot_list(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        normalized = _normalize_slot_value(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return tuple(out)


def _extract_json_payload(text: str) -> dict[str, Any]:
    source = str(text or "").strip()
    if not source:
        raise ValueError("empty classifier response")

    code_match = _JSON_BLOCK_RE.search(source)
    if code_match:
        source = code_match.group(1).strip()

    return json.loads(source)


_INTERVIEW_MARKERS = (
    "interview",
    "mock interview",
    "interviewer",
    "recruiter",
    "hiring process",
    "tell me about yourself",
    "self intro",
    "answer questions",
)
_WORKPLACE_MARKERS = (
    "team",
    "manager",
    "stakeholder",
    "product manager",
    "operations",
    "client",
    "colleague",
    "meeting",
    "standup",
    "status update",
    "workplace",
    "cross functional",
    "non technical",
    "nontechnical",
)
_PROJECT_MARKERS = (
    "project",
    "architecture",
    "tradeoff",
    "trade off",
    "system design",
    "technical story",
    "walkthrough",
    "impact",
    "metric",
    "implementation",
    "pipeline",
    "model",
    "rag",
)
_TARGET_MARKET_ONLY_MARKERS = (
    "job abroad",
    "international company",
    "target market",
    "job search",
    "career move",
    "abroad",
)


def _semantic_blob(*values: Any) -> str:
    parts: list[str] = []
    for value in values:
        if not value:
            continue
        if isinstance(value, (list, tuple, set)):
            parts.extend(str(item or "") for item in value)
        else:
            parts.append(str(value))
    return _normalize_text(" ".join(parts).replace("_", " "))


def _has_any_marker(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def validate_classifier_semantics(
    result: CareerRoutingClassifierResult,
) -> CareerRoutingSemanticValidation:
    """Check whether classifier label agrees with extracted semantic slots."""
    if not result.primary_context:
        return CareerRoutingSemanticValidation(False, ("no_primary_context",))

    slot_blob = _semantic_blob(
        result.intent_action,
        result.audience,
        result.artifact_focus,
        result.job_process_stage,
        result.target_market,
        result.domain_mentions,
        result.reason_codes,
        result.evidence_spans,
    )
    if not any(
        (
            result.intent_action,
            result.audience,
            result.artifact_focus,
            result.job_process_stage,
        )
    ):
        return CareerRoutingSemanticValidation(False, ("missing_semantic_slots",))

    has_interview = _has_any_marker(slot_blob, _INTERVIEW_MARKERS)
    has_workplace = _has_any_marker(slot_blob, _WORKPLACE_MARKERS)
    has_project = _has_any_marker(slot_blob, _PROJECT_MARKERS)
    has_target_market_only = _has_any_marker(slot_blob, _TARGET_MARKET_ONLY_MARKERS)
    intent_blob = _semantic_blob(result.intent_action, result.job_process_stage)
    audience_blob = _semantic_blob(result.audience)

    violations: list[str] = []
    if result.primary_context == "interviews":
        if not has_interview:
            violations.append("interview_without_interview_process")
        if has_target_market_only and not has_interview:
            violations.append("job_market_bias")
    elif result.primary_context == "workplace_communication":
        if not has_workplace:
            violations.append("workplace_without_workplace_audience")
    elif result.primary_context == "project_walkthrough":
        if not has_project:
            violations.append("project_without_project_artifact")
        if has_workplace and not has_project:
            violations.append("audience_ignored")
        if (
            _has_any_marker(audience_blob, _WORKPLACE_MARKERS)
            and _has_any_marker(intent_blob, _WORKPLACE_MARKERS)
        ):
            violations.append("audience_ignored")
        if not has_project and result.domain_mentions:
            violations.append("domain_bias")

    return CareerRoutingSemanticValidation(
        safe=not violations,
        violations=tuple(dict.fromkeys(violations)),
    )


def _build_classifier_prompt(
    *,
    transcript_text: str,
    latest_user_message: str,
    existing_goal_brief: Optional[dict[str, Any]],
) -> tuple[str, str]:
    existing_goal_brief = existing_goal_brief or {}
    system_prompt = """You classify noisy onboarding text for a career-English coach.

Task:
- Extract the user's routing semantics, then infer primary_context.
- Stay inside the allowed schema.
- Do not generate advice.
- Do not invent new labels.

Allowed primary_context / secondary_contexts:
- interviews
- workplace_communication
- project_walkthrough

Meaning of the labels:
- interviews = the user wants interview/recruiter/hiring-process practice.
- workplace_communication = the user wants to speak with team, manager, PM, client, stakeholder, or colleagues at work.
- project_walkthrough = the user wants to explain a concrete project, architecture, tradeoff, metric, or impact story.

Return ONLY valid JSON with this shape:
{
  "primary_context": "interviews|workplace_communication|project_walkthrough|null",
  "secondary_contexts": ["..."],
  "confidence": 0.0,
  "requires_confirmation": true,
  "explicit_correction_detected": false,
  "negated_contexts": ["..."],
  "target_role": "string or null",
  "domain": "string or null",
  "target_market": "string or null",
  "intent_action": "short snake_case action or null",
  "audience": "short snake_case audience or null",
  "artifact_focus": "short snake_case artifact or null",
  "job_process_stage": "short snake_case stage or null",
  "domain_mentions": ["short snake_case domains"],
  "routing_rationale": "one short sentence",
  "reason_codes": ["short snake_case reasons"],
  "evidence_spans": ["short supporting phrases from the user"]
}

Rules:
- Choose exactly one primary_context or null.
- Decide by intent/action first, then audience, then artifact. Role/domain/target_market are metadata only.
- Respect negation like "not interviews".
- If the signal is mixed, pick the most likely primary_context and lower confidence.
- If target_market is unclear but the user is discussing international work/interviews, use "international_company".
- Use null for unknown scalar fields.
- "ML engineer", "AI", "RAG", "model", or "job abroad" alone must NOT force interviews or project_walkthrough.
- If the user wants to explain work to team/manager/stakeholders, prefer workplace_communication even when they mention ML or a project.
- If the user wants to explain a project/architecture/tradeoff/impact story, prefer project_walkthrough even when they mention job abroad.
- Use interviews only when the user asks for interview/recruiter/hiring-process/self-intro practice.

Counterexamples:
- "speaking better in an international team" + "ML engineer job abroad" + "explain work to team" => workplace_communication.
- "explain my ML projects more clearly for an ML engineer job abroad" => project_walkthrough, not interviews.
- "tell me about yourself in ML engineer interviews" => interviews.
"""
    user_message = json.dumps(
        {
            "latest_user_message": latest_user_message,
            "full_user_transcript": transcript_text,
            "existing_goal_brief": existing_goal_brief,
        },
        ensure_ascii=True,
    )
    return system_prompt, user_message


def _sanitize_classifier_payload(
    payload: dict[str, Any],
    *,
    model_version: str,
) -> CareerRoutingClassifierResult:
    primary_context = str(payload.get("primary_context") or "").strip().lower() or None
    if primary_context not in _SUPPORTED_PRIMARY_CONTEXTS:
        primary_context = None

    secondary_contexts = tuple(
        value
        for value in _normalize_context_list(payload.get("secondary_contexts") or [])
        if value != primary_context
    )
    negated_contexts = _normalize_context_list(payload.get("negated_contexts") or [])
    reason_codes = tuple(
        str(value).strip().lower()
        for value in (payload.get("reason_codes") or [])
        if str(value).strip()
    )
    evidence_spans = tuple(
        str(value).strip()
        for value in (payload.get("evidence_spans") or [])
        if str(value).strip()
    )

    target_role = str(payload.get("target_role") or "").strip() or None
    domain = str(payload.get("domain") or "").strip().lower() or None
    target_market = str(payload.get("target_market") or "").strip().lower() or None
    intent_action = _normalize_slot_value(payload.get("intent_action"))
    audience = _normalize_slot_value(payload.get("audience"))
    artifact_focus = _normalize_slot_value(payload.get("artifact_focus"))
    job_process_stage = _normalize_slot_value(payload.get("job_process_stage"))
    domain_mentions = _normalize_slot_list(payload.get("domain_mentions") or [])
    routing_rationale = str(payload.get("routing_rationale") or "").strip() or None

    return CareerRoutingClassifierResult(
        primary_context=primary_context,
        secondary_contexts=secondary_contexts,
        confidence=_coerce_confidence(payload.get("confidence")),
        requires_confirmation=bool(payload.get("requires_confirmation", True)),
        explicit_correction_detected=bool(payload.get("explicit_correction_detected", False)),
        negated_contexts=negated_contexts,
        target_role=target_role,
        domain=domain,
        target_market=target_market,
        intent_action=intent_action,
        audience=audience,
        artifact_focus=artifact_focus,
        job_process_stage=job_process_stage,
        domain_mentions=domain_mentions,
        routing_rationale=routing_rationale,
        reason_codes=reason_codes,
        evidence_spans=evidence_spans,
        classifier_source="llm",
        model_version=model_version,
        raw_payload=dict(payload),
    )


class LLMCareerRoutingClassifier:
    def __init__(self, *, model_version: Optional[str] = None):
        self._llm = get_llm_provider()
        self._model_version = model_version or settings.career_routing_classifier_model_version

    async def classify(
        self,
        *,
        transcript_text: str,
        latest_user_message: str,
        existing_goal_brief: Optional[dict[str, Any]] = None,
    ) -> CareerRoutingClassifierResult:
        system_prompt, user_message = _build_classifier_prompt(
            transcript_text=transcript_text,
            latest_user_message=latest_user_message,
            existing_goal_brief=existing_goal_brief,
        )
        response = await self._llm.generate(
            user_message=user_message,
            system_prompt=system_prompt,
            max_tokens=settings.career_routing_classifier_max_tokens,
        )
        payload = _extract_json_payload(response)
        return _sanitize_classifier_payload(payload, model_version=self._model_version)


async def classify_career_routing(
    *,
    transcript_text: str,
    latest_user_message: str,
    existing_goal_brief: Optional[dict[str, Any]] = None,
) -> Optional[CareerRoutingClassifierResult]:
    if settings.career_routing_classifier_mode == "off":
        return None
    if not transcript_text.strip():
        return None

    started_at = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            LLMCareerRoutingClassifier().classify(
                transcript_text=transcript_text,
                latest_user_message=latest_user_message,
                existing_goal_brief=existing_goal_brief,
            ),
            timeout=settings.career_routing_classifier_timeout_seconds,
        )
        outcome = "classified" if result.primary_context else "no_primary"
        return result
    except asyncio.TimeoutError:
        logger.warning("[CareerRoutingClassifier] Timed out after %.1fs", settings.career_routing_classifier_timeout_seconds)
        outcome = "timeout"
        return None
    except (LLMEmptyContentError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("[CareerRoutingClassifier] Invalid classifier output: %s", exc)
        outcome = "invalid_output"
        return None
    except Exception as exc:
        logger.warning("[CareerRoutingClassifier] Classifier error: %s", exc)
        outcome = "error"
        return None
    finally:
        latency_seconds = time.perf_counter() - started_at
        agent_career_routing_classifier_latency_seconds.labels(source="llm").observe(
            latency_seconds
        )
        agent_career_routing_classifier_total.labels(
            mode=settings.career_routing_classifier_mode,
            outcome=outcome,
            source="llm",
        ).inc()


def _lexical_primary_context(lexical_goal_brief: Optional[dict[str, Any]]) -> Optional[str]:
    contexts = lexical_goal_brief.get("main_contexts") if lexical_goal_brief else None
    if not contexts:
        return None
    primary = str(contexts[0] or "").strip().lower()
    return primary if primary in _SUPPORTED_PRIMARY_CONTEXTS else None


def _is_legacy_ambiguous(
    *,
    lexical_goal_brief: Optional[dict[str, Any]],
    transcript_text: str,
) -> bool:
    if not lexical_goal_brief:
        return True
    primary = _lexical_primary_context(lexical_goal_brief)
    if not primary:
        return True
    scores = score_context_signals(transcript_text)
    positive_scores = sorted(
        (score for score in scores.values() if score > 0),
        reverse=True,
    )
    if not positive_scores:
        return True
    if len(positive_scores) >= 2 and positive_scores[0] == positive_scores[1]:
        return True
    return False


def _build_goal_brief_update_from_classifier(
    result: CareerRoutingClassifierResult,
) -> Optional[dict[str, Any]]:
    contexts = list(result.ordered_contexts)
    if not contexts and not any((result.target_role, result.domain, result.target_market)):
        return None

    update: dict[str, Any] = {
        "routing_decision_source": "classifier_inferred",
        "routing_classifier_source": result.classifier_source,
        "routing_classifier_confidence": round(float(result.confidence), 3),
        "routing_classifier_model_version": result.model_version,
        "routing_classifier_reason_codes": list(result.reason_codes),
        "routing_classifier_evidence_spans": list(result.evidence_spans),
        "routing_classifier_semantic_safe": result.semantic_safe,
        "routing_classifier_semantic_violations": list(
            result.semantic_validation.violations
        ),
    }
    semantic_slots = {
        "intent_action": result.intent_action,
        "audience": result.audience,
        "artifact_focus": result.artifact_focus,
        "job_process_stage": result.job_process_stage,
        "domain_mentions": list(result.domain_mentions),
        "routing_rationale": result.routing_rationale,
    }
    update["routing_classifier_semantic_slots"] = {
        key: value
        for key, value in semantic_slots.items()
        if value not in (None, [], ())
    }
    if contexts:
        update["main_contexts"] = contexts
    if result.target_role:
        update["target_role"] = result.target_role
    if result.domain:
        update["domain"] = result.domain
    if result.target_market:
        update["target_market"] = result.target_market
    return update


def arbitrate_career_routing(
    *,
    existing_goal_brief: Optional[dict[str, Any]],
    lexical_goal_brief: Optional[dict[str, Any]],
    classifier_result: Optional[CareerRoutingClassifierResult],
    transcript_text: str,
    mode: ClassifierMode,
    min_confidence: float,
    scope_status: Optional[str] = None,
) -> CareerRoutingArbiterDecision:
    in_scope = scope_status in (None, "in_scope")
    if mode == "off" or not classifier_result:
        return CareerRoutingArbiterDecision(
            goal_brief_update=lexical_goal_brief,
            classifier_result=classifier_result,
            lexical_goal_brief=lexical_goal_brief,
            applied_source="legacy" if lexical_goal_brief else "fallback",
            mode=mode,
            disagreement=False,
            ambiguous_legacy=_is_legacy_ambiguous(
                lexical_goal_brief=lexical_goal_brief,
                transcript_text=transcript_text,
            ),
            applied_classifier=False,
            scope_status=scope_status,
            scoped_gate_applied=False,
        )

    lexical_primary = _lexical_primary_context(lexical_goal_brief)
    classifier_primary = (
        str(classifier_result.primary_context).strip().lower()
        if classifier_result.primary_context
        else None
    )
    disagreement = bool(
        lexical_primary
        and classifier_primary
        and lexical_primary != classifier_primary
    )
    ambiguous_legacy = _is_legacy_ambiguous(
        lexical_goal_brief=lexical_goal_brief,
        transcript_text=transcript_text,
    )
    if disagreement:
        agent_career_routing_classifier_disagreements_total.labels(mode=mode).inc()

    classifier_update = _build_goal_brief_update_from_classifier(classifier_result)
    semantic_slot_validity = bool(classifier_result.semantic_safe)
    classifier_eligible = bool(
        classifier_update
        and classifier_primary
        and semantic_slot_validity
        and classifier_result.confidence >= min_confidence
    )

    # Plan contract: classifier may only override legacy when scope_status == "in_scope".
    # Out-of-scope or needs_narrowing inputs must never be filled in by the classifier.
    scoped_gate_predicate = bool(
        in_scope
        and ambiguous_legacy
        and classifier_eligible
        and lexical_primary is not None
        and semantic_slot_validity
    )

    if mode == "shadow":
        return CareerRoutingArbiterDecision(
            goal_brief_update=lexical_goal_brief,
            classifier_result=classifier_result,
            lexical_goal_brief=lexical_goal_brief,
            applied_source="legacy" if lexical_goal_brief else "fallback",
            mode=mode,
            disagreement=disagreement,
            ambiguous_legacy=ambiguous_legacy,
            applied_classifier=False,
            scope_status=scope_status,
            scoped_gate_applied=False,
        )

    if mode == "gate":
        if scoped_gate_predicate:
            return CareerRoutingArbiterDecision(
                goal_brief_update=classifier_update,
                classifier_result=classifier_result,
                lexical_goal_brief=lexical_goal_brief,
                applied_source="classifier",
                mode=mode,
                disagreement=disagreement,
                ambiguous_legacy=ambiguous_legacy,
                applied_classifier=True,
                scope_status=scope_status,
                scoped_gate_applied=True,
            )
        return CareerRoutingArbiterDecision(
            goal_brief_update=lexical_goal_brief,
            classifier_result=classifier_result,
            lexical_goal_brief=lexical_goal_brief,
            applied_source="legacy" if lexical_goal_brief else "fallback",
            mode=mode,
            disagreement=disagreement,
            ambiguous_legacy=ambiguous_legacy,
            applied_classifier=False,
            scope_status=scope_status,
            scoped_gate_applied=False,
        )

    if in_scope and classifier_eligible:
        return CareerRoutingArbiterDecision(
            goal_brief_update=classifier_update,
            classifier_result=classifier_result,
            lexical_goal_brief=lexical_goal_brief,
            applied_source="classifier",
            mode=mode,
            disagreement=disagreement,
            ambiguous_legacy=ambiguous_legacy,
            applied_classifier=True,
            scope_status=scope_status,
            scoped_gate_applied=False,
        )

    return CareerRoutingArbiterDecision(
        goal_brief_update=lexical_goal_brief,
        classifier_result=classifier_result,
        lexical_goal_brief=lexical_goal_brief,
        applied_source="legacy" if lexical_goal_brief else "fallback",
        mode=mode,
        disagreement=disagreement,
        ambiguous_legacy=ambiguous_legacy,
        applied_classifier=False,
        scope_status=scope_status,
        scoped_gate_applied=False,
    )
