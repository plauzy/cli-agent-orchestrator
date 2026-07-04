"""Web-interaction primitives for Polecat workers (Phase 5).

Currently exports:
  * ``AiManifest`` + ``fetch_ai_manifest`` — discovers and parses
    ``/.well-known/ai-manifest.json`` published by sites that opt in
    to structured AI-agent interaction (commit 28).

The ``AiManifest`` is the emerging analog of ``robots.txt`` for AI
agents: a JSON document describing endpoints, allowed actions, rate
limits, and structured data shapes. When a Polecat encounters a site
that publishes one, it consults the manifest first instead of scraping
HTML — both more reliable and more polite.
"""

from cli_agent_orchestrator.web.ai_manifest import (
    AiManifest,
    AiManifestError,
    fetch_ai_manifest,
    parse_ai_manifest,
)

__all__ = [
    "AiManifest",
    "AiManifestError",
    "fetch_ai_manifest",
    "parse_ai_manifest",
]
