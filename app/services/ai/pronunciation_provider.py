from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Optional, Protocol

from app.core.config import settings
from app.services.ai.russian_error_detector import (
    PRONUNCIATION_WATCH_WORDS,
    analyze_student_text,
)

logger = logging.getLogger(__name__)


def _clamp_score(value: float, minimum: float = 1.0, maximum: float = 10.0) -> float:
    return round(max(minimum, min(maximum, value)), 1)


@dataclass
class PronunciationWordFeedback:
    word: str
    issue: str
    severity: str
    tip: str


@dataclass
class PronunciationAssessmentResult:
    provider: str
    assessment_mode: str
    overall_score: float
    accuracy_score: float
    fluency_score: float
    prosody_score: Optional[float]
    confidence: float
    notes: str
    recommended_focus: list[str] = field(default_factory=list)
    word_feedback: list[PronunciationWordFeedback] = field(default_factory=list)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["word_feedback"] = [asdict(item) for item in self.word_feedback]
        return payload


class PronunciationProvider(Protocol):
    async def assess(
        self,
        *,
        transcript: str,
        locale: str = "en-US",
        scenario: Optional[str] = None,
        reference_text: Optional[str] = None,
    ) -> PronunciationAssessmentResult:
        """Assess pronunciation-related signal for a transcript or audio-backed provider."""


class HeuristicPronunciationProvider:
    """Text-based pronunciation estimate for the current Vosk -> text pipeline.

    This does not claim acoustic truth. It extracts pronunciation risk signals from
    transcript content so the product can already surface actionable speech feedback,
    while keeping a provider boundary ready for a future audio-backed service.
    """

    provider_name = "heuristic_text"

    async def assess(
        self,
        *,
        transcript: str,
        locale: str = "en-US",
        scenario: Optional[str] = None,
        reference_text: Optional[str] = None,
    ) -> PronunciationAssessmentResult:
        del locale, reference_text  # Reserved for future providers.

        normalized = transcript.strip()
        if not normalized:
            return PronunciationAssessmentResult(
                provider=self.provider_name,
                assessment_mode="text_heuristic",
                overall_score=1.0,
                accuracy_score=1.0,
                fluency_score=1.0,
                prosody_score=None,
                confidence=0.0,
                notes="Not enough transcript to estimate speech quality.",
                recommended_focus=["Produce a fuller spoken answer before judging speech quality."],
                word_feedback=[],
            )

        analysis = analyze_student_text(normalized)
        word_feedback = self._extract_word_feedback(normalized)
        filler_hits = len(re.findall(r"\b(um|uh|er|erm|like)\b", normalized.lower()))
        word_count = len(re.findall(r"\b[a-zA-Z']+\b", normalized))
        sentence_count = max(1, len(re.findall(r"[.!?]", normalized)))
        avg_words_per_sentence = word_count / sentence_count if sentence_count else word_count

        warning_penalty = len(analysis.pronunciation_warnings) * 0.8 + max(0, len(word_feedback) - 1) * 0.4
        short_answer_penalty = 0.7 if word_count < 10 else 0.0
        accuracy_score = _clamp_score(8.7 - warning_penalty - short_answer_penalty)

        fluency_base = 5.1 + min(2.6, word_count / 20)
        fluency_penalty = filler_hits * 0.45
        if avg_words_per_sentence > 28:
            fluency_penalty += 0.5
        fluency_score = _clamp_score(fluency_base - fluency_penalty)

        overall_score = _clamp_score(accuracy_score * 0.65 + fluency_score * 0.35)
        confidence = round(min(0.7, 0.25 + word_count / 100), 2)

        recommended_focus = self._build_focus(
            warnings=analysis.pronunciation_warnings,
            word_feedback=word_feedback,
            scenario=scenario,
        )

        notes = "Text-based pronunciation estimate from transcript patterns and common Russian-speaker risks."

        return PronunciationAssessmentResult(
            provider=self.provider_name,
            assessment_mode="text_heuristic",
            overall_score=overall_score,
            accuracy_score=accuracy_score,
            fluency_score=fluency_score,
            prosody_score=None,
            confidence=confidence,
            notes=notes,
            recommended_focus=recommended_focus,
            word_feedback=word_feedback[:4],
        )

    def _extract_word_feedback(self, transcript: str) -> list[PronunciationWordFeedback]:
        words = set(re.findall(r"\b[a-z]+\b", transcript.lower()))
        feedback: list[PronunciationWordFeedback] = []

        def add_feedback(matches: set[str], issue: str, tip: str, severity: str = "medium") -> None:
            for word in sorted(matches):
                feedback.append(
                    PronunciationWordFeedback(
                        word=word,
                        issue=issue,
                        severity=severity,
                        tip=tip.format(word=word),
                    )
                )

        add_feedback(
            words.intersection(set(PRONUNCIATION_WATCH_WORDS["w_words"])),
            issue="W vs V contrast",
            tip="Round the lips for /w/ in '{word}' instead of using a flat /v/ shape.",
        )
        add_feedback(
            words.intersection(
                set(PRONUNCIATION_WATCH_WORDS["th_voiceless"]) | set(PRONUNCIATION_WATCH_WORDS["th_voiced"])
            ),
            issue="TH articulation",
            tip="Let the tongue come lightly between the teeth in '{word}' before voicing it.",
        )
        add_feedback(
            words.intersection(set(PRONUNCIATION_WATCH_WORDS["final_voiced"])),
            issue="Final voiced consonant",
            tip="Keep the final consonant in '{word}' voiced instead of devoicing it.",
        )
        return feedback[:4]

    def _build_focus(
        self,
        *,
        warnings: list[str],
        word_feedback: list[PronunciationWordFeedback],
        scenario: Optional[str],
    ) -> list[str]:
        focus: list[str] = []
        issue_lookup = {item.issue: item for item in word_feedback}

        if "TH articulation" in issue_lookup:
            sample = issue_lookup["TH articulation"].word
            focus.append(f"Drill TH words like '{sample}' with the tongue slightly between the teeth.")
        if "W vs V contrast" in issue_lookup:
            sample = issue_lookup["W vs V contrast"].word
            focus.append(f"Practice rounded /w/ in words like '{sample}' before your next answer.")
        if "Final voiced consonant" in issue_lookup:
            sample = issue_lookup["Final voiced consonant"].word
            focus.append(f"Keep the voice on the final sound in words like '{sample}'.")

        if not focus and warnings:
            focus.append(warnings[0])

        if scenario == "hr_intro":
            focus.append("Keep interview answers in short, calm chunks so pronunciation stays controlled.")
        elif scenario == "project_walkthrough":
            focus.append("Slow down slightly on technical terms so key architecture words stay crisp.")
        elif scenario == "workplace_communication":
            focus.append("Use short standup-style sentences to keep delivery clear and steady.")
        else:
            focus.append("Use one clear sentence per idea instead of rushing through the whole answer.")

        deduped: list[str] = []
        seen: set[str] = set()
        for item in focus:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped[:3]


def get_pronunciation_provider() -> PronunciationProvider:
    if settings.pronunciation_provider == "azure":
        logger.warning(
            "Azure pronunciation provider is configured but not integrated in this runtime yet. "
            "Falling back to heuristic text assessment."
        )
    return HeuristicPronunciationProvider()
