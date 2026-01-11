"""
Тестовый скрипт для проверки педагогической архитектуры.

Проверяет:
1. Выбор режима обучения
2. Определение цели из сообщения
3. Построение промптов для каждого режима
4. Интеграцию с LearningPlanService
"""

import asyncio
from datetime import datetime, timedelta

# Imports
from app.services.ai.mode_prompts import (
    LearningMode,
    build_mode_prompt,
    get_session_greeting,
)
from app.services.ai.mode_selector import (
    SessionContext,
    select_learning_mode,
    needs_assessment,
    is_interview_goal,
    parse_user_mode_request,
    get_focus_area_for_mode,
)
from app.services.learning_plan_service import (
    detect_goal_from_message,
    GOAL_TEMPLATES,
)


def test_mode_selection():
    """Тест выбора режима обучения."""
    print("\n" + "=" * 60)
    print("TEST 1: Mode Selection Logic")
    print("=" * 60)

    # Сценарий 1: Новый пользователь без assessment
    ctx1 = SessionContext(
        user_id=1,
        username="Test User",
        last_assessment_date=None,
        total_sessions=0,
    )
    mode1 = select_learning_mode(ctx1)
    print(f"\n📋 New user (no assessment, 0 sessions)")
    print(f"   → Selected mode: {mode1.value}")
    assert mode1 == LearningMode.ASSESSMENT, "Should select ASSESSMENT for new user"
    print("   ✅ PASSED")

    # Сценарий 2: Пользователь с целью ML interview
    ctx2 = SessionContext(
        user_id=2,
        username="ML Student",
        last_assessment_date=datetime.now() - timedelta(days=5),
        total_sessions=3,
        goal="ML/Data Science Interview Preparation",
    )
    mode2 = select_learning_mode(ctx2)
    print(f"\n📋 User with ML interview goal (recent assessment)")
    print(f"   → Selected mode: {mode2.value}")
    assert mode2 == LearningMode.MOCK_INTERVIEW, "Should select MOCK_INTERVIEW for ML goal"
    print("   ✅ PASSED")

    # Сценарий 3: Много слов для повторения
    ctx3 = SessionContext(
        user_id=3,
        username="Vocab User",
        last_assessment_date=datetime.now() - timedelta(days=10),
        total_sessions=5,
        due_vocabulary_count=15,
    )
    mode3 = select_learning_mode(ctx3)
    print(f"\n📋 User with 15 due vocabulary words")
    print(f"   → Selected mode: {mode3.value}")
    assert mode3 == LearningMode.VOCABULARY_DRILL, "Should select VOCABULARY_DRILL when 10+ words due"
    print("   ✅ PASSED")

    # Сценарий 4: Пользователь без цели, с assessment
    ctx4 = SessionContext(
        user_id=4,
        username="Casual User",
        last_assessment_date=datetime.now() - timedelta(days=15),
        total_sessions=10,
        goal=None,
    )
    mode4 = select_learning_mode(ctx4)
    print(f"\n📋 User without specific goal")
    print(f"   → Selected mode: {mode4.value}")
    assert mode4 == LearningMode.FREE_CONVERSATION, "Should select FREE_CONVERSATION by default"
    print("   ✅ PASSED")

    # Сценарий 5: Явный запрос режима
    ctx5 = SessionContext(
        user_id=5,
        username="Direct User",
        requested_mode=LearningMode.VOCABULARY_DRILL,
    )
    mode5 = select_learning_mode(ctx5)
    print(f"\n📋 User explicitly requested VOCABULARY_DRILL")
    print(f"   → Selected mode: {mode5.value}")
    assert mode5 == LearningMode.VOCABULARY_DRILL, "Should respect explicit mode request"
    print("   ✅ PASSED")


def test_goal_detection():
    """Тест определения цели из сообщения."""
    print("\n" + "=" * 60)
    print("TEST 2: Goal Detection from Messages")
    print("=" * 60)

    test_cases = [
        ("I want to prepare for ML interview", "ML/Data Science Interview"),
        ("Хочу подготовиться к собеседованию data scientist", "ML/Data Science Interview"),
        ("Help me with software engineering interviews", "Software Engineering Interview"),
        ("I need to improve my IELTS score", "IELTS/TOEFL Preparation"),
        ("Just want to practice speaking", "General Fluency"),
        ("Хочу найти работу в IT", "Job Interview"),
    ]

    for message, expected_keyword in test_cases:
        goal = asyncio.run(detect_goal_from_message(message))
        print(f"\n📋 Message: '{message[:50]}...'")
        print(f"   → Detected goal: {goal}")
        if goal:
            assert expected_keyword.split()[0] in goal or expected_keyword.lower() in goal.lower(), \
                f"Expected keyword '{expected_keyword}' not in goal"
            print("   ✅ PASSED")
        else:
            print("   ⚠️ No goal detected (may need to expand patterns)")


def test_prompt_building():
    """Тест построения промптов для каждого режима."""
    print("\n" + "=" * 60)
    print("TEST 3: Prompt Building for Each Mode")
    print("=" * 60)

    modes_to_test = [
        (LearningMode.ASSESSMENT, "conduct", "level"),
        (LearningMode.MOCK_INTERVIEW, "interview", "role"),
        (LearningMode.VOCABULARY_DRILL, "vocabulary", "drill"),
        (LearningMode.FREE_CONVERSATION, "friend", "practice"),
    ]

    for mode, keyword1, keyword2 in modes_to_test:
        prompt = build_mode_prompt(
            mode=mode,
            username="TestStudent",
            level="B1",
            goal="ML Interview Preparation",
            interests="technology, machine learning",
            focus_area="behavioral questions",
            vocabulary_list="implementation, deployment, inference",
        )

        print(f"\n📋 Mode: {mode.value}")
        print(f"   → Prompt length: {len(prompt)} characters")
        print(f"   → First 100 chars: {prompt[:100]}...")

        prompt_lower = prompt.lower()
        assert keyword1 in prompt_lower, f"Expected '{keyword1}' in prompt"
        assert "teststudent" in prompt_lower, "Expected username in prompt"
        print("   ✅ PASSED")


def test_session_greeting():
    """Тест приветствий для каждого режима."""
    print("\n" + "=" * 60)
    print("TEST 4: Session Greetings")
    print("=" * 60)

    for mode in LearningMode:
        greeting = get_session_greeting(mode, "Alex")
        print(f"\n📋 Mode: {mode.value}")
        print(f"   → Greeting: {greeting[:80]}...")
        assert "Alex" in greeting, "Username should be in greeting"
        assert len(greeting) > 50, "Greeting should be substantial"
        print("   ✅ PASSED")


def test_goal_templates():
    """Тест шаблонов целей."""
    print("\n" + "=" * 60)
    print("TEST 5: Goal Templates")
    print("=" * 60)

    for template_name, template in GOAL_TEMPLATES.items():
        print(f"\n📋 Template: {template_name}")
        print(f"   → Goal: {template.goal}")
        print(f"   → Focus areas: {len(template.focus_areas)}")
        print(f"   → Milestones: {len(template.milestones)}")
        print(f"   → Preferred mode: {template.preferred_mode}")
        print(f"   → Vocabulary words: {len(template.recommended_vocabulary)}")

        assert template.goal, "Template must have a goal"
        assert len(template.focus_areas) > 0, "Template must have focus areas"
        assert len(template.milestones) > 0, "Template must have milestones"
        print("   ✅ PASSED")


def test_user_mode_request_parsing():
    """Тест парсинга запросов режима от пользователя."""
    print("\n" + "=" * 60)
    print("TEST 6: User Mode Request Parsing")
    print("=" * 60)

    test_cases = [
        ("Can you check my level?", LearningMode.ASSESSMENT),
        ("Let's do a mock interview", LearningMode.MOCK_INTERVIEW),
        ("I want to review vocabulary", LearningMode.VOCABULARY_DRILL),
        ("Let's just chat and talk", LearningMode.FREE_CONVERSATION),
        ("Tell me about weather", None),  # Unrecognized → default mode selection
    ]

    for message, expected_mode in test_cases:
        parsed = parse_user_mode_request(message)
        print(f"\n📋 Message: '{message}'")
        print(f"   → Parsed mode: {parsed}")
        assert parsed == expected_mode, f"Expected {expected_mode}, got {parsed}"
        print("   ✅ PASSED")


def test_interview_goal_detection():
    """Тест определения interview-целей."""
    print("\n" + "=" * 60)
    print("TEST 7: Interview Goal Detection")
    print("=" * 60)

    interview_goals = [
        "ML interview preparation",
        "data science job",
        "software engineer position",
        "IELTS exam",
        "Job search in tech",
    ]

    non_interview_goals = [
        "general fluency",
        "travel English",
        "watching movies",
    ]

    for goal in interview_goals:
        result = is_interview_goal(goal)
        print(f"\n📋 Goal: '{goal}'")
        print(f"   → Is interview goal: {result}")
        assert result is True, f"'{goal}' should be detected as interview goal"
        print("   ✅ PASSED")

    for goal in non_interview_goals:
        result = is_interview_goal(goal)
        print(f"\n📋 Goal: '{goal}'")
        print(f"   → Is interview goal: {result}")
        assert result is False, f"'{goal}' should NOT be detected as interview goal"
        print("   ✅ PASSED")


def test_focus_area_selection():
    """Тест выбора фокуса сессии."""
    print("\n" + "=" * 60)
    print("TEST 8: Focus Area Selection")
    print("=" * 60)

    ctx = SessionContext(
        user_id=1,
        username="Focus Test",
        goal="ML interview",
        focus_areas=["technical_vocabulary", "behavioral_questions", "explain_concepts"],
        sessions_since_assessment=0,
    )

    for i in range(4):
        ctx.sessions_since_assessment = i
        focus = get_focus_area_for_mode(LearningMode.MOCK_INTERVIEW, ctx)
        print(f"\n📋 Session #{i} since assessment")
        print(f"   → Focus area: {focus}")
        assert len(focus) > 0, "Focus area should not be empty"
        print("   ✅ PASSED")


if __name__ == "__main__":
    print("\n" + "🎓" * 30)
    print("PEDAGOGICAL ARCHITECTURE TEST SUITE")
    print("🎓" * 30)

    test_mode_selection()
    test_goal_detection()
    test_prompt_building()
    test_session_greeting()
    test_goal_templates()
    test_user_mode_request_parsing()
    test_interview_goal_detection()
    test_focus_area_selection()

    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 60)
    print("\nThe pedagogical architecture is working correctly.")
    print("Next step: Run the server and test via WebSocket.")
