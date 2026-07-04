"""Integration tests for the /.well-known endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cli_agent_orchestrator.agent_card import build_listener_app
from cli_agent_orchestrator.agent_card import router as card_router
from cli_agent_orchestrator.agent_card.signing import Signer, verify_compact_jws


@pytest.fixture
def app(tmp_path: Path):
    """Spin up the dedicated card-listener FastAPI app on a temp key dir."""
    signer = Signer(tmp_path / "agent_card")
    metadata = lambda: {"agent_id": "cao-test-01", "name": "Test CAO"}
    app = build_listener_app(signer, metadata)
    yield app, signer
    card_router.reset()


@pytest.fixture
def client(app):
    fastapi_app, _signer = app
    return TestClient(fastapi_app)


# ---------------------------------------------------------------------------
# /.well-known/agent-card.json
# ---------------------------------------------------------------------------


class TestAgentCardEndpoint:
    def test_returns_200_with_signed_card(self, client):
        resp = client.get("/.well-known/agent-card.json")
        assert resp.status_code == 200
        body = resp.json()
        assert body["agentId"] == "cao-test-01"
        assert body["name"] == "Test CAO"
        assert "AgentCardSignature" in body

    def test_signature_verifies_against_jwks(self, client, app):
        _, signer = app
        body = client.get("/.well-known/agent-card.json").json()
        # Verify with the signer's public key directly.
        assert signer.verify_card(body) is True

    def test_signature_verifies_against_published_jwks(self, client, app):
        # Stronger end-to-end test: pull the public key from the JWKS
        # endpoint, then verify the card against it. This is what an
        # external A2A peer would do.
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        from cli_agent_orchestrator.agent_card.signing import _b64u_decode

        body = client.get("/.well-known/agent-card.json").json()
        jwks = client.get("/.well-known/jwks.json").json()
        keys = jwks["keys"]
        assert len(keys) == 1
        pub_raw = _b64u_decode(keys[0]["x"])
        public = Ed25519PublicKey.from_public_bytes(pub_raw)

        signature = body["AgentCardSignature"]
        assert verify_compact_jws(public, signature, omit_field=True, card=body)


# ---------------------------------------------------------------------------
# /.well-known/jwks.json
# ---------------------------------------------------------------------------


class TestJWKSEndpoint:
    def test_returns_200_with_one_key(self, client):
        resp = client.get("/.well-known/jwks.json")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["keys"], list)
        assert len(body["keys"]) == 1

    def test_jwk_has_required_fields(self, client):
        body = client.get("/.well-known/jwks.json").json()
        key = body["keys"][0]
        assert key["kty"] == "OKP"
        assert key["crv"] == "Ed25519"
        assert key["alg"] == "EdDSA"
        assert "x" in key
