"""Tests for the SSE event publisher plugin (commit 7)."""

from __future__ import annotations

import asyncio
import importlib.metadata

import pytest

from cli_agent_orchestrator.plugins import PluginRegistry
from cli_agent_orchestrator.plugins.builtin.sse_event_publisher import (
    SseEventPublisherPlugin,
)
from cli_agent_orchestrator.plugins.events import (
    PostCreateSessionEvent,
    PostCreateTerminalEvent,
    PostKillSessionEvent,
    PostKillTerminalEvent,
    PostSendMessageEvent,
)
from cli_agent_orchestrator.services import sse_bus

_TRACEPARENT = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"


@pytest.fixture(autouse=True)
def _reset_sse_bus():
    sse_bus.reset_bus()
    yield
    sse_bus.reset_bus()


class TestEntryPointRegistration:
    def test_sse_event_publisher_is_registered_under_cao_plugins(self):
        eps = importlib.metadata.entry_points(group="cao.plugins")
        names = {ep.name for ep in eps}
        assert "sse_event_publisher" in names

    def test_loaded_class_is_sse_event_publisher_plugin(self):
        eps = importlib.metadata.entry_points(group="cao.plugins")
        ep = next(ep for ep in eps if ep.name == "sse_event_publisher")
        loaded = ep.load()
        assert loaded is SseEventPublisherPlugin


class TestEventTranslation:
    """Each Post* event must produce a JSON-serializable bus envelope."""

    @pytest.mark.asyncio
    async def test_post_create_session_publishes_session_created(self):
        plugin = SseEventPublisherPlugin()
        registry = PluginRegistry()
        registry._register(plugin)

        published: list[dict] = []

        async def listener():
            async for ev in sse_bus.get_bus().subscribe():
                published.append(ev)
                return

        listener_task = asyncio.create_task(listener())
        await asyncio.sleep(0)

        await registry.dispatch(
            "post_create_session",
            PostCreateSessionEvent(session_name="cao-test", traceparent=_TRACEPARENT),
        )
        await listener_task

        assert published[0]["type"] == "session.created"
        assert published[0]["payload"] == {"session_name": "cao-test"}
        assert published[0]["traceparent"] == _TRACEPARENT

    @pytest.mark.asyncio
    async def test_post_kill_session_publishes_session_killed(self):
        await self._verify_one_event(
            "post_kill_session",
            PostKillSessionEvent(session_name="cao-test"),
            "session.killed",
            {"session_name": "cao-test"},
        )

    @pytest.mark.asyncio
    async def test_post_create_terminal_publishes_terminal_created(self):
        await self._verify_one_event(
            "post_create_terminal",
            PostCreateTerminalEvent(terminal_id="t-1", agent_name="developer", provider="kiro_cli"),
            "terminal.created",
            {"terminal_id": "t-1", "agent_name": "developer", "provider": "kiro_cli"},
        )

    @pytest.mark.asyncio
    async def test_post_kill_terminal_publishes_terminal_killed(self):
        await self._verify_one_event(
            "post_kill_terminal",
            PostKillTerminalEvent(terminal_id="t-1", agent_name="developer"),
            "terminal.killed",
            {"terminal_id": "t-1", "agent_name": "developer"},
        )

    @pytest.mark.asyncio
    async def test_post_send_message_omits_message_body(self):
        """Critical privacy invariant: the message body must NOT be republished."""
        await self._verify_one_event(
            "post_send_message",
            PostSendMessageEvent(
                sender="t-A",
                receiver="t-B",
                message="SECRET=hunter2",
                orchestration_type="send_message",
            ),
            "message.sent",
            {"sender": "t-A", "receiver": "t-B", "orchestration_type": "send_message"},
        )

    async def _verify_one_event(
        self, event_type: str, event: object, expected_type: str, expected_payload: dict
    ) -> None:
        plugin = SseEventPublisherPlugin()
        registry = PluginRegistry()
        registry._register(plugin)

        published: list[dict] = []

        async def listener():
            async for ev in sse_bus.get_bus().subscribe():
                published.append(ev)
                return

        listener_task = asyncio.create_task(listener())
        await asyncio.sleep(0)
        await registry.dispatch(event_type, event)
        await listener_task

        assert published[0]["type"] == expected_type
        assert published[0]["payload"] == expected_payload
