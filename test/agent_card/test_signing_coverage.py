"""Coverage for the Ed25519 Agent Card signer verification branches.

Targets the failure paths in ``agent_card/signing.verify_compact_jws`` and
``Signer.verify_card``: wrong segment count, undecodable signature base64,
``omit_field`` payload mismatch, and a cryptographically-invalid signature
(the ``public.verify`` exception branch). Also round-trips a real sign →
verify to keep the happy path anchored.
"""

from __future__ import annotations

from cli_agent_orchestrator.agent_card.signing import (
    JWS,
    Signer,
    _b64u,
    verify_compact_jws,
)


def test_sign_and_verify_card_roundtrip(tmp_path) -> None:
    signer = Signer(tmp_path / "kd")
    card = {"name": "cao", "version": "1.0.0"}
    card["AgentCardSignature"] = signer.sign_card(card)
    assert signer.verify_card(card) is True


def test_verify_card_rejects_non_string_signature(tmp_path) -> None:
    signer = Signer(tmp_path / "kd")
    assert signer.verify_card({"name": "cao"}) is False  # no signature field
    assert signer.verify_card({"AgentCardSignature": 123}) is False  # wrong type


def test_verify_compact_jws_wrong_segment_count(tmp_path) -> None:
    signer = Signer(tmp_path / "kd")
    assert verify_compact_jws(signer._public, "onlyonepart") is False
    assert verify_compact_jws(signer._public, "a.b") is False


def test_verify_compact_jws_undecodable_signature(tmp_path) -> None:
    signer = Signer(tmp_path / "kd")
    # A signature segment that base64url cannot decode raises → False.
    bad = "aGVhZGVy.cGF5bG9hZA.@@@not-base64@@@"
    assert verify_compact_jws(signer._public, bad) is False


def test_verify_compact_jws_invalid_signature_bytes(tmp_path) -> None:
    signer = Signer(tmp_path / "kd")
    jws = signer.sign(b"hello world")
    # Replace the signature with a valid-base64 but wrong-length/content blob
    # so cryptography's verify() raises InvalidSignature → caught → False.
    tampered = JWS(jws.header_b64, jws.payload_b64, _b64u(b"\x00" * 64))
    assert verify_compact_jws(signer._public, tampered.to_compact()) is False


def test_verify_compact_jws_omit_field_payload_mismatch(tmp_path) -> None:
    signer = Signer(tmp_path / "kd")
    card = {"name": "cao"}
    compact = signer.sign_card(card)
    # Verify against a DIFFERENT card body → rebuilt payload won't match.
    assert (
        verify_compact_jws(signer._public, compact, omit_field=True, card={"name": "other"})
        is False
    )
