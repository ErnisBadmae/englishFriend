from __future__ import annotations

import re
from typing import Optional

from app.agent.intent_policy.types import IntentContext, IntentResult, IntentType

TOKEN_RE = re.compile(r"[a-zA-Z']+|\d+")
NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]")
MULTISPACE_RE = re.compile(r"\s+")

FILLER_TOKENS = {
    "a",
    "ah",
    "an",
    "and",
    "as",
    "eh",
    "erm",
    "hmm",
    "i",
    "im",
    "is",
    "just",
    "let",
    "lets",
    "like",
    "mean",
    "mm",
    "my",
    "no",
    "now",
    "of",
    "ok",
    "okay",
    "please",
    "say",
    "sorry",
    "test",
    "the",
    "to",
    "uh",
    "um",
    "well",
    "yeah",
    "yes",
    "you",
    "your",
}
NUMBER_WORDS = {
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
}
SUPPORT_REQUEST_PATTERNS = (
    "my english is bad",
    "my english is very bad",
    "my english is weak",
    "could you teach me",
    "teach me",
    "i can not describe",
    "i cannot describe",
    "i cant describe",
    "i dont know how to say",
    "i don't know how to say",
    "i do not know how to say",
    "i dont know how can i say",
    "i don't know how can i say",
    "i cant explain in english",
    "i can't explain in english",
)
SUPPORT_REQUEST_RU_PATTERNS = (
    "не понял",
    "не поняла",
    "не понимаю",
    "не понятно",
    "непонятно",
    "можешь на русском",
    "можно на русском",
    "по-русски",
    "по русски",
    "объясни",
    "объясните",
    "поясни",
    "что значит",
    "что это значит",
    "как сказать",
    "как будет",
    "помоги",
    "перевед",
)
LEXICAL_CONFUSION_PATTERNS = (
    "what does",
    "what is the meaning",
    "what does it mean",
    "what mean",
    "i dont understand",
    "i don't understand",
    "i do not understand",
    "i dont know this word",
    "i don't know this word",
)
META_PROGRESS_PATTERNS = (
    "let s go",
    "lets go",
    "go on",
    "continue",
    "prepare my program",
    "build my program",
    "waiting that you",
    "just tell",
    "start now",
    "skip",
    "next",
)
END_REQUEST_PATTERNS = (
    "stop",
    "stop here",
    "end session",
    "finish session",
    "i am done",
    "im done",
    "i m done",
    "done for today",
    "that is enough",
)


def normalize_text(text: Optional[str]) -> str:
    source = (text or "").lower().replace("-", " ")
    normalized = NON_ALNUM_RE.sub(" ", source)
    normalized = MULTISPACE_RE.sub(" ", normalized).strip()
    return f" {normalized} " if normalized else ""


def tokenize_text(text: Optional[str]) -> list[str]:
    if not text:
        return []
    return [token.lower() for token in TOKEN_RE.findall(text)]


def classify_fast_intent(text: Optional[str], context: IntentContext) -> Optional[IntentResult]:
    normalized = normalize_text(text)
    tokens = tokenize_text(text)
    if not normalized or not tokens:
        return IntentResult(
            type=IntentType.LOW_SIGNAL_NOISE,
            confidence=0.95,
            reason_codes=["empty_text"],
            normalized_text=normalized,
            matched_anchor_id=context.anchor_question_id,
            needs_composer_hint=context.low_signal_turn_streak >= 1,
            classifier_source="fast_rule",
        )

    if _matches_any(normalized, END_REQUEST_PATTERNS):
        return IntentResult(
            type=IntentType.END_REQUEST,
            confidence=0.96,
            reason_codes=["end_request_pattern"],
            normalized_text=normalized,
            matched_anchor_id=context.anchor_question_id,
            classifier_source="fast_rule",
        )

    if _is_lexical_confusion(normalized):
        return IntentResult(
            type=IntentType.LEXICAL_CONFUSION,
            confidence=0.94,
            reason_codes=["lexical_confusion_pattern"],
            normalized_text=normalized,
            matched_anchor_id=context.anchor_question_id,
            classifier_source="fast_rule",
        )

    if _matches_any(normalized, SUPPORT_REQUEST_PATTERNS):
        return IntentResult(
            type=IntentType.SUPPORT_REQUEST,
            confidence=0.93,
            reason_codes=["support_request_pattern"],
            normalized_text=normalized,
            matched_anchor_id=context.anchor_question_id,
            needs_composer_hint=context.low_signal_turn_streak >= 1,
            classifier_source="fast_rule",
        )

    if _matches_russian_support(text):
        return IntentResult(
            type=IntentType.SUPPORT_REQUEST,
            confidence=0.93,
            reason_codes=["support_request_ru_pattern"],
            normalized_text=normalized,
            matched_anchor_id=context.anchor_question_id,
            needs_composer_hint=context.low_signal_turn_streak >= 1,
            classifier_source="fast_rule",
        )

    if _matches_any(normalized, META_PROGRESS_PATTERNS):
        return IntentResult(
            type=IntentType.META_PROGRESS,
            confidence=0.9,
            reason_codes=["meta_progress_pattern"],
            normalized_text=normalized,
            matched_anchor_id=context.anchor_question_id,
            classifier_source="fast_rule",
        )

    noise_reason_codes = _noise_reason_codes(tokens, context)
    if noise_reason_codes:
        return IntentResult(
            type=IntentType.LOW_SIGNAL_NOISE,
            confidence=0.88,
            reason_codes=noise_reason_codes,
            normalized_text=normalized,
            matched_anchor_id=context.anchor_question_id,
            needs_composer_hint=context.low_signal_turn_streak >= 1,
            classifier_source="fast_rule",
        )

    return None


def _matches_any(normalized_text: str, patterns: tuple[str, ...]) -> bool:
    return any(f" {pattern} " in normalized_text for pattern in patterns)


def _matches_russian_support(text: Optional[str]) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(pattern in lowered for pattern in SUPPORT_REQUEST_RU_PATTERNS)


def _is_lexical_confusion(normalized_text: str) -> bool:
    if _matches_any(normalized_text, LEXICAL_CONFUSION_PATTERNS):
        return True
    return " what does " in normalized_text and " mean " in normalized_text


def _noise_reason_codes(tokens: list[str], context: IntentContext) -> list[str]:
    filler_or_number_hits = sum(
        1 for token in tokens if token in FILLER_TOKENS or token in NUMBER_WORDS or token.isdigit()
    )
    content_tokens = [
        token
        for token in tokens
        if token not in FILLER_TOKENS and token not in NUMBER_WORDS and not token.isdigit()
    ]

    reason_codes: list[str] = []
    if len(content_tokens) < 3:
        reason_codes.append(f"content_tokens_{len(content_tokens)}")
    filler_ratio = filler_or_number_hits / max(len(tokens), 1)
    if filler_ratio > 0.45:
        reason_codes.append(f"filler_ratio_{round(filler_ratio, 2)}")
    if len(set(content_tokens)) <= 2 and len(content_tokens) >= 4:
        reason_codes.append("low_unique_content")
    # A short but meaningful answer stays a real answer after a noisy turn:
    # short answers are normal at A2-B1, so the previous turn must not lower
    # the bar for the current one. The streak still drives composer hints.
    return reason_codes
