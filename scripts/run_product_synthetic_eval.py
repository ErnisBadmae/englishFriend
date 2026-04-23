"""Run live synthetic product scenarios against the mainline chat_v2 flow.

This runner is product-first, not STT-first:

- it uses `composer` text input by default
- it measures the business loop after a live websocket session
- it checks whether the service produced the right persisted state

The current target is the mainline first-value path:

goal -> first useful mission -> embedded baseline -> session evidence -> ready snapshot
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import websockets

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.test_agent_e2e import (
    DEFAULT_BASE_URL,
    SmokeFailure,
    SmokeRuntimeFailure,
    assert_event_contract,
    build_ws_url,
    drain_events,
    event_summary,
    fetch_snapshot,
    format_event_tail,
    generate_telegram_id,
    has_session_complete,
    resolve_or_create_user,
    wait_for_assistant_turn,
    wait_for_connected,
    wait_for_session_complete,
)


@dataclass(frozen=True)
class ProductSyntheticScenario:
    slug: str
    description: str
    user_messages: tuple[str, ...]
    expected_primary_context: str
    expected_track_id: str
    expected_session_task_type: str
    expected_assessment_source: str = "embedded_first_mission"
    expected_setup_state: str = "ready_for_program"
    handoff_keywords: tuple[str, ...] = ("real mission",)
    forbidden_assistant_substrings: tuple[str, ...] = (
        "i'm having trouble right now",
        "server error. please refresh the page.",
        "what do you do now?",
    )


MAINLINE_SCENARIOS: dict[str, ProductSyntheticScenario] = {
    "workplace_first_value": ProductSyntheticScenario(
        slug="workplace_first_value",
        description="Workplace-first goal should hand off into a stakeholder mission and persist embedded baseline plus evidence.",
        user_messages=(
            "speaking better in an international team",
            "ML engineer job abroad",
            "I built an AI agent and a RAG pipeline for internal support, and it helped the team answer questions faster.",
        ),
        expected_primary_context="workplace_communication",
        expected_track_id="workplace_communication",
        expected_session_task_type="stakeholder_explanation_drill",
        handoff_keywords=("real mission", "non-technical stakeholder"),
    ),
    "interview_first_value": ProductSyntheticScenario(
        slug="interview_first_value",
        description="Interview-first goal should start with a foundation mission, then persist embedded baseline and evidence.",
        user_messages=(
            "I want machine learning interview practice for an ML engineer job abroad",
            "I currently explain my background too vaguely and want a cleaner intro in English.",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission", "speaking skill feels weakest"),
    ),
    "project_first_value": ProductSyntheticScenario(
        slug="project_first_value",
        description="Project-first goal should start with a technical walkthrough and persist embedded baseline plus evidence.",
        user_messages=(
            "I want to explain my machine learning projects more clearly for an ML engineer job abroad",
            "I built a churn model for e-commerce, chose gradient boosting, and improved recall on risky users.",
        ),
        expected_primary_context="project_walkthrough",
        expected_track_id="project_walkthrough",
        expected_session_task_type="technical_project_walkthrough",
        handoff_keywords=("real mission", "recent technical project"),
    ),
    "workplace_status_update": ProductSyntheticScenario(
        slug="workplace_status_update",
        description="A cross-functional workplace user should still land in stakeholder-friendly communication work.",
        user_messages=(
            "I need to explain project updates more clearly to product managers in English",
            "I work as a data scientist and often speak with product and operations teams",
            "I built a retention model and need to explain impact without too much jargon",
        ),
        expected_primary_context="workplace_communication",
        expected_track_id="workplace_communication",
        expected_session_task_type="stakeholder_explanation_drill",
        handoff_keywords=("real mission", "non-technical stakeholder"),
    ),
    "project_tradeoff_story": ProductSyntheticScenario(
        slug="project_tradeoff_story",
        description="A technical project user with system tradeoffs should land in project walkthrough mode.",
        user_messages=(
            "I want to explain system design tradeoffs in my machine learning project better in English",
            "I built a RAG assistant and had to trade off latency and answer quality",
        ),
        expected_primary_context="project_walkthrough",
        expected_track_id="project_walkthrough",
        expected_session_task_type="technical_project_walkthrough",
        handoff_keywords=("real mission", "recent technical project"),
    ),
    "interview_self_intro_gap": ProductSyntheticScenario(
        slug="interview_self_intro_gap",
        description="An interview user with a weak self-introduction should start with an interview-safe foundation drill.",
        user_messages=(
            "I need to answer tell me about yourself better in ML engineer interviews abroad",
            "I moved from analytics to ML and struggle to describe my background clearly",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission", "speaking skill feels weakest"),
    ),
    # --- Live-tester scenarios: diverse real-user behaviors ---
    "broken_english_workplace": ProductSyntheticScenario(
        slug="broken_english_workplace",
        description="Russian-speaking ML engineer with broken grammar should still route to workplace communication.",
        user_messages=(
            "I need speak better English at work. I explain to manager in team meeting, they not understand me.",
            "Yes my goal improve English for team standup and presentation to stakeholder, not technical people.",
            "I ML engineer. I want better explain my work to colleague and manager in English at work.",
        ),
        expected_primary_context="workplace_communication",
        expected_track_id="workplace_communication",
        expected_session_task_type="stakeholder_explanation_drill",
        handoff_keywords=("real mission",),
    ),
    "mixed_intent_interview_project": ProductSyntheticScenario(
        slug="mixed_intent_interview_project",
        description="User mixes interview and project signals; interview should win via cumulative scoring and canonical order.",
        user_messages=(
            "I want prepare technical interview where I explain my ML project to interviewer.",
            "My main project recommendation system. I need explain it well in interviews.",
            "I focus on interview preparation for ML engineer role abroad.",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
    "vague_progressive_interview": ProductSyntheticScenario(
        slug="vague_progressive_interview",
        description="User starts vague ('better job') and progressively narrows to interview context over three turns.",
        user_messages=(
            "I want improve my English for get better job.",
            "I am ML engineer and want work in international company abroad.",
            "I need practice interview in English. Want pass interview for ML engineer position.",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
    "explicit_correction_to_project": ProductSyntheticScenario(
        slug="explicit_correction_to_project",
        description="User starts with interview signals then explicitly corrects to project walkthrough; correction lane must fire.",
        user_messages=(
            "I want practice English interview. I ML engineer, need interview preparation for job abroad.",
            "Actually no, not interview. More important is explain my ML project. I need project walkthrough practice.",
            "Yes I build recommendation system. Want explain architecture and design decision in English.",
        ),
        expected_primary_context="project_walkthrough",
        expected_track_id="project_walkthrough",
        expected_session_task_type="technical_project_walkthrough",
        handoff_keywords=("real mission",),
    ),
    "minimal_answers_workplace": ProductSyntheticScenario(
        slug="minimal_answers_workplace",
        description="User gives very brief 3-5 word answers; cumulative workplace signals should accumulate across turns.",
        user_messages=(
            "ML engineer, team communication",
            "explain model to manager",
            "workplace meetings, presentation",
        ),
        expected_primary_context="workplace_communication",
        expected_track_id="workplace_communication",
        expected_session_task_type="stakeholder_explanation_drill",
        handoff_keywords=("real mission",),
    ),
    "data_engineer_interview": ProductSyntheticScenario(
        slug="data_engineer_interview",
        description="Data engineer profile (not ML engineer) should still route correctly to interview track.",
        user_messages=(
            "I am data engineer. I want prepare for senior data engineer interview abroad.",
            "I build ETL pipeline and data warehouse. Need interview practice for FAANG company.",
            "My focus data pipeline interview preparation for international company.",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
    # --- Live-tester scenarios batch 2: more edge cases ---
    "long_rambling_workplace": ProductSyntheticScenario(
        slug="long_rambling_workplace",
        description="User gives long rambling answer with multiple topics; workplace signals must dominate over interview noise.",
        user_messages=(
            "I work as senior ML engineer at big company and have many things to improve. First I need communicate better with product manager and business stakeholders. I also present to CTO sometimes. I have interviews occasionally for other roles but mostly my day is team meetings and stakeholder updates.",
            "Yes main problem is stakeholder presentation at work. Manager not understand my technical explanation.",
            "I want improve English for work communication, explain clearly to non-technical colleague and manager.",
        ),
        expected_primary_context="workplace_communication",
        expected_track_id="workplace_communication",
        expected_session_task_type="stakeholder_explanation_drill",
        handoff_keywords=("real mission",),
    ),
    "backend_engineer_interview": ProductSyntheticScenario(
        slug="backend_engineer_interview",
        description="Backend engineer (not ML) should route to interview track when interview intent is clear.",
        user_messages=(
            "I am backend engineer. I want interview practice for senior backend engineer role abroad.",
            "I build REST API and microservices. Need pass interview at international company.",
            "I focus on interview preparation for backend engineer position.",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
    "company_specific_interview": ProductSyntheticScenario(
        slug="company_specific_interview",
        description="User mentions specific company (FAANG/Google) in interview context; should route to interview track.",
        user_messages=(
            "I want to pass interview at Google as ML engineer.",
            "I applying for senior ML engineer position at FAANG company abroad.",
            "I need interview practice in English for ML engineer role at big tech company.",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
    "off_topic_then_interview": ProductSyntheticScenario(
        slug="off_topic_then_interview",
        description="User starts with off-topic or meta question, then clarifies interview intent; no generic fallback should appear.",
        user_messages=(
            "What can I practice here? What kind of help you give?",
            "I need interview practice for ML engineer role abroad.",
            "I want prepare for ML engineer interview at international company.",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
    # --- Live-tester scenarios batch 3 ---
    "negative_context_no_interview": ProductSyntheticScenario(
        slug="negative_context_no_interview",
        description="User explicitly says NOT interview, wants workplace only; negation should push routing to workplace.",
        user_messages=(
            "I don't want to practice interviews. I need help with team meetings and manager communication.",
            "My goal is workplace English, not interview preparation.",
            "I need explain better to stakeholder and colleague at work.",
        ),
        expected_primary_context="workplace_communication",
        expected_track_id="workplace_communication",
        expected_session_task_type="stakeholder_explanation_drill",
        handoff_keywords=("real mission",),
    ),
    "one_word_answers_interview": ProductSyntheticScenario(
        slug="one_word_answers_interview",
        description="User gives one-word answers; pure keyword match should be enough to route to interviews.",
        user_messages=(
            "interviews",
            "ML engineer",
            "abroad, FAANG interview",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
    "mlops_engineer_interview": ProductSyntheticScenario(
        slug="mlops_engineer_interview",
        description="MLOps/DevOps ML engineer seeking interview practice; domain differs from ML but interview intent is clear.",
        user_messages=(
            "I am MLOps engineer. I want interview for senior MLOps role at international company.",
            "I work with ML pipeline, model deployment, monitoring in production.",
            "I need interview practice for MLOps engineer position abroad.",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
    "freelancer_client_workplace": ProductSyntheticScenario(
        slug="freelancer_client_workplace",
        description="ML freelancer explaining to clients; client meeting context should route to workplace communication.",
        user_messages=(
            "I am ML freelancer. I need explain my work to client in English better.",
            "I have client meeting in English, need explain project result and recommendation to client.",
            "My goal improve English for client presentation and meeting.",
        ),
        expected_primary_context="workplace_communication",
        expected_track_id="workplace_communication",
        expected_session_task_type="stakeholder_explanation_drill",
        handoff_keywords=("real mission",),
    ),
    "researcher_project_walkthrough": ProductSyntheticScenario(
        slug="researcher_project_walkthrough",
        description="PhD researcher explaining ML research at conference; should route to project walkthrough.",
        user_messages=(
            "I PhD student. I need explain my ML research project in English to audience.",
            "I present my research on NLP at conference. Need explain method and result clearly.",
            "I want improve English for research project presentation and technical walkthrough.",
        ),
        expected_primary_context="project_walkthrough",
        expected_track_id="project_walkthrough",
        expected_session_task_type="technical_project_walkthrough",
        handoff_keywords=("real mission",),
    ),
    "project_ambiguous_wins_workplace": ProductSyntheticScenario(
        slug="project_ambiguous_wins_workplace",
        description="User mixes project and workplace signals with workplace emphasis; workplace should win.",
        user_messages=(
            "I need explain my ML project to stakeholders at work. They not technical.",
            "My main problem is communication at work, explain to manager and product team.",
            "I want better English for work meeting and stakeholder update, not project technical detail.",
        ),
        expected_primary_context="workplace_communication",
        expected_track_id="workplace_communication",
        expected_session_task_type="stakeholder_explanation_drill",
        handoff_keywords=("real mission",),
    ),
    # --- Live-tester scenarios batch 4 ---
    "product_manager_workplace": ProductSyntheticScenario(
        slug="product_manager_workplace",
        description="Product manager working with ML team; workplace communication with engineers and stakeholders.",
        user_messages=(
            "I am product manager. I work with ML team and need explain requirements to engineers in English.",
            "I need better English for product meeting and engineering discussion with technical team.",
            "My goal improve workplace communication with ML engineers and business stakeholders.",
        ),
        expected_primary_context="workplace_communication",
        expected_track_id="workplace_communication",
        expected_session_task_type="stakeholder_explanation_drill",
        handoff_keywords=("real mission",),
    ),
    "career_switcher_interview": ProductSyntheticScenario(
        slug="career_switcher_interview",
        description="Data analyst switching career to ML engineer; interview preparation is the goal.",
        user_messages=(
            "I was data analyst, now studying ML. I want switch career to ML engineer position.",
            "I applying for junior ML engineer position. I need interview practice in English.",
            "I need prepare for ML engineer job interview at international company abroad.",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
    "team_lead_workplace": ProductSyntheticScenario(
        slug="team_lead_workplace",
        description="Recently promoted tech lead needing leadership communication in English.",
        user_messages=(
            "I become team lead recently. I need improve English for leading team meeting and technical discussion.",
            "I need explain technical decision to non-technical manager and business stakeholder.",
            "My goal is better workplace English for team lead communication and presentation.",
        ),
        expected_primary_context="workplace_communication",
        expected_track_id="workplace_communication",
        expected_session_task_type="stakeholder_explanation_drill",
        handoff_keywords=("real mission",),
    ),
    "startup_pitch_project": ProductSyntheticScenario(
        slug="startup_pitch_project",
        description="ML startup founder pitching technology and model to investors; project walkthrough context.",
        user_messages=(
            "I building ML startup. I need explain my product and ML technology to investor in English.",
            "I have demo day presentation, need explain ML model and business impact clearly.",
            "I want better English for technical pitch and project walkthrough to investor audience.",
        ),
        expected_primary_context="project_walkthrough",
        expected_track_id="project_walkthrough",
        expected_session_task_type="technical_project_walkthrough",
        handoff_keywords=("real mission",),
    ),
    "repeated_same_signals_interview": ProductSyntheticScenario(
        slug="repeated_same_signals_interview",
        description="User repeats 'interview' in every turn with slight variation; routing must converge cleanly.",
        user_messages=(
            "I want interview practice.",
            "Yes interview preparation is my main goal.",
            "I need pass interview as ML engineer for job abroad.",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
    "eu_relocation_interview": ProductSyntheticScenario(
        slug="eu_relocation_interview",
        description="ML engineer relocating from CIS to EU; interview in English is the driver.",
        user_messages=(
            "I ML engineer from Russia. I want relocate to EU and need interview in English.",
            "I apply for job in Germany and Netherlands as senior ML engineer.",
            "I need practice interview in English for EU company. Want pass technical and HR interview.",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
    "grammar_only_no_context": ProductSyntheticScenario(
        slug="grammar_only_no_context",
        description="User asks only about grammar/vocabulary with no job or workplace context; routing should default somewhere.",
        user_messages=(
            "I need improve my grammar in English. I make many mistakes.",
            "I have problem with articles and tenses. My English not good.",
            "I want better vocabulary for professional English communication.",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
    "anxiety_vague_no_context": ProductSyntheticScenario(
        slug="anxiety_vague_no_context",
        description="User expresses frustration and anxiety about English with no specific context; system must not crash.",
        user_messages=(
            "My English is very bad. I cannot speak well in English at all.",
            "I am afraid to speak English. I make many mistake and people don't understand me.",
            "I need improve English but don't know where to start. I just want speak better.",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
    # --- Live-tester scenarios batch 5: formatting, tie-breaking, correction reverse ---
    "all_caps_interview": ProductSyntheticScenario(
        slug="all_caps_interview",
        description="ALL CAPS input; signal extraction must be case-insensitive and route correctly.",
        user_messages=(
            "I NEED INTERVIEW PRACTICE FOR ML ENGINEER JOB ABROAD",
            "I AM ML ENGINEER AND WANT PASS INTERVIEWS AT INTERNATIONAL COMPANY",
            "INTERVIEW PREPARATION IS MY GOAL FOR ML ENGINEER POSITION",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
    "emoji_in_message_workplace": ProductSyntheticScenario(
        slug="emoji_in_message_workplace",
        description="Emoji mixed into text; routing and session must handle unicode cleanly.",
        user_messages=(
            "I need better English for work 💼. I explain to manager 👔 in team meetings.",
            "My goal is workplace communication 📊 with stakeholder and non-technical colleague.",
            "I want improve English for team standup 🤝 and manager presentation at work.",
        ),
        expected_primary_context="workplace_communication",
        expected_track_id="workplace_communication",
        expected_session_task_type="stakeholder_explanation_drill",
        handoff_keywords=("real mission",),
    ),
    "three_contexts_equal_signals": ProductSyntheticScenario(
        slug="three_contexts_equal_signals",
        description="User mentions interview, workplace, and project equally; canonical tiebreaker (interviews first) must apply.",
        user_messages=(
            "I need interview practice, improve work communication, and explain my ML projects better.",
            "I have interviews next month, team meetings every week, and project presentations too.",
            "All three are important: interview preparation, workplace English, project walkthrough.",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
    "question_style_interview": ProductSyntheticScenario(
        slug="question_style_interview",
        description="User asks questions instead of stating goals; system must probe and still extract intent.",
        user_messages=(
            "Would interview practice help me get a job as ML engineer abroad?",
            "What should I do to prepare for ML engineer interviews in English?",
            "Is this the right place to practice for ML job interviews at international company?",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
    "salary_motivation_interview": ProductSyntheticScenario(
        slug="salary_motivation_interview",
        description="User's motivation is salary/job upgrade; interview intent emerges as the path.",
        user_messages=(
            "I ML engineer but stuck at local company with low salary. English is my main barrier.",
            "I need get job at international company abroad. Better salary and career.",
            "I think I need interview practice in English for better job and salary abroad.",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
    "project_correction_to_workplace": ProductSyntheticScenario(
        slug="project_correction_to_workplace",
        description="User starts with project signals then explicitly corrects to workplace; tests correction lane in opposite direction vs БАГ-002.",
        user_messages=(
            "I need explain my ML project better in English. I work on recommendation system.",
            "Actually more important is my daily work communication with manager and team at office.",
            "Yes workplace English is my real goal, not project explanation. I need team meeting English.",
        ),
        expected_primary_context="workplace_communication",
        expected_track_id="workplace_communication",
        expected_session_task_type="stakeholder_explanation_drill",
        handoff_keywords=("real mission",),
    ),
    "devops_sre_interview": ProductSyntheticScenario(
        slug="devops_sre_interview",
        description="DevOps/SRE engineer (non-ML) seeking interview practice; should route to interviews.",
        user_messages=(
            "I am DevOps engineer. I want prepare for senior SRE interview at international company.",
            "I work with Kubernetes, CI/CD, cloud infrastructure AWS. Need interview practice.",
            "I need pass DevOps SRE interview for job abroad at big tech company.",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
    "stt_noise_interview": ProductSyntheticScenario(
        slug="stt_noise_interview",
        description="Simulated STT transcription noise: phonetic misspellings of key words; routing must be robust.",
        user_messages=(
            "I wont intarview practis for ML injineer jab abrod.",
            "I need prepear for teknikal intarview at internashenal compny.",
            "Intarview preparashon iz my goal for ML injineer pozishon.",
        ),
        expected_primary_context="interviews",
        expected_track_id="hr_intro",
        expected_session_task_type="foundation_speaking_drill",
        handoff_keywords=("real mission",),
    ),
}

MAINLINE_SCENARIO_SET = (
    "workplace_first_value",
    "interview_first_value",
    "project_first_value",
)

LIVE_TESTER_SCENARIO_SET = (
    "broken_english_workplace",
    "mixed_intent_interview_project",
    "vague_progressive_interview",
    "explicit_correction_to_project",
    "minimal_answers_workplace",
    "data_engineer_interview",
    "long_rambling_workplace",
    "backend_engineer_interview",
    "company_specific_interview",
    "off_topic_then_interview",
    "negative_context_no_interview",
    "one_word_answers_interview",
    "mlops_engineer_interview",
    "freelancer_client_workplace",
    "researcher_project_walkthrough",
    "project_ambiguous_wins_workplace",
    "product_manager_workplace",
    "career_switcher_interview",
    "team_lead_workplace",
    "startup_pitch_project",
    "repeated_same_signals_interview",
    "eu_relocation_interview",
    "grammar_only_no_context",
    "anxiety_vague_no_context",
    "all_caps_interview",
    "emoji_in_message_workplace",
    "three_contexts_equal_signals",
    "question_style_interview",
    "salary_motivation_interview",
    "project_correction_to_workplace",
    "devops_sre_interview",
    "stt_noise_interview",
)

EXPANDED_SCENARIO_SET = (
    *MAINLINE_SCENARIO_SET,
    "workplace_status_update",
    "project_tradeoff_story",
    "interview_self_intro_gap",
    *LIVE_TESTER_SCENARIO_SET,
)


def has_completion_signal(events: list[dict[str, Any]]) -> bool:
    if has_session_complete(events):
        return True
    return any(
        str(event.get("type") or "") == "transcript"
        and str(event.get("role") or "") == "assistant"
        and str(event.get("phase") or "") == "session_end"
        and str(event.get("text") or "").strip()
        for event in events
    )


@dataclass(slots=True)
class ScenarioCheck:
    name: str
    passed: bool
    detail: str
    category: str = "routing_check"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Canonical classification so a single red check can be triaged without guessing
# whether the failure is about routing logic or runtime recovery.
_ROUTING_CHECKS: frozenset[str] = frozenset({
    "primary_context",
    "recommended_track",
    "assessment_source",
    "latest_evidence_task_type",
    "first_useful_mission_handoff",
})

_RUNTIME_CHECKS: frozenset[str] = frozenset({
    "completion_signal_seen",
    "setup_state",
    "latest_evidence_saved",
    "latest_evidence_summary",
    "no_generic_fallback_leak",
})


def _check_category(name: str) -> str:
    if name in _ROUTING_CHECKS:
        return "routing_check"
    if name in _RUNTIME_CHECKS:
        return "runtime_check"
    return "other"


# Assistant substrings that indicate the session leaked a generic recovery
# message (legacy "I'm having trouble" family) instead of mission-safe recovery.
_GENERIC_FALLBACK_LEAKS: tuple[str, ...] = (
    "i'm having trouble",
    "i'm having a bit of trouble",
    "server error. please refresh",
)


def _detect_generic_fallback_leak(assistant_texts: list[str]) -> tuple[bool, str]:
    for text in assistant_texts:
        lowered = text.lower()
        for phrase in _GENERIC_FALLBACK_LEAKS:
            if phrase in lowered:
                return True, phrase
    return False, ""


@dataclass(slots=True)
class ScenarioReport:
    slug: str
    description: str
    passed: bool
    score: float
    user_id: int
    telegram_id: int
    checks: list[ScenarioCheck] = field(default_factory=list)
    snapshot_excerpt: dict[str, Any] = field(default_factory=dict)
    event_tail: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "description": self.description,
            "passed": self.passed,
            "score": self.score,
            "user_id": self.user_id,
            "telegram_id": self.telegram_id,
            "checks": [item.to_dict() for item in self.checks],
            "snapshot_excerpt": self.snapshot_excerpt,
            "event_tail": self.event_tail,
        }


@dataclass(slots=True)
class EvalReport:
    generated_at: str
    base_url: str
    scenario_set: str
    reports: list[ScenarioReport]
    average_score: float
    pass_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "base_url": self.base_url,
            "scenario_set": self.scenario_set,
            "reports": [report.to_dict() for report in self.reports],
            "average_score": self.average_score,
            "pass_rate": self.pass_rate,
        }


def _assistant_texts(events: list[dict[str, Any]]) -> list[str]:
    return [
        str(event.get("text") or "").strip()
        for event in events
        if str(event.get("type") or "") == "transcript"
        and str(event.get("role") or "") == "assistant"
        and str(event.get("text") or "").strip()
    ]


def _snapshot_excerpt(snapshot: dict[str, Any]) -> dict[str, Any]:
    goal_brief = ((snapshot.get("goal") or {}).get("brief") or {})
    interview = snapshot.get("interview") or {}
    recommended_track = interview.get("recommended_track") or {}
    assessment = snapshot.get("assessment") or {}
    session_evidence = (snapshot.get("session_evidence") or {}).get("latest") or {}
    setup = snapshot.get("setup") or {}
    return {
        "primary_context": (goal_brief.get("main_contexts") or [None])[0],
        "recommended_track_id": recommended_track.get("id"),
        "setup_state": setup.get("state"),
        "assessment_source": assessment.get("source"),
        "assessment_level": assessment.get("level"),
        "latest_evidence_task_type": session_evidence.get("task_type"),
        "latest_evidence_summary": session_evidence.get("summary"),
    }


def evaluate_product_snapshot(
    *,
    snapshot: dict[str, Any],
    events: list[dict[str, Any]],
    scenario: ProductSyntheticScenario,
) -> list[ScenarioCheck]:
    excerpt = _snapshot_excerpt(snapshot)
    assistant_texts = _assistant_texts(events)
    latest_evidence = (snapshot.get("session_evidence") or {}).get("latest") or {}

    def make_check(name: str, passed: bool, detail: str) -> ScenarioCheck:
        return ScenarioCheck(
            name=name,
            passed=passed,
            detail=detail,
            category=_check_category(name),
        )

    leaked, leak_phrase = _detect_generic_fallback_leak(assistant_texts)

    checks = [
        make_check(
            "completion_signal_seen",
            has_completion_signal(events),
            "session_complete event present"
            if has_session_complete(events)
            else (
                "farewell/session_end transcript present"
                if has_completion_signal(events)
                else "missing completion signal"
            ),
        ),
        make_check(
            "first_useful_mission_handoff",
            any(keyword in text.lower() for keyword in scenario.handoff_keywords for text in assistant_texts),
            "assistant used first-mission handoff language"
            if any(keyword in text.lower() for keyword in scenario.handoff_keywords for text in assistant_texts)
            else f"missing handoff keywords: {', '.join(scenario.handoff_keywords)}",
        ),
        make_check(
            "primary_context",
            excerpt.get("primary_context") == scenario.expected_primary_context,
            f"expected={scenario.expected_primary_context}, actual={excerpt.get('primary_context')}",
        ),
        make_check(
            "recommended_track",
            excerpt.get("recommended_track_id") == scenario.expected_track_id,
            f"expected={scenario.expected_track_id}, actual={excerpt.get('recommended_track_id')}",
        ),
        make_check(
            "setup_state",
            excerpt.get("setup_state") == scenario.expected_setup_state,
            f"expected={scenario.expected_setup_state}, actual={excerpt.get('setup_state')}",
        ),
        make_check(
            "assessment_source",
            excerpt.get("assessment_source") == scenario.expected_assessment_source,
            f"expected={scenario.expected_assessment_source}, actual={excerpt.get('assessment_source')}",
        ),
        make_check(
            "latest_evidence_saved",
            bool(latest_evidence),
            "latest session evidence present" if latest_evidence else "missing latest session evidence",
        ),
        make_check(
            "latest_evidence_task_type",
            excerpt.get("latest_evidence_task_type") == scenario.expected_session_task_type,
            f"expected={scenario.expected_session_task_type}, actual={excerpt.get('latest_evidence_task_type')}",
        ),
        make_check(
            "latest_evidence_summary",
            bool(excerpt.get("latest_evidence_summary")),
            "latest evidence summary present"
            if excerpt.get("latest_evidence_summary")
            else "latest evidence summary missing",
        ),
        make_check(
            "no_generic_fallback_leak",
            not leaked,
            "no generic fallback leak in assistant transcripts"
            if not leaked
            else f"generic fallback leaked: '{leak_phrase}'",
        ),
    ]
    return checks


async def run_product_scenario(
    *,
    base_url: str,
    scenario: ProductSyntheticScenario,
    telegram_id: int,
    turn_timeout_s: float,
    session_timeout_s: float,
) -> ScenarioReport:
    user = await resolve_or_create_user(base_url, telegram_id=telegram_id)
    resolved_user_id = int(user.get("id") or 0)
    if resolved_user_id <= 0:
        raise SmokeRuntimeFailure(f"Resolved user payload has invalid id: {user}")

    ws_url = build_ws_url(base_url, user_id=resolved_user_id, stt_provider="composer")
    events: list[dict[str, Any]] = []

    try:
        async with websockets.connect(ws_url, max_size=2_000_000) as websocket:
            connected = await wait_for_connected(websocket, events=events, timeout_s=turn_timeout_s)
            if not bool(connected.get("is_new_user")):
                raise SmokeRuntimeFailure("Synthetic scenario requires a fresh user, but connected payload was not marked as new")

            initial_assistant = await wait_for_assistant_turn(
                websocket,
                scenario=scenario,
                events=events,
                timeout_s=turn_timeout_s,
            )
            print(f"Initial assistant: {str(initial_assistant.get('text') or '').strip()[:140]}")
            await drain_events(websocket, scenario=scenario, events=events)

            for index, message in enumerate(scenario.user_messages, start=1):
                payload = {"type": "text", "text": message, "source": "composer"}
                await websocket.send(json.dumps(payload))
                assistant = await wait_for_assistant_turn(
                    websocket,
                    scenario=scenario,
                    events=events,
                    timeout_s=turn_timeout_s,
                )
                print(f"Turn {index} assistant: {str(assistant.get('text') or '').strip()[:140]}")
                await drain_events(websocket, scenario=scenario, events=events)

            if not has_completion_signal(events):
                await websocket.send(json.dumps({"type": "end"}))
                try:
                    completion_event = await wait_for_session_complete(
                        websocket,
                        scenario=scenario,
                        events=events,
                        timeout_s=session_timeout_s,
                    )
                    print(
                        f"Session complete: reason={completion_event.get('reason')}, "
                        f"return_screen={completion_event.get('return_screen')}"
                    )
                    await drain_events(websocket, scenario=scenario, events=events)
                except Exception:
                    if not has_completion_signal(events):
                        raise
    except SmokeFailure:
        raise
    except Exception as exc:  # pragma: no cover - live networking guard
        raise SmokeRuntimeFailure(
            f"Product synthetic scenario failed after {len(events)} events: {exc}. "
            f"Tail: {format_event_tail(events)}"
        ) from exc

    snapshot = await fetch_snapshot(base_url, user_id=resolved_user_id)
    checks = evaluate_product_snapshot(snapshot=snapshot, events=events, scenario=scenario)
    passed_checks = sum(1 for item in checks if item.passed)
    score = round((passed_checks / max(len(checks), 1)) * 100.0, 1)
    return ScenarioReport(
        slug=scenario.slug,
        description=scenario.description,
        passed=all(item.passed for item in checks),
        score=score,
        user_id=resolved_user_id,
        telegram_id=telegram_id,
        checks=checks,
        snapshot_excerpt=_snapshot_excerpt(snapshot),
        event_tail=[event_summary(event) for event in events[-10:]],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run live synthetic product scenarios against /api/v1/voice/chat/v2.")
    parser.add_argument(
        "--scenario",
        default=None,
        choices=sorted(MAINLINE_SCENARIOS),
        help="Synthetic scenario to execute.",
    )
    parser.add_argument(
        "--scenario-set",
        default="mainline",
        choices=("mainline", "expanded", "live_tester"),
        help="Named synthetic scenario set to execute sequentially.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Backend base URL. Default: http://localhost:8000",
    )
    parser.add_argument(
        "--turn-timeout",
        type=float,
        default=20.0,
        help="Timeout in seconds for connected and assistant-turn waits. Use a higher value for remote/corporate LLM backends.",
    )
    parser.add_argument(
        "--session-timeout",
        type=float,
        default=15.0,
        help="Timeout in seconds for waiting on session_complete after end.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write a JSON report.",
    )
    args = parser.parse_args()
    if args.scenario:
        args.scenario_set = None
    return args


def resolve_scenario_slugs(args: argparse.Namespace) -> tuple[str, ...]:
    if args.scenario:
        return (args.scenario,)
    if args.scenario_set == "expanded":
        return EXPANDED_SCENARIO_SET
    if args.scenario_set == "live_tester":
        return LIVE_TESTER_SCENARIO_SET
    return MAINLINE_SCENARIO_SET


def _is_blocking_scenario(args: argparse.Namespace, slug: str) -> bool:
    if args.scenario:
        return True
    return slug in MAINLINE_SCENARIO_SET


def _scenario_gate_label(args: argparse.Namespace, slug: str) -> str:
    return "blocking" if _is_blocking_scenario(args, slug) else "advisory"


def print_header(*, base_url: str, scenario_slugs: tuple[str, ...]) -> None:
    print("=" * 72)
    print("chat_v2 synthetic product eval")
    print("=" * 72)
    print(f"base_url: {base_url}")
    print(f"scenario_count: {len(scenario_slugs)}")


def print_report(report: ScenarioReport, *, gate: str) -> None:
    verdict = "PASS" if report.passed else "FAIL"
    print(f"\n{verdict} {report.slug} | gate={gate} | score={report.score:.1f}")
    print(f"description: {report.description}")
    print(f"user_id: {report.user_id} | telegram_id: {report.telegram_id}")
    for check in report.checks:
        status = "ok" if check.passed else "fail"
        print(f"  [{status}] [{check.category}] {check.name}: {check.detail}")


async def async_main() -> int:
    args = parse_args()
    scenario_slugs = resolve_scenario_slugs(args)
    print_header(base_url=args.base_url, scenario_slugs=scenario_slugs)

    reports: list[ScenarioReport] = []

    for slug in scenario_slugs:
        scenario = MAINLINE_SCENARIOS[slug]
        telegram_id = generate_telegram_id()
        gate = _scenario_gate_label(args, scenario.slug)
        print(f"\nscenario: {scenario.slug}")
        print(f"description: {scenario.description}")
        try:
            report = await run_product_scenario(
                base_url=args.base_url,
                scenario=scenario,
                telegram_id=telegram_id,
                turn_timeout_s=args.turn_timeout,
                session_timeout_s=args.session_timeout,
            )
        except SmokeFailure as exc:
            print(f"FAIL {scenario.slug}: {exc}")
            reports.append(
                ScenarioReport(
                    slug=scenario.slug,
                    description=scenario.description,
                    passed=False,
                    score=0.0,
                    user_id=0,
                    telegram_id=telegram_id,
                    checks=[
                        ScenarioCheck(
                            name="runtime",
                            passed=False,
                            detail=str(exc),
                            category="runtime_check",
                        )
                    ],
                    snapshot_excerpt={},
                    event_tail=[],
                )
            )
            continue

        print_report(report, gate=gate)
        reports.append(report)

    average_score = round(sum(report.score for report in reports) / max(len(reports), 1), 1)
    pass_rate = round(sum(1 for report in reports if report.passed) / max(len(reports), 1), 3)
    eval_report = EvalReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        base_url=args.base_url,
        scenario_set=args.scenario_set or "custom",
        reports=reports,
        average_score=average_score,
        pass_rate=pass_rate,
    )

    blocking_reports = [
        report for report in reports
        if _is_blocking_scenario(args, report.slug)
    ]
    blocking_all_pass = bool(blocking_reports) and all(
        item.passed for item in blocking_reports
    )
    advisory_reports = [
        report for report in reports
        if not _is_blocking_scenario(args, report.slug)
    ]

    if args.output:
        Path(args.output).write_text(
            json.dumps(eval_report.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"\nWrote report to {args.output}")

    print("\nSynthetic eval summary:")
    for report in reports:
        verdict = "PASS" if report.passed else "FAIL"
        gate = _scenario_gate_label(args, report.slug)
        tier = "mainline" if report.slug in MAINLINE_SCENARIO_SET else "expanded"
        print(f"  {verdict} [{tier}] [{gate}] {report.slug} score={report.score:.1f}")
    print(f"average_score: {average_score:.1f}")
    print(f"pass_rate: {pass_rate:.1%}")

    if advisory_reports:
        expanded_pass = sum(1 for report in advisory_reports if report.passed)
        print(
            "advisory: expanded "
            f"{expanded_pass}/{len(advisory_reports)} passed "
            "(advisory only — does not block release)"
        )

    return 0 if blocking_all_pass else 1


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
