"""Coverage for the Agent Card discovery router.

Targets ``agent_card/router.py`` branches: the uninitialized-signer
defensive returns for the agent-card + JWKS routes, and the
OAuth Protected-Resource-Metadata route in both its 404 (auth disabled)
and populated (auth enabled) forms.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import cli_agent_orchestrator.security as security_mod
from cli_agent_orchestrator.agent_card import router as card_router
from cli_agent_orchestrator.agent_card.signing import Signer


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(card_router.router)
    return TestClient(app, raise_server_exceptions=False)


def test_agent_card_uninitialized_returns_error(client: TestClient) -> None:
    card_router.reset()
    resp = client.get("/.well-known/agent-card.json")
    assert resp.status_code == 200
    assert resp.json() == {"error": "agent card listener not initialized"}


def test_jwks_uninitialized_returns_empty_keys(client: TestClient) -> None:
    card_router.reset()
    resp = client.get("/.well-known/jwks.json")
    assert resp.json() == {"keys": []}


def test_agent_card_and_jwks_when_configured(tmp_path, client: TestClient) -> None:
    signer = Signer(tmp_path / "kd")
    card_router.configure(signer, lambda: {"name": "cao"})
    try:
        card = client.get("/.well-known/agent-card.json").json()
        assert "AgentCardSignature" in card
        jwks = client.get("/.well-known/jwks.json").json()
        assert jwks["keys"][0]["kty"] == "OKP"
    finally:
        card_router.reset()


def test_oauth_protected_resource_404_when_auth_disabled(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(security_mod, "is_auth_enabled", lambda: False)
    resp = client.get("/.well-known/oauth-protected-resource")
    assert resp.status_code == 404


def test_oauth_protected_resource_document_when_auth_enabled(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(security_mod, "is_auth_enabled", lambda: True)
    monkeypatch.setenv("AUTH0_DOMAIN", "example.auth0.com")
    monkeypatch.setenv("AUTH0_AUDIENCE", "https://cao.example/api")
    resp = client.get("/.well-known/oauth-protected-resource")
    assert resp.status_code == 200
    body = resp.json()
    assert body["resource"] == "https://cao.example/api"
    assert body["authorization_servers"] == ["https://example.auth0.com/"]
    assert body["bearer_methods_supported"] == ["header"]
    assert isinstance(body["scopes_supported"], list)
