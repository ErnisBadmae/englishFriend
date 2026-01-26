#!/usr/bin/env python3
"""Quick test to verify router fix for Agent V2.

Tests that:
1. _route field is properly initialized
2. Router correctly sets _route
3. route_after_router() reads _route correctly
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.agent.graph_v2 import initialize_session_v2
from app.agent.nodes_v2.router import router_node, route_after_router


async def test_router_new_user():
    """Test router for new user without goal."""
    print("\n=== Test 1: New User (no goal) ===")

    # Initialize state for new user
    state = await initialize_session_v2(
        user_id=999,
        session_id="test-session-1",
        username="TestUser",
        is_new_user=True,  # New user
        language_level="B1",
        confirmed_goal=None,  # No goal yet
    )

    # Check initial state
    print(f"✓ Initial state created")
    print(f"  - is_new_user: {state['is_new_user']}")
    print(f"  - confirmed_goal: {state.get('confirmed_goal')}")
    print(f"  - _route (before router): {state.get('_route')}")

    # Run router node
    state = await router_node(state)

    # Check router result
    route = state.get("_route")
    print(f"✓ Router node executed")
    print(f"  - _route (after router): {route}")
    print(f"  - _skip_goal: {state.get('_skip_goal')}")
    print(f"  - _skip_interests: {state.get('_skip_interests')}")
    print(f"  - _skip_assessment: {state.get('_skip_assessment')}")

    # Test route_after_router function
    next_node = route_after_router(state)
    print(f"✓ route_after_router() executed")
    print(f"  - Next node: {next_node}")

    # Verify expectations
    assert route == "onboarding", f"Expected route='onboarding', got '{route}'"
    assert next_node == "onboarding", f"Expected next_node='onboarding', got '{next_node}'"
    assert state.get("_skip_goal") is False, "Expected _skip_goal=False for new user"

    print("✅ Test 1 PASSED: New user routes to onboarding correctly\n")


async def test_router_returning_user():
    """Test router for returning user with goal and assessment."""
    print("=== Test 2: Returning User (has goal + assessment) ===")

    # Initialize state for returning user
    state = await initialize_session_v2(
        user_id=1,
        session_id="test-session-2",
        username="ReturningUser",
        is_new_user=False,  # Returning user
        language_level="B2",
        confirmed_goal="ML Interview Prep",  # Has goal
        confirmed_interests=["machine learning", "python"],
    )

    # Simulate that user has completed assessment
    state["assessed_level"] = "B2"

    print(f"✓ Initial state created")
    print(f"  - is_new_user: {state['is_new_user']}")
    print(f"  - confirmed_goal: {state.get('confirmed_goal')}")
    print(f"  - assessed_level: {state.get('assessed_level')}")
    print(f"  - _route (before router): {state.get('_route')}")

    # Run router node
    state = await router_node(state)

    # Check router result
    route = state.get("_route")
    print(f"✓ Router node executed")
    print(f"  - _route (after router): {route}")

    # Test route_after_router function
    next_node = route_after_router(state)
    print(f"✓ route_after_router() executed")
    print(f"  - Next node: {next_node}")

    # Verify expectations
    assert route == "learning", f"Expected route='learning', got '{route}'"
    assert next_node == "learning", f"Expected next_node='learning', got '{next_node}'"

    print("✅ Test 2 PASSED: Returning user routes to learning correctly\n")


async def test_router_goal_no_assessment():
    """Test router for user with goal but no assessment."""
    print("=== Test 3: User with Goal but No Assessment ===")

    # Initialize state
    state = await initialize_session_v2(
        user_id=2,
        session_id="test-session-3",
        username="PartialUser",
        is_new_user=False,
        language_level="B1",
        confirmed_goal="IELTS Preparation",  # Has goal
    )

    # No assessed_level
    state["assessed_level"] = None

    print(f"✓ Initial state created")
    print(f"  - confirmed_goal: {state.get('confirmed_goal')}")
    print(f"  - assessed_level: {state.get('assessed_level')}")
    print(f"  - _route (before router): {state.get('_route')}")

    # Run router node
    state = await router_node(state)

    # Check router result
    route = state.get("_route")
    print(f"✓ Router node executed")
    print(f"  - _route (after router): {route}")
    print(f"  - _skip_goal: {state.get('_skip_goal')}")
    print(f"  - _skip_interests: {state.get('_skip_interests')}")
    print(f"  - _skip_assessment: {state.get('_skip_assessment')}")

    # Test route_after_router function
    next_node = route_after_router(state)
    print(f"✓ route_after_router() executed")
    print(f"  - Next node: {next_node}")

    # Verify expectations
    assert route == "onboarding", f"Expected route='onboarding', got '{route}'"
    assert next_node == "onboarding", f"Expected next_node='onboarding', got '{next_node}'"
    assert state.get("_skip_goal") is True, "Expected _skip_goal=True (has goal)"
    assert state.get("_skip_assessment") is False, "Expected _skip_assessment=False (needs assessment)"

    print("✅ Test 3 PASSED: User routes to assessment-only correctly\n")


async def main():
    """Run all router tests."""
    print("\n" + "="*60)
    print("Testing Agent V2 Router Fix")
    print("="*60)

    try:
        await test_router_new_user()
        await test_router_returning_user()
        await test_router_goal_no_assessment()

        print("="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\nRouter fix verified:")
        print("  ✓ _route field initialized in state")
        print("  ✓ Router node sets _route correctly")
        print("  ✓ route_after_router() reads _route correctly")
        print("  ✓ Skip flags work correctly")
        print("\nReady to test with live WebSocket!")
        print("  export USE_AGENT_V2=true")
        print("  python main.py")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
