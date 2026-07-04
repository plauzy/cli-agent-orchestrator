"""Ed25519 signing for the CAO Agent Card.

Produces an A2A v1.0 ``AgentCardSignature`` field — a JWS in compact
form (header.payload.signature) using Ed25519 (alg=EdDSA).

Conventions:
  * Private key file lives at ``CAO_HOME_DIR/agent_card/key.ed25519``,
    generated lazily with mode 0600 the first time ``Signer`` is constructed.
  * Signed payload is the canonical JSON of the card *without* its
    ``AgentCardSignature`` field — standard "self-referential signature"
    handling so the signed bytes are stable.
  * Public key is exported as a JWK (RFC 8037 OKP/Ed25519) at
    ``/.well-known/jwks.json`` so external A2A peers can verify.

We rely only on ``cryptography`` (already in tree) — no JWT/JWS library
dependency. The JWS compact form is short and well-defined.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def _b64u(data: bytes) -> str:
    """Base64url without padding (RFC 7515 §2)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _canonical_json(obj: dict[str, Any]) -> bytes:
    """Stable serialization for signing (sorted keys, no spaces)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class JWS:
    """Parsed JWS compact form: header.payload.signature (all base64url)."""

    header_b64: str
    payload_b64: str
    signature_b64: str

    def to_compact(self) -> str:
        return f"{self.header_b64}.{self.payload_b64}.{self.signature_b64}"


class Signer:
    """Ed25519 signer with a lazily-generated on-disk key."""

    KEY_FILENAME = "key.ed25519"
    KID = "cao-agent-card-v1"
    ALG = "EdDSA"

    def __init__(self, key_dir: Path) -> None:
        self._key_dir = key_dir
        self._key_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._key_path = key_dir / self.KEY_FILENAME
        self._private = self._load_or_generate()
        self._public = self._private.public_key()

    # -- key management -----------------------------------------------------

    def _load_or_generate(self) -> Ed25519PrivateKey:
        if self._key_path.exists():
            data = self._key_path.read_bytes()
            return serialization.load_pem_private_key(data, password=None)  # type: ignore[return-value]
        # Generate fresh key with mode 0600.
        key = Ed25519PrivateKey.generate()
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        # Write atomically with restrictive permissions.
        tmp = self._key_path.with_suffix(self._key_path.suffix + ".tmp")
        tmp.write_bytes(pem)
        os.chmod(tmp, 0o600)
        tmp.replace(self._key_path)
        return key

    def public_jwk(self) -> dict[str, Any]:
        """Return the public key as a JWK (RFC 8037 OKP, Ed25519)."""
        raw = self._public.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return {
            "kty": "OKP",
            "crv": "Ed25519",
            "kid": self.KID,
            "alg": self.ALG,
            "use": "sig",
            "x": _b64u(raw),
        }

    # -- signing / verification -------------------------------------------

    def sign(self, payload: bytes) -> JWS:
        """Produce a JWS compact-form signature over ``payload``."""
        header = {"alg": self.ALG, "kid": self.KID, "typ": "JWS"}
        header_b64 = _b64u(_canonical_json(header))
        payload_b64 = _b64u(payload)
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        signature = self._private.sign(signing_input)
        return JWS(header_b64, payload_b64, _b64u(signature))

    def sign_card(self, card: dict[str, Any]) -> str:
        """Sign an Agent Card dict and return the compact JWS string.

        The ``AgentCardSignature`` field, if present on input, is stripped
        before signing so the signed bytes are stable across re-issues.
        """
        body = {k: v for k, v in card.items() if k != "AgentCardSignature"}
        jws = self.sign(_canonical_json(body))
        return jws.to_compact()

    def verify_card(self, card: dict[str, Any]) -> bool:
        """Verify a signed Agent Card. Returns True if the signature is valid."""
        signature = card.get("AgentCardSignature")
        if not isinstance(signature, str):
            return False
        return verify_compact_jws(self._public, signature, omit_field=True, card=card)


def verify_compact_jws(
    public: Ed25519PublicKey,
    compact: str,
    *,
    omit_field: bool = False,
    card: dict[str, Any] | None = None,
) -> bool:
    """Verify a compact JWS against a public key.

    When ``omit_field`` is True, the verifier rebuilds the signed payload
    from ``card`` minus its ``AgentCardSignature`` field rather than from
    the JWS payload segment. This is what we need to verify a card that
    embeds its own signature.
    """
    parts = compact.split(".")
    if len(parts) != 3:
        return False
    header_b64, payload_b64, signature_b64 = parts
    try:
        signature = _b64u_decode(signature_b64)
    except Exception:
        return False

    if omit_field and card is not None:
        body = {k: v for k, v in card.items() if k != "AgentCardSignature"}
        expected_payload_b64 = _b64u(_canonical_json(body))
        if expected_payload_b64 != payload_b64:
            return False

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    try:
        public.verify(signature, signing_input)
        return True
    except Exception:
        return False
