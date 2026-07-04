"""Agent Card builder.

Phase 1 / commit 6: produces an A2A v1.0-conformant ``agent-card.json``
document from CAO's runtime state — provider list, MCP tool surface, and
operator-supplied metadata stored in ``settings.json``.

The card is signed by ``signing.Signer`` and served at
``/.well-known/agent-card.json`` from the dedicated :9890 listener.
"""

from __future__ import annotations

import shutil
from importlib import metadata as _md
from typing import Any

# A2A v1.0 declared MCP-tool surface for CAO. These names are the same
# tools the FastMCP server exposes — see mcp_server/server.py.
_DECLARED_MCP_TOOLS = ["assign", "handoff", "send_message", "load_skill"]


# Provider binary lookup, mirroring api/main.py:list_providers_endpoint.
_PROVIDER_BINARIES = {
    "kiro_cli": "kiro-cli",
    "claude_code": "claude",
    "q_cli": "q",
    "codex": "codex",
    "gemini_cli": "gemini",
    "kimi_cli": "kimi",
    "copilot_cli": "copilot",
    "opencode_cli": "opencode",
}


def _package_version() -> str:
    try:
        return _md.version("cli-agent-orchestrator")
    except _md.PackageNotFoundError:  # pragma: no cover - install-time only
        return "0.0.0"


def _detect_installed_providers() -> list[dict[str, Any]]:
    """Mirror api/main.py:list_providers_endpoint without importing FastAPI."""
    return [
        {"name": p, "binary": b, "installed": shutil.which(b) is not None}
        for p, b in _PROVIDER_BINARIES.items()
    ]


def build_agent_card(
    metadata: dict[str, Any] | None = None,
    *,
    rpc_endpoint: str | None = None,
    stream_endpoint: str | None = None,
    tasks_endpoint: str | None = None,
) -> dict[str, Any]:
    """Build the unsigned Agent Card.

    ``metadata`` is operator-supplied configuration (``description``,
    ``contact``, ``vendor``, ``agent_id``) typically read from
    ``settings.json`` via ``settings_service``.

    Endpoints default to ``None`` because the full A2A transport surface
    arrives in Phase 5 (commit see plan §12). In Phase 1 the card declares
    skills and capabilities only — peers wishing to actually invoke tools
    must wait until the transport layer is published.
    """
    metadata = metadata or {}

    skills = [
        {"id": "orchestrate", "description": "Decompose tasks and dispatch to specialists."},
        {"id": "plan", "description": "Single-threaded planning over a write spine."},
        {
            "id": "code",
            "description": "Code generation through the Refinery write queue (planned for Phase 3).",
        },
        {"id": "review", "description": "Independent N=3 majority-vote review."},
        {
            "id": "search",
            "description": "Breadth-first read via Polecat swarm (planned for Phase 3).",
        },
    ]

    return {
        "$schema": "https://a2aproject.org/schemas/v1.0/agent-card.json",
        "agentId": metadata.get("agent_id", "cao-mayor-local"),
        "name": metadata.get("name", "CAO Mayor"),
        "description": metadata.get(
            "description",
            "CLI Agent Orchestrator — Tier-1 orchestrator for hierarchical multi-agent workflows.",
        ),
        "organization": metadata.get("organization", "local"),
        "vendor": metadata.get("vendor", "AWS Labs"),
        "contact": metadata.get("contact"),
        "version": _package_version(),
        "capabilities": {
            "skills": skills,
            "supportedModalities": ["text", "structured-data"],
            "tools": _DECLARED_MCP_TOOLS,
        },
        "providers": _detect_installed_providers(),
        "protocols": {
            "transport": ["json-rpc-2.0"],
            "streaming": "sse",
            "security": ["oauth2.1", "mtls"],
        },
        "endpoints": {
            "rpc": rpc_endpoint,
            "stream": stream_endpoint,
            "tasks": tasks_endpoint,
        },
        # AgentCardSignature is filled in by router.py when the card is
        # actually served — separating "build" from "sign" lets the tests
        # exercise each in isolation.
    }
