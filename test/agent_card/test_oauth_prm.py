"""Tests for the Auth0-for-MCP Protected Resource Metadata endpoint.

Sibling RFC: docs/rfc/cao-auth0-mcp-integration-2026-05-11-v1.md §4.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cli_agent_orchestrator.agent_card.router import router


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestOAuthProtectedResource:
    def test_returns_404_when_auth_disabled(self, client, monkeypatch) -> None:
        monkeypatch.delenv("AUTH0_DOMAIN", raising=False)
        resp = client.get("/.well-known/oauth-protected-resource")
        assert resp.status_code == 404

    def test_returns_metadata_when_auth_enabled(self, client, monkeypatch) -> None:
        monkeypatch.setenv("AUTH0_DOMAIN", "tenant.auth0.com")
        monkeypatch.setenv("AUTH0_AUDIENCE", "cao://my-host")
        resp = client.get("/.well-known/oauth-protected-resource")
        assert resp.status_code == 200
        body = resp.json()
        assert body["resource"] == "cao://my-host"
        assert body["authorization_servers"] == ["https://tenant.auth0.com/"]
        assert "cao:read" in body["scopes_supported"]
        assert "cao:write" in body["scopes_supported"]
        assert "cao:admin" in body["scopes_supported"]
        assert body["bearer_methods_supported"] == ["header"]
