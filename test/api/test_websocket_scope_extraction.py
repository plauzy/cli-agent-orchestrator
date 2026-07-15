"""Unit tests for the WebSocket ``cao.bearer.<jwt>`` scope extraction.

Browsers can't set an ``Authorization`` header on the WebSocket handshake, so
an auth-enabled ``/terminals/{id}/ws`` connection carries the JWT in the
``Sec-WebSocket-Protocol`` slot as ``cao.bearer.<jwt>``. These tests pin the
scope-extraction contract (malformed/expired/missing → unauthorized) without
binding a socket.
"""

from __future__ import annotations

from typing import Any, Dict, List

import jwt
import pytest

import cli_agent_orchestrator.api.main as main


class _FakeWebSocket:
    """Just enough of a WebSocket for ``_extract_ws_scopes`` (reads ``.scope`` only)."""

    def __init__(self, subprotocols: List[str]) -> None:
        self.scope: Dict[str, Any] = {"subprotocols": subprotocols}


@pytest.fixture(autouse=True)
def _auth_on(monkeypatch):
    # Enable auth so the real token-validation path runs.
    monkeypatch.setenv("AUTH0_DOMAIN", "unit-test-tenant.invalid")


class TestWsScopeExtraction:
    def test_malformed_bearer_returns_none(self):
        ws = _FakeWebSocket(["cao.bearer.not-a-jwt"])
        assert main._extract_ws_scopes(ws) is None  # type: ignore[arg-type]

    def test_expired_bearer_returns_none(self, monkeypatch):
        def _raise(_tok: str) -> List[str]:
            raise jwt.ExpiredSignatureError("Signature has expired")

        monkeypatch.setattr(main, "extract_scopes_from_token", _raise)
        ws = _FakeWebSocket(["cao.bearer.e.x.p"])
        assert main._extract_ws_scopes(ws) is None  # type: ignore[arg-type]

    def test_valid_bearer_scopes_pass_through(self, monkeypatch):
        monkeypatch.setattr(main, "extract_scopes_from_token", lambda tok: ["cao:read"])
        ws = _FakeWebSocket(["cao.bearer.good"])
        assert main._extract_ws_scopes(ws) == ["cao:read"]  # type: ignore[arg-type]

    def test_missing_bearer_returns_none(self):
        ws = _FakeWebSocket([])
        assert main._extract_ws_scopes(ws) is None  # type: ignore[arg-type]
