"""
Тест WebSocket педагогической системы.

Проверяет полный flow:
1. Подключение пользователя
2. Отправка сообщения о цели (ML interview)
3. Проверка, что режим переключается на MOCK_INTERVIEW
4. Проверка, что промпт содержит нужные элементы
"""

import asyncio
import json
from datetime import datetime

# Test imports
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.services.learning_plan_service import LearningPlanService, detect_goal_from_message
from app.services.ai.mode_selector import SessionContext, select_learning_mode, parse_user_mode_request
from app.services.ai.mode_prompts import LearningMode, build_mode_prompt, get_session_greeting


async def simulate_voice_session(user_id: int = 1, first_message: str = "I want to prepare for ML interview"):
    """
    Симуляция voice session без запуска сервера.

    Проверяет логику, которая выполняется при подключении пользователя.
    """
    print("\n" + "=" * 70)
    print("SIMULATING VOICE SESSION - Pedagogical Flow Test")
    print("=" * 70)

    # Create async engine (settings.database_url already includes asyncpg)
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        print(f"\n📌 User ID: {user_id}")
        print(f"📌 First message: '{first_message}'")

        # Step 1: Initialize LearningPlanService
        print("\n--- Step 1: Loading Learning Plan ---")
        learning_plan_service = LearningPlanService(db)
        learning_plan = await learning_plan_service.get_or_create_plan(user_id)

        goal = learning_plan_service.get_goal(learning_plan)
        focus_areas = learning_plan_service.get_focus_areas(learning_plan)
        preferred_mode = learning_plan_service.get_preferred_mode(learning_plan)
        last_assessment = learning_plan_service.get_last_assessment_date(learning_plan)
        session_count = learning_plan_service.get_session_count(learning_plan)

        print(f"   Current goal: {goal}")
        print(f"   Focus areas: {focus_areas}")
        print(f"   Preferred mode: {preferred_mode}")
        print(f"   Last assessment: {last_assessment}")
        print(f"   Sessions completed: {session_count}")

        # Step 2: Detect goal from first message
        print("\n--- Step 2: Goal Detection ---")
        detected_goal = await detect_goal_from_message(first_message)
        print(f"   Detected goal from message: {detected_goal}")

        if detected_goal and not goal:
            print("   → Setting new goal...")
            learning_plan = await learning_plan_service.set_goal(user_id, detected_goal)
            goal = detected_goal
            focus_areas = learning_plan_service.get_focus_areas(learning_plan)
            preferred_mode = learning_plan_service.get_preferred_mode(learning_plan)
            print(f"   ✅ Goal set: {goal}")
            print(f"   ✅ Focus areas: {focus_areas}")
            print(f"   ✅ Preferred mode: {preferred_mode}")

        # Step 3: Build session context
        print("\n--- Step 3: Building Session Context ---")
        session_context = SessionContext(
            user_id=user_id,
            username="TestStudent",
            language_level="B1",
            goal=goal,
            focus_areas=focus_areas,
            preferred_mode=preferred_mode,
            last_assessment_date=last_assessment,
            total_sessions=session_count,
            due_vocabulary_count=3,  # Simulate some due words
        )
        print(f"   Context created: {session_context}")

        # Step 4: Select learning mode
        print("\n--- Step 4: Mode Selection ---")
        current_mode = select_learning_mode(session_context)
        print(f"   Selected mode: {current_mode.value}")

        # Explain why
        if session_context.last_assessment_date is None and session_context.total_sessions < 1:
            print("   Reason: New user without assessment → ASSESSMENT")
        elif session_context.due_vocabulary_count >= 10:
            print("   Reason: 10+ words due for review → VOCABULARY_DRILL")
        elif goal and "interview" in goal.lower():
            print("   Reason: Interview goal detected → MOCK_INTERVIEW")
        else:
            print("   Reason: Default → FREE_CONVERSATION")

        # Step 5: Check for explicit mode request
        print("\n--- Step 5: User Mode Request Parsing ---")
        explicit_mode = parse_user_mode_request(first_message)
        if explicit_mode:
            print(f"   User explicitly requested: {explicit_mode.value}")
            current_mode = explicit_mode
        else:
            print("   No explicit mode request detected")

        # Step 6: Build mode-specific prompt
        print("\n--- Step 6: Building Mode Prompt ---")
        system_prompt = build_mode_prompt(
            mode=current_mode,
            username="TestStudent",
            level="B1",
            goal=goal or "improve English",
            interests="technology, machine learning",
            focus_area=focus_areas[0] if focus_areas else "general communication",
            vocabulary_list="implementation, deployment, inference" if current_mode == LearningMode.VOCABULARY_DRILL else "",
        )

        print(f"   Prompt mode: {current_mode.value}")
        print(f"   Prompt length: {len(system_prompt)} chars")
        print(f"   Prompt preview (first 300 chars):\n")
        print("-" * 50)
        print(system_prompt[:300])
        print("-" * 50)

        # Step 7: Get session greeting
        print("\n--- Step 7: Session Greeting ---")
        greeting = get_session_greeting(current_mode, "TestStudent")
        print(f"   Greeting: {greeting}")

        # Step 8: Verify correct mode for ML interview goal
        print("\n--- Step 8: Verification ---")

        if "ml" in first_message.lower() or "interview" in first_message.lower():
            if current_mode == LearningMode.MOCK_INTERVIEW:
                print("   ✅ CORRECT: ML Interview goal → MOCK_INTERVIEW mode")
            elif current_mode == LearningMode.ASSESSMENT:
                print("   ✅ CORRECT: New user → ASSESSMENT first (before interview practice)")
            else:
                print(f"   ❌ UNEXPECTED: Got {current_mode.value} instead of MOCK_INTERVIEW or ASSESSMENT")

        # Check prompt content
        if current_mode == LearningMode.MOCK_INTERVIEW:
            if "interviewer" in system_prompt.lower():
                print("   ✅ CORRECT: Prompt contains interviewer persona")
            else:
                print("   ❌ UNEXPECTED: Prompt missing interviewer persona")

            if "behavioral" in system_prompt.lower():
                print("   ✅ CORRECT: Prompt includes behavioral questions")
            else:
                print("   ⚠️ NOTE: Prompt might need behavioral questions section")

        print("\n" + "=" * 70)
        print("SESSION SIMULATION COMPLETE")
        print("=" * 70)

        return {
            "goal": goal,
            "mode": current_mode.value,
            "greeting": greeting,
            "prompt_length": len(system_prompt),
        }


async def test_multiple_scenarios():
    """Test multiple user scenarios."""
    print("\n" + "🎯" * 35)
    print("TESTING MULTIPLE SCENARIOS")
    print("🎯" * 35)

    scenarios = [
        {
            "user_id": 101,
            "message": "I want to prepare for ML interview at Google",
            "expected_goal": "ML/Data Science Interview",
        },
        {
            "user_id": 102,
            "message": "Хочу подготовиться к собеседованию на позицию Data Scientist",
            "expected_goal": "ML/Data Science Interview",
        },
        {
            "user_id": 103,
            "message": "Help me improve my IELTS speaking score",
            "expected_goal": "IELTS/TOEFL Preparation",
        },
        {
            "user_id": 104,
            "message": "Just want to practice casual English conversation",
            "expected_goal": "General Fluency",
        },
    ]

    results = []
    for scenario in scenarios:
        print(f"\n{'='*60}")
        print(f"Scenario: {scenario['message'][:50]}...")
        result = await simulate_voice_session(
            user_id=scenario["user_id"],
            first_message=scenario["message"],
        )
        result["scenario"] = scenario
        results.append(result)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY OF ALL SCENARIOS")
    print("=" * 70)

    for r in results:
        scenario = r["scenario"]
        status = "✅" if r["goal"] else "⚠️"
        print(f"\n{status} User {scenario['user_id']}: '{scenario['message'][:40]}...'")
        print(f"   Goal: {r['goal']} (expected: {scenario['expected_goal']})")
        print(f"   Mode: {r['mode']}")


if __name__ == "__main__":
    print("\n" + "🚀" * 35)
    print("PEDAGOGICAL WEBSOCKET FLOW TEST")
    print("🚀" * 35)

    asyncio.run(simulate_voice_session(
        user_id=1,
        first_message="I want to prepare for ML interview"
    ))
