"""Tests for the cao-mcp-apps v2 MCP tools.

Covers:
  * render_dashboard returns a snapshot with the documented shape
  * render_agent_view fetches per-terminal state
  * cao_fetch_history returns events from the rolling buffer
  * submit_command rejects unknown kinds and emits events for valid ones
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from cli_agent_orchestrator.services.event_log_service import (
    get_event_log,
    reset_event_log,
)


def _run(coro):  # type: ignore[no-untyped-def]
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_response(payload: Any, *, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    resp.raise_for_status = MagicMock()
    return resp


class TestRenderDashboard:
    def setup_method(self) -> None:
        reset_event_log()

    @patch("cli_agent_orchestrator.mcp_server.server.requests.get")
    def test_returns_snapshot_shape(self, mock_get: MagicMock) -> None:
        from cli_agent_orchestrator.mcp_server.server import render_dashboard

        # /sessions
        sessions = [{"name": "cao-x", "terminal_count": 1, "active_terminal_count": 1}]
        # /sessions/cao-x/terminals
        terminals = [
            {
                "id": "t1",
                "session_name": "cao-x",
                "provider": "claude_code",
                "agent_profile": "developer",
                "status": "idle",
                "parent_terminal_id": None,
            }
        ]
        providers = [{"name": "claude_code", "binary": "claude", "installed": True}]

        def _route(url: str, params: Any = None) -> MagicMock:  # type: ignore[no-untyped-def]
            if url.endswith("/sessions"):
                return _make_response(sessions)
            if url.endswith("/sessions/cao-x/terminals"):
                return _make_response(terminals)
            if url.endswith("/agents/providers"):
                return _make_response(providers)
            return _make_response([])

        mock_get.side_effect = _route

        result: Dict[str, Any] = _run(render_dashboard())  # type: ignore[arg-type]
        assert result["cao_version"]
        assert result["sessions"][0]["name"] == "cao-x"
        assert result["terminals"][0]["id"] == "t1"
        assert result["providers"][0]["name"] == "claude_code"
        assert "cognitive_load" in result
        assert "scopes" in result


class TestCaoFetchHistory:
    def setup_method(self) -> None:
        reset_event_log()

    def teardown_method(self) -> None:
        reset_event_log()

    def test_returns_event_log(self) -> None:
        from cli_agent_orchestrator.mcp_server.server import _cao_fetch_history_impl

        log = get_event_log()
        log.append("launch", terminal_id="abc")
        log.append("completion", terminal_id="abc")

        result = _cao_fetch_history_impl(10, None)
        assert result["count"] == 2
        assert result["events"][0]["kind"] == "launch"
        assert result["events"][1]["kind"] == "completion"


class TestSubmitCommand:
    def setup_method(self) -> None:
        reset_event_log()

    def teardown_method(self) -> None:
        reset_event_log()

    def test_unknown_kind_rejected(self) -> None:
        from cli_agent_orchestrator.mcp_server.server import _submit_command_impl

        result = _submit_command_impl("frobnicate", {})
        assert result["success"] is False
        assert "unknown" in result["error"]

    @patch("cli_agent_orchestrator.mcp_server.server.requests.post")
    def test_interrupt_posts_to_signal_endpoint(self, mock_post: MagicMock) -> None:
        """Phase 3: interrupt is now a real POST to /terminals/{id}/interrupt."""
        from cli_agent_orchestrator.mcp_server.server import _submit_command_impl

        mock_post.return_value = _make_response(
            {"success": True, "terminal_id": "tx", "kind": "interrupt"}
        )
        result = _submit_command_impl("interrupt", {"terminal_id": "tx"})
        assert result["success"] is True
        assert result["result"]["kind"] == "interrupt"
        mock_post.assert_called_once()
        called_url = mock_post.call_args[0][0]
        assert called_url.endswith("/terminals/tx/interrupt")

    @patch("cli_agent_orchestrator.mcp_server.server.requests.post")
    def test_pause_and_resume_post_to_matching_endpoints(self, mock_post: MagicMock) -> None:
        from cli_agent_orchestrator.mcp_server.server import _submit_command_impl

        mock_post.return_value = _make_response({"success": True})

        _submit_command_impl("pause", {"terminal_id": "tx"})
        assert mock_post.call_args[0][0].endswith("/terminals/tx/pause")

        _submit_command_impl("resume", {"terminal_id": "tx"})
        assert mock_post.call_args[0][0].endswith("/terminals/tx/resume")

    def test_signal_kinds_require_terminal_id(self) -> None:
        from cli_agent_orchestrator.mcp_server.server import _submit_command_impl

        for kind in ("interrupt", "pause", "resume"):
            result = _submit_command_impl(kind, {})
            assert result["success"] is False
            assert "terminal_id" in result["error"]

    @patch("cli_agent_orchestrator.mcp_server.server.requests.delete")
    def test_shutdown_session_calls_delete(self, mock_delete: MagicMock) -> None:
        from cli_agent_orchestrator.mcp_server.server import _submit_command_impl

        mock_delete.return_value = _make_response({"deleted": True})
        result = _submit_command_impl("shutdown_session", {"session_name": "cao-x"})
        assert result["success"] is True
        mock_delete.assert_called_once()
        events = get_event_log().history(kinds=["session.shutdown"])
        assert events[-1]["session_name"] == "cao-x"

    def test_shutdown_requires_session_name(self) -> None:
        from cli_agent_orchestrator.mcp_server.server import _submit_command_impl

        result = _submit_command_impl("shutdown_session", {})
        assert result["success"] is False
        assert "session_name" in result["error"]
