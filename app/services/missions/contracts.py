"""Domain contracts for bounded coaching missions.

The contract layer describes what a mission needs from the learner. It does not
own transport, WebSocket state, or prompt templates. A runtime node can use this
module to turn messy learner input into a small deterministic next step.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping, Optional


@dataclass(frozen=True)
class MissionSlot:
    id: str
    label: str
    follow_up_question: str
    signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class MissionContract:
    task_type: str
    label: str
    primary_question: str
    slots: tuple[MissionSlot, ...]
    final_instruction: str


@dataclass(frozen=True)
class MissionTurnDecision:
    response_text: str
    updated_slots: dict[str, str]
    final_requested: bool = False


TECHNICAL_ARTIFACT_SIGNALS = (
    " agent ",
    " api ",
    " app ",
    " automation ",
    " baseline ",
    " classifier ",
    " dashboard ",
    " embedding ",
    " embeddings ",
    " feature ",
    " llm ",
    " model ",
    " pipeline ",
    " rag ",
    " retriever ",
    " retrieval ",
    " service ",
    " system ",
    " tool ",
    " vector ",
    " workflow ",
)


PROJECT_WALKTHROUGH_CONTRACT = MissionContract(
    task_type="technical_project_walkthrough",
    label="one technical project",
    primary_question=(
        "Explain one recent ML or technical project: problem, approach, "
        "metric, and impact."
    ),
    slots=(
        MissionSlot(
            id="problem",
            label="problem or task",
            follow_up_question=(
                "What concrete problem did it solve: search, extraction, Q&A, "
                "compliance, automation, prediction, or another task?"
            ),
            signals=(
                " problem ",
                " goal ",
                " task ",
                " needed ",
                " solve ",
                " solved ",
                " search ",
                " extract ",
                " extraction ",
                " classify ",
                " predict ",
                " detect ",
                " answer questions ",
                " automate ",
                " compliance ",
            ),
        ),
        MissionSlot(
            id="approach",
            label="technical approach",
            follow_up_question=(
                "What was your technical approach: data flow, model choice, "
                "retrieval design, prompts, validation, or deployment?"
            ),
            signals=(
                " built ",
                " build ",
                " created ",
                " create ",
                " developed ",
                " implemented ",
                " used ",
                " designed ",
                " trained ",
                " fine tuned ",
                " deployed ",
            )
            + TECHNICAL_ARTIFACT_SIGNALS,
        ),
        MissionSlot(
            id="metric",
            label="metric or evidence",
            follow_up_question=(
                "What metric or success signal did you use: answer accuracy, "
                "retrieval quality, latency, cost, time saved, or user feedback?"
            ),
            signals=(
                " metric ",
                " accuracy ",
                " precision ",
                " recall ",
                " f1 ",
                " latency ",
                " cost ",
                " evaluation ",
                " eval ",
                " quality ",
                " hit rate ",
                " mrr ",
                " grounded ",
                " hallucination ",
                " time saved ",
                " user feedback ",
            ),
        ),
        MissionSlot(
            id="impact",
            label="impact",
            follow_up_question=(
                "What changed after this project: faster work, fewer manual "
                "checks, better quality, lower cost, or another business impact?"
            ),
            signals=(
                " impact ",
                " result ",
                " improved ",
                " reduced ",
                " increased ",
                " saved ",
                " faster ",
                " fewer ",
                " better ",
                " production ",
                " business ",
                " users ",
                " manual ",
            ),
        ),
    ),
    final_instruction=(
        "Good. Now combine it into 3 interview sentences: problem, approach, "
        "metric, and impact."
    ),
)


MISSION_CONTRACTS: dict[str, MissionContract] = {
    PROJECT_WALKTHROUGH_CONTRACT.task_type: PROJECT_WALKTHROUGH_CONTRACT,
}


ACRONYMS = {
    "ai": "AI",
    "api": "API",
    "cv": "CV",
    "llm": "LLM",
    "ml": "ML",
    "mrr": "MRR",
    "nlp": "NLP",
    "rag": "RAG",
}


def get_mission_contract(task_type: Optional[str]) -> Optional[MissionContract]:
    if not task_type:
        return None
    return MISSION_CONTRACTS.get(task_type)


def plan_mission_turn(
    contract: MissionContract,
    user_text: Optional[str],
    *,
    existing_slots: Optional[Mapping[str, str]] = None,
    final_requested: bool = False,
) -> Optional[MissionTurnDecision]:
    """Return the next deterministic coaching step for a bounded mission."""
    if not (user_text or "").strip():
        return None

    captured_slots = extract_mission_slots(contract, user_text)
    if not captured_slots:
        return None

    updated_slots = dict(existing_slots or {})
    for slot_id in captured_slots:
        updated_slots[slot_id] = "captured"

    missing_slot = _first_missing_slot(contract, updated_slots)
    recast = recast_project_answer(user_text)

    if missing_slot:
        return MissionTurnDecision(
            response_text=_render_missing_slot_prompt(missing_slot, recast=recast, slots=updated_slots),
            updated_slots=updated_slots,
            final_requested=final_requested,
        )

    if not final_requested:
        suffix = f' Start with: "{recast}"' if recast else ""
        return MissionTurnDecision(
            response_text=f"{contract.final_instruction}{suffix}",
            updated_slots=updated_slots,
            final_requested=True,
        )

    return None


def extract_mission_slots(contract: MissionContract, user_text: Optional[str]) -> set[str]:
    normalized = normalize_for_matching(user_text)
    if not normalized.strip():
        return set()

    captured: set[str] = set()
    for slot in contract.slots:
        if any(signal in normalized for signal in slot.signals):
            captured.add(slot.id)

    if _has_purpose_clause(normalized):
        captured.add("problem")

    if _has_metric_value(user_text):
        captured.add("metric")

    return captured


def normalize_for_matching(text: Optional[str]) -> str:
    source = (text or "").lower().replace("-", " ")
    normalized = re.sub(r"[^a-z0-9%.\s]", " ", source)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return f" {normalized} "


def recast_project_answer(text: Optional[str]) -> Optional[str]:
    """Return a light interview-style recast without deciding product state."""
    if not (text or "").strip():
        return None

    source = _repair_common_transcript_noise(text or "")
    match = re.search(
        r"\bi\s+(?:have\s+|ve\s+|'ve\s+)?"
        r"(?P<verb>created|built|developed|implemented|made|designed)\s+"
        r"(?P<body>.+)",
        source,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    body = match.group("body").strip(" .")
    body = _trim_after_sentence_boundary(body)
    body = _format_technical_phrase(body)
    if not body:
        return None

    return f"I built {body}."


def _first_missing_slot(
    contract: MissionContract,
    slots: Mapping[str, str],
) -> Optional[MissionSlot]:
    for slot in contract.slots:
        if not slots.get(slot.id):
            return slot
    return None


def _render_missing_slot_prompt(
    missing_slot: MissionSlot,
    *,
    recast: Optional[str],
    slots: Mapping[str, str],
) -> str:
    if missing_slot.id == "metric" and {"problem", "approach"}.issubset(slots):
        prefix = "Good. You already have the project, task, and approach."
    elif missing_slot.id == "impact" and {"problem", "approach", "metric"}.issubset(slots):
        prefix = "Good. You already have the project, task, approach, and metric."
    else:
        prefix = "Good start."

    recast_part = f' You can say: "{recast}"' if recast else ""
    return f"{prefix}{recast_part} {missing_slot.follow_up_question}"


def _has_purpose_clause(normalized_text: str) -> bool:
    return bool(re.search(r"\b(to|for)\s+[a-z]{3,}", normalized_text.strip()))


def _has_metric_value(text: Optional[str]) -> bool:
    if not text:
        return False
    return bool(re.search(r"\d+(?:\.\d+)?\s*(%|ms|s|sec|seconds?|minutes?|hours?|x)\b", text.lower()))


def _repair_common_transcript_noise(text: str) -> str:
    repaired = text.strip()
    repaired = re.sub(r"\banalys\b", "analyze", repaired, flags=re.IGNORECASE)
    repaired = re.sub(r"\banalyse\b", "analyze", repaired, flags=re.IGNORECASE)
    repaired = re.sub(r"\banalysing\b", "analyzing", repaired, flags=re.IGNORECASE)
    repaired = re.sub(r"\s+", " ", repaired)
    return repaired


def _trim_after_sentence_boundary(text: str) -> str:
    return re.split(r"[.!?]", text, maxsplit=1)[0].strip()


def _format_technical_phrase(text: str) -> str:
    phrase = text.strip(" .")
    if not phrase:
        return ""

    phrase = re.sub(r"\s+", " ", phrase)
    words = [_format_word(word) for word in phrase.split(" ")]
    phrase = " ".join(words)

    first_word = words[0] if words else ""
    first_word_normalized = first_word.lower()
    if first_word_normalized not in {"a", "an", "the"} and first_word in {"AI", "LLM", "ML", "NLP"}:
        phrase = f"an {phrase}"

    return phrase


def _format_word(word: str) -> str:
    stripped = word.strip()
    normalized = stripped.lower().strip(".,:;")
    replacement = ACRONYMS.get(normalized)
    if not replacement:
        return stripped

    return re.sub(re.escape(stripped), replacement, stripped, count=1, flags=re.IGNORECASE)
