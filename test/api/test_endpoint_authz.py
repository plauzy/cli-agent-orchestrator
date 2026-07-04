"""Tests for Auth0-for-MCP scope enforcement on FastAPI mutation endpoints.

Sibling RFC: docs/rfc/cao-auth0-mcp-integration-2026-05-11-v1.md §5.

The defense-in-depth backstop: even if an attacker bypasses the MCP App
and hits the REST surface directly, the FastAPI dependency raises 403
on insufficient scope. This file table-drives the mutation surface to
confirm each kind requires the right scope.

The tests run in auth-enabled mode and use `get_current_scopes`
dependency overrides to inject the granted scope set; we don't mint JWTs
here (that's covered by test/security/test_auth.py).
"""

from __future__ import annotations

import pytest

from cli_agent_orchestrator.api.main import app
from cli_agent_orchestrator.plugins import PluginRegistry
from cli_agent_orchestrator.security import (
    SCOPE_ADMIN,
    SCOPE_READ,
    SCOPE_WRITE,
    get_current_scopes,
)


@pytest.fixture
def client_with_scopes():
    """Builds a TestClient with a configurable scope-injection override."""
    from test.api.conftest import TestClientWithHost

    def _client(scopes: list[str]):
        app.state.plugin_registry = PluginRegistry()
        # Override the dependency for the duration of one TestClient.
        # Using a closure so different test cases can inject different scopes.
        app.dependency_overrides[get_current_scopes] = lambda: list(scopes)
        return TestClientWithHost(app)

    yield _client
    app.dependency_overrides.pop(get_current_scopes, None)


# Each entry: (method, path, body/params, required_scope).
# We send through endpoints that match real Phase 3 paths; some 404 or
# 500 downstream because the resource doesn't exist, but that happens
# AFTER the scope check so we still observe the 403 vs not-403 boundary.
_MUTATION_MATRIX = [
    (
        "POST",
        "/sessions",
        {"params": {"provider": "kiro_cli", "agent_profile": "developer"}},
        SCOPE_WRITE,
    ),
    ("DELETE", "/sessions/cao-x", {}, SCOPE_ADMIN),
    (
        "POST",
        "/sessions/cao-x/assign",
        {"params": {"agent_profile": "developer", "message": "x"}},
        SCOPE_WRITE,
    ),
    (
        "POST",
        "/sessions/cao-x/terminals",
        {"params": {"provider": "kiro_cli", "agent_profile": "developer"}},
        SCOPE_WRITE,
    ),
    ("POST", "/terminals/abc12345/input", {"params": {"message": "x"}}, SCOPE_WRITE),
    ("POST", "/terminals/abc12345/exit", {}, SCOPE_WRITE),
    ("POST", "/terminals/abc12345/interrupt", {}, SCOPE_WRITE),
    ("POST", "/terminals/abc12345/pause", {}, SCOPE_WRITE),
    ("POST", "/terminals/abc12345/resume", {}, SCOPE_WRITE),
    ("DELETE", "/terminals/abc12345", {}, SCOPE_ADMIN),
    (
        "POST",
        "/terminals/abc12345/inbox/messages",
        {"params": {"sender_id": "s", "message": "m"}},
        SCOPE_WRITE,
    ),
]


@pytest.mark.parametrize("method,path,kwargs,required", _MUTATION_MATRIX)
def test_mutation_rejects_when_required_scope_absent(
    client_with_scopes, method, path, kwargs, required
):
    """A read-only token should be rejected on every mutation endpoint."""
    client = client_with_scopes([SCOPE_READ])
    resp = client.request(method, path, **kwargs)
    assert (
        resp.status_code == 403
    ), f"{method} {path} should require {required}; got {resp.status_code} {resp.text}"
    assert required in resp.text


@pytest.mark.parametrize("method,path,kwargs,required", _MUTATION_MATRIX)
def test_mutation_passes_scope_check_with_admin(client_with_scopes, method, path, kwargs, required):
    """An admin token has every scope; the scope check passes (regardless of
    downstream success/failure, which depends on whether the resource exists)."""
    client = client_with_scopes([SCOPE_READ, SCOPE_WRITE, SCOPE_ADMIN])
    resp = client.request(method, path, **kwargs)
    # The endpoint may 404/500 because the test resource doesn't exist,
    # but it should NOT be a 403 (which would mean the scope check failed).
    assert (
        resp.status_code != 403
    ), f"{method} {path} unexpectedly 403'd with admin scope: {resp.text}"
