"""E2E Test for LangGraph Agent.

Tests the full conversation flow through the new /chat/v2 endpoint:
1. New user onboarding (goal discovery + confirmation)
2. Interest probing
3. Assessment
4. Program building
5. Learning session
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import websockets


async def test_agent_new_user_flow():
    """Test complete onboarding flow for a new user."""
    print("\n=== Testing LangGraph Agent (New User Flow) ===\n")

    uri = "ws://localhost:8000/api/v1/voice/chat/v2?user_id=999999"

    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connected to /chat/v2")

            # Receive connection message
            msg = await websocket.recv()
            data = json.loads(msg)
            print(f"✓ Connected: phase={data.get('phase')}, is_new={data.get('is_new_user')}")

            # Should receive initial greeting/question
            msg = await websocket.recv()
            data = json.loads(msg)
            if data.get("type") == "transcript":
                print(f"✓ Initial question: {data.get('text')[:80]}...")

            # Simulate user responding about their goal
            print("\n--- Step 1: Goal Discovery ---")
            await websocket.send(json.dumps({
                "type": "text",
                "text": "I want to prepare for machine learning interviews"
            }))

            # Wait for responses
            responses = []
            for _ in range(3):  # Expect: user transcript, assistant transcript, (maybe audio)
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(msg)
                    responses.append(data)
                    if data.get("type") == "transcript" and data.get("role") == "assistant":
                        print(f"✓ Agent response: {data.get('text')[:80]}...")
                except asyncio.TimeoutError:
                    break

            # Check if agent is asking for confirmation
            last_response = next((r for r in reversed(responses) if r.get("type") == "transcript" and r.get("role") == "assistant"), None)
            if last_response and ("right" in last_response.get("text", "").lower() or "correct" in last_response.get("text", "").lower()):
                print("✓ Agent asking for goal confirmation")

                # Confirm the goal
                print("\n--- Step 2: Goal Confirmation ---")
                await websocket.send(json.dumps({
                    "type": "text",
                    "text": "Yes, that's right"
                }))

                # Wait for confirmation response
                responses = []
                for _ in range(3):
                    try:
                        msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        data = json.loads(msg)
                        responses.append(data)
                        if data.get("type") == "transcript" and data.get("role") == "assistant":
                            print(f"✓ Agent response: {data.get('text')[:80]}...")
                    except asyncio.TimeoutError:
                        break

                # Check for phase change to interest_probe
                phase_change = next((r for r in responses if r.get("type") == "phase_changed"), None)
                if phase_change:
                    print(f"✓ Phase changed to: {phase_change.get('phase')}")

            # Interests
            print("\n--- Step 3: Interest Probe ---")
            await websocket.send(json.dumps({
                "type": "text",
                "text": "I like technology, machine learning, and data science"
            }))

            responses = []
            for _ in range(3):
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(msg)
                    responses.append(data)
                    if data.get("type") == "transcript" and data.get("role") == "assistant":
                        print(f"✓ Agent response: {data.get('text')[:80]}...")
                except asyncio.TimeoutError:
                    break

            # Assessment
            print("\n--- Step 4: Assessment ---")
            # Answer first assessment question
            await websocket.send(json.dumps({
                "type": "text",
                "text": "My name is Test User and I'm from Russia"
            }))

            responses = []
            for _ in range(3):
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(msg)
                    responses.append(data)
                    if data.get("type") == "transcript" and data.get("role") == "assistant":
                        print(f"✓ Assessment Q1 response: {data.get('text')[:80]}...")
                except asyncio.TimeoutError:
                    break

            # Answer second assessment question
            await websocket.send(json.dumps({
                "type": "text",
                "text": "I like to read books, watch movies, and work on machine learning projects"
            }))

            responses = []
            for _ in range(3):
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(msg)
                    responses.append(data)
                    if data.get("type") == "transcript" and data.get("role") == "assistant":
                        print(f"✓ Assessment Q2 response: {data.get('text')[:80]}...")
                except asyncio.TimeoutError:
                    break

            # Answer third assessment question
            await websocket.send(json.dumps({
                "type": "text",
                "text": "I would invest some money, travel around the world, and donate to charity"
            }))

            responses = []
            for _ in range(3):
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(msg)
                    responses.append(data)
                    if data.get("type") == "transcript" and data.get("role") == "assistant":
                        print(f"✓ Assessment Q3 response: {data.get('text')[:80]}...")
                        # Check if assessment summary
                        if "level" in data.get("text", "").lower():
                            print("✓ Assessment completed with level feedback")
                except asyncio.TimeoutError:
                    break

            # Program building phase
            print("\n--- Step 5: Program Building ---")
            # Should receive roadmap automatically
            responses = []
            for _ in range(2):
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(msg)
                    responses.append(data)
                    if data.get("type") == "transcript" and data.get("role") == "assistant":
                        print(f"✓ Roadmap: {data.get('text')[:80]}...")
                        if "plan" in data.get("text", "").lower() or "focus" in data.get("text", "").lower():
                            print("✓ Program building completed")
                except asyncio.TimeoutError:
                    break

            # Learning session
            print("\n--- Step 6: Learning Session ---")
            # One turn of conversation
            await websocket.send(json.dumps({
                "type": "text",
                "text": "I have experience with Python and scikit-learn"
            }))

            responses = []
            for _ in range(3):
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(msg)
                    responses.append(data)
                    if data.get("type") == "transcript" and data.get("role") == "assistant":
                        print(f"✓ Learning session response: {data.get('text')[:80]}...")
                        mode = data.get("mode", "unknown")
                        print(f"✓ Mode: {mode}")
                except asyncio.TimeoutError:
                    break

            # End session
            print("\n--- Step 7: Session End ---")
            await websocket.send(json.dumps({"type": "end"}))

            # Wait for farewell
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(msg)
                if data.get("type") == "transcript" and data.get("role") == "assistant":
                    print(f"✓ Farewell: {data.get('text')[:80]}...")
            except asyncio.TimeoutError:
                print("⚠ No farewell received (timeout)")

            print("\n=== Test Completed Successfully ===")
            return True

    except websockets.exceptions.WebSocketException as e:
        print(f"✗ WebSocket error: {e}")
        print("\nMake sure the FastAPI server is running:")
        print("  python main.py")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_agent_returning_user():
    """Test returning user with existing goal."""
    print("\n=== Testing LangGraph Agent (Returning User) ===\n")

    # Use a user ID that has a goal
    uri = "ws://localhost:8000/api/v1/voice/chat/v2?user_id=1"

    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connected to /chat/v2")

            # Receive connection message
            msg = await websocket.recv()
            data = json.loads(msg)
            print(f"✓ Connected: phase={data.get('phase')}, goal={data.get('goal')}")

            # Should go directly to learning session
            if data.get("phase") == "learning_session" or data.get("mode"):
                print("✓ Skipped onboarding, went directly to learning session")
            else:
                print(f"⚠ Unexpected phase: {data.get('phase')}")

            # Receive initial greeting
            msg = await websocket.recv()
            data = json.loads(msg)
            if data.get("type") == "transcript":
                print(f"✓ Greeting: {data.get('text')[:80]}...")

            # One turn of conversation
            await websocket.send(json.dumps({
                "type": "text",
                "text": "Let's practice!"
            }))

            responses = []
            for _ in range(3):
                try:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(msg)
                    responses.append(data)
                    if data.get("type") == "transcript" and data.get("role") == "assistant":
                        print(f"✓ Response: {data.get('text')[:80]}...")
                except asyncio.TimeoutError:
                    break

            # End session
            await websocket.send(json.dumps({"type": "end"}))

            print("\n=== Returning User Test Completed ===")
            return True

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("  LangGraph Agent E2E Test")
    print("=" * 60)
    print("\nPrerequisites:")
    print("  1. FastAPI server running: python main.py")
    print("  2. PostgreSQL running: docker compose up -d postgres")
    print("  3. LangGraph dependencies installed: pip install langgraph langchain-core")
    print()

    try:
        # Test new user flow
        success1 = asyncio.run(test_agent_new_user_flow())

        # Test returning user
        success2 = asyncio.run(test_agent_returning_user())

        if success1 and success2:
            print("\n" + "=" * 60)
            print("  ✓ All tests passed!")
            print("=" * 60)
            sys.exit(0)
        else:
            print("\n" + "=" * 60)
            print("  ✗ Some tests failed")
            print("=" * 60)
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
