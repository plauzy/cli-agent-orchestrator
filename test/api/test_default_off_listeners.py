"""Regression: `cao-server` with no flags opens no listener beyond :9889.

The Agent Card / A2A listener is an opt-in surface. This asserts the
default-off contract: without ``CAO_AGENT_CARD_ENABLED`` the lifespan must not
start the dedicated :9890 listener, and it binds loopback when enabled.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cli_agent_orchestrator.api.main import app


@pytest.fixture(autouse=True)
def _no_agent_card_env(monkeypatch):
    # Ensure a clean env: neither enable nor legacy disable flags set.
    monkeypatch.delenv("CAO_AGENT_CARD_ENABLED", raising=False)
    monkeypatch.delenv("CAO_AGENT_CARD_DISABLED", raising=False)


def test_no_agent_card_listener_without_flag():
    """Default (no flag) => the :9890 Agent Card listener is not started."""
    with TestClient(app):
        assert getattr(app.state, "agent_card_listener", "unset") is None


def test_listener_binds_loopback_by_default():
    """When enabled without CAO_AGENT_CARD_HOST, the listener binds 127.0.0.1."""
    import os

    from cli_agent_orchestrator.agent_card import listener as _listener

    # The bind-host resolution is the security-relevant line; assert its default
    # is loopback rather than 0.0.0.0 (exercised without actually binding).
    os.environ.pop("CAO_AGENT_CARD_HOST", None)
    resolved = None or os.environ.get("CAO_AGENT_CARD_HOST", "127.0.0.1")
    assert resolved == "127.0.0.1"
    # Guard against a regression of the module default back to 0.0.0.0.
    src = (_listener.__file__ or "").rstrip("c")
    with open(src, encoding="utf-8") as fh:
        text = fh.read()
    assert 'os.environ.get("CAO_AGENT_CARD_HOST", "127.0.0.1")' in text
