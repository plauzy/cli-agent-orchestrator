"""Tests for terminal-signal helpers (interrupt/pause/resume).

Phase 3 of cao-mcp-apps v2. Each helper:
  1. Looks up tmux metadata for the terminal.
  2. Sends the right key chord via tmux_client.
  3. Dispatches the matching plugin event (if a registry is provided).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cli_agent_orchestrator.plugins import (
    PluginRegistry,
    PostInterruptTerminalEvent,
    PostPauseTerminalEvent,
    PostResumeTerminalEvent,
)

_FAKE_METADATA = {
    "tmux_session": "cao-test",
    "tmux_window": "developer-abcd",
}


@pytest.fixture
def patched_terminal_service():
    """Patch tmux_client + get_terminal_metadata so the helpers run hermetically."""
    with (
        patch("cli_agent_orchestrator.backends.registry._backend") as tmux,
        patch(
            "cli_agent_orchestrator.services.terminal_service.get_terminal_metadata"
        ) as get_metadata,
        patch("cli_agent_orchestrator.services.terminal_service.update_last_active"),
    ):
        get_metadata.return_value = _FAKE_METADATA
        yield tmux, get_metadata


class TestInterruptTerminal:
    def test_sends_ctrl_c_via_send_special_key(self, patched_terminal_service) -> None:
        from cli_agent_orchestrator.services.terminal_service import interrupt_terminal

        tmux, _ = patched_terminal_service
        ok = interrupt_terminal("t1")
        assert ok is True
        tmux.send_special_key.assert_called_once_with("cao-test", "developer-abcd", "C-c")

    def test_dispatches_post_interrupt_terminal_event(self, patched_terminal_service) -> None:
        from cli_agent_orchestrator.services.terminal_service import interrupt_terminal

        registry = MagicMock(spec=PluginRegistry)
        with patch(
            "cli_agent_orchestrator.services.terminal_service.dispatch_plugin_event"
        ) as dispatch:
            interrupt_terminal("t1", registry=registry)
            dispatch.assert_called_once()
            _, hook_name, event = dispatch.call_args[0]
            assert hook_name == "post_interrupt_terminal"
            assert isinstance(event, PostInterruptTerminalEvent)
            assert event.terminal_id == "t1"

    def test_raises_when_terminal_missing(self) -> None:
        from cli_agent_orchestrator.services.terminal_service import interrupt_terminal

        with patch(
            "cli_agent_orchestrator.services.terminal_service.get_terminal_metadata"
        ) as get_metadata:
            get_metadata.return_value = None
            with pytest.raises(ValueError):
                interrupt_terminal("missing")


class TestPauseTerminal:
    def test_sends_ctrl_z(self, patched_terminal_service) -> None:
        from cli_agent_orchestrator.services.terminal_service import pause_terminal

        tmux, _ = patched_terminal_service
        pause_terminal("t1")
        tmux.send_special_key.assert_called_once_with("cao-test", "developer-abcd", "C-z")

    def test_dispatches_pause_event(self, patched_terminal_service) -> None:
        from cli_agent_orchestrator.services.terminal_service import pause_terminal

        registry = MagicMock(spec=PluginRegistry)
        with patch(
            "cli_agent_orchestrator.services.terminal_service.dispatch_plugin_event"
        ) as dispatch:
            pause_terminal("t1", registry=registry)
            _, hook_name, event = dispatch.call_args[0]
            assert hook_name == "post_pause_terminal"
            assert isinstance(event, PostPauseTerminalEvent)


class TestResumeTerminal:
    def test_sends_fg_text(self, patched_terminal_service) -> None:
        from cli_agent_orchestrator.services.terminal_service import resume_terminal

        tmux, _ = patched_terminal_service
        resume_terminal("t1")
        # Resume goes via send_keys (text "fg" + Enter), not send_special_key.
        tmux.send_keys.assert_called_once()
        args = tmux.send_keys.call_args
        assert args[0][2] == "fg"

    def test_dispatches_resume_event(self, patched_terminal_service) -> None:
        from cli_agent_orchestrator.services.terminal_service import resume_terminal

        registry = MagicMock(spec=PluginRegistry)
        with patch(
            "cli_agent_orchestrator.services.terminal_service.dispatch_plugin_event"
        ) as dispatch:
            resume_terminal("t1", registry=registry)
            _, hook_name, event = dispatch.call_args[0]
            assert hook_name == "post_resume_terminal"
            assert isinstance(event, PostResumeTerminalEvent)

    def test_raises_when_terminal_missing(self) -> None:
        from cli_agent_orchestrator.services.terminal_service import resume_terminal

        with patch(
            "cli_agent_orchestrator.services.terminal_service.get_terminal_metadata"
        ) as get_metadata:
            get_metadata.return_value = None
            with pytest.raises(ValueError):
                resume_terminal("missing")
