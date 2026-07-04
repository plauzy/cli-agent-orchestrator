"""End-to-end integration: dispatched plugin events appear in /events/history.

Verifies the full Phase 2 loop:
  service layer dispatches Post* events
    → EventLogPublisherPlugin handles them
      → event_log buffer accumulates
        → GET /events/history returns them as JSON

Uses the existing TestClient fixture from conftest.py.
"""

from __future__ import annotations

import pytest

from cli_agent_orchestrator.api.main import app
from cli_agent_orchestrator.plugins import PluginRegistry
from cli_agent_orchestrator.plugins.builtin.event_log_publisher import (
    EventLogPublisherPlugin,
)
from cli_agent_orchestrator.plugins.events import (
    PostCreateSessionEvent,
    PostCreateTerminalEvent,
    PostSendMessageEvent,
)
from cli_agent_orchestrator.services.event_log_service import reset_event_log


@pytest.fixture(autouse=True)
def _reset_event_log():
    reset_event_log()
    yield
    reset_event_log()


@pytest.fixture
def client_with_event_log_plugin():
    """TestClient with the EventLogPublisherPlugin registered.

    Bypasses entry-point discovery so the test is hermetic — it doesn't
    depend on whether other plugins (otel_sidecar etc.) are installed in
    the test environment.
    """
    from test.api.conftest import TestClientWithHost

    registry = PluginRegistry()
    registry._register(EventLogPublisherPlugin())
    app.state.plugin_registry = registry
    return TestClientWithHost(app), registry


class TestEndToEndEventFlow:
    @pytest.mark.asyncio
    async def test_session_create_event_appears_in_history(
        self, client_with_event_log_plugin
    ) -> None:
        client, registry = client_with_event_log_plugin

        await registry.dispatch(
            "post_create_session",
            PostCreateSessionEvent(session_name="cao-integration-test"),
        )

        resp = client.get("/events/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["events"][0]["kind"] == "session.created"
        assert body["events"][0]["session_name"] == "cao-integration-test"

    @pytest.mark.asyncio
    async def test_full_lifecycle_chain_is_recorded(self, client_with_event_log_plugin) -> None:
        client, registry = client_with_event_log_plugin

        await registry.dispatch(
            "post_create_session",
            PostCreateSessionEvent(session_name="cao-integration-test"),
        )
        await registry.dispatch(
            "post_create_terminal",
            PostCreateTerminalEvent(
                terminal_id="t-int-1",
                agent_name="developer",
                provider="claude_code",
            ),
        )
        await registry.dispatch(
            "post_send_message",
            PostSendMessageEvent(
                sender="supervisor",
                receiver="t-int-1",
                message="please respect privacy boundary",
                orchestration_type="handoff",
            ),
        )

        resp = client.get("/events/history")
        body = resp.json()
        assert body["count"] == 3
        kinds = [e["kind"] for e in body["events"]]
        assert kinds == ["session.created", "terminal.created", "message.sent"]

        # Privacy: message body must not be persisted.
        assert "please respect" not in resp.text
