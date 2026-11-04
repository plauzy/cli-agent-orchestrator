"""Tests for GET /agui/v1/capabilities (#1192).

AG-UI 1.0 ``basic/capabilities.mdx``: "An implementation that exposes
capabilities by any means MUST use this shape for them." The shape is the
schema's ``AgentCapabilities``; retrieval is the implementation's choice, and
CAO serves it beside the run plane, at the same scope floor.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

import cli_agent_orchestrator.api.main as main
from cli_agent_orchestrator.api.main import app

client = TestClient(app, base_url="http://localhost")

ROUTE = "/agui/v1/capabilities"


@pytest.fixture(autouse=True)
def _agui_on(monkeypatch):
    monkeypatch.setenv("CAO_AGUI_ENABLED", "true")


@pytest.fixture(autouse=True)
def _auth_off(monkeypatch):
    monkeypatch.setattr(main, "is_auth_enabled", lambda: False)
    monkeypatch.setattr("cli_agent_orchestrator.security.auth.is_auth_enabled", lambda: False)


def _assert_no_extra(model: Any, path: str = "") -> None:
    """Fail if any model in the tree kept a key the schema does not define."""
    extra = getattr(model, "model_extra", None) or {}
    assert not extra, f"undescribed capability key(s) at {path or '<root>'}: {sorted(extra)}"
    for name in type(model).model_fields:
        child = getattr(model, name)
        if hasattr(child, "model_fields"):
            _assert_no_extra(child, f"{path}.{name}" if path else name)


def test_capabilities_route_returns_the_declaration():
    resp = client.get(ROUTE)
    assert resp.status_code == 200
    body: Dict[str, Any] = resp.json()
    assert body["humanInTheLoop"] == {"supported": True, "approvals": True, "interrupts": True}


def test_capabilities_404_when_agui_disabled(monkeypatch):
    monkeypatch.setenv("CAO_AGUI_ENABLED", "false")
    monkeypatch.delenv("CAO_MCP_APPS_ENABLED", raising=False)
    assert client.get(ROUTE).status_code == 404


def test_capabilities_body_is_the_1_0_schema_shape():
    """Every key validates against the SDK's AgentCapabilities, with nothing extra."""
    pytest.importorskip("ag_ui")
    from ag_ui.core import AgentCapabilities

    body = client.get(ROUTE).json()
    model = AgentCapabilities.model_validate(body)
    _assert_no_extra(model)
    # Round trip: the wire form is exactly the model's camelCase, None-free form.
    assert model.model_dump(by_alias=True, exclude_none=True) == body


def test_capabilities_omit_approve_with_edits_and_resumable():
    """#1192: approveWithEdits is left to the per-interrupt responseSchema; and
    the HTTP binding has no resumption, so transport.resumable is never declared."""
    body = client.get(ROUTE).json()
    assert "approveWithEdits" not in body.get("humanInTheLoop", {})
    assert "resumable" not in body.get("transport", {})


def test_capabilities_requires_read_scope(monkeypatch):
    """Same floor as POST /agui/v1/run: a token with no scope is refused."""
    monkeypatch.setattr(main, "is_auth_enabled", lambda: True)
    monkeypatch.setattr("cli_agent_orchestrator.security.auth.is_auth_enabled", lambda: True)
    monkeypatch.setattr(
        "cli_agent_orchestrator.security.auth.extract_scopes_from_token", lambda tok: []
    )
    resp = client.get(ROUTE, headers={"Authorization": "Bearer test-token"})
    assert resp.status_code == 403


def test_capabilities_read_scope_is_enough(monkeypatch):
    monkeypatch.setattr(main, "is_auth_enabled", lambda: True)
    monkeypatch.setattr("cli_agent_orchestrator.security.auth.is_auth_enabled", lambda: True)
    monkeypatch.setattr(
        "cli_agent_orchestrator.security.auth.extract_scopes_from_token",
        lambda tok: ["cao:read"],
    )
    resp = client.get(ROUTE, headers={"Authorization": "Bearer test-token"})
    assert resp.status_code == 200
