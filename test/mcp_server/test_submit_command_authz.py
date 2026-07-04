"""Tests for Auth0-for-MCP scope precheck in `_submit_command_impl`.

Sibling RFC: docs/rfc/cao-auth0-mcp-integration-2026-05-11-v1.md §6.

This is the UX-friendly pre-check layer. The FastAPI endpoint authz
tests in test/api/test_endpoint_authz.py cover the defense-in-depth
boundary; this file just confirms `_submit_command_impl` returns a
helpful `insufficient scope` payload before making the round-trip.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from cli_agent_orchestrator.services.event_log_service import reset_event_log


@pytest.fixture(autouse=True)
def _reset_event_log():
    reset_event_log()
    yield
    reset_event_log()


@pytest.mark.parametrize(
    "kind,required",
    [
        ("send_message", "cao:write"),
        ("assign", "cao:write"),
        ("create_session", "cao:write"),
        ("interrupt", "cao:write"),
        ("pause", "cao:write"),
        ("resume", "cao:write"),
        ("shutdown_session", "cao:admin"),
    ],
)
def test_submit_command_blocks_when_scope_missing(kind: str, required: str):
    """A read-only token blocks every kind with the matching scope hint."""
    from cli_agent_orchestrator.mcp_server.server import _submit_command_impl

    with patch(
        "cli_agent_orchestrator.security.get_scopes_for_local_token",
        return_value=["cao:read"],
    ):
        result = _submit_command_impl(kind, {"terminal_id": "abc12345", "session_name": "cao-x"})

    assert result["success"] is False
    assert result["error"] == "insufficient scope"
    assert result["required"] == required
    assert result["granted"] == ["cao:read"]


def test_submit_command_passes_precheck_with_admin_scope():
    """Admin tokens pass the precheck for every kind."""
    from cli_agent_orchestrator.mcp_server.server import _submit_command_impl

    # We mock requests.post so the impl doesn't try to reach a real server.
    with (
        patch(
            "cli_agent_orchestrator.security.get_scopes_for_local_token",
            return_value=["cao:read", "cao:write", "cao:admin"],
        ),
        patch("cli_agent_orchestrator.mcp_server.server.requests.delete") as mock_del,
    ):
        mock_del.return_value.json.return_value = {"deleted": True}
        mock_del.return_value.raise_for_status = lambda: None

        result = _submit_command_impl("shutdown_session", {"session_name": "cao-x"})
        assert result["success"] is True
        mock_del.assert_called_once()


def test_submit_command_unknown_kind_does_not_consult_scopes():
    """Unknown kinds fail before the scope check."""
    from cli_agent_orchestrator.mcp_server.server import _submit_command_impl

    with patch(
        "cli_agent_orchestrator.security.get_scopes_for_local_token",
    ) as mock_scopes:
        result = _submit_command_impl("frobnicate", {})
        assert result["success"] is False
        assert "unknown" in result["error"]
        # The scope check is only consulted for known kinds.
        mock_scopes.assert_not_called()
