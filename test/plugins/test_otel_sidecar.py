"""Tests for the built-in OtelSidecarPlugin.

Phase 1 / commit 2: the plugin should register via the ``cao.plugins`` entry
point, expose hooks for all five lifecycle events, and never raise. Real OTel
span emission from within the hooks is deferred to commit 3 (when CaoEvent
carries a ``traceparent``).
"""

from __future__ import annotations

import importlib.metadata

import pytest

from cli_agent_orchestrator.plugins import PluginRegistry
from cli_agent_orchestrator.plugins.builtin.otel_sidecar import OtelSidecarPlugin
from cli_agent_orchestrator.plugins.events import (
    PostCreateSessionEvent,
    PostCreateTerminalEvent,
    PostKillSessionEvent,
    PostKillTerminalEvent,
    PostSendMessageEvent,
)


class TestEntryPointRegistration:
    def test_otel_sidecar_is_registered_under_cao_plugins(self):
        eps = importlib.metadata.entry_points(group="cao.plugins")
        names = {ep.name for ep in eps}
        assert (
            "otel_sidecar" in names
        ), f"otel_sidecar entry point missing from cao.plugins (found: {names})"

    def test_loaded_class_is_otel_sidecar_plugin(self):
        eps = importlib.metadata.entry_points(group="cao.plugins")
        ep = next(ep for ep in eps if ep.name == "otel_sidecar")
        loaded = ep.load()
        assert loaded is OtelSidecarPlugin


class TestHookCoverage:
    def test_plugin_declares_all_five_post_event_hooks(self):
        plugin = OtelSidecarPlugin()
        registry = PluginRegistry()
        registry._register(plugin)

        for event_type in (
            "post_create_session",
            "post_kill_session",
            "post_create_terminal",
            "post_kill_terminal",
            "post_send_message",
        ):
            assert registry._dispatch.get(
                event_type
            ), f"OtelSidecarPlugin missing hook for {event_type}"


class TestHooksNeverRaise:
    """Hooks must be defensive — a misformed event must not crash the dispatcher."""

    @pytest.mark.asyncio
    async def test_dispatch_each_event_type_completes_cleanly(self):
        plugin = OtelSidecarPlugin()
        registry = PluginRegistry()
        registry._register(plugin)

        events: list[tuple[str, object]] = [
            ("post_create_session", PostCreateSessionEvent(session_name="cao-test")),
            ("post_kill_session", PostKillSessionEvent(session_name="cao-test")),
            (
                "post_create_terminal",
                PostCreateTerminalEvent(
                    terminal_id="term-1", agent_name="developer", provider="kiro_cli"
                ),
            ),
            (
                "post_kill_terminal",
                PostKillTerminalEvent(terminal_id="term-1", agent_name="developer"),
            ),
            (
                "post_send_message",
                PostSendMessageEvent(
                    sender="term-1",
                    receiver="term-2",
                    message="ping",
                    orchestration_type="send_message",
                ),
            ),
        ]
        for event_type, event in events:
            await registry.dispatch(event_type, event)
