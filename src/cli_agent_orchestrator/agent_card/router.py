"""APIRouter exposing the Agent Card and JWKS at well-known URIs.

Mounted on the dedicated :9890 listener (no TrustedHostMiddleware) so
external A2A peers can discover CAO. Read-only — no other routes.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import APIRouter

from cli_agent_orchestrator.agent_card.builder import build_agent_card
from cli_agent_orchestrator.agent_card.signing import Signer

MetadataProvider = Callable[[], dict[str, Any]]

_signer: Optional[Signer] = None
_metadata_provider: Optional[MetadataProvider] = None


def configure(signer: Signer, metadata_provider: MetadataProvider) -> None:
    """Inject the dependencies the router needs to sign and assemble cards.

    Called once from the lifespan before the router starts serving. Keeping
    these as module-level injectables avoids forcing the FastAPI app to
    carry app.state.* through to a sub-application.
    """
    global _signer, _metadata_provider
    _signer = signer
    _metadata_provider = metadata_provider


def reset() -> None:
    """Forget injected state. Used in tests to start clean."""
    global _signer, _metadata_provider
    _signer = None
    _metadata_provider = None


router = APIRouter()


@router.get("/.well-known/agent-card.json")
def well_known_agent_card() -> dict[str, Any]:
    if _signer is None:
        # Defensive — should never happen if lifespan wired correctly.
        return {"error": "agent card listener not initialized"}
    metadata = _metadata_provider() if _metadata_provider else {}
    card = build_agent_card(metadata)
    card["AgentCardSignature"] = _signer.sign_card(card)
    return card


@router.get("/.well-known/jwks.json")
def well_known_jwks() -> dict[str, Any]:
    if _signer is None:
        return {"keys": []}
    return {"keys": [_signer.public_jwk()]}


@router.get("/.well-known/oauth-protected-resource")
def well_known_oauth_protected_resource() -> Any:
    """Protected Resource Metadata per RFC 9728.

    Auth0-for-MCP sibling RFC §4. Returns a JSON document letting MCP
    clients discover which authorization server issues tokens for this
    CAO instance and which scopes the API requires. When ``AUTH0_DOMAIN``
    is unset, the route returns 404 — discovery correctly signals "no
    auth required, treat as localhost-only".
    """
    from fastapi import HTTPException, Request
    from fastapi.responses import JSONResponse

    from cli_agent_orchestrator.security import SCOPES_SUPPORTED as ALL_SCOPES
    from cli_agent_orchestrator.security import is_auth_enabled as auth_enabled

    if not auth_enabled():
        raise HTTPException(status_code=404, detail="OAuth not configured")

    import os

    domain = os.environ.get("AUTH0_DOMAIN", "")
    audience = os.environ.get("AUTH0_AUDIENCE", "")

    return JSONResponse(
        {
            "resource": audience,
            "authorization_servers": [f"https://{domain}/"],
            "bearer_methods_supported": ["header"],
            "scopes_supported": list(ALL_SCOPES),
            "resource_documentation": (
                "https://github.com/awslabs/cli-agent-orchestrator/blob/main/docs/auth.md"
            ),
        }
    )
