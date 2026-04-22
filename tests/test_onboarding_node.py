from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.nodes_v2.onboarding import (
    _apply_onboarding_action,
    _build_assessment_followup_question,
    _coerce_goal_brief_state,
    _infer_goal_brief_from_message,
    onboarding_node,
)
from app.agent.graph_v2 import initialize_session_v2, run_agent_turn_v2
from app.agent.state import AgentPhase, LearningModeEnum, create_initial_state
from app.services.ai.llm_provider import LLMEmptyContentError


def test_coerce_goal_brief_marks_routing_ready_goal_as_draft():
    brief = _coerce_goal_brief_state(
        {
            "primary_goal": "Get an ML role abroad",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "target_market": "international_company",
            "main_contexts": ["interviews"],
        }
    )

    assert brief["status"] == "draft"


def test_infer_goal_brief_from_noisy_ml_input_creates_draft():
    brief = _infer_goal_brief_from_message(
        "wanna improve vocabulary machine learning and pass interview for job abroad"
    )

    assert brief is not None
    assert brief["target_role"] == "ML Engineer"
    assert brief["domain"] == "machine_learning"
    assert brief["target_market"] == "international_company"
    assert "interviews" in brief["main_contexts"]
    assert brief["status"] == "draft"


def test_infer_goal_brief_accepts_doesnt_matter_as_company_context():
    brief = _infer_goal_brief_from_message(
        "doesnt matter for me whatever company, I just want machine learning interview practice",
        {
            "primary_goal": "Get an ML role abroad",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "main_contexts": ["interviews"],
        },
    )

    assert brief is not None
    assert brief["target_market"] == "international_company"
    assert brief["status"] == "draft"


def test_infer_goal_brief_keeps_explicit_workplace_context_first():
    brief = _infer_goal_brief_from_message(
        "I talk with product managers and operations team on standup and status update meetings",
        {
            "primary_goal": "Get an ML role abroad",
            "target_role": "ML Engineer",
            "domain": "machine_learning",
            "target_market": "international_company",
            "main_contexts": ["project_walkthrough"],
        },
    )

    assert brief is not None
    assert brief["main_contexts"][0] == "workplace_communication"
    assert "project_walkthrough" in brief["main_contexts"]


@pytest.mark.asyncio
async def test_transition_to_learning_moves_routing_ready_goal_to_first_useful_mission():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Get an ML role abroad",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews"],
        "status": "incomplete",
    }
    state["confirmed_goal"] = "Get an ML role abroad"
    state["goal_setup_complete"] = False

    updated = await _apply_onboarding_action(
        state,
        {"action": "transition_to_learning", "response_text": "Let's begin."},
        pedagogy=None,
    )

    assert updated["current_phase"] == AgentPhase.LEARNING_SESSION
    assert updated["setup_step"] == "first_useful_mission"
    # primary_context=interviews must anchor the first mission to a
    # foundation speaking drill, regardless of the ML domain field.
    assert updated["mission_task_type"] == "foundation_speaking_drill"
    assert "real mission" in updated["pending_response"].lower()


@pytest.mark.asyncio
async def test_goal_skipped_keeps_draft_and_moves_to_first_useful_mission():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["last_user_message"] = "I want a machine learning job abroad and need interview English"
    state["goal_brief"] = {
        "primary_goal": "Build English for an international ML/AI role with stronger interview and project communication.",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews", "project_walkthrough"],
        "status": "draft",
    }
    state["goal_setup_complete"] = True

    updated = await _apply_onboarding_action(
        state,
        {"action": "goal_skipped", "response_text": "skip"},
        pedagogy=None,
    )

    assert updated["goal_brief"]["status"] == "draft"
    assert updated["goal_setup_complete"] is True
    assert updated["current_phase"] == AgentPhase.LEARNING_SESSION
    # main_contexts[0] is "interviews" → foundation drill, not project walkthrough.
    assert updated["mission_task_type"] == "foundation_speaking_drill"
    assert "real mission" in updated["pending_response"].lower()


@pytest.mark.asyncio
async def test_transition_to_learning_allows_draft_goal_with_assessment():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Get an ML role abroad",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews", "project_walkthrough"],
        "status": "draft",
    }
    state["detected_goal"] = "Get an ML role abroad"
    state["goal_setup_complete"] = True
    state["assessed_level"] = "B1"

    updated = await _apply_onboarding_action(
        state,
        {"action": "transition_to_learning", "response_text": "Let's begin."},
        pedagogy=None,
    )

    assert updated["current_phase"] == AgentPhase.LEARNING_SESSION


def test_build_assessment_followup_question_is_short_for_draft_goal():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Get an ML role abroad",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews", "project_walkthrough"],
        "status": "draft",
    }

    prompt = _build_assessment_followup_question(state)

    assert "what do you do now?" in prompt.lower()
    assert "what role are you aiming for" not in prompt.lower()


@pytest.mark.asyncio
async def test_initialize_session_v2_treats_draft_goal_as_setup_complete():
    state = await initialize_session_v2(
        user_id=1,
        session_id="session-1",
        username="Student",
        is_new_user=False,
        language_level="B1",
        roadmap={
            "goal_brief": {
                "primary_goal": "Get an ML role abroad",
                "target_role": "ML Engineer",
                "domain": "machine_learning",
                "target_market": "international_company",
                "deadline_type": "open_ended",
                "main_contexts": ["interviews"],
                "status": "draft",
            }
        },
    )

    assert state["goal_setup_complete"] is True
    assert state["setup_step"] == "first_useful_mission"


@pytest.mark.asyncio
async def test_onboarding_first_mission_handoff_counts_turns_and_updates_history():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Get an ML role abroad",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews", "project_walkthrough"],
        "status": "draft",
    }
    state["goal_setup_complete"] = True
    state["_skip_assessment"] = True
    state["last_user_message"] = "I build machine learning models at work."

    updated = await onboarding_node(state)

    assert updated["turn_count"] == 1
    assert updated["current_phase"] == AgentPhase.LEARNING_SESSION
    assert updated["current_mode"] == LearningModeEnum.FREE_CONVERSATION
    # primary_context=interviews (first in main_contexts) → foundation drill.
    assert updated["mission_task_type"] == "foundation_speaking_drill"
    assert updated["conversation_history"][0]["role"] == "user"
    assert updated["conversation_history"][-1]["role"] == "assistant"
    assert "real mission" in updated["pending_response"].lower()


@pytest.mark.asyncio
async def test_onboarding_current_role_rejects_goal_statement_as_answer():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Get an ML role abroad",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews", "project_walkthrough"],
        "status": "draft",
    }
    state["goal_setup_complete"] = True
    state["current_mode"] = LearningModeEnum.ASSESSMENT
    state["assessment_step_index"] = 0
    state["last_user_message"] = "I want an ML engineer job abroad."

    updated = await onboarding_node(state)

    assert updated["assessment_answers"] == {}
    assert updated["assessment_step_index"] == 0
    assert "did not catch your current work clearly" in updated["pending_response"].lower()


@pytest.mark.asyncio
async def test_onboarding_empty_first_turn_asks_deterministic_goal_question():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["last_user_message"] = ""

    updated = await onboarding_node(state)

    assert updated["current_phase"] == AgentPhase.ONBOARDING
    assert updated["setup_step"] == "goal_setup"
    assert updated["last_question_type"] == "goal_setup"
    assert "what is closest right now" in updated["pending_response"].lower()


@pytest.mark.asyncio
async def test_onboarding_current_role_accepts_not_working_now_answer():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Get an ML role abroad",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews", "project_walkthrough"],
        "status": "draft",
    }
    state["goal_setup_complete"] = True
    state["current_mode"] = LearningModeEnum.ASSESSMENT
    state["assessment_step_index"] = 0
    state["last_user_message"] = "I don't work now. I want to get an ML engineer role."

    updated = await onboarding_node(state)

    assert updated["assessment_answers"]["current_role"] == "I don't work now. I want to get an ML engineer role."
    assert updated["assessment_step_index"] == 1
    assert "what role do you want next" in updated["pending_response"].lower()


@pytest.mark.asyncio
async def test_onboarding_current_role_accepts_affirmative_prefix_answer():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Get an ML role abroad",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews", "project_walkthrough"],
        "status": "draft",
    }
    state["goal_setup_complete"] = True
    state["current_mode"] = LearningModeEnum.ASSESSMENT
    state["assessment_step_index"] = 0
    state["low_signal_turn_streak"] = 1
    state["last_user_message"] = "Yes, I work as a data analyst now."

    updated = await onboarding_node(state)

    assert updated["assessment_answers"]["current_role"] == "Yes, I work as a data analyst now."
    assert updated["assessment_step_index"] == 1
    assert updated["low_signal_turn_streak"] == 0
    assert "what role do you want next" in updated["pending_response"].lower()


@pytest.mark.asyncio
async def test_onboarding_routing_ready_goal_answer_skips_llm_and_starts_first_mission():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["last_question_type"] = "goal_setup"
    state["last_user_message"] = "I want a machine learning engineer job abroad."

    updated = await onboarding_node(state)

    assert updated["goal_setup_complete"] is True
    assert updated["current_phase"] == AgentPhase.LEARNING_SESSION
    assert updated["current_mode"] == LearningModeEnum.FREE_CONVERSATION
    # "machine learning engineer job abroad" → primary_context=interviews →
    # foundation speaking drill, not a technical project walkthrough.
    assert updated["mission_task_type"] == "foundation_speaking_drill"
    assert updated["last_question_type"] == "first_mission_handoff"
    assert "real mission" in updated["pending_response"].lower()


@pytest.mark.asyncio
async def test_onboarding_llm_error_preserves_inferred_goal_signal():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["last_user_message"] = "I want to speak better in an international team."
    state["last_question_type"] = "goal_setup"

    with patch(
        "app.agent.nodes_v2.onboarding.get_llm_provider",
        return_value=MagicMock(generate=AsyncMock(side_effect=RuntimeError("boom"))),
    ), patch(
        "app.agent.nodes_v2.onboarding.get_prompt_service",
        return_value=MagicMock(log_usage=AsyncMock()),
    ), patch(
        "app.agent.nodes_v2.onboarding.get_pedagogy_logger",
        return_value=MagicMock(),
    ):
        updated = await onboarding_node(state)

    assert "having trouble" not in updated["pending_response"].lower()
    assert "workplace communication" in updated["pending_response"].lower()
    assert updated["goal_brief"]["main_contexts"][0] == "workplace_communication"


@pytest.mark.asyncio
async def test_run_agent_turn_v2_first_goal_answer_transitions_to_first_mission():
    state = await initialize_session_v2(
        user_id=1,
        session_id="session-1",
        username="Student",
        is_new_user=True,
    )

    state = await run_agent_turn_v2(state)
    updated = await run_agent_turn_v2(state, user_message="I want a machine learning engineer job abroad.")

    assert updated["goal_setup_complete"] is True
    assert updated["current_phase"] == AgentPhase.LEARNING_SESSION
    assert updated["current_mode"] == LearningModeEnum.FREE_CONVERSATION
    assert updated["mission_task_type"] == "foundation_speaking_drill"
    assert updated["last_question_type"] == "first_mission_handoff"
    assert updated["last_intent"]["type"] == "direct_answer"
    assert updated["last_intent"]["policy_action"] == "llm_turn"
    assert "real mission" in updated["pending_response"].lower()


@pytest.mark.asyncio
async def test_run_agent_turn_v2_second_turn_routes_into_learning_after_first_mission_handoff():
    state = await initialize_session_v2(
        user_id=1,
        session_id="session-1",
        username="Student",
        is_new_user=True,
    )
    state = await run_agent_turn_v2(state)
    state = await run_agent_turn_v2(state, user_message="I want a machine learning engineer job abroad.")
    updated = await run_agent_turn_v2(state, user_message="I built a churn model for e-commerce.")

    assert updated["current_phase"] == AgentPhase.LEARNING_SESSION
    # primary_context is sticky at "interviews" after first turn → mission stays
    # pinned to foundation drill even when later user input mentions a project.
    assert updated["mission_task_type"] == "foundation_speaking_drill"
    assert updated.get("session_complete_reason") is None
    assert updated["pending_response"]


@pytest.mark.asyncio
async def test_onboarding_current_role_assessment_does_not_reorder_explicit_workplace_context():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Speak better in an international ML team",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["workplace_communication", "project_walkthrough"],
        "status": "draft",
    }
    state["goal_setup_complete"] = True
    state["current_phase"] = AgentPhase.ASSESSMENT
    state["current_mode"] = LearningModeEnum.ASSESSMENT
    state["assessment_step_index"] = 0
    state["last_question_type"] = "current_role"
    state["last_user_message"] = (
        "now i am just learning ml theory and try to learn some math theorems and building pet project"
    )

    updated = await onboarding_node(state)

    assert updated["assessment_answers"]["current_role"] == state["last_user_message"]
    assert updated["goal_brief"]["main_contexts"][0] == "workplace_communication"
    assert "project_walkthrough" in updated["goal_brief"]["main_contexts"]


@pytest.mark.asyncio
async def test_run_agent_turn_v2_workplace_goal_survives_into_first_mission_selection():
    state = await initialize_session_v2(
        user_id=1,
        session_id="session-1",
        username="Student",
        is_new_user=True,
    )

    state = await run_agent_turn_v2(state)
    state = await run_agent_turn_v2(state, user_message="speaking better in an international team")
    updated = await run_agent_turn_v2(state, user_message="ML engineer job abroad")

    assert updated["goal_brief"]["main_contexts"][0] == "workplace_communication"
    assert updated["mission_task_type"] == "stakeholder_explanation_drill"
    assert updated["current_phase"] == AgentPhase.LEARNING_SESSION


@pytest.mark.asyncio
async def test_onboarding_explicit_correction_rewrites_primary_context_and_requires_confirmation():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Build English for ML Engineer interviews in an international company.",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews", "project_walkthrough"],
        "status": "draft",
    }
    state["goal_setup_complete"] = True
    state["current_phase"] = AgentPhase.ONBOARDING
    state["last_question_type"] = "goal_setup"
    state["last_user_message"] = (
        "Actually not interviews. I need workplace communication with product managers instead."
    )

    updated = await onboarding_node(state)

    assert updated["goal_brief"]["main_contexts"][0] == "workplace_communication"
    assert updated["goal_brief"]["routing_decision_source"] == "explicit_user_correction"
    assert updated["goal_needs_confirmation"] is True
    assert updated["current_phase"] == AgentPhase.ONBOARDING
    assert updated["last_question_type"] == "goal_setup"
    assert updated["confirmed_goal"] is None


@pytest.mark.asyncio
async def test_onboarding_explicit_correction_can_change_role_and_reset_confirmed_goal():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Build English for ML Engineer interviews in an international company.",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews"],
        "status": "confirmed",
        "confirmed_by_user": True,
    }
    state["confirmed_goal"] = "Build English for ML Engineer interviews in an international company."
    state["goal_setup_complete"] = True
    state["current_phase"] = AgentPhase.ONBOARDING
    state["last_question_type"] = "goal_setup"
    state["last_user_message"] = "Actually I need data scientist interviews instead."

    updated = await onboarding_node(state)

    assert updated["goal_brief"]["target_role"] == "Data Scientist"
    assert updated["goal_brief"]["domain"] == "data_science"
    assert updated["goal_brief"]["status"] == "draft"
    assert updated["goal_brief"]["main_contexts"][0] == "interviews"
    assert updated["confirmed_goal"] is None
    assert updated["goal_needs_confirmation"] is True


@pytest.mark.asyncio
async def test_onboarding_second_baseline_answer_asks_project_before_completion():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Get an ML role abroad",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews", "project_walkthrough"],
        "status": "draft",
    }
    state["goal_setup_complete"] = True
    state["current_mode"] = LearningModeEnum.ASSESSMENT
    state["assessment_step_index"] = 1
    state["assessment_answers"] = {
        "current_role": "I work as a data analyst now.",
    }
    state["last_user_message"] = "ML engineer."

    updated = await onboarding_node(state)

    assert updated.get("session_complete_reason") is None
    assert updated["assessment_step_index"] == 2
    assert updated["assessment_answers"]["target_role"] == "ML engineer."
    assert "tell me about one ml or work task" in updated["pending_response"].lower()


@pytest.mark.asyncio
async def test_onboarding_meta_answer_produces_provisional_baseline_instead_of_loop():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Get an ML role abroad",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews", "project_walkthrough"],
        "status": "draft",
    }
    state["goal_setup_complete"] = True
    state["current_mode"] = LearningModeEnum.ASSESSMENT
    state["assessment_step_index"] = 1
    state["assessment_answers"] = {"current_role": "I build machine learning models at work."}
    state["last_user_message"] = "I am waiting that you prepare my program."

    updated = await onboarding_node(state)

    assert updated["assessed_level"] in {"A2", "B1"}
    assert updated["baseline_provisional"] is True
    assert updated["assessment_status"] == "provisional"
    assert "what do you do now?" not in updated["pending_response"].lower()


@pytest.mark.asyncio
async def test_onboarding_baseline_completion_marks_session_handoff():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Get an ML role abroad",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews", "project_walkthrough"],
        "status": "draft",
    }
    state["goal_setup_complete"] = True
    state["current_mode"] = LearningModeEnum.ASSESSMENT
    state["assessment_step_index"] = 2
    state["assessment_answers"] = {
        "current_role": "I work as a data analyst now.",
        "target_role": "I want to become an ML engineer.",
    }
    state["last_user_message"] = "My recent project was churn prediction for e-commerce."

    updated = await onboarding_node(state)

    assert updated["assessed_level"] in {"A2", "B1"}
    assert updated["session_complete_reason"] == "baseline_complete"
    assert updated["session_complete_return_screen"] == "home"
    assert "dashboard" in updated["pending_response"].lower()


@pytest.mark.asyncio
async def test_onboarding_rejects_low_signal_project_answer():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["goal_brief"] = {
        "primary_goal": "Get an ML role abroad",
        "target_role": "ML Engineer",
        "domain": "machine_learning",
        "target_market": "international_company",
        "deadline_type": "open_ended",
        "main_contexts": ["interviews", "project_walkthrough"],
        "status": "draft",
    }
    state["goal_setup_complete"] = True
    state["current_mode"] = LearningModeEnum.ASSESSMENT
    state["assessment_step_index"] = 2
    state["assessment_answers"] = {
        "current_role": "I work as a data scientist.",
        "target_role": "ML engineer.",
    }
    state["last_user_message"] = "now sorry want to name to fire smoke test using and my age of test"

    updated = await onboarding_node(state)

    assert updated.get("assessed_level") is None
    assert updated["low_signal_turn_streak"] == 1
    assert "did not catch the project answer" in updated["pending_response"].lower()
    assert "project_task" not in updated["assessment_answers"]


@pytest.mark.asyncio
async def test_onboarding_empty_final_content_uses_goal_followup():
    state = create_initial_state(user_id=1, session_id="session-1")
    state["last_user_message"] = "help me"

    llm = MagicMock()
    llm.generate = AsyncMock(
        side_effect=LLMEmptyContentError(
            provider_name="llama_cpp",
            model="CPU Qwen 3.5 256k node3",
            finish_reason="length",
            has_reasoning=True,
            used_compat_retry=True,
        )
    )

    with patch("app.agent.nodes_v2.onboarding.get_llm_provider", return_value=llm), patch(
        "app.agent.nodes_v2.onboarding.get_prompt_service",
        return_value=MagicMock(log_usage=AsyncMock()),
    ), patch(
        "app.agent.nodes_v2.onboarding.get_pedagogy_logger",
        return_value=MagicMock(),
    ):
        updated = await onboarding_node(state)

    assert updated["needs_user_input"] is True
    assert "What is closest right now" in updated["pending_response"]
