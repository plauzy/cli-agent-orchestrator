"""Tests for the three terminal-signal FastAPI endpoints.

Phase 3 of cao-mcp-apps v2. Verifies that each endpoint delegates to
the matching terminal_service helper and that the matching plugin
event is recorded in the rolling event log (via EventLogPublisherPlugin).
"""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from cli_agent_orchestrator.api.main import app
from cli_agent_orchestrator.plugins import PluginRegistry
from cli_agent_orchestrator.plugins.builtin.event_log_publisher import (
    EventLogPublisherPlugin,
)
from cli_agent_orchestrator.services.event_log_service import reset_event_log


@pytest.fixture(autouse=True)
def _reset_event_log():
    reset_event_log()
    yield
    reset_event_log()


@pytest.fixture
def client_with_event_log_plugin():
    from test.api.conftest import TestClientWithHost

    registry = PluginRegistry()
    registry._register(EventLogPublisherPlugin())
    app.state.plugin_registry = registry
    return TestClientWithHost(app)


class TestInterruptEndpoint:
    def test_posts_through_helper_and_returns_kind(self, client_with_event_log_plugin) -> None:
        client = client_with_event_log_plugin
        with patch("cli_agent_orchestrator.api.main.terminal_service.interrupt_terminal") as helper:
            helper.return_value = True
            resp = client.post("/terminals/abc12345/interrupt")
        assert resp.status_code == 200
        assert resp.json() == {"success": True, "terminal_id": "abc12345", "kind": "interrupt"}
        helper.assert_called_once()
        # The endpoint passes the plugin registry through so the helper
        # dispatches the plugin event.
        assert helper.call_args.kwargs.get("registry") is not None


class TestPauseEndpoint:
    def test_pause_endpoint_calls_helper(self, client_with_event_log_plugin) -> None:
        client = client_with_event_log_plugin
        with patch("cli_agent_orchestrator.api.main.terminal_service.pause_terminal") as helper:
            helper.return_value = True
            resp = client.post("/terminals/abc12345/pause")
        assert resp.status_code == 200
        assert resp.json()["kind"] == "pause"


class TestResumeEndpoint:
    def test_resume_endpoint_calls_helper(self, client_with_event_log_plugin) -> None:
        client = client_with_event_log_plugin
        with patch("cli_agent_orchestrator.api.main.terminal_service.resume_terminal") as helper:
            helper.return_value = True
            resp = client.post("/terminals/abc12345/resume")
        assert resp.status_code == 200
        assert resp.json()["kind"] == "resume"


class TestEventLogIntegration:
    """When the helper actually dispatches the event, the publisher plugin
    records it into the rolling buffer. We test the end-to-end wiring
    without mocking the helper — only the backend + metadata."""

    def _patched_tmux(self):
        # The signal helpers route key sends through get_backend(); patch the
        # backend singleton so no real tmux session is touched. Metadata +
        # update_last_active are stubbed so the helpers run hermetically.
        stack = ExitStack()
        stack.enter_context(patch("cli_agent_orchestrator.backends.registry._backend", MagicMock()))
        stack.enter_context(
            patch(
                "cli_agent_orchestrator.services.terminal_service.get_terminal_metadata",
                MagicMock(return_value={"tmux_session": "cao-x", "tmux_window": "w1"}),
            )
        )
        stack.enter_context(
            patch(
                "cli_agent_orchestrator.services.terminal_service.update_last_active",
                MagicMock(),
            )
        )
        return stack

    @pytest.mark.asyncio
    async def test_interrupt_endpoint_records_event(self, client_with_event_log_plugin) -> None:
        from cli_agent_orchestrator.services.event_log_service import get_event_log

        client = client_with_event_log_plugin
        with self._patched_tmux():
            resp = client.post("/terminals/abc12345/interrupt")
        assert resp.status_code == 200
        events = get_event_log().history()
        assert events[-1]["kind"] == "terminal.interrupt"
        assert events[-1]["terminal_id"] == "abc12345"

    @pytest.mark.asyncio
    async def test_pause_endpoint_records_event(self, client_with_event_log_plugin) -> None:
        from cli_agent_orchestrator.services.event_log_service import get_event_log

        client = client_with_event_log_plugin
        with self._patched_tmux():
            resp = client.post("/terminals/abc12345/pause")
        assert resp.status_code == 200
        events = get_event_log().history()
        assert events[-1]["kind"] == "terminal.pause"

    @pytest.mark.asyncio
    async def test_resume_endpoint_records_event(self, client_with_event_log_plugin) -> None:
        from cli_agent_orchestrator.services.event_log_service import get_event_log

        client = client_with_event_log_plugin
        with self._patched_tmux():
            resp = client.post("/terminals/abc12345/resume")
        assert resp.status_code == 200
        events = get_event_log().history()
        assert events[-1]["kind"] == "terminal.resume"
