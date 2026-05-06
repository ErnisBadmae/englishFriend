from scripts.replay_session import build_snapshot_excerpt, select_session_evidence


def test_select_session_evidence_returns_matching_item():
    items = [
        {"session_id": "s-1", "summary": "first"},
        {"session_id": "s-2", "summary": "second"},
    ]

    assert select_session_evidence("s-2", items) == {"session_id": "s-2", "summary": "second"}


def test_build_snapshot_excerpt_keeps_operator_focused_fields():
    snapshot = {
        "mission": {
            "mode": "mock_interview",
            "task_type": "foundation_speaking_drill",
            "title": "Interview intro",
            "reason": "Weak structure",
            "adaptation_reason": "Repeat intro clarity",
            "repeat_vs_advance": "repeat",
        },
        "setup": {"state": "ready_for_program", "scope_status": "in_scope", "progress": 100},
        "product_signals": {
            "activation_stage": "activated",
            "value_stage": "visible",
            "conversion_stage": "not_ready",
            "retention_stage": "unknown",
        },
        "monetization": {
            "value_visible": True,
            "value_signals": ["session_evidence"],
            "cta_reason": "first_session_evidence",
        },
        "session_evidence": {
            "latest": {"session_id": "s-1", "summary": "latest evidence"},
        },
    }

    excerpt = build_snapshot_excerpt(snapshot)

    assert excerpt["mission"]["task_type"] == "foundation_speaking_drill"
    assert excerpt["setup"]["scope_status"] == "in_scope"
    assert excerpt["product_signals"]["value_stage"] == "visible"
    assert excerpt["latest_session_evidence"]["session_id"] == "s-1"
