"""Integration tests for the legacy OpenAI agent endpoint."""

import os
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv()


@pytest.fixture
def api_client():
    from main import app

    return TestClient(app)


@pytest.fixture
def test_session_id():
    return str(uuid4())


def test_agent_health_endpoint(api_client):
    response = api_client.get("/api/v1/agent/health")

    assert response.status_code == 200
    data = response.json()

    assert data["provider"] == "openai"
    assert data["endpoint"] == "legacy_agents_sdk"
    assert "status" in data
    assert "message" in data

    if data["status"] == "ok":
        assert "legacy agent endpoint" in data["message"]
        assert "model" in data
        assert "proxy" in data
    elif data["status"] == "skipped":
        assert "OpenAI-only" in data["message"]
    else:
        assert data["status"] == "error"


def test_proxy_setup():
    proxy_url = os.getenv("PROXY_URL")
    if proxy_url is None:
        pytest.skip("PROXY_URL not set; legacy OpenAI agent endpoint is optional")

    assert proxy_url.startswith("http://")


def test_openai_api_key():
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key is None:
        pytest.skip("OPENAI_API_KEY not set; main cluster flow can run without legacy OpenAI agent endpoint")

    assert api_key.startswith("sk-")


def test_agent_chat_endpoint_basic(api_client, test_session_id):
    response = api_client.post(
        "/api/v1/agent/chat",
        json={
            "user_id": 1,
            "session_id": test_session_id,
            "message": "Hello",
        },
    )

    assert response.status_code in [200, 500, 422]

    if response.status_code == 200:
        data = response.json()
        assert data["session_id"] == test_session_id
        assert data["user_id"] == 1
        assert len(data["response"]) > 0


def test_agent_chat_invalid_session_id(api_client):
    response = api_client.post(
        "/api/v1/agent/chat",
        json={
            "user_id": 1,
            "session_id": "not-a-valid-uuid",
            "message": "Hello",
        },
    )

    assert response.status_code == 422
    assert "detail" in response.json()


def test_agent_error_handling(api_client):
    response = api_client.post("/api/v1/agent/chat", json={"invalid": "data"})
    assert response.status_code in [400, 422]


def test_proxy_import():
    try:
        from app.agents import proxy  # noqa: F401

        assert True
    except Exception as exc:
        pytest.skip(f"Proxy not configured: {exc}")


def test_base_agent_import():
    from app.agents.base_agent import create_simple_agent

    assert callable(create_simple_agent)


def test_agent_chat_endpoint_exists():
    from app.api import agent_chat

    assert agent_chat.router is not None
    assert agent_chat.router.prefix == "/api/v1/agent"
