"""LLM-backed structured analyzer for onboarding turns.

The analyzer is a port: it interprets messy learner text into a small contract,
but it does not decide product state. Onboarding owns validation and transitions.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
from typing import Any, Literal, Optional

from app.services.ai.llm_provider import get_llm_provider
from app.services.goal_brief_contract import (
    SUPPORTED_GOAL_CONTEXTS,
    SUPPORTED_SCOPE_STATUSES,
    normalize_goal_brief_contexts,
    normalize_scope_status,
)

logger = logging.getLogger(__name__)

AnalyzerNextAction = Literal[
    "ask_goal",
    "ask_target_role",
    "ask_company_context",
    "ask_practice_context",
    "start_first_mission",
]

_SUPPORTED_NEXT_ACTIONS: tuple[str, ...] = (
    "ask_goal",
    "ask_target_role",
    "ask_company_context",
    "ask_practice_context",
    "start_first_mission",
)
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class OnboardingTurnAnalysis:
    scope_status: str
    main_contexts: tuple[str, ...] = ()
    target_role: Optional[str] = None
    domain: Optional[str] = None
    target_market: Optional[str] = None
    next_action: AnalyzerNextAction = "ask_goal"
    confidence: float = 0.0
    rationale: Optional[str] = None

    def to_goal_brief_update(self) -> dict[str, Any]:
        update: dict[str, Any] = {}
        if self.main_contexts:
            update["main_contexts"] = list(self.main_contexts)
        if self.target_role:
            update["target_role"] = self.target_role
        if self.domain:
            update["domain"] = self.domain
        if self.target_market:
            update["target_market"] = self.target_market
        if update:
            update["routing_decision_source"] = "turn_analyzer"
        return update

    def to_observability_payload(self) -> dict[str, Any]:
        return {
            "scope_status": self.scope_status,
            "main_contexts": list(self.main_contexts),
            "target_role": self.target_role,
            "domain": self.domain,
            "target_market": self.target_market,
            "next_action": self.next_action,
            "confidence": round(float(self.confidence), 3),
            "rationale": self.rationale,
        }


async def analyze_onboarding_turn(
    *,
    user_message: str,
    conversation_history: list[dict[str, Any]],
    existing_goal_brief: dict[str, Any],
    llm: Any = None,
) -> Optional[OnboardingTurnAnalysis]:
    if not (user_message or "").strip():
        return None

    provider = llm or get_llm_provider()
    prompt = _build_analyzer_prompt(
        user_message=user_message,
        conversation_history=conversation_history,
        existing_goal_brief=existing_goal_brief,
    )
    try:
        response = await provider.generate(
            user_message=user_message,
            system_prompt=prompt,
            conversation_history=[],
            max_tokens=280,
        )
    except Exception as exc:
        logger.warning("[OnboardingTurnAnalyzer] LLM analysis failed: %s", exc)
        return None

    try:
        payload = _extract_json_payload(response or "")
        return _parse_analysis_payload(payload)
    except Exception as exc:
        logger.warning("[OnboardingTurnAnalyzer] Invalid analyzer payload: %s", exc)
        return None


def _build_analyzer_prompt(
    *,
    user_message: str,
    conversation_history: list[dict[str, Any]],
    existing_goal_brief: dict[str, Any],
) -> str:
    recent_user_turns = [
        str(item.get("content") or "")
        for item in conversation_history[-8:]
        if item.get("role") == "user" and item.get("content")
    ]
    transcript = "\n".join(recent_user_turns + [user_message])
    return f"""You analyze one onboarding turn for English Friend, a career-English coach.

Supported practice contexts:
- interviews
- workplace_communication
- project_walkthrough

Return only compact JSON. Do not write prose.

Rules:
1. If the learner selects a supported context but the target role is missing, use next_action="ask_target_role".
2. "HR interview", "mock interview", "interview prep", and recruiter calls are interviews.
3. Do not invent a specific target role. Use null if unknown.
4. Use scope_status="in_scope" only for career-English goals in the supported contexts.
5. Use confidence below 0.7 if the message is nonsense, off-topic, or too vague.

Existing goal brief:
{json.dumps(existing_goal_brief or {}, ensure_ascii=False)}

Recent learner transcript:
{transcript}

JSON schema:
{{
  "scope_status": "in_scope|needs_narrowing|generic_english_only",
  "main_contexts": ["interviews|workplace_communication|project_walkthrough"],
  "target_role": "string or null",
  "domain": "machine_learning|data_science|software_engineering|professional_communication|null",
  "target_market": "international_company|null",
  "next_action": "ask_goal|ask_target_role|ask_company_context|ask_practice_context|start_first_mission",
  "confidence": 0.0,
  "rationale": "short reason"
}}"""


def _extract_json_payload(text: str) -> dict[str, Any]:
    source = str(text or "").strip()
    if not source:
        raise ValueError("empty analyzer response")
    match = _JSON_BLOCK_RE.search(source)
    if match:
        source = match.group(1)
    return json.loads(source)


def _parse_analysis_payload(payload: dict[str, Any]) -> OnboardingTurnAnalysis:
    scope_status = normalize_scope_status(payload.get("scope_status"))
    if scope_status not in SUPPORTED_SCOPE_STATUSES:
        scope_status = "needs_narrowing"

    contexts = tuple(normalize_goal_brief_contexts(payload.get("main_contexts") or []))
    contexts = tuple(context for context in contexts if context in SUPPORTED_GOAL_CONTEXTS)

    next_action = str(payload.get("next_action") or "ask_goal").strip().lower()
    if next_action not in _SUPPORTED_NEXT_ACTIONS:
        next_action = "ask_goal"

    return OnboardingTurnAnalysis(
        scope_status=scope_status,
        main_contexts=contexts,
        target_role=_clean_optional_text(payload.get("target_role")),
        domain=_clean_optional_text(payload.get("domain")),
        target_market=_clean_optional_text(payload.get("target_market")),
        next_action=next_action,  # type: ignore[arg-type]
        confidence=_coerce_confidence(payload.get("confidence")),
        rationale=_clean_optional_text(payload.get("rationale")),
    )


def _clean_optional_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text or text.lower() in {"none", "null", "unknown", "n/a"}:
        return None
    return text


def _coerce_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))

