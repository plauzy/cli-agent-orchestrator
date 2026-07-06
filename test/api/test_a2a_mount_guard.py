"""Fail-closed guard for the A2A task routes (#387 review, blocking finding).

``CAO_AGENT_CARD_HOST=0.0.0.0`` (the documented opt-in for external A2A
discoverability) combined with auth-off used to expose an unauthenticated
``task.send``/``task.cancel`` write API to any network peer. The lifespan now
refuses to mount the A2A routers on a non-loopback bind unless auth is
configured — discovery (Agent Card + JWKS) still serves, the task API doesn't.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cli_agent_orchestrator.api.main import app


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in ("AUTH0_DOMAIN", "AUTH0_AUDIENCE", "CAO_AUTH_JWKS_URI", "CAO_A2A_DISABLED"):
        monkeypatch.delenv(var, raising=False)


def test_non_loopback_bind_without_auth_refuses_a2a_mount(monkeypatch, caplog):
    monkeypatch.setenv("CAO_AGENT_CARD_ENABLED", "true")
    monkeypatch.setenv("CAO_AGENT_CARD_HOST", "0.0.0.0")
    with TestClient(app, base_url="http://localhost"):
        listener = app.state.agent_card_listener
        # The discovery listener itself may start (that's read-only), but the
        # A2A task store/bus must not be wired.
        assert getattr(app.state, "a2a_store", None) is None
        if listener is not None:
            paths = {r.path for r in listener.server.config.app.routes}
            assert not any(p.startswith("/a2a") for p in paths)
    assert "Refusing to mount the A2A task routes" in caplog.text


def test_loopback_bind_without_auth_still_mounts(monkeypatch):
    monkeypatch.setenv("CAO_AGENT_CARD_ENABLED", "true")
    monkeypatch.delenv("CAO_AGENT_CARD_HOST", raising=False)
    with TestClient(app, base_url="http://localhost"):
        listener = app.state.agent_card_listener
        assert listener is not None
        paths = {r.path for r in listener.server.config.app.routes}
        assert any(p.startswith("/a2a") for p in paths)
        # The bounded store is the env-configured one.
        assert getattr(app.state, "a2a_store", None) is not None


def test_default_off_no_listener(monkeypatch):
    monkeypatch.delenv("CAO_AGENT_CARD_ENABLED", raising=False)
    with TestClient(app, base_url="http://localhost"):
        assert app.state.agent_card_listener is None
