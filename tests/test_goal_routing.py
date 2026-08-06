"""Tests for the canonical goal routing policy.

These tests pin the contract that routing decisions are:
- cumulative across user turns,
- sticky after the brief becomes routing-ready,
- consistent between primary_context, recommended_track_id, and
  first_mission_task_type.
"""

from __future__ import annotations

import pytest

from app.services.routing import (
    GoalRoutingProfile,
    build_goal_routing_from_goal_brief,
    resolve_goal_routing,
    score_context_signals,
)


def _history(*messages: str) -> list[dict[str, str]]:
    return [{"role": "user", "content": message} for message in messages]


def test_defaults_when_no_signals() -> None:
    profile = resolve_goal_routing(goal_brief=None)
    assert profile.primary_context == "interviews"
    assert profile.recommended_track_id == "hr_intro"
    assert profile.first_mission_task_type == "foundation_speaking_drill"
    assert profile.decision_source == "default"


def test_interview_cumulative_wins_over_project_mention() -> None:
    history = _history(
        "I need interview English practice",
        "mostly tell me about yourself and behavioural questions",
        "I also built an ML project last year",
    )
    profile = resolve_goal_routing(conversation_history=history)
    assert profile.primary_context == "interviews"
    assert profile.recommended_track_id == "hr_intro"
    assert profile.first_mission_task_type == "foundation_speaking_drill"


def test_workplace_cumulative_wins_over_technical_keywords() -> None:
    history = _history(
        "I give status updates to product managers in English",
        "I work on cross-functional teams with operations",
        "and I built a retention model last quarter",
    )
    profile = resolve_goal_routing(conversation_history=history)
    assert profile.primary_context == "workplace_communication"
    assert profile.recommended_track_id == "workplace_communication"
    assert profile.first_mission_task_type == "stakeholder_explanation_drill"


def test_project_walkthrough_for_tradeoff_talk() -> None:
    history = _history(
        "I want to explain system design tradeoffs in my ML project",
        "I built a RAG assistant with latency and architecture tradeoffs",
    )
    profile = resolve_goal_routing(conversation_history=history)
    assert profile.primary_context == "project_walkthrough"
    assert profile.recommended_track_id == "project_walkthrough"
    assert profile.first_mission_task_type == "technical_project_walkthrough"


def test_sticky_primary_after_goal_setup_complete() -> None:
    goal_brief = {
        "status": "draft",
        "main_contexts": ["interviews"],
        "primary_goal": "ml interviews",
    }
    history = _history(
        "I need interview English",
        "and here is a project I built with a pipeline and latency tradeoffs",
    )
    profile = resolve_goal_routing(goal_brief=goal_brief, conversation_history=history)
    # primary stays sticky even though project signals outscore interview signals
    assert profile.primary_context == "interviews"
    assert profile.recommended_track_id == "hr_intro"
    assert profile.first_mission_task_type == "foundation_speaking_drill"
    assert profile.decision_source == "goal_brief_sticky"


def test_confirmed_goal_marks_decision_source() -> None:
    goal_brief = {"status": "confirmed", "main_contexts": ["workplace_communication"]}
    profile = resolve_goal_routing(goal_brief=goal_brief)
    assert profile.primary_context == "workplace_communication"
    assert profile.decision_source == "user_confirmed"


def test_build_from_brief_only() -> None:
    brief = {"status": "confirmed", "main_contexts": ["project_walkthrough"]}
    profile = build_goal_routing_from_goal_brief(brief)
    assert profile.first_mission_task_type == "technical_project_walkthrough"
    assert profile.recommended_track_id == "project_walkthrough"


def test_explicit_user_correction_marks_decision_source() -> None:
    brief = {
        "status": "draft",
        "main_contexts": ["workplace_communication", "project_walkthrough"],
        "routing_decision_source": "explicit_user_correction",
    }
    profile = build_goal_routing_from_goal_brief(brief)
    assert profile.primary_context == "workplace_communication"
    assert profile.decision_source == "explicit_user_correction"


def test_track_and_first_mission_always_consistent() -> None:
    # Enumerate every primary_context path to lock the mapping.
    for primary in ("interviews", "workplace_communication", "project_walkthrough"):
        brief = {"status": "confirmed", "main_contexts": [primary]}
        profile = build_goal_routing_from_goal_brief(brief)
        assert isinstance(profile, GoalRoutingProfile)
        assert profile.primary_context == primary
        # These three fields must never drift relative to one another.
        expected_track = {
            "interviews": "hr_intro",
            "workplace_communication": "workplace_communication",
            "project_walkthrough": "project_walkthrough",
        }[primary]
        expected_mission = {
            "interviews": "foundation_speaking_drill",
            "workplace_communication": "stakeholder_explanation_drill",
            "project_walkthrough": "technical_project_walkthrough",
        }[primary]
        assert profile.recommended_track_id == expected_track
        assert profile.first_mission_task_type == expected_mission


def test_score_context_signals_returns_zeroes_on_empty_text() -> None:
    scores = score_context_signals("")
    assert scores == {
        "interviews": 0,
        "workplace_communication": 0,
        "project_walkthrough": 0,
    }


def test_score_context_signals_splits_by_pattern() -> None:
    scores = score_context_signals(
        "I work with product managers and explain trade-offs in my pipeline"
    )
    # "product manager" + "product managers" hits workplace twice.
    assert scores["workplace_communication"] >= 1
    # "trade-off" + "pipeline" hit project.
    assert scores["project_walkthrough"] >= 2
    # No interview signals here.
    assert scores["interviews"] == 0


def test_score_context_signals_ignores_negated_context_phrases() -> None:
    scores = score_context_signals(
        "I don't want to practice interviews. I need team meetings and manager communication."
    )
    assert scores["interviews"] == 0
    assert scores["workplace_communication"] >= 2


def test_score_context_signals_handles_common_stt_noise() -> None:
    scores = score_context_signals(
        "I wont intarview practis for ML injineer jab abrod."
    )
    assert scores["interviews"] > 0


def test_build_from_brief_normalizes_llm_context_alias() -> None:
    brief = {"status": "draft", "main_contexts": ["job interview"]}
    profile = build_goal_routing_from_goal_brief(brief)
    assert profile.primary_context == "interviews"
    assert profile.main_contexts == ("interviews",)


@pytest.mark.parametrize(
    "contexts, expected_primary",
    [
        (["interviews", "project_walkthrough"], "interviews"),
        (["workplace_communication"], "workplace_communication"),
        (["project_walkthrough", "workplace_communication"], "project_walkthrough"),
    ],
)
def test_primary_follows_first_main_context(
    contexts: list[str], expected_primary: str
) -> None:
    brief = {"status": "draft", "main_contexts": contexts}
    profile = resolve_goal_routing(goal_brief=brief)
    assert profile.primary_context == expected_primary
    assert profile.main_contexts[0] == expected_primary


@pytest.mark.parametrize(
    "text, expected_primary, expected_first_mission",
    [
        # Observed 2026-08-06: the owner picked the product's own "ML job"
        # option and was routed to workplace_communication, because "team" was
        # the only scoring word in the sentence.
        (
            "my closest goal right now is getting a new ML job in international team",
            "interviews",
            "foundation_speaking_drill",
        ),
        (
            "I need to prepare for job interviews",
            "interviews",
            "foundation_speaking_drill",
        ),
        (
            "I need English for team meetings and status updates",
            "workplace_communication",
            "stakeholder_explanation_drill",
        ),
        (
            "I need to explain my ML project architecture and impact",
            "project_walkthrough",
            "technical_project_walkthrough",
        ),
    ],
)
def test_job_search_goal_routes_to_interviews(
    text: str, expected_primary: str, expected_first_mission: str
) -> None:
    profile = resolve_goal_routing(last_user_message=text)
    assert profile.primary_context == expected_primary
    assert profile.first_mission_task_type == expected_first_mission


def test_job_search_signal_outranks_a_lone_workplace_word() -> None:
    scores = score_context_signals("looking for a new job with the team")
    assert scores["interviews"] >= scores["workplace_communication"]


def test_workplace_heavy_goal_still_wins_over_single_job_word() -> None:
    profile = resolve_goal_routing(
        last_user_message=(
            "In my job I present status updates to stakeholders and clients "
            "in cross-functional meetings"
        )
    )
    assert profile.primary_context == "workplace_communication"


def test_job_search_signals_do_not_override_a_confirmed_brief() -> None:
    brief = {"status": "confirmed", "main_contexts": ["workplace_communication"]}
    profile = resolve_goal_routing(
        goal_brief=brief,
        last_user_message="I want a new job offer",
    )
    assert profile.primary_context == "workplace_communication"
    assert profile.decision_source == "user_confirmed"
