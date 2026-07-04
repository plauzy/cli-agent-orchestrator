"""AI Manifest fetcher + parser (Phase 5 / commit 28).

The AI Manifest is the emerging convention for sites to publish a
structured guide for AI agents at ``/.well-known/ai-manifest.json``.
Think of it as the AI-agent analog of ``robots.txt`` and the OpenAPI
spec rolled into one: a JSON document describing endpoints, allowed
actions, rate limits, schema hints, and any contact metadata the
agent should respect.

The spec is still in flux across the ecosystem (no single normative
schema as of writing). This module models the core fields that have
converged across the major proposals and round-trips everything else
into ``extra`` so downstream code can read novel fields without
losing them.

Polecat workflow:

  1. Before any HTML scraping, ``fetch_ai_manifest(base_url)`` tries
     ``GET {base_url}/.well-known/ai-manifest.json`` (with bounded
     timeout + size cap).
  2. On success → return an ``AiManifest``; the Polecat consults
     ``endpoints``, ``rate_limit``, etc. before issuing further
     requests.
  3. On 404, network error, or schema violation → return ``None``;
     the Polecat falls back to HTML scraping.

Failure modes are explicit and non-fatal — a site without a manifest
is the common case, and we never want manifest-fetch errors to break
the broader Polecat workflow.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


# Cap manifest size to a defensive limit. The spec doesn't mandate
# one, but a multi-MB "manifest" is almost certainly malicious.
_MAX_MANIFEST_BYTES = 1_048_576  # 1 MiB

# Bounded fetch timeout. Polecat can't afford to block forever on a
# slow well-known endpoint.
_DEFAULT_TIMEOUT_SECONDS = 5.0


class AiManifestError(Exception):
    """Raised when a manifest is fetched but doesn't parse.

    Network errors and 404s do NOT raise — those map to ``None`` from
    ``fetch_ai_manifest``. Only structural violations (oversize body,
    invalid JSON, wrong top-level type) raise.
    """


@dataclass
class AiManifest:
    """Parsed AI Manifest. Lossy round-trip — unknown fields land in ``extra``.

    Field semantics follow the converging conventions across the major
    proposals. Most fields are optional because the spec is still
    evolving; downstream callers should treat anything beyond ``name``
    as best-effort.
    """

    name: str = ""
    description: str = ""
    version: str = ""
    base_url: str = ""
    endpoints: list[dict[str, Any]] = field(default_factory=list)
    rate_limit: Optional[dict[str, Any]] = None
    contact: dict[str, Any] = field(default_factory=dict)
    schemas: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def has_endpoints(self) -> bool:
        return len(self.endpoints) > 0

    def endpoint_for(self, name: str) -> Optional[dict[str, Any]]:
        """Look up an endpoint by its ``name`` field."""
        for ep in self.endpoints:
            if ep.get("name") == name:
                return ep
        return None


def parse_ai_manifest(payload: Any) -> AiManifest:
    """Parse a decoded JSON payload into an ``AiManifest``.

    Raises ``AiManifestError`` if the top-level structure isn't an
    object. Tolerates missing optional fields.
    """
    if not isinstance(payload, dict):
        raise AiManifestError(f"manifest must be a JSON object; got {type(payload).__name__}")

    known = {
        "name",
        "description",
        "version",
        "base_url",
        "endpoints",
        "rate_limit",
        "contact",
        "schemas",
    }
    return AiManifest(
        name=str(payload.get("name", "")),
        description=str(payload.get("description", "")),
        version=str(payload.get("version", "")),
        base_url=str(payload.get("base_url", "")),
        endpoints=list(payload.get("endpoints") or []),
        rate_limit=payload.get("rate_limit"),
        contact=dict(payload.get("contact") or {}),
        schemas=dict(payload.get("schemas") or {}),
        extra={k: v for k, v in payload.items() if k not in known},
    )


def fetch_ai_manifest(
    base_url: str,
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    fetcher: Any = None,
) -> Optional[AiManifest]:
    """Best-effort fetch of ``{base_url}/.well-known/ai-manifest.json``.

    Returns ``None`` for sites that don't publish a manifest (404),
    timeouts, network errors, oversize bodies, or invalid JSON. Returns
    an ``AiManifest`` on a clean fetch + parse.

    The ``fetcher`` parameter is for tests — pass a callable
    ``(url, timeout) -> (status_code, body_bytes)`` to substitute the
    HTTP layer. Production calls go through ``urllib.request`` so we
    don't add a dependency on requests/httpx for a 1-shot fetch.
    """
    if not base_url:
        return None
    url = urljoin(base_url.rstrip("/") + "/", ".well-known/ai-manifest.json")
    fetch = fetcher or _urllib_fetch

    try:
        status, body = fetch(url, timeout_seconds)
    except Exception:
        logger.debug("AI Manifest fetch errored for %s", url, exc_info=True)
        return None

    if status != 200:
        logger.debug("AI Manifest fetch %s → status %d", url, status)
        return None
    if len(body) > _MAX_MANIFEST_BYTES:
        logger.warning(
            "AI Manifest at %s exceeds %d bytes; treating as missing",
            url,
            _MAX_MANIFEST_BYTES,
        )
        return None

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("AI Manifest at %s is not valid JSON; ignoring", url)
        return None

    try:
        manifest = parse_ai_manifest(payload)
    except AiManifestError:
        logger.warning("AI Manifest at %s failed schema validation; ignoring", url)
        return None
    return manifest


def _urllib_fetch(url: str, timeout_seconds: float) -> tuple[int, bytes]:
    """Minimal stdlib fetcher. Returns (status_code, body)."""
    # Imported here so the production fetcher path doesn't pay the
    # cost when tests inject their own fetcher.
    import urllib.request

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "cli-agent-orchestrator/2.5 AI-Manifest-fetch",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            return resp.status, resp.read(_MAX_MANIFEST_BYTES + 1)
    except urllib.error.HTTPError as exc:
        # 404, 403, etc. — surface the status, empty body.
        return exc.code, b""
