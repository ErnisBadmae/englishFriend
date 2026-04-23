from app.services.goal_brief_contract import (
    goal_brief_missing_labels,
    goal_brief_setup_progress,
    is_goal_brief_complete,
    is_goal_brief_routing_ready,
    normalize_goal_brief,
    normalize_goal_brief_contexts,
)


def test_routing_ready_does_not_require_target_market_or_deadline():
    brief = {
        "primary_goal": "Explain my ML project in English",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "main_contexts": ["project_walkthrough"],
    }

    assert is_goal_brief_routing_ready(brief) is True
    assert is_goal_brief_complete(brief) is False


def test_missing_labels_routing_only_returns_blocking_fields():
    brief = {
        "primary_goal": "Improve English",
        "domain": "machine_learning",
    }

    assert goal_brief_missing_labels(brief, mode="routing") == [
        "target role",
        "practice context",
    ]


def test_missing_labels_full_includes_enrichment_fields_after_blocking_fields():
    brief = {
        "primary_goal": "Improve English",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "main_contexts": ["interviews"],
    }

    assert goal_brief_missing_labels(brief, mode="full") == [
        "target company context",
        "timeline",
    ]


def test_setup_progress_counts_enrichment_without_blocking_handoff():
    brief = {
        "primary_goal": "Explain my ML project in English",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "deadline_type": "open_ended",
        "main_contexts": ["project_walkthrough"],
    }

    assert goal_brief_setup_progress(brief, assessment_complete=False) == 71
    assert goal_brief_setup_progress(brief, assessment_complete=True) == 86


def test_normalize_goal_contexts_maps_aliases_to_canonical_enums():
    assert normalize_goal_brief_contexts(
        ["job interview", "client meeting", "technical walkthrough", "unknown"]
    ) == ["interviews", "workplace_communication", "project_walkthrough"]


def test_routing_ready_rejects_unknown_llm_context_labels():
    brief = {
        "primary_goal": "Improve English",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "main_contexts": ["random coaching mode"],
    }

    assert normalize_goal_brief(brief)["main_contexts"] == []
    assert is_goal_brief_routing_ready(brief) is False


def test_routing_ready_accepts_llm_alias_after_normalization():
    brief = {
        "primary_goal": "Improve English",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "main_contexts": ["job interview"],
    }

    assert normalize_goal_brief(brief)["main_contexts"] == ["interviews"]
    assert is_goal_brief_routing_ready(brief) is True
