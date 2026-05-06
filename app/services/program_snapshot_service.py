from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.core_tables import Correction, Feedback, Session, User
from app.services.goal_brief_contract import (
    goal_brief_missing_labels,
    goal_brief_setup_progress,
    is_goal_brief_routing_ready,
)
from app.services.ai.vocabulary_service import VocabularyService
from app.services.gamification import StreakService, XPService
from app.services.interview_service import build_interview_summary
from app.services.learning_plan_service import LearningPlanService
from app.services.pronunciation_assessment_service import build_pronunciation_summary
from app.services.routing import (
    GoalRoutingProfile,
    build_goal_routing_from_goal_brief,
    resolve_scope_status,
)

_WEAKEST_AREA_MISSIONS: dict[str, dict[str, Any]] = {
    "structure": {
        "mode": "mock_interview",
        "launch_mode": "mock_interview",
        "title": "Run a STAR structure drill",
        "reason": "Structure was the weakest area in your latest interview run.",
        "why_now": "Cleaner structure makes every future interview answer easier to follow and easier to trust.",
        "linked_goal_context": "interviews",
        "linked_skill_gap": "structure",
        "interview_track_id": "hr_intro",
        "from_interview": True,
        "task_type": "hr_intro_drill",
        "expected_outcome": "One tighter STAR-style answer you can reuse in future interviews.",
        "estimated_minutes": 10,
        "success_signal": "Your answer has a clear situation, action, and result.",
    },
    "vocabulary": {
        "mode": "vocabulary_drill",
        "launch_mode": "vocabulary_drill",
        "title": "Reinforce interview vocabulary",
        "reason": "Vocabulary was the weakest area in your latest interview run.",
        "why_now": "Tightening vocabulary now makes the next interview run noticeably easier.",
        "linked_goal_context": "interviews",
        "linked_skill_gap": "professional_vocabulary",
        "interview_track_id": None,
        "from_interview": True,
        "task_type": "vocabulary_reinforcement",
        "expected_outcome": "Stronger recall of role-specific terms in live speaking.",
        "estimated_minutes": 8,
        "success_signal": "You can use at least 3 due words in full answers without hesitation.",
    },
    "accuracy": {
        "mode": "free_conversation",
        "launch_mode": "free_conversation",
        "title": "Run a grammar rescue drill",
        "reason": "Accuracy was the weakest area in your latest interview run.",
        "why_now": "Cleaning up grammar now raises credibility across interviews and workplace communication.",
        "linked_goal_context": "grammar",
        "linked_skill_gap": "grammar_accuracy",
        "interview_track_id": None,
        "from_interview": True,
        "task_type": "grammar_rescue",
        "expected_outcome": "Cleaner sentence control in high-value career answers.",
        "estimated_minutes": 9,
        "success_signal": "The same grammar issue appears less often in your next answer.",
    },
    "confidence": {
        "mode": "mock_interview",
        "launch_mode": "mock_interview",
        "title": "Build confidence with a workplace run",
        "reason": "Confidence was the weakest area in your latest interview run.",
        "why_now": "A shorter workplace-style run lowers pressure while training decisive speaking.",
        "linked_goal_context": "workplace_communication",
        "linked_skill_gap": "confidence",
        "interview_track_id": "workplace_communication",
        "from_interview": True,
        "task_type": "workplace_update_drill",
        "expected_outcome": "A shorter, more decisive workplace-style update.",
        "estimated_minutes": 8,
        "success_signal": "You can explain done / next / blocked without trailing off.",
    },
    "clarity": {
        "mode": "mock_interview",
        "launch_mode": "mock_interview",
        "title": "Practice clearer project explanations",
        "reason": "Clarity was the weakest area in your latest interview run.",
        "why_now": "Sharper project explanations transfer directly to interviews and real work conversations.",
        "linked_goal_context": "project_walkthrough",
        "linked_skill_gap": "clarity",
        "interview_track_id": "project_walkthrough",
        "from_interview": True,
        "task_type": "project_walkthrough_drill",
        "expected_outcome": "One clearer project explanation with trade-offs and impact.",
        "estimated_minutes": 10,
        "success_signal": "You can explain the project in one clean flow without drifting.",
    },
}

_TECHNICAL_FOCUS_MISSIONS: tuple[dict[str, Any], ...] = (
    {
        "patterns": ("trade-off", "tradeoffs", "tradeoffs", "trade off", "trade offs"),
        "mission": {
            "mode": "free_conversation",
            "launch_mode": "free_conversation",
            "title": "Defend one trade-off decision",
            "reason": "You need a cleaner way to justify technical trade-offs under pressure.",
            "why_now": "Trade-off explanations are one of the fastest ways to sound more senior in ML interviews.",
            "linked_goal_context": "project_walkthrough",
            "linked_skill_gap": "tradeoff_explanation",
            "task_type": "tradeoff_explanation_drill",
            "expected_outcome": "One stronger explanation of why you chose one approach over another.",
            "estimated_minutes": 9,
            "success_signal": "You can compare two options and defend the choice with one clear reason.",
        },
    },
    {
        "patterns": ("metric", "metrics", "roc", "auc", "precision", "recall", "f1"),
        "mission": {
            "mode": "free_conversation",
            "launch_mode": "free_conversation",
            "title": "Explain one metric clearly",
            "reason": "You need to explain why a metric matters, not just name it.",
            "why_now": "Metric explanations are a common weak point in ML interviews and project walkthroughs.",
            "linked_goal_context": "project_walkthrough",
            "linked_skill_gap": "metrics_explanation",
            "task_type": "metrics_explainer",
            "expected_outcome": "One clearer metric explanation in simple interview English.",
            "estimated_minutes": 8,
            "success_signal": "You can explain what the metric measures and why you chose it.",
        },
    },
    {
        "patterns": ("model choice", "choose the model", "model selection", "models", "production decision"),
        "mission": {
            "mode": "free_conversation",
            "launch_mode": "free_conversation",
            "title": "Explain one model choice",
            "reason": "You need to explain why you chose one model instead of another.",
            "why_now": "Model-choice explanations connect technical judgment to business impact in interviews.",
            "linked_goal_context": "project_walkthrough",
            "linked_skill_gap": "model_choice",
            "task_type": "model_choice_drill",
            "expected_outcome": "One cleaner explanation of a model decision in interview English.",
            "estimated_minutes": 9,
            "success_signal": "You can explain the baseline, the chosen model, and one reason it fit the task better.",
        },
    },
    {
        "patterns": ("stakeholder", "non-technical", "business impact", "business", "explain to"),
        "mission": {
            "mode": "free_conversation",
            "launch_mode": "free_conversation",
            "title": "Explain the project to a stakeholder",
            "reason": "You need a version of your project story that a non-technical stakeholder can follow.",
            "why_now": "This strengthens both interview communication and real workplace clarity.",
            "linked_goal_context": "workplace_communication",
            "linked_skill_gap": "stakeholder_clarity",
            "task_type": "stakeholder_explanation_drill",
            "expected_outcome": "One simpler explanation of a technical project for a non-technical listener.",
            "estimated_minutes": 8,
            "success_signal": "You can explain the problem, outcome, and business value without drifting into jargon.",
        },
    },
    {
        "patterns": ("failure", "didn't perform", "did not perform", "debug", "debugging", "issue", "incident"),
        "mission": {
            "mode": "free_conversation",
            "launch_mode": "free_conversation",
            "title": "Explain one failure and recovery",
            "reason": "You need a stronger answer for when a model or system did not work as expected.",
            "why_now": "Failure analysis is a high-signal interview skill for ML and production roles.",
            "linked_goal_context": "interviews",
            "linked_skill_gap": "failure_debugging",
            "task_type": "failure_debugging_drill",
            "expected_outcome": "One clearer explanation of the failure, diagnosis, and recovery.",
            "estimated_minutes": 9,
            "success_signal": "You can explain what broke, how you found it, and what changed after the fix.",
        },
    },
    {
        "patterns": ("project", "architecture", "impact", "walkthrough"),
        "mission": {
            "mode": "free_conversation",
            "launch_mode": "free_conversation",
            "title": "Walk through one technical project",
            "reason": "You need one project explanation that is structured, concrete, and easy to follow.",
            "why_now": "Project walkthroughs are reusable across interviews, recruiters, and workplace conversations.",
            "linked_goal_context": "project_walkthrough",
            "linked_skill_gap": "technical_clarity",
            "task_type": "technical_project_walkthrough",
            "expected_outcome": "One clearer project walkthrough with problem, approach, metric, and impact.",
            "estimated_minutes": 10,
            "success_signal": "You can explain one project in one clean flow without losing the listener.",
        },
    },
)


def _mission_payload(
    *,
    mode: str,
    launch_mode: Optional[str],
    title: str,
    reason: str,
    why_now: str,
    linked_goal_context: Optional[str],
    linked_skill_gap: Optional[str],
    task_type: str,
    expected_outcome: str,
    estimated_minutes: int,
    success_signal: str,
    from_interview: bool = False,
    interview_track_id: Optional[str] = None,
    adaptation_reason: Optional[str] = None,
    evidence_source: str = "stage_default",
    repeat_vs_advance: str = "new",
) -> dict[str, Any]:
    return {
        "mode": mode,
        "launch_mode": launch_mode,
        "title": title,
        "reason": reason,
        "why_now": why_now,
        "linked_goal_context": linked_goal_context,
        "linked_skill_gap": linked_skill_gap,
        "from_interview": from_interview,
        "interview_track_id": interview_track_id,
        "task_type": task_type,
        "expected_outcome": expected_outcome,
        "estimated_minutes": estimated_minutes,
        "success_signal": success_signal,
        "adaptation_reason": adaptation_reason,
        "evidence_source": evidence_source,
        "repeat_vs_advance": repeat_vs_advance,
    }


def _pick_technical_focus_mission(
    goal_brief: Optional[dict[str, Any]],
    program_plan: Optional[dict[str, Any]],
    interview_pack: Optional[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    if not goal_brief or goal_brief.get("domain") != "machine_learning":
        return None

    current_stage = (program_plan or {}).get("current_stage")
    if current_stage not in {"foundation", "career_scenarios"}:
        return None
    if current_stage == "career_scenarios" and interview_pack and interview_pack.get("recommended_track"):
        return None
    primary_context = str(((goal_brief or {}).get("main_contexts") or [None])[0] or "").strip().lower()

    weekly_focus = (program_plan or {}).get("weekly_focus") or []
    text_parts = [str(item) for item in weekly_focus]
    if interview_pack:
        text_parts.append(str(interview_pack.get("summary") or ""))
        text_parts.extend(str(item) for item in (interview_pack.get("top_blockers") or []))
        text_parts.extend(str(item) for item in (interview_pack.get("must_answer_questions") or []))
        text_parts.extend(str(item) for item in (interview_pack.get("project_story_prompts") or []))
    focus_text = " ".join(text_parts).lower()

    if primary_context == "workplace_communication":
        if any(pattern in focus_text for pattern in ("failure", "didn't perform", "did not perform", "debug", "issue", "incident")):
            return dict(next(item["mission"] for item in _TECHNICAL_FOCUS_MISSIONS if item["mission"]["task_type"] == "failure_debugging_drill"))
        return dict(next(item["mission"] for item in _TECHNICAL_FOCUS_MISSIONS if item["mission"]["task_type"] == "stakeholder_explanation_drill"))

    for candidate in _TECHNICAL_FOCUS_MISSIONS:
        if any(pattern in focus_text for pattern in candidate["patterns"]):
            return dict(candidate["mission"])
    return None


def build_latest_assessment(roadmap: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not roadmap:
        return None

    profile = roadmap.get("proficiency_profile") or {}
    if profile:
        return {
            "date": roadmap.get("last_assessment"),
            "level": profile.get("cefr_level"),
            "scores": {
                "fluency": profile.get("fluency"),
                "grammar": profile.get("grammar_accuracy"),
                "vocabulary": profile.get("professional_vocabulary"),
                "comprehension": profile.get("listening_comprehension"),
            },
            "notes": profile.get("notes"),
            "confidence": profile.get("confidence"),
            "status": profile.get("status") or ("provisional" if profile.get("provisional") else "confirmed"),
            "provisional": bool(profile.get("provisional")),
            "source": profile.get("source") or "explicit_assessment",
            "goal_readiness": profile.get("goal_readiness"),
            "critical_gaps": profile.get("critical_gaps") or [],
            "skill_axes": {
                "fluency": profile.get("fluency"),
                "grammar_accuracy": profile.get("grammar_accuracy"),
                "listening_comprehension": profile.get("listening_comprehension"),
                "professional_vocabulary": profile.get("professional_vocabulary"),
            },
        }

    history = roadmap.get("assessment_history") or []
    if history:
        latest = history[-1]
        return {
            "date": latest.get("date"),
            "level": latest.get("level"),
            "scores": latest.get("scores") or {},
            "notes": latest.get("notes"),
            "confidence": None,
            "status": "confirmed",
            "provisional": False,
            "source": "explicit_assessment",
            "goal_readiness": None,
            "critical_gaps": [],
            "skill_axes": {},
        }
    return None


def extract_focus_areas(roadmap: Optional[dict[str, Any]], limit: int = 3) -> list[str]:
    if not roadmap:
        return []
    focus_areas = roadmap.get("focus_areas") or []
    result: list[str] = []
    for item in focus_areas:
        if isinstance(item, dict):
            area = item.get("description") or item.get("area")
            if area:
                result.append(str(area))
        elif item:
            result.append(str(item))
    return result[:limit]


def build_setup_state(goal_status: Optional[str], assessment_complete: bool) -> str:
    if goal_status not in {"draft", "confirmed"}:
        return "needs_goal"
    if not assessment_complete:
        return "needs_first_mission"
    return "ready_for_program"


def build_setup_progress(goal_brief: Optional[dict[str, Any]], assessment: Optional[dict[str, Any]]) -> int:
    return goal_brief_setup_progress(
        goal_brief,
        assessment_complete=assessment is not None,
    )


def build_next_question_type(goal_status: Optional[str], assessment: Optional[dict[str, Any]]) -> str:
    if goal_status not in {"draft", "confirmed"}:
        return "goal_setup"
    if not assessment:
        return "mission"
    return "mission"


def build_snapshot_scope_status(goal_brief: Optional[dict[str, Any]]) -> str:
    """Snapshot-side scope_status: routing-ready brief => in_scope, else needs_narrowing.

    Live conversation context is not available at snapshot time, so we deterministically
    derive scope_status from the persisted goal brief. Onboarding owns the live resolution.
    """
    if is_goal_brief_routing_ready(goal_brief):
        return "in_scope"
    return resolve_scope_status(goal_brief=goal_brief)


def _evidence_main_issue_text(item: dict[str, Any]) -> str:
    return str(item.get("main_issue") or "").strip()


def _evidence_weakness_tags(item: dict[str, Any]) -> list[str]:
    raw = item.get("weakness_tags") or []
    if not isinstance(raw, list):
        return []
    return [str(tag).strip() for tag in raw if str(tag).strip()]


def _evidence_improvement_tags(item: dict[str, Any]) -> list[str]:
    raw = item.get("improvement_tags") or []
    if not isinstance(raw, list):
        return []
    return [str(tag).strip() for tag in raw if str(tag).strip()]


def build_recurring_issue(session_evidence: list[dict[str, Any]], window: int = 4) -> Optional[str]:
    """Return a weakness tag (or main_issue) that appears in >= 2 of the last `window` sessions."""
    if not session_evidence:
        return None
    counts: Counter[str] = Counter()
    first_seen: dict[str, str] = {}
    for item in session_evidence[:window]:
        if not isinstance(item, dict):
            continue
        labels: list[str] = []
        main_issue = _evidence_main_issue_text(item)
        if main_issue:
            labels.append(main_issue)
        labels.extend(_evidence_weakness_tags(item))
        seen_in_item: set[str] = set()
        for label in labels:
            key = label.lower()
            if key in seen_in_item:
                continue
            seen_in_item.add(key)
            counts[key] += 1
            first_seen.setdefault(key, label)
    for key, occurrences in counts.most_common():
        if occurrences >= 2:
            return first_seen[key]
    return None


def build_what_improved(session_evidence: list[dict[str, Any]]) -> list[str]:
    """Improvement tags present in the latest session but absent from the prior session."""
    if not session_evidence:
        return []
    latest = session_evidence[0] if isinstance(session_evidence[0], dict) else {}
    previous = session_evidence[1] if len(session_evidence) > 1 and isinstance(session_evidence[1], dict) else {}
    latest_tags = _evidence_improvement_tags(latest)
    previous_tags = {tag.lower() for tag in _evidence_improvement_tags(previous)}
    fresh = [tag for tag in latest_tags if tag.lower() not in previous_tags]
    return fresh[:3]


def build_western_readiness(
    interview_summary: dict[str, Any],
    interview_pack: Optional[dict[str, Any]],
    session_evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Rollup of interview-pack signals + completed career missions, scaled 0-1."""
    completed_runs = int(interview_summary.get("completed_runs") or 0)
    pack_ready = bool(interview_pack)
    career_missions = count_career_missions(session_evidence)
    # Cap each component so a single signal cannot dominate.
    interview_component = min(completed_runs, 3) / 3.0
    pack_component = 1.0 if pack_ready else 0.0
    mission_component = min(career_missions, 5) / 5.0
    score = round(0.5 * interview_component + 0.2 * pack_component + 0.3 * mission_component, 2)
    return {
        "score": score,
        "interview_runs_completed": completed_runs,
        "career_missions_completed": career_missions,
        "interview_pack_ready": pack_ready,
    }


def count_career_missions(session_evidence: list[dict[str, Any]]) -> int:
    career_task_types = {
        "hr_intro_drill",
        "foundation_speaking_drill",
        "stakeholder_explanation_drill",
        "technical_project_walkthrough",
    }
    return sum(
        1
        for item in session_evidence or []
        if isinstance(item, dict) and str(item.get("task_type") or "").lower() in career_task_types
    )


def build_reusable_answers(session_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Polished reusable answers: career-task evidence with an outcome score >= 0.65."""
    polished: list[dict[str, Any]] = []
    seen_summaries: set[str] = set()
    career_task_types = {
        "hr_intro_drill",
        "foundation_speaking_drill",
        "stakeholder_explanation_drill",
        "technical_project_walkthrough",
    }
    for item in session_evidence or []:
        if not isinstance(item, dict):
            continue
        task_type = str(item.get("task_type") or "").lower()
        if task_type not in career_task_types:
            continue
        score_raw = item.get("outcome_score")
        try:
            score = float(score_raw) if score_raw is not None else None
        except (TypeError, ValueError):
            score = None
        if score is None or score < 0.65:
            continue
        summary = str(item.get("summary") or "").strip()
        if not summary or summary.lower() in seen_summaries:
            continue
        seen_summaries.add(summary.lower())
        polished.append(
            {
                "task_type": task_type,
                "summary": summary,
                "outcome_score": score,
            }
        )
        if len(polished) >= 5:
            break
    return polished


def build_value_signals(
    *,
    session_evidence: list[dict[str, Any]],
    reusable_answers: list[dict[str, Any]],
    western_readiness: Optional[dict[str, Any]],
    interview_summary: dict[str, Any],
) -> list[str]:
    """Human-readable proof that the loop is already producing value."""
    signals: list[str] = []
    latest = session_evidence[0] if session_evidence and isinstance(session_evidence[0], dict) else None
    if latest and latest.get("mission_title"):
        signals.append(f"Structured evidence is already saved from {latest['mission_title']}.")

    reusable_count = len(reusable_answers)
    if reusable_count > 0:
        noun = "answer" if reusable_count == 1 else "answers"
        signals.append(f"{reusable_count} reusable {noun} already look strong enough to reuse.")

    completed_runs = int(interview_summary.get("completed_runs") or 0)
    if completed_runs > 0:
        noun = "run" if completed_runs == 1 else "runs"
        signals.append(f"{completed_runs} mock interview {noun} already contribute scored readiness data.")

    readiness = western_readiness or {}
    readiness_score = float(readiness.get("score") or 0)
    readiness_runs = int(readiness.get("interview_runs_completed") or 0)
    readiness_missions = int(readiness.get("career_missions_completed") or 0)
    if readiness_score > 0 and (readiness_runs > 0 or readiness_missions > 0):
        signals.append(f"Western interview readiness is already measurable at {round(readiness_score * 100)}%.")

    return signals[:4]


def build_monetization_state(
    *,
    assessment_complete: bool,
    interview_pack: Optional[dict[str, Any]],
    latest_paid_intent: Optional[dict[str, Any]],
    session_evidence: list[dict[str, Any]],
    reusable_answers: list[dict[str, Any]],
    western_readiness: Optional[dict[str, Any]],
    interview_summary: dict[str, Any],
) -> dict[str, Any]:
    """Drive the paid CTA from value reveal, not from generic engagement."""
    value_signals = build_value_signals(
        session_evidence=session_evidence,
        reusable_answers=reusable_answers,
        western_readiness=western_readiness,
        interview_summary=interview_summary,
    )

    reusable_count = len(reusable_answers)
    completed_runs = int(interview_summary.get("completed_runs") or 0)
    latest = session_evidence[0] if session_evidence and isinstance(session_evidence[0], dict) else None

    cta_reason: Optional[str] = None
    cta_source: Optional[str] = None
    if reusable_count > 0:
        noun = "answer" if reusable_count == 1 else "answers"
        cta_reason = f"You already have {reusable_count} reusable {noun} from real career practice."
        cta_source = "reusable_answers"
    elif completed_runs > 0:
        noun = "run" if completed_runs == 1 else "runs"
        cta_reason = f"You already finished {completed_runs} scored mock interview {noun} and the next mission is adapting from them."
        cta_source = "interview_runs"
    elif latest and latest.get("mission_title"):
        cta_reason = f"You already have structured evidence from {latest['mission_title']} and a concrete next mission."
        cta_source = "first_session_evidence"

    value_visible = bool(cta_reason and value_signals)
    show_paid_cta = bool(
        assessment_complete
        and interview_pack
        and not latest_paid_intent
        and value_visible
    )

    return {
        "show_paid_cta": show_paid_cta,
        "paid_intent_submitted": latest_paid_intent is not None,
        "latest_paid_intent_at": latest_paid_intent.get("submitted_at") if isinstance(latest_paid_intent, dict) else None,
        "latest_paid_intent_context": latest_paid_intent.get("source") if isinstance(latest_paid_intent, dict) else None,
        "value_visible": value_visible,
        "value_signals": value_signals,
        "cta_reason": cta_reason,
        "cta_source": cta_source,
    }


def build_product_signals(
    *,
    setup_state: str,
    session_evidence: list[dict[str, Any]],
    reusable_answers: list[dict[str, Any]],
    western_readiness: Optional[dict[str, Any]],
    interview_summary: dict[str, Any],
    monetization: dict[str, Any],
) -> dict[str, Any]:
    """Expose product-loop state as one backend contract for UI and analytics."""
    career_missions = count_career_missions(session_evidence)
    reusable_answers_count = len(reusable_answers)
    interview_runs_completed = int(interview_summary.get("completed_runs") or 0)
    latest_evidence = session_evidence[0] if session_evidence and isinstance(session_evidence[0], dict) else None
    readiness_score = float((western_readiness or {}).get("score") or 0)

    if setup_state == "needs_goal":
        activation_stage = "goal_not_ready"
    elif career_missions <= 0:
        activation_stage = "first_useful_mission_pending"
    elif career_missions == 1:
        activation_stage = "first_useful_mission_completed"
    else:
        activation_stage = "main_loop_active"

    latest_value_signal: Optional[str] = None
    if reusable_answers_count > 0:
        value_stage = "reusable_answers_visible"
        latest_value_signal = f"{reusable_answers_count} reusable answers are already available."
    elif interview_runs_completed > 0 and readiness_score > 0:
        value_stage = "scored_readiness_visible"
        latest_value_signal = f"Interview readiness is already measurable at {round(readiness_score * 100)}%."
    elif latest_evidence and latest_evidence.get("mission_title"):
        value_stage = "structured_evidence_visible"
        latest_value_signal = f"Structured evidence is already saved from {latest_evidence['mission_title']}."
    else:
        value_stage = "not_visible"

    if monetization.get("paid_intent_submitted"):
        conversion_stage = "paid_intent_submitted"
    elif monetization.get("show_paid_cta"):
        conversion_stage = "ready_for_paid_cta"
    elif monetization.get("value_visible"):
        conversion_stage = "value_visible_not_eligible"
    else:
        conversion_stage = "not_ready"

    if career_missions >= 2:
        retention_stage = "returned_after_first_evidence"
    elif career_missions == 1:
        retention_stage = "awaiting_return_after_first_evidence"
    else:
        retention_stage = "not_applicable_yet"

    if activation_stage == "goal_not_ready":
        next_measurement_focus = "Confirm a concrete career target before measuring product value."
    elif activation_stage == "first_useful_mission_pending":
        next_measurement_focus = "Get the learner through the first useful mission."
    elif retention_stage == "awaiting_return_after_first_evidence":
        next_measurement_focus = "See whether the learner returns for the next mission after first evidence."
    elif conversion_stage == "ready_for_paid_cta":
        next_measurement_focus = "Measure willingness to pay after visible proof of value."
    else:
        next_measurement_focus = "Keep measuring whether evidence turns into stronger reusable interview performance."

    return {
        "activation_stage": activation_stage,
        "value_stage": value_stage,
        "conversion_stage": conversion_stage,
        "retention_stage": retention_stage,
        "completed_career_missions": career_missions,
        "reusable_answers_count": reusable_answers_count,
        "interview_runs_completed": interview_runs_completed,
        "latest_value_signal": latest_value_signal,
        "next_measurement_focus": next_measurement_focus,
    }


def build_improvement_signals(
    interview_summary: dict[str, Any],
    pronunciation_summary: dict[str, Any],
    session_evidence: list[dict[str, Any]],
    latest_assessment: Optional[dict[str, Any]],
    milestones: list[dict[str, Any]],
) -> list[str]:
    signals: list[str] = []

    latest_run = interview_summary.get("latest_run")
    if isinstance(latest_run, dict) and latest_run.get("delta_vs_previous") not in (None, 0):
        delta = float(latest_run["delta_vs_previous"])
        direction = "up" if delta > 0 else "down"
        signals.append(f"Interview score moved {direction} {abs(delta):.1f} vs the previous run.")

    if pronunciation_summary.get("latest_score") is not None:
        latest_score = float(pronunciation_summary["latest_score"])
        focus = (pronunciation_summary.get("focus") or [])
        if focus:
            signals.append(f"Speech signal is {latest_score:.1f}/10; current pronunciation focus: {focus[0]}.")
        else:
            signals.append(f"Speech signal is {latest_score:.1f}/10 from recent spoken answers.")

    latest_evidence = session_evidence[0] if session_evidence else None
    if isinstance(latest_evidence, dict):
        main_issue = latest_evidence.get("main_issue")
        if main_issue:
            signals.append(f"Latest mission surfaced one repeatable issue: {main_issue}.")
        elif latest_evidence.get("summary"):
            signals.append(str(latest_evidence["summary"]))

    completed_milestones = [
        str(item.get("name"))
        for item in milestones
        if isinstance(item, dict) and item.get("done") and item.get("name")
    ]
    if completed_milestones:
        signals.append(f"Completed milestone: {completed_milestones[-1]}.")

    if latest_assessment and latest_assessment.get("goal_readiness") is not None:
        signals.append(f"Current goal readiness sits at {float(latest_assessment['goal_readiness']):.1f}/10.")

    return signals[:4]


def _track_goal_context(track_id: str) -> str:
    return {
        "hr_intro": "interviews",
        "project_walkthrough": "project_walkthrough",
        "workplace_communication": "workplace_communication",
    }.get(track_id, "interviews")


def _track_task_type(track_id: str) -> str:
    return {
        "hr_intro": "hr_intro_drill",
        "project_walkthrough": "project_walkthrough_drill",
        "workplace_communication": "stakeholder_explanation_drill",
    }.get(track_id, "career_mission")


def _track_success_signal(track_id: str) -> str:
    if track_id == "project_walkthrough":
        return "You can explain one project with problem, trade-offs, metric, and impact."
    if track_id == "workplace_communication":
        return "You can explain the project in simple business language for a stakeholder."
    return "You finish with one answer strong enough to reuse in a real interview."


def _apply_track_to_mission(mission: dict[str, Any], track_id: str, track_title: str, reason: str) -> dict[str, Any]:
    updated = dict(mission)
    updated["title"] = f"Run {track_title}"
    updated["reason"] = reason
    updated["interview_track_id"] = track_id
    updated["task_type"] = _track_task_type(track_id)
    updated["linked_goal_context"] = _track_goal_context(track_id)
    updated["success_signal"] = _track_success_signal(track_id)
    return updated


def _evidence_task_type(item: dict[str, Any]) -> str:
    return str(item.get("task_type") or item.get("mission_type") or "").strip()


def _evidence_main_issue(item: dict[str, Any]) -> Optional[str]:
    weakness_tags = [str(tag).strip() for tag in (item.get("weakness_tags") or []) if str(tag).strip()]
    if weakness_tags:
        return weakness_tags[0]
    main_issue = str(item.get("main_issue") or "").strip()
    return main_issue or None


def _evidence_outcome_score(item: dict[str, Any]) -> Optional[float]:
    raw = item.get("outcome_score")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _detect_repeat_vs_advance(
    session_evidence: list[dict[str, Any]] | None,
    mission_type: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    evidence_items = [
        item
        for item in (session_evidence or [])
        if isinstance(item, dict) and _evidence_task_type(item) and _evidence_task_type(item) not in {"assessment", "goal_setup"}
    ]
    if not evidence_items:
        return None

    target_type = mission_type or _evidence_task_type(evidence_items[0])
    relevant = [item for item in evidence_items if _evidence_task_type(item) == target_type][:3]
    if not relevant:
        return None

    latest = relevant[0]
    latest_score = _evidence_outcome_score(latest)
    previous_score = _evidence_outcome_score(relevant[1]) if len(relevant) > 1 else None
    main_issue = _evidence_main_issue(latest) or "the same weak area"

    if latest_score is not None and len(relevant) >= 2 and previous_score is not None:
        if latest_score <= previous_score + 0.02:
            return {
                "decision": "repeat",
                "task_type": target_type,
                "latest_evidence": latest,
                "main_issue": main_issue,
                "reason": f"Repeat {target_type.replace('_', ' ')} because the outcome score is flat and {main_issue} is still visible.",
            }
        if latest_score >= previous_score + 0.1:
            return {
                "decision": "advance",
                "task_type": target_type,
                "latest_evidence": latest,
                "main_issue": main_issue,
                "reason": f"Advance because the latest run improved while {main_issue} stayed trackable.",
            }

    if latest_score is not None and latest_score < 0.52:
        return {
            "decision": "repeat",
            "task_type": target_type,
            "latest_evidence": latest,
            "main_issue": main_issue,
            "reason": f"Repeat {target_type.replace('_', ' ')} because the last run still struggled on {main_issue}.",
        }
    return None


def _build_repeat_mission_from_evidence(adaptation: dict[str, Any]) -> dict[str, Any]:
    latest = dict(adaptation.get("latest_evidence") or {})
    task_type = str(adaptation.get("task_type") or _evidence_task_type(latest) or "guided_speaking_session")
    mode = str(latest.get("mode") or "free_conversation")
    issue = str(adaptation.get("main_issue") or "the same weak area")
    mission_title = str(latest.get("mission_title") or "Repeat the weak-spot drill")
    linked_goal_context = latest.get("linked_goal_context")
    estimated_minutes = int(latest.get("duration_minutes") or 8)

    return _mission_payload(
        mode=mode,
        launch_mode=mode if mode != "guided_setup" else None,
        title=mission_title,
        reason=f"Repeat the same drill and stay narrow around {issue}.",
        why_now="The last two similar runs did not show enough improvement yet.",
        linked_goal_context=linked_goal_context,
        linked_skill_gap=issue,
        task_type=task_type,
        expected_outcome=f"One tighter repetition of {task_type.replace('_', ' ')} with the same weak spot made explicit.",
        estimated_minutes=max(6, estimated_minutes),
        success_signal=str(latest.get("adaptation_hint") or f"The next run shows less of {issue}."),
        interview_track_id=latest.get("interview_track_id"),
        adaptation_reason=str(adaptation.get("reason") or f"Repeating because {issue} is still visible."),
        evidence_source="repeated_main_issue",
        repeat_vs_advance="repeat",
    )


def _apply_adaptation_metadata(
    mission: dict[str, Any],
    *,
    adaptation_reason: Optional[str],
    evidence_source: str,
    repeat_vs_advance: str,
) -> dict[str, Any]:
    updated = dict(mission)
    updated["adaptation_reason"] = adaptation_reason
    updated["evidence_source"] = evidence_source
    updated["repeat_vs_advance"] = repeat_vs_advance
    return updated


def _build_evidence_binding(
    session_evidence: list[dict[str, Any]] | None,
    advance_reason: Optional[str],
) -> tuple[Optional[str], str, str]:
    """Return (adaptation_reason, evidence_source, repeat_vs_advance) for stage-default branches.

    Guarantee: when session_evidence is non-empty, adaptation_reason is non-empty and
    evidence_source references the most recent weakness or improvement when available.
    """
    if advance_reason:
        return advance_reason, "stage_default", "advance"
    items = [item for item in (session_evidence or []) if isinstance(item, dict)]
    if not items:
        return None, "stage_default", "new"
    latest = items[0]
    improvement_tags = _evidence_improvement_tags(latest)
    main_issue = _evidence_main_issue(latest)
    if improvement_tags:
        return (
            f"Carrying forward last session's improvement: {improvement_tags[0]}.",
            "latest_improvement",
            "advance",
        )
    if main_issue:
        return (
            f"Last session's main issue stayed visible: {main_issue}.",
            "latest_weakness",
            "new",
        )
    summary = str(latest.get("summary") or "").strip()
    if summary:
        return (
            f"Building on the latest session: {summary}",
            "latest_summary",
            "new",
        )
    return (
        "Continuing from the last completed session.",
        "latest_session",
        "new",
    )


def _is_entry_main_loop_mission(
    *,
    current_stage: Optional[str],
    interview_runs_count: int,
    session_evidence: list[dict[str, Any]] | None,
) -> bool:
    if current_stage not in {"foundation", "career_scenarios", "target_role_simulation"}:
        return False
    if interview_runs_count > 0:
        return False

    evidence_items = [
        item for item in (session_evidence or [])
        if isinstance(item, dict)
    ]
    return not any(
        str(item.get("mission_type") or "").strip() not in {"assessment", "guided_setup"}
        for item in evidence_items
    )


def _build_entry_main_loop_mission(
    goal_brief: dict[str, Any],
    program_plan: Optional[dict[str, Any]],
    error_patterns: list[dict[str, Any]],
) -> dict[str, Any]:
    """Pick the first main-loop mission using the canonical routing profile."""
    weekly_focus = (program_plan or {}).get("weekly_focus") or []
    profile = build_goal_routing_from_goal_brief(goal_brief)

    if profile.first_mission_task_type == "stakeholder_explanation_drill":
        return _mission_payload(
            mode="free_conversation",
            launch_mode="free_conversation",
            title="Explain the project to a stakeholder",
            reason=weekly_focus[0] if weekly_focus else "Start with the workplace scenario that matters most right now.",
            why_now="Your first main-loop mission should match the workplace context you prioritized in onboarding.",
            linked_goal_context="workplace_communication",
            linked_skill_gap="stakeholder_clarity",
            task_type="stakeholder_explanation_drill",
            expected_outcome="One clear stakeholder-friendly explanation of your work.",
            estimated_minutes=8,
            success_signal="You can explain the project in simple business language for a stakeholder.",
        )

    if profile.first_mission_task_type == "technical_project_walkthrough":
        return _mission_payload(
            mode="free_conversation",
            launch_mode="free_conversation",
            title="Walk through one technical project",
            reason=weekly_focus[0] if weekly_focus else "Start with the project story that best proves your technical value.",
            why_now="Your first main-loop mission should match the project walkthrough context you prioritized in onboarding.",
            linked_goal_context="project_walkthrough",
            linked_skill_gap="technical_clarity",
            task_type="technical_project_walkthrough",
            expected_outcome="One clear project walkthrough with problem, approach, metric, and impact.",
            estimated_minutes=10,
            success_signal="You can explain one project in one clean flow without losing the listener.",
        )

    return _mission_payload(
        mode="free_conversation",
        launch_mode="free_conversation",
        title="Run an interview-aligned foundation speaking drill",
        reason=weekly_focus[0] if weekly_focus else "Start with a lower-pressure answer about your background and fit.",
        why_now="Your first main-loop mission should stay low-pressure while building toward interview speaking.",
        linked_goal_context="interviews",
        linked_skill_gap="grammar_accuracy" if error_patterns else "fluency",
        task_type="foundation_speaking_drill",
        expected_outcome="One cleaner interview-aligned answer about your background, fit, or motivation.",
        estimated_minutes=9,
        success_signal="You can answer a simple interview question in English with fewer corrections and clearer delivery.",
    )


def _build_first_useful_mission_without_assessment(
    goal_brief: dict[str, Any],
    program_plan: Optional[dict[str, Any]],
    error_patterns: list[dict[str, Any]],
) -> dict[str, Any]:
    """Pick the first useful mission strictly from ``primary_context``.

    Mapping is owned by :mod:`app.services.routing.goal_routing` so
    ``recommended_track_id`` and ``first_mission_task_type`` cannot drift.
    Domain and secondary contexts influence wording only — never the task type.
    """
    weekly_focus = (program_plan or {}).get("weekly_focus") or []
    profile = build_goal_routing_from_goal_brief(goal_brief)
    return _first_mission_payload_for_profile(
        profile,
        weekly_focus=weekly_focus,
        error_patterns=error_patterns,
    )


def _first_mission_payload_for_profile(
    profile: GoalRoutingProfile,
    *,
    weekly_focus: list[Any],
    error_patterns: list[dict[str, Any]],
) -> dict[str, Any]:
    task_type = profile.first_mission_task_type

    if task_type == "stakeholder_explanation_drill":
        return _mission_payload(
            mode="free_conversation",
            launch_mode="free_conversation",
            title="Explain the project to a stakeholder",
            reason=weekly_focus[0] if weekly_focus else "Start with one concrete explanation of your work for a non-technical listener.",
            why_now="The fastest way to create a first win is a clearer explanation of what you already do. The coach will also estimate your speaking baseline from this real task.",
            linked_goal_context="workplace_communication",
            linked_skill_gap="stakeholder_clarity",
            task_type="stakeholder_explanation_drill",
            expected_outcome="One simpler stakeholder-friendly explanation of your work that already sounds more reusable.",
            estimated_minutes=8,
            success_signal="You can explain the problem, your contribution, and the business value without collapsing into jargon.",
        )

    if task_type == "technical_project_walkthrough":
        return _mission_payload(
            mode="free_conversation",
            launch_mode="free_conversation",
            title="Walk through one technical project",
            reason=weekly_focus[0] if weekly_focus else "Start with the project answer that best proves your value.",
            why_now="The fastest way to create a first career-English win is a clearer project answer. The coach will also capture a working baseline from this real mission.",
            linked_goal_context="project_walkthrough",
            linked_skill_gap="technical_clarity",
            task_type="technical_project_walkthrough",
            expected_outcome="One clearer project walkthrough with problem, approach, metric, and impact.",
            estimated_minutes=10,
            success_signal="You can explain one project in one clean flow with less drift and more concrete value.",
        )

    return _mission_payload(
        mode="free_conversation",
        launch_mode="free_conversation",
        title="Run an interview-aligned foundation speaking drill",
        reason=weekly_focus[0] if weekly_focus else "Start with one lower-pressure answer about your background and fit.",
        why_now="You still need a first useful speaking win, but the coach can estimate the baseline from a real answer instead of a separate test.",
        linked_goal_context="interviews",
        linked_skill_gap="grammar_accuracy" if error_patterns else "fluency",
        task_type="foundation_speaking_drill",
        expected_outcome="One cleaner career-aligned answer you can already reuse in future speaking practice.",
        estimated_minutes=9,
        success_signal="You can answer a simple career question in English with fewer corrections and clearer delivery.",
    )


_MISSION_CHOICE_OVERRIDES: dict[str, dict[str, Any]] = {
    "mock_interview": {
        "mode": "mock_interview",
        "launch_mode": "mock_interview",
        "title": "Mock interview practice",
        "reason": "You chose to try a mock interview to build real interview confidence.",
        "why_now": "You signalled at the end of your last session that a mock interview would be more useful right now.",
        "linked_goal_context": "interviews",
        "linked_skill_gap": None,
        "task_type": "mock_interview_prep",
        "expected_outcome": "One realistic interview answer delivered under pressure.",
        "estimated_minutes": 10,
        "success_signal": "You answered the interview question in under 90 seconds with a clear structure.",
        "adaptation_reason": "User chose mock interview at end of previous session.",
        "evidence_source": "user_choice",
        "repeat_vs_advance": "new",
    },
    "interview_intro": {
        "mode": "foundation_speaking_drill",
        "launch_mode": "foundation_speaking_drill",
        "title": "Self-introduction drill",
        "reason": "You chose to sharpen your interview self-introduction.",
        "why_now": "You signalled at the end of your last session that you want to work on your self-introduction.",
        "linked_goal_context": "interviews",
        "linked_skill_gap": "fluency",
        "task_type": "foundation_speaking_drill",
        "expected_outcome": "A cleaner tell-me-about-yourself answer you can reuse in interviews.",
        "estimated_minutes": 9,
        "success_signal": "You can introduce yourself in English in under 60 seconds with clear structure.",
        "adaptation_reason": "User chose self-introduction drill at end of previous session.",
        "evidence_source": "user_choice",
        "repeat_vs_advance": "new",
    },
}


def _build_mission_choice_override(choice: str) -> Optional[dict[str, Any]]:
    payload = _MISSION_CHOICE_OVERRIDES.get(choice)
    if payload:
        return dict(payload)
    return None


def recommend_next_mission(
    goal_brief: Optional[dict[str, Any]],
    program_plan: Optional[dict[str, Any]],
    due_count: int,
    error_patterns: list[dict[str, Any]],
    has_assessment: bool,
    weakest_interview_area: Optional[str] = None,
    interview_pack: Optional[dict[str, Any]] = None,
    session_evidence: list[dict[str, Any]] | None = None,
    interview_runs_count: int = 0,
) -> dict[str, Any]:
    adaptation = _detect_repeat_vs_advance(session_evidence)
    advance_reason = (
        adaptation.get("reason")
        if adaptation and adaptation.get("decision") == "advance"
        else None
    )
    evidence_reason, evidence_source, evidence_decision = _build_evidence_binding(
        session_evidence,
        advance_reason,
    )

    if not goal_brief or goal_brief.get("status") not in {"draft", "confirmed"}:
        missing = goal_brief_missing_labels(goal_brief, mode="routing")
        why_now = "The coach still needs a concrete role and context before it can build a useful program."
        if missing:
            why_now = f"Missing: {', '.join(missing)}."
        return _mission_payload(
            mode="guided_setup",
            launch_mode=None,
            title="Complete your goal setup",
            reason="Turn your goal into a clear career-English target.",
            why_now=why_now,
            linked_goal_context="goal_setup",
            linked_skill_gap=None,
            task_type="goal_setup",
            expected_outcome="A confirmed goal brief with role, context, and timeline.",
            estimated_minutes=4,
            success_signal="Your target role, company context, and practice situations are locked in.",
        )

    # Honor user's mission preference captured at end of previous session.
    # Stored in session_evidence[0]["next_mission_choice"]; self-expires when new evidence pushes it to index 1+.
    if session_evidence:
        _override = (session_evidence[0] or {}).get("next_mission_choice")
        if _override:
            _override_mission = _build_mission_choice_override(_override)
            if _override_mission:
                return _override_mission

    if not has_assessment:
        return _build_first_useful_mission_without_assessment(
            goal_brief=goal_brief,
            program_plan=program_plan,
            error_patterns=error_patterns,
        )

    if weakest_interview_area and weakest_interview_area in _WEAKEST_AREA_MISSIONS:
        mission = dict(_WEAKEST_AREA_MISSIONS[weakest_interview_area])
        mission["adaptation_reason"] = f"Latest interview evidence says {weakest_interview_area.replace('_', ' ')} is still the main weak spot."
        mission["evidence_source"] = "last_session_weakness"
        mission["repeat_vs_advance"] = "new"
        return mission

    current_stage = (program_plan or {}).get("current_stage")
    if adaptation and adaptation.get("decision") == "repeat":
        return _build_repeat_mission_from_evidence(adaptation)

    if _is_entry_main_loop_mission(
        current_stage=current_stage,
        interview_runs_count=interview_runs_count,
        session_evidence=session_evidence,
    ):
        mission = _build_entry_main_loop_mission(
            goal_brief=goal_brief,
            program_plan=program_plan,
            error_patterns=error_patterns,
        )
        if evidence_reason:
            mission = _apply_adaptation_metadata(
                mission,
                adaptation_reason=evidence_reason,
                evidence_source=evidence_source,
                repeat_vs_advance=evidence_decision,
            )
        return mission

    technical_focus_mission = _pick_technical_focus_mission(
        goal_brief=goal_brief,
        program_plan=program_plan,
        interview_pack=interview_pack,
    )
    if technical_focus_mission:
        mission = _mission_payload(
            **technical_focus_mission,
            adaptation_reason=evidence_reason,
            evidence_source=evidence_source,
            repeat_vs_advance=evidence_decision,
        )
        return mission

    weekly_focus = (program_plan or {}).get("weekly_focus") or []
    if (
        interview_pack
        and current_stage in {"career_scenarios", "target_role_simulation"}
        and interview_pack.get("recommended_track")
    ):
        track_id = str(interview_pack.get("recommended_track"))
        track_title = str(interview_pack.get("recommended_track_title") or "Career Mission")
        blockers = interview_pack.get("top_blockers") or []
        mission_title = f"Run {track_title}"
        reason = str(
            interview_pack.get("summary")
            or (weekly_focus[0] if weekly_focus else "Practice the most likely interview theme for your target role.")
        )
        why_now = "This is the most interview-relevant speaking drill for your current target role and vacancy context."
        if blockers:
            why_now = f"Main blocker right now: {blockers[0]}"
        mission = _apply_track_to_mission(_mission_payload(
            mode="mock_interview",
            launch_mode="mock_interview",
            title=mission_title,
            reason=reason,
            why_now=why_now,
            linked_goal_context=_track_goal_context(track_id),
            linked_skill_gap=None,
            task_type=_track_task_type(track_id),
            expected_outcome="One stronger answer for the most likely interview scenario.",
            estimated_minutes=10,
            success_signal=_track_success_signal(track_id),
            interview_track_id=track_id,
            adaptation_reason=evidence_reason,
            evidence_source=evidence_source,
            repeat_vs_advance=evidence_decision,
        ), track_id, track_title, reason)
        return mission

    if due_count >= 5:
        return _mission_payload(
            mode="vocabulary_drill",
            launch_mode="vocabulary_drill",
            title="Clear your review queue",
            reason=f"You have {due_count} vocabulary cards due right now.",
            why_now="Keeping recall fresh prevents new practice from collapsing under forgotten vocabulary.",
            linked_goal_context="vocabulary",
            linked_skill_gap="professional_vocabulary",
            task_type="vocabulary_reinforcement",
            expected_outcome=f"At least {min(5, due_count)} due words reinforced in context.",
            estimated_minutes=7,
            success_signal="Your due queue shrinks and the same words feel easier in live speaking.",
            adaptation_reason=evidence_reason,
            evidence_source=evidence_source,
            repeat_vs_advance=evidence_decision,
        )

    if current_stage == "foundation":
        return _mission_payload(
            mode="free_conversation",
            launch_mode="free_conversation",
            title="Run a foundation speaking drill",
            reason=weekly_focus[0] if weekly_focus else "Stabilize grammar and fluency before higher-pressure scenarios.",
            why_now="Your baseline says the fastest path forward is cleaner spoken English under low pressure.",
            linked_goal_context="foundation",
            linked_skill_gap="grammar_accuracy" if error_patterns else "fluency",
            task_type="foundation_speaking_drill",
            expected_outcome="One cleaner career-related answer with fewer avoidable slips.",
            estimated_minutes=9,
            success_signal="You can answer in English with fewer corrections and clearer delivery.",
            adaptation_reason=evidence_reason,
            evidence_source=evidence_source,
            repeat_vs_advance=evidence_decision,
        )

    if current_stage in {"career_scenarios", "target_role_simulation"}:
        return _mission_payload(
            mode="mock_interview",
            launch_mode="mock_interview",
            title="Run one career mission",
            reason=weekly_focus[0] if weekly_focus else "Career-focused speaking is your highest-leverage next step.",
            why_now="The current stage of the program is about practicing real work and interview situations, not generic chatting.",
            linked_goal_context=(goal_brief.get("main_contexts") or ["interviews"])[0],
            linked_skill_gap=weakest_interview_area,
            task_type="career_mission",
            expected_outcome="One realistic career scenario completed with score and next focus.",
            estimated_minutes=10,
            success_signal="You finish one track with concrete feedback and a clearer next step.",
            adaptation_reason=evidence_reason,
            evidence_source=evidence_source,
            repeat_vs_advance=evidence_decision,
        )

    if error_patterns:
        return _mission_payload(
            mode="free_conversation",
            launch_mode="free_conversation",
            title="Do a grammar rescue session",
            reason=f"Your most frequent issue right now is {error_patterns[0]['label']}.",
            why_now="Cleaning up the most common error gives immediate lift across all future speaking tasks.",
            linked_goal_context="grammar",
            linked_skill_gap=error_patterns[0]["label"],
            task_type="grammar_rescue",
            expected_outcome="Fewer repeats of the most common spoken error.",
            estimated_minutes=8,
            success_signal="That same grammar issue appears less often in the next mission.",
            adaptation_reason=evidence_reason,
            evidence_source=evidence_source,
            repeat_vs_advance=evidence_decision,
        )

    return _mission_payload(
        mode=(program_plan or {}).get("preferred_mode") or "free_conversation",
        launch_mode=(program_plan or {}).get("preferred_mode") or "free_conversation",
        title="Do a focused speaking session",
        reason=weekly_focus[0] if weekly_focus else "You are ready for another guided practice session.",
        why_now="This keeps momentum on the current stage of your program.",
        linked_goal_context=(goal_brief.get("main_contexts") or ["general_fluency"])[0],
        linked_skill_gap=None,
        task_type="guided_speaking_session",
        expected_outcome="One useful practice repetition tied to your current stage.",
        estimated_minutes=8,
        success_signal="You finish with one clearer improvement target for the next session.",
        adaptation_reason=evidence_reason,
        evidence_source=evidence_source,
        repeat_vs_advance=evidence_decision,
    )


class ProgramSnapshotService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.learning_plan_service = LearningPlanService(db)
        self.vocabulary_service = VocabularyService(db)
        self.xp_service = XPService(db)
        self.streak_service = StreakService(db)

    async def get_snapshot(self, user_id: int) -> Optional[dict[str, Any]]:
        user = await self.db.get(User, user_id)
        if not user:
            return None

        plan = await self.learning_plan_service.get_or_create_plan(user_id)
        roadmap = plan.roadmap or {}
        goal_brief = self.learning_plan_service.get_goal_brief(plan)
        program_plan = self.learning_plan_service.get_program_plan(plan)
        career_context = self.learning_plan_service.get_career_context(plan)
        interview_pack = self.learning_plan_service.get_interview_pack(plan)
        project_story_pack = self.learning_plan_service.get_project_story_pack(plan)
        interview_runs = roadmap.get("interview_runs") or []

        vocabulary_stats = await self.vocabulary_service.get_vocabulary_stats(user_id)
        due_cards = await self.vocabulary_service.get_due_cards(user_id, limit=5)
        xp_info = await self.xp_service.get_level_info(user_id)
        streak_info = await self.streak_service.get_streak_info(user_id)
        error_patterns = await self._get_top_error_patterns(user_id)
        recent_sessions = await self._get_recent_sessions(user_id)
        total_sessions = await self._get_total_sessions(user_id)
        session_evidence = self.learning_plan_service.get_session_evidence(plan)

        latest_assessment = build_latest_assessment(roadmap)
        goal = self.learning_plan_service.get_goal(plan)
        weakest_interview_area = roadmap.get("weakest_interview_area")
        interview_summary = build_interview_summary(
            interview_runs,
            goal=goal,
            main_contexts=(goal_brief or {}).get("main_contexts") or [],
        )
        interview_summary["weakest_area"] = weakest_interview_area
        interview_summary["interview_focus"] = roadmap.get("interview_focus") or []
        interview_summary["last_track"] = roadmap.get("last_interview_track")
        pronunciation_summary = build_pronunciation_summary(roadmap.get("pronunciation_assessments") or [])

        mission = recommend_next_mission(
            goal_brief=goal_brief,
            program_plan=program_plan,
            due_count=vocabulary_stats["due_now"],
            error_patterns=error_patterns,
            has_assessment=latest_assessment is not None,
            weakest_interview_area=weakest_interview_area,
            interview_pack=interview_pack,
            session_evidence=session_evidence,
            interview_runs_count=len(interview_runs),
        )
        if mission["mode"] == "mock_interview" and not mission.get("from_interview"):
            recommended_track = interview_summary["recommended_track"]
            mission = _apply_track_to_mission(
                mission,
                recommended_track["id"],
                recommended_track["title"],
                recommended_track["subtitle"],
            )

        goal_status = (goal_brief or {}).get("status")
        goal_complete = self.learning_plan_service.is_goal_setup_complete(plan)
        assessment_complete = latest_assessment is not None
        setup_state = build_setup_state(goal_status, assessment_complete)
        setup_progress = build_setup_progress(goal_brief, latest_assessment)
        next_question_type = build_next_question_type(goal_status, latest_assessment)
        latest_paid_intent = roadmap.get("latest_paid_intent")
        western_readiness = build_western_readiness(
            interview_summary=interview_summary,
            interview_pack=interview_pack,
            session_evidence=session_evidence,
        )
        reusable_answers = build_reusable_answers(session_evidence)
        monetization = build_monetization_state(
            assessment_complete=assessment_complete,
            interview_pack=interview_pack,
            latest_paid_intent=latest_paid_intent if isinstance(latest_paid_intent, dict) else None,
            session_evidence=session_evidence,
            reusable_answers=reusable_answers,
            western_readiness=western_readiness,
            interview_summary=interview_summary,
        )
        product_signals = build_product_signals(
            setup_state=setup_state,
            session_evidence=session_evidence,
            reusable_answers=reusable_answers,
            western_readiness=western_readiness,
            interview_summary=interview_summary,
            monetization=monetization,
        )

        return {
            "user": {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "language_level": self.learning_plan_service.get_current_level(plan) or user.language_level,
            },
            "goal": {
                "text": goal,
                "preferred_mode": self.learning_plan_service.get_preferred_mode(plan),
                "target_level": plan.level_target,
                "focus_areas": extract_focus_areas(roadmap),
                "brief": goal_brief,
                "missing_fields": self.learning_plan_service.get_goal_setup_missing(plan),
                "draft_available": bool(goal_brief and goal_brief.get("status") in {"draft", "confirmed"}),
            },
            "assessment": latest_assessment,
            "program": program_plan,
            "career_context": career_context,
            "interview_pack": interview_pack,
            "project_story_pack": project_story_pack,
            "mission": mission,
            "gamification": {"xp": xp_info, "streak": streak_info},
            "interview": interview_summary,
            "pronunciation": pronunciation_summary,
            "vocabulary": {
                "stats": vocabulary_stats,
                "due_preview": [
                    {
                        "id": card.id,
                        "word": card.word,
                        "translation": card.translation,
                        "example_sentence": card.example_sentence,
                        "due_at": card.due_at,
                        "state": card.fsrs_state,
                    }
                    for card in due_cards
                ],
            },
            "progress": {
                "sessions_completed": max(total_sessions, self.learning_plan_service.get_session_count(plan)),
                "milestones": roadmap.get("milestones") or [],
                "recommended_vocabulary": self.learning_plan_service.get_recommended_vocabulary(plan)[:8],
                "top_error_patterns": error_patterns,
                "recent_sessions": recent_sessions,
                "improvement_signals": build_improvement_signals(
                    interview_summary=interview_summary,
                    pronunciation_summary=pronunciation_summary,
                    session_evidence=session_evidence,
                    latest_assessment=latest_assessment,
                    milestones=roadmap.get("milestones") or [],
                ),
                "recurring_issue": build_recurring_issue(session_evidence),
                "what_improved": build_what_improved(session_evidence),
                "western_readiness": western_readiness,
                "reusable_answers": reusable_answers,
            },
            "session_evidence": {
                "latest": session_evidence[0] if session_evidence else None,
                "recent": session_evidence[:5],
            },
            "setup": {
                "goal_complete": goal_complete,
                "assessment_complete": assessment_complete,
                "needs_attention": setup_state != "ready_for_program",
                "state": setup_state,
                "scope_status": build_snapshot_scope_status(goal_brief),
                "next_question_type": next_question_type,
                "progress": setup_progress,
            },
            "product_signals": product_signals,
            "monetization": monetization,
        }

    async def _get_total_sessions(self, user_id: int) -> int:
        result = await self.db.execute(select(func.count(Session.id)).where(Session.user_id == user_id))
        return int(result.scalar() or 0)

    async def _get_top_error_patterns(self, user_id: int, limit: int = 5) -> list[dict[str, Any]]:
        stmt = (
            select(Correction.rule_tag, func.count(Correction.id).label("count"))
            .join(Session, Correction.session_id == Session.id)
            .where(Session.user_id == user_id)
            .where(Correction.rule_tag.is_not(None))
            .group_by(Correction.rule_tag)
            .order_by(func.count(Correction.id).desc(), Correction.rule_tag.asc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [
            {"label": str(row.rule_tag).replace("_", " "), "count": int(row.count)}
            for row in result.all()
            if row.rule_tag
        ]

    async def _get_recent_sessions(self, user_id: int, limit: int = 5) -> list[dict[str, Any]]:
        stmt = (
            select(Session)
            .options(selectinload(Session.corrections), selectinload(Session.feedback))
            .where(Session.user_id == user_id)
            .order_by(Session.started_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        sessions = result.scalars().all()
        response: list[dict[str, Any]] = []
        for session in sessions:
            feedback_items = [item.content for item in (session.feedback or []) if getattr(item, "content", None)]
            summary = feedback_items[0] if feedback_items else None
            response.append(
                {
                    "id": str(session.id),
                    "started_at": session.started_at,
                    "ended_at": session.ended_at,
                    "duration_minutes": session.duration_minutes,
                    "corrections_count": len(session.corrections or []),
                    "summary": summary,
                }
            )
        return response
