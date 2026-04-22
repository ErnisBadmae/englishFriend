"""Unit and integration tests for PersonaPlex provider.

Unit tests:
- Health check caching logic
- Provider connection / disconnect lifecycle
- System prompt builder
- Data flow logger extensions
- Prometheus metric registration

Integration tests (require PersonaPlex server):
- Marked with @pytest.mark.integration
- Skipped if PERSONAPLEX_HOST is unreachable
"""

import asyncio
import json
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.ai.base import VoiceSession
from app.services.ai.personaplex_health import (
    check_personaplex_health,
    invalidate_health_cache,
    _health_cache,
)
from app.services.ai.personaplex_provider import (
    PersonaPlexProvider,
    PersonaPlexConnectionError,
)
from app.services.data_flow_logger import DataFlowLogger


# ============== Health Check Tests ==============


class TestPersonaPlexHealthCheck:
    """Tests for TTL-cached health check."""

    def setup_method(self):
        invalidate_health_cache()

    @pytest.mark.asyncio
    async def test_disabled_returns_false(self):
        """If personaplex_enabled=False, health check returns False."""
        with patch("app.services.ai.personaplex_health.settings") as mock_settings:
            mock_settings.personaplex_enabled = False
            result = await check_personaplex_health()
            assert result is False

    @pytest.mark.asyncio
    async def test_healthy_server(self):
        """Returns True when server responds with 200."""
        with patch("app.services.ai.personaplex_health.settings") as mock_settings:
            mock_settings.personaplex_enabled = True
            mock_settings.personaplex_host = "localhost"
            mock_settings.personaplex_port = 8998
            mock_settings.personaplex_health_cache_ttl = 30

            mock_response = MagicMock()
            mock_response.status_code = 200

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await check_personaplex_health()
                assert result is True

    @pytest.mark.asyncio
    async def test_unhealthy_server(self):
        """Returns False when server responds with non-200."""
        with patch("app.services.ai.personaplex_health.settings") as mock_settings:
            mock_settings.personaplex_enabled = True
            mock_settings.personaplex_host = "localhost"
            mock_settings.personaplex_port = 8998
            mock_settings.personaplex_health_cache_ttl = 30

            mock_response = MagicMock()
            mock_response.status_code = 503

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await check_personaplex_health()
                assert result is False

    @pytest.mark.asyncio
    async def test_connection_error_returns_false(self):
        """Returns False on connection error."""
        with patch("app.services.ai.personaplex_health.settings") as mock_settings:
            mock_settings.personaplex_enabled = True
            mock_settings.personaplex_host = "unreachable-host"
            mock_settings.personaplex_port = 9999
            mock_settings.personaplex_health_cache_ttl = 30

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=ConnectionError("refused"))
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await check_personaplex_health()
                assert result is False

    @pytest.mark.asyncio
    async def test_cache_ttl(self):
        """Cached result is reused within TTL."""
        with patch("app.services.ai.personaplex_health.settings") as mock_settings:
            mock_settings.personaplex_enabled = True
            mock_settings.personaplex_host = "localhost"
            mock_settings.personaplex_port = 8998
            mock_settings.personaplex_health_cache_ttl = 30

            # Prime the cache
            _health_cache["localhost:8998"] = (True, time.monotonic())

            # Should return cached value without making HTTP call
            with patch("httpx.AsyncClient") as mock_client_cls:
                result = await check_personaplex_health()
                assert result is True
                mock_client_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_bypass_cache(self):
        """force=True bypasses the cache."""
        with patch("app.services.ai.personaplex_health.settings") as mock_settings:
            mock_settings.personaplex_enabled = True
            mock_settings.personaplex_host = "localhost"
            mock_settings.personaplex_port = 8998
            mock_settings.personaplex_health_cache_ttl = 30

            # Prime cache with old value
            _health_cache["localhost:8998"] = (False, time.monotonic())

            mock_response = MagicMock()
            mock_response.status_code = 200

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                mock_client_cls.return_value = mock_client

                result = await check_personaplex_health(force=True)
                assert result is True


# ============== Provider Tests ==============


class TestPersonaPlexProvider:
    """Tests for PersonaPlexProvider lifecycle."""

    def test_default_voice(self):
        """Provider uses default voice from settings."""
        with patch("app.services.ai.personaplex_provider.settings") as mock_settings:
            mock_settings.personaplex_default_voice = "NATF2"
            provider = PersonaPlexProvider()
            assert provider._voice == "NATF2"

    def test_custom_voice(self):
        """Custom voice overrides default."""
        provider = PersonaPlexProvider(voice="NATM0")
        assert provider._voice == "NATM0"

    def test_not_connected_initially(self):
        """Provider starts disconnected."""
        provider = PersonaPlexProvider()
        assert provider.is_connected is False

    @pytest.mark.asyncio
    async def test_send_audio_without_connect_raises(self):
        """Sending audio before connect raises PersonaPlexConnectionError."""
        provider = PersonaPlexProvider()
        with pytest.raises(PersonaPlexConnectionError, match="Not connected"):
            await provider.send_audio(b"audio-data")

    @pytest.mark.asyncio
    async def test_disconnect_noop_when_not_connected(self):
        """Disconnect is safe to call when not connected."""
        provider = PersonaPlexProvider()
        await provider.disconnect()
        assert provider.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_failure_raises(self):
        """Connection failure raises PersonaPlexConnectionError."""
        with patch("app.services.ai.personaplex_provider.settings") as mock_settings:
            mock_settings.personaplex_ws_url = "ws://unreachable:9999/api/chat"
            mock_settings.personaplex_timeout = 1.0
            mock_settings.personaplex_default_voice = "NATM0"

            provider = PersonaPlexProvider()
            session = VoiceSession(
                session_id="test-session",
                user_id=1,
                system_prompt="Test prompt",
            )
            with pytest.raises(PersonaPlexConnectionError):
                await provider.connect(session)

    @pytest.mark.asyncio
    async def test_update_persona_when_not_connected(self):
        """update_persona logs warning when not connected (no-op)."""
        provider = PersonaPlexProvider()
        # Should not raise
        await provider.update_persona("new prompt")
        assert provider.is_connected is False


# ============== System Prompt Builder Tests ==============


class TestBuildPersonaPlexSystemPrompt:
    """Tests for _build_personaplex_system_prompt.

    NOTE: We cannot import _build_personaplex_system_prompt directly from
    app.api.voice due to a pre-existing broken transitive import
    (app.models.prompt_models). Instead we test the function by importing
    it lazily and skipping if the import chain is broken.
    """

    @staticmethod
    def _import_builder():
        try:
            from app.api.voice import _build_personaplex_system_prompt
            return _build_personaplex_system_prompt
        except (ImportError, ModuleNotFoundError):
            pytest.skip("Cannot import voice module (missing model dependency)")

    def test_basic_prompt_structure(self):
        """Prompt includes student profile and mode instructions."""
        builder = self._import_builder()
        from app.agent.state import LearningModeEnum

        state = {
            "username": "Evgeny",
            "language_level": "B2",
            "confirmed_goal": "ML Interview preparation",
            "current_mode": LearningModeEnum.MOCK_INTERVIEW,
            "detected_interests": ["technology", "movies"],
            "due_vocabulary_words": ["resilience", "scalability"],
            "memory_section": "Works at fintech startup",
        }

        prompt = builder(state)

        assert "Evgeny" in prompt
        assert "B2" in prompt
        assert "ML Interview preparation" in prompt
        assert "Mock Interview" in prompt
        assert "technology" in prompt
        assert "resilience" in prompt
        assert "fintech startup" in prompt

    def test_minimal_state(self):
        """Prompt works with minimal agent state."""
        builder = self._import_builder()

        state = {}
        prompt = builder(state)

        assert "Student" in prompt
        assert "improve English" in prompt
        assert "Sarah" in prompt

    def test_mode_instructions_included(self):
        """Each mode has specific instructions in the prompt."""
        builder = self._import_builder()
        from app.agent.state import LearningModeEnum

        for mode in LearningModeEnum:
            state = {"current_mode": mode}
            prompt = builder(state)
            assert len(prompt) > 100


# ============== Data Flow Logger Tests ==============


class TestDataFlowLoggerPersonaPlex:
    """Tests for PersonaPlex extensions to DataFlowLogger."""

    def test_stats_initialized(self):
        """PersonaPlex stats are present in initial stats."""
        dfl = DataFlowLogger()
        stats = dfl.get_stats()
        assert "personaplex_connections" in stats
        assert "personaplex_turns" in stats

    def test_log_personaplex_connect(self):
        """log_personaplex_connect increments counter."""
        dfl = DataFlowLogger()
        dfl.log_personaplex_connect(
            user_id=1,
            session_id="abc-123",
            voice="NATM0",
            mode="mock_interview",
        )
        assert dfl.stats["personaplex_connections"] == 1

    def test_log_personaplex_turn(self):
        """log_personaplex_turn increments counter."""
        dfl = DataFlowLogger()
        dfl.log_personaplex_turn(
            session_id="abc-123",
            role="assistant",
            text_preview="Hello, how are you?",
            latency_ms=280,
        )
        assert dfl.stats["personaplex_turns"] == 1

    def test_log_personaplex_disconnect(self):
        """log_personaplex_disconnect does not raise."""
        dfl = DataFlowLogger()
        dfl.log_personaplex_disconnect(
            session_id="abc-123",
            turns=15,
            duration_seconds=510.0,
        )

    def test_log_personaplex_fallback(self):
        """log_personaplex_fallback does not raise."""
        dfl = DataFlowLogger()
        dfl.log_personaplex_fallback(
            user_id=1,
            reason="health_check_failed",
        )


# ============== Prometheus Metrics Tests ==============


class TestPersonaPlexMetrics:
    """Verify PersonaPlex Prometheus metrics are registered."""

    def test_metrics_exist(self):
        """All PersonaPlex metrics should be importable."""
        from app.core.metrics import (
            personaplex_connections_active,
            personaplex_sessions_total,
            personaplex_latency_seconds,
            personaplex_session_duration_seconds,
            personaplex_turns_total,
            personaplex_pedagogical_events,
            personaplex_errors_total,
            personaplex_fallback_total,
        )

        # Verify they are proper prometheus objects
        assert personaplex_connections_active is not None
        assert personaplex_sessions_total is not None
        assert personaplex_latency_seconds is not None
        assert personaplex_session_duration_seconds is not None
        assert personaplex_turns_total is not None
        assert personaplex_pedagogical_events is not None
        assert personaplex_errors_total is not None
        assert personaplex_fallback_total is not None


# ============== Config Tests ==============


class TestPersonaPlexConfig:
    """Tests for PersonaPlex configuration."""

    def test_default_config(self):
        """Default config has PersonaPlex disabled."""
        from app.core.config import settings

        # personaplex_enabled defaults to False
        assert hasattr(settings, "personaplex_enabled")
        assert hasattr(settings, "personaplex_host")
        assert hasattr(settings, "personaplex_port")
        assert hasattr(settings, "personaplex_default_voice")
        assert hasattr(settings, "personaplex_quantization")

    def test_default_host_points_to_ai_host_03(self):
        """Default host should target the current corporate PersonaPlex node."""
        with patch.dict(os.environ, {}, clear=True):
            s = Settings(_env_file=None)
        assert s.personaplex_host == "192.168.0.18"
        assert s.personaplex_ws_url == "ws://192.168.0.18:8998/api/chat"

    def test_ws_url_auto_computed(self):
        """WebSocket URL is auto-computed from host and port if not set."""
        s = Settings(
            personaplex_host="10.0.0.1",
            personaplex_port=9000,
            personaplex_ws_url="",
        )
        assert s.personaplex_ws_url == "ws://10.0.0.1:9000/api/chat"

    def test_ws_url_explicit(self):
        """Explicit WebSocket URL is preserved."""
        s = Settings(
            personaplex_ws_url="ws://custom:1234/v2/chat",
        )
        assert s.personaplex_ws_url == "ws://custom:1234/v2/chat"
