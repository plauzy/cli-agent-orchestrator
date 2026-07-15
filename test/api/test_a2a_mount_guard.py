"""Fail-closed guard for the A2A task routes.

``CAO_AGENT_CARD_HOST=0.0.0.0`` (the documented opt-in for external A2A
discoverability) combined with auth-off used to expose an unauthenticated
``task.send``/``task.cancel`` write API to any network peer. The lifespan now
refuses to mount the A2A routers on a non-loopback bind unless auth is
configured — discovery (Agent Card + JWKS) still serves, the task API doesn't.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cli_agent_orchestrator.api.main import _should_mount_a2a, app


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in ("AUTH0_DOMAIN", "AUTH0_AUDIENCE", "CAO_AUTH_JWKS_URI", "CAO_A2A_DISABLED"):
        monkeypatch.delenv(var, raising=False)
    # These lifespan integration tests start a real uvicorn listener. Pin it to
    # an OS-assigned ephemeral port (0) so back-to-back tests never contend on
    # the fixed :9890 — that contention caused EADDRINUSE / CancelledError
    # flakiness under CI's full-suite run (passed only in isolation locally).
    monkeypatch.setenv("CAO_AGENT_CARD_PORT", "0")


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


# ---------------------------------------------------------------------------
# Decision table on the extracted pure function (ported from the Kiro
# remediation) — the lifespan integration tests above cover the wiring; this
# covers the full matrix without binding a socket.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bind_host, a2a_disabled, auth_enabled, expected",
    [
        ("127.0.0.1", False, False, True),  # loopback + no auth: OK (dev)
        ("localhost", False, False, True),  # loopback alias
        ("::1", False, False, True),  # ipv6 loopback
        ("0.0.0.0", False, False, False),  # non-loopback + no auth: REFUSED
        ("0.0.0.0", False, True, True),  # non-loopback + auth: OK
        ("10.0.0.5", False, False, False),  # arbitrary external + no auth: REFUSED
        ("0.0.0.0", True, True, False),  # explicitly disabled always wins
        ("127.0.0.1", True, False, False),  # disabled wins on loopback too
    ],
)
def test_mount_decision(bind_host, a2a_disabled, auth_enabled, expected):
    assert (
        _should_mount_a2a(bind_host=bind_host, a2a_disabled=a2a_disabled, auth_enabled=auth_enabled)
        is expected
    )
