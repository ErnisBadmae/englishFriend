"""Unit tests for the pre-routing scope gate.

Plan contract (scalable-booping-quilt.md, "Pre-routing scope gate"):
  - career-signal => in_scope
  - generic English wording with no career anchor => generic_english_only
  - anxiety / vague intent with no career anchor => needs_narrowing
  - empty transcript => default needs_narrowing
"""

from app.services.routing.goal_routing import resolve_scope_status


def test_empty_inputs_default_to_needs_narrowing():
    assert resolve_scope_status() == "needs_narrowing"
    assert resolve_scope_status(goal_brief={}) == "needs_narrowing"
    assert resolve_scope_status(last_user_message="") == "needs_narrowing"


def test_routing_ready_goal_brief_is_in_scope():
    brief = {
        "primary_goal": "Pass an ML interview abroad",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "main_contexts": ["interviews"],
    }
    assert resolve_scope_status(goal_brief=brief) == "in_scope"


def test_career_role_signal_resolves_in_scope():
    assert (
        resolve_scope_status(last_user_message="I am a backend engineer at a startup.")
        == "in_scope"
    )


def test_interview_signal_resolves_in_scope():
    assert (
        resolve_scope_status(
            last_user_message="I want to prepare for a technical interview next month."
        )
        == "in_scope"
    )


def test_workplace_signal_resolves_in_scope():
    assert (
        resolve_scope_status(
            last_user_message="I need help with stakeholder updates and team meetings."
        )
        == "in_scope"
    )


def test_project_walkthrough_signal_resolves_in_scope():
    assert (
        resolve_scope_status(
            last_user_message="I want to walk through my ML project clearly."
        )
        == "in_scope"
    )


def test_generic_grammar_only_resolves_generic_english_only():
    assert (
        resolve_scope_status(
            last_user_message="My grammar is bad. I want to improve my grammar."
        )
        == "generic_english_only"
    )


def test_generic_vocabulary_only_resolves_generic_english_only():
    assert (
        resolve_scope_status(
            last_user_message="I want to learn more vocabulary and improve pronunciation."
        )
        == "generic_english_only"
    )


def test_anxiety_only_resolves_needs_narrowing():
    assert (
        resolve_scope_status(
            last_user_message="I am very anxious when I speak. I freeze."
        )
        == "needs_narrowing"
    )


def test_anxiety_plus_generic_resolves_needs_narrowing():
    """Mixed signals (anxiety + generic English) tilt toward narrowing question."""
    assert (
        resolve_scope_status(
            last_user_message="I am afraid to speak English and I want to improve grammar."
        )
        == "needs_narrowing"
    )


def test_vague_no_signal_resolves_needs_narrowing():
    assert (
        resolve_scope_status(
            last_user_message="I don't know where to start. Help me."
        )
        == "needs_narrowing"
    )


def test_career_anchor_overrides_generic_wording():
    """Career anchor wins over generic English signal."""
    assert (
        resolve_scope_status(
            last_user_message="As a developer I want to improve my grammar for work."
        )
        == "in_scope"
    )


def test_conversation_history_aggregated_into_decision():
    history = [
        {"role": "user", "content": "I'm preparing for interviews."},
        {"role": "assistant", "content": "What role are you targeting?"},
    ]
    assert (
        resolve_scope_status(
            conversation_history=history,
            last_user_message="ML Engineer at a US startup.",
        )
        == "in_scope"
    )
