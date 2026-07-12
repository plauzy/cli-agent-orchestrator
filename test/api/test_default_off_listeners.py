"""Regression: `cao-server` with no flags opens no listener beyond :9889.

The A2A / Agent Card transport was split out of the AG-UI core PR (review
feedback on awslabs/cli-agent-orchestrator#387) and lands hardened in Phase-B.
It is present in this build but **default-off**: with no flags set there is no
lifespan wiring, no listener handle, and no ``/a2a`` routes on the main :9889
app (the transport only mounts on the dedicated :9890 listener when
``CAO_AGENT_CARD_ENABLED`` is set — see test_a2a_mount_guard.py). This asserts
that default-off contract, plus the AG-UI surface's own default-off behavior
(no flags => 404).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cli_agent_orchestrator.api.main import app


@pytest.fixture(autouse=True)
def _no_surface_env(monkeypatch):
    # Ensure a clean env: no AG-UI / MCP Apps / legacy agent-card flags set.
    for var in (
        "CAO_AGENT_CARD_ENABLED",
        "CAO_AGENT_CARD_DISABLED",
        "CAO_AGUI_ENABLED",
        "CAO_MCP_APPS_ENABLED",
    ):
        monkeypatch.delenv(var, raising=False)


def test_a2a_surface_importable_but_not_wired_by_default():
    """The A2A/Agent Card modules exist (Phase-B) but importing them has no
    side effects: no listener is started and no routes mount without the flag.
    """
    import cli_agent_orchestrator.a2a  # noqa: F401
    import cli_agent_orchestrator.agent_card  # noqa: F401


def test_no_agent_card_listener_state_without_flag():
    """Default (no flag) => no listener handle and no /a2a routes are mounted."""
    with TestClient(app, base_url="http://localhost"):
        assert getattr(app.state, "agent_card_listener", None) is None
        paths = {getattr(route, "path", "") for route in app.routes}
        assert not any(p.startswith("/a2a") for p in paths)


def test_agui_surface_defaults_off():
    """No flags => the AG-UI routes 404 (byte-identical default posture)."""
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/agui/v1/stream").status_code == 404
        resp = client.post("/agui/v1/emit_ui", json={"component": "progress", "props": {}})
        assert resp.status_code == 404
