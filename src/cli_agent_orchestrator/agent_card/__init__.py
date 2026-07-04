"""Signed A2A v1.0 Agent Card publication.

Surface:
  * ``Signer`` — Ed25519 sign/verify, lazily-generated key on disk.
  * ``build_agent_card`` — assembles the unsigned Agent Card from
    settings + provider list + MCP tool surface.
  * ``router`` — APIRouter exposing /.well-known/agent-card.json and
    /.well-known/jwks.json.
  * ``start_agent_card_listener`` — dedicated :9890 uvicorn server
    (no TrustedHostMiddleware) so external A2A peers can discover CAO.
"""

from cli_agent_orchestrator.agent_card.builder import build_agent_card
from cli_agent_orchestrator.agent_card.listener import (
    AgentCardListener,
    build_listener_app,
    start_agent_card_listener,
)
from cli_agent_orchestrator.agent_card.signing import JWS, Signer, verify_compact_jws

__all__ = [
    "AgentCardListener",
    "JWS",
    "Signer",
    "build_agent_card",
    "build_listener_app",
    "start_agent_card_listener",
    "verify_compact_jws",
]
