from app.services.missions.contracts import (
    PROJECT_WALKTHROUGH_CONTRACT,
    extract_mission_slots,
    plan_mission_turn,
    recast_project_answer,
)


def test_project_contract_extracts_slots_without_case_specific_branching():
    slots = extract_mission_slots(
        PROJECT_WALKTHROUGH_CONTRACT,
        "i ve created llm agent and rag pipeline to analys documents in buildings",
    )

    assert "problem" in slots
    assert "approach" in slots
    assert "metric" not in slots
    assert "impact" not in slots


def test_project_contract_recasts_build_phrase_generically():
    recast = recast_project_answer(
        "i ve created llm agent and rag pipeline to analys documents in buildings"
    )

    assert recast == "I built an LLM agent and RAG pipeline to analyze documents in buildings."


def test_project_contract_policy_asks_first_missing_slot():
    decision = plan_mission_turn(
        PROJECT_WALKTHROUGH_CONTRACT,
        "i ve created llm agent and rag pipeline to analys documents in buildings",
    )

    assert decision is not None
    assert decision.updated_slots["problem"] == "captured"
    assert decision.updated_slots["approach"] == "captured"
    assert "metric or success signal" in decision.response_text.lower()
    assert "problem, approach, metric, and impact" not in decision.response_text.lower()


def test_project_contract_policy_asks_impact_after_metric():
    decision = plan_mission_turn(
        PROJECT_WALKTHROUGH_CONTRACT,
        "We measured answer accuracy and retrieval quality.",
        existing_slots={
            "problem": "captured",
            "approach": "captured",
        },
    )

    assert decision is not None
    assert decision.updated_slots["metric"] == "captured"
    assert "what changed after this project" in decision.response_text.lower()

