"""Tests for Ed25519 Agent Card signing.

Pinned invariants:
  * The signer creates the key file lazily with mode 0600.
  * sign_card() / verify_card() round-trip a card.
  * Tampering with the card invalidates the signature.
  * The signature is over the card *minus* its AgentCardSignature field
    (otherwise the signature would be self-referential).
  * The public JWK uses RFC 8037 OKP / Ed25519 conventions.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from cli_agent_orchestrator.agent_card.signing import (
    Signer,
    _b64u,
    _b64u_decode,
    _canonical_json,
    verify_compact_jws,
)


@pytest.fixture
def signer(tmp_path: Path) -> Signer:
    return Signer(tmp_path / "agent_card")


# ---------------------------------------------------------------------------
# Key generation + on-disk format
# ---------------------------------------------------------------------------


class TestKeyManagement:
    def test_key_is_generated_lazily(self, tmp_path: Path):
        key_dir = tmp_path / "agent_card"
        assert not key_dir.exists()
        Signer(key_dir)
        assert (key_dir / Signer.KEY_FILENAME).exists()

    def test_key_file_is_mode_0600(self, tmp_path: Path):
        key_dir = tmp_path / "agent_card"
        Signer(key_dir)
        mode = (key_dir / Signer.KEY_FILENAME).stat().st_mode
        # Owner read/write only — group + other have no access.
        assert stat.S_IMODE(mode) == 0o600

    def test_second_construction_loads_existing_key(self, tmp_path: Path):
        key_dir = tmp_path / "agent_card"
        s1 = Signer(key_dir)
        first_jwk = s1.public_jwk()
        s2 = Signer(key_dir)
        # Same key on disk → same JWK fingerprint.
        assert s2.public_jwk() == first_jwk


# ---------------------------------------------------------------------------
# Public JWK
# ---------------------------------------------------------------------------


class TestPublicJwk:
    def test_jwk_uses_rfc8037_okp_ed25519(self, signer: Signer):
        jwk = signer.public_jwk()
        assert jwk["kty"] == "OKP"
        assert jwk["crv"] == "Ed25519"
        assert jwk["alg"] == "EdDSA"
        assert jwk["kid"] == Signer.KID
        assert jwk["use"] == "sig"
        assert "x" in jwk

    def test_jwk_x_decodes_to_32_bytes(self, signer: Signer):
        jwk = signer.public_jwk()
        raw = _b64u_decode(jwk["x"])
        assert len(raw) == 32  # Ed25519 public key length


# ---------------------------------------------------------------------------
# sign_card / verify_card round-trip
# ---------------------------------------------------------------------------


class TestSignCardRoundTrip:
    def test_signed_card_verifies(self, signer: Signer):
        card = {"name": "CAO Mayor", "version": "1.0.0"}
        signature = signer.sign_card(card)
        signed = {**card, "AgentCardSignature": signature}
        assert signer.verify_card(signed) is True

    def test_signature_does_not_cover_itself(self, signer: Signer):
        """Signing twice with and without an existing AgentCardSignature
        field must yield the same result — otherwise the signature would be
        self-referential and re-issuing would invalidate the previous one.
        """
        card = {"name": "CAO", "version": "1.0.0"}
        sig1 = signer.sign_card(card)
        sig2 = signer.sign_card({**card, "AgentCardSignature": "stale-value"})
        assert sig1 == sig2

    def test_tampered_card_does_not_verify(self, signer: Signer):
        card = {"name": "CAO Mayor", "version": "1.0.0"}
        signed = {**card, "AgentCardSignature": signer.sign_card(card)}
        signed["name"] = "Imposter"
        assert signer.verify_card(signed) is False

    def test_missing_signature_does_not_verify(self, signer: Signer):
        card = {"name": "CAO Mayor"}
        assert signer.verify_card(card) is False

    def test_garbled_signature_does_not_raise(self, signer: Signer):
        card = {"name": "CAO Mayor", "AgentCardSignature": "not.a.real.jws"}
        # Must return False rather than raise — a malformed signature is
        # an attacker, not a programming error.
        assert signer.verify_card(card) is False


# ---------------------------------------------------------------------------
# Compact JWS structural checks
# ---------------------------------------------------------------------------


class TestCompactJWS:
    def test_signature_is_three_dot_separated_segments(self, signer: Signer):
        compact = signer.sign_card({"name": "x"})
        parts = compact.split(".")
        assert len(parts) == 3
        # All three parts decode as base64url.
        for p in parts:
            _b64u_decode(p)

    def test_header_declares_eddsa_alg_and_kid(self, signer: Signer):
        compact = signer.sign_card({"name": "x"})
        header_b64 = compact.split(".")[0]
        header = json.loads(_b64u_decode(header_b64))
        assert header["alg"] == "EdDSA"
        assert header["kid"] == Signer.KID

    def test_canonical_json_is_stable(self):
        # Sorted keys + compact separators → byte-identical regardless of
        # input ordering.
        a = _canonical_json({"b": 2, "a": 1})
        b = _canonical_json({"a": 1, "b": 2})
        assert a == b
