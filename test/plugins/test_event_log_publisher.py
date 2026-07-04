"""Tests for the EventLogPublisherPlugin (Phase 2 / cao-mcp-apps v2)."""

from __future__ import annotations

import importlib.metadata

import pytest

from cli_agent_orchestrator.plugins import PluginRegistry
from cli_agent_orchestrator.plugins.builtin.event_log_publisher import (
    EventLogPublisherPlugin,
)
from cli_agent_orchestrator.plugins.events import (
    PostCreateSessionEvent,
    PostCreateTerminalEvent,
    PostInterruptTerminalEvent,
    PostKillSessionEvent,
    PostKillTerminalEvent,
    PostPauseTerminalEvent,
    PostResumeTerminalEvent,
    PostSendMessageEvent,
)
from cli_agent_orchestrator.services.event_log_service import (
    get_event_log,
    reset_event_log,
)

_TRACEPARENT = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"


@pytest.fixture(autouse=True)
def _reset_event_log():
    reset_event_log()
    yield
    reset_event_log()


class TestEntryPointRegistration:
    def test_event_log_publisher_is_registered_under_cao_plugins(self):
        eps = importlib.metadata.entry_points(group="cao.plugins")
        names = {ep.name for ep in eps}
        assert "event_log_publisher" in names

    def test_loaded_class_is_event_log_publisher_plugin(self):
        eps = importlib.metadata.entry_points(group="cao.plugins")
        ep = next(ep for ep in eps if ep.name == "event_log_publisher")
        loaded = ep.load()
        assert loaded is EventLogPublisherPlugin


class TestEventTranslation:
    """Each Post* event must produce a single matching entry in the log."""

    async def _dispatch(self, event_type, event):  # type: ignore[no-untyped-def]
        plugin = EventLogPublisherPlugin()
        registry = PluginRegistry()
        registry._register(plugin)
        await registry.dispatch(event_type, event)

    @pytest.mark.asyncio
    async def test_post_create_session_records_session_created(self):
        await self._dispatch(
            "post_create_session",
            PostCreateSessionEvent(session_name="cao-test", traceparent=_TRACEPARENT),
        )
        events = get_event_log().history()
        assert len(events) == 1
        assert events[0]["kind"] == "session.created"
        assert events[0]["session_name"] == "cao-test"
        assert events[0]["detail"]["traceparent"] == _TRACEPARENT

    @pytest.mark.asyncio
    async def test_post_kill_session_records_session_killed(self):
        await self._dispatch(
            "post_kill_session",
            PostKillSessionEvent(session_name="cao-test"),
        )
        events = get_event_log().history()
        assert events[-1]["kind"] == "session.killed"
        assert events[-1]["session_name"] == "cao-test"

    @pytest.mark.asyncio
    async def test_post_create_terminal_records_terminal_created(self):
        await self._dispatch(
            "post_create_terminal",
            PostCreateTerminalEvent(
                terminal_id="t1",
                agent_name="developer",
                provider="claude_code",
            ),
        )
        events = get_event_log().history()
        assert events[-1]["kind"] == "terminal.created"
        assert events[-1]["terminal_id"] == "t1"
        assert events[-1]["detail"]["agent_name"] == "developer"
        assert events[-1]["detail"]["provider"] == "claude_code"

    @pytest.mark.asyncio
    async def test_post_kill_terminal_records_terminal_killed(self):
        await self._dispatch(
            "post_kill_terminal",
            PostKillTerminalEvent(terminal_id="t1", agent_name="developer"),
        )
        events = get_event_log().history()
        assert events[-1]["kind"] == "terminal.killed"
        assert events[-1]["terminal_id"] == "t1"

    @pytest.mark.asyncio
    async def test_post_send_message_records_message_sent_without_body(self):
        await self._dispatch(
            "post_send_message",
            PostSendMessageEvent(
                sender="s",
                receiver="r",
                message="this body must not be persisted",
                orchestration_type="handoff",
            ),
        )
        events = get_event_log().history()
        assert events[-1]["kind"] == "message.sent"
        assert events[-1]["terminal_id"] == "r"
        # Privacy boundary: message body never persisted.
        assert "message" not in events[-1]["detail"]
        assert "this body" not in str(events[-1])
        assert events[-1]["detail"]["sender"] == "s"
        assert events[-1]["detail"]["receiver"] == "r"
        assert events[-1]["detail"]["orchestration_type"] == "handoff"

    @pytest.mark.asyncio
    async def test_optional_fields_dropped_when_none(self):
        await self._dispatch(
            "post_create_session",
            PostCreateSessionEvent(session_name="cao-test"),
        )
        events = get_event_log().history()
        # No traceparent field when not provided.
        assert "traceparent" not in events[-1]["detail"]

    @pytest.mark.asyncio
    async def test_post_interrupt_terminal_records_terminal_interrupt(self):
        await self._dispatch(
            "post_interrupt_terminal",
            PostInterruptTerminalEvent(terminal_id="tx", traceparent=_TRACEPARENT),
        )
        events = get_event_log().history()
        assert events[-1]["kind"] == "terminal.interrupt"
        assert events[-1]["terminal_id"] == "tx"
        assert events[-1]["detail"]["traceparent"] == _TRACEPARENT

    @pytest.mark.asyncio
    async def test_post_pause_terminal_records_terminal_pause(self):
        await self._dispatch(
            "post_pause_terminal",
            PostPauseTerminalEvent(terminal_id="tx"),
        )
        events = get_event_log().history()
        assert events[-1]["kind"] == "terminal.pause"
        assert events[-1]["terminal_id"] == "tx"

    @pytest.mark.asyncio
    async def test_post_resume_terminal_records_terminal_resume(self):
        await self._dispatch(
            "post_resume_terminal",
            PostResumeTerminalEvent(terminal_id="tx"),
        )
        events = get_event_log().history()
        assert events[-1]["kind"] == "terminal.resume"
        assert events[-1]["terminal_id"] == "tx"
