"""``ui://cao/*`` MCP App resources, ``_meta.ui`` annotations, and registration.

The three views are shipped as **single-file HTML** artifacts built by the
``cao_mcp_apps`` frontend (``vite-plugin-singlefile``) into ``apps_static/``.
``register_apps`` mounts each artifact as an MCP resource under its ``ui://cao/*``
URI so an MCP App host can load it into a sandboxed iframe.

Resolution of ``apps_static/`` tries, in order:

1. the ``CAO_MCP_APPS_STATIC_DIR`` environment override,
2. the packaged location ``<package>/apps_static`` (wheel installs), then
3. the source-tree location ``<repo-root>/apps_static`` (editable/dev installs).

This module imports nothing from ``clients.*`` — it stays on the HTTP-only side of
the boundary and only reads static files from disk.
"""

import logging
import os
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# Stable ``ui://cao/*`` resource URIs the iframe entry points are served under.
DASHBOARD_RESOURCE_URI = "ui://cao/dashboard"
AGENT_RESOURCE_URI = "ui://cao/agent"
EVENT_STREAM_RESOURCE_URI = "ui://cao/event-stream"

# Default Content-Security-Policy domains for the sandboxed iframe, expressed in the
# **structured** SEP-1865 ``_meta.ui.csp`` shape (NOT a raw CSP string — see the
# research note in tasks.md task 9.1). The host composes the actual CSP header from
# these declared domains. ``connectDomains`` allows the iframe to stream the loopback
# Backplane ``/events`` directly; no remote origins are declared. The spec's default
# ``script-src`` is ``'self' 'unsafe-inline'`` with **no** ``'unsafe-eval'`` — our
# JIT-free bundle (task 1.2 scan) is what lets the views run under that policy.
DEFAULT_CSP = {
    "connectDomains": ["http://127.0.0.1:9889", "http://localhost:9889"],
    "resourceDomains": [],
    "frameDomains": [],
    "baseUriDomains": [],
}

# SEP-1865 mandates this MIME type for HTML MCP App resources.
RESOURCE_MIME_TYPE = "text/html;profile=mcp-app"

# Maps each resource URI to the single-file artifact built under apps_static/.
_RESOURCE_FILES = {
    DASHBOARD_RESOURCE_URI: "dashboard.html",
    AGENT_RESOURCE_URI: "agent.html",
    EVENT_STREAM_RESOURCE_URI: "event-stream.html",
}


def _is_enabled() -> bool:
    """Return whether the MCP App surface is enabled via ``CAO_MCP_APPS_ENABLED``."""

    return os.getenv("CAO_MCP_APPS_ENABLED", "false").lower() in ("1", "true", "yes")


def apps_static_dir() -> Optional[Path]:
    """Return the first existing ``apps_static`` directory, or ``None``.

    Tries the env override, the packaged location, then the source-tree location.
    """

    override = os.getenv("CAO_MCP_APPS_STATIC_DIR")
    candidates: List[Path] = []
    if override:
        candidates.append(Path(override))
    # <package>/ext_apps/apps_static — the package-shipped location the frontend
    # build (`npm run build:all`) emits to and the Phase 0 gates scan.
    package_root = Path(__file__).resolve().parents[1]
    candidates.append(package_root / "ext_apps" / "apps_static")
    # <package>/apps_static  (alternate packaged location)
    candidates.append(package_root / "apps_static")
    # <repo-root>/apps_static  (editable/dev fallback)
    repo_root = Path(__file__).resolve().parents[3]
    candidates.append(repo_root / "apps_static")

    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def ui_meta(
    csp: Optional[dict] = None,
    required_scopes: Optional[List[str]] = None,
    visibility: Optional[List[str]] = None,
    resource_uri: Optional[str] = None,
) -> dict:
    """Build the ``_meta.ui`` annotation attached to an MCP App tool/resource.

    Returns the SEP-1865 ``_meta.ui`` object. ``visibility`` and ``resourceUri``
    are the spec-defined keys (nested under ``ui``); ``csp`` is the structured
    domain object the host composes a CSP from; ``requiredScopes`` is a CAO
    extension the choke point reads for its scope pre-check.

    Args:
        csp: Structured CSP domains (``connectDomains`` / ``resourceDomains`` /
            ``frameDomains`` / ``baseUriDomains``). Defaults to :data:`DEFAULT_CSP`.
        required_scopes: CAO scopes the host should require before invoking the
            tool. Empty/None means no scope gate (a read tool).
        visibility: ``["model", "app"]`` or ``["app"]`` per SEP-1865. Omitted for
            resources (which are not tools).
        resource_uri: The ``ui://cao/*`` resource the tool result renders in.

    Returns:
        ``{"ui": {...}}`` suitable to pass as a tool's ``_meta``.
    """

    ui: dict = {
        "csp": csp or dict(DEFAULT_CSP),
        "requiredScopes": list(required_scopes) if required_scopes else [],
    }
    if visibility is not None:
        ui["visibility"] = list(visibility)
    if resource_uri is not None:
        ui["resourceUri"] = resource_uri
    return {"ui": ui}


def _read_resource_html(filename: str) -> Optional[str]:
    """Read a single-file artifact from ``apps_static/`` if present."""

    static_dir = apps_static_dir()
    if static_dir is None:
        return None
    path = static_dir / filename
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def register_apps(mcp: Any) -> bool:
    """Register the three ``ui://cao/*`` resources on the FastMCP server.

    Best-effort and side-effect free when disabled:

    * returns ``False`` (logging at info level) when ``CAO_MCP_APPS_ENABLED`` is
      unset, when the running FastMCP has no ``resource`` decorator, or when the
      ``apps_static/`` build output is missing;
    * otherwise registers one resource per built artifact and returns ``True``.
    """

    if not _is_enabled():
        logger.info(
            "MCP Apps disabled (CAO_MCP_APPS_ENABLED unset); skipping resource registration"
        )
        return False

    resource_decorator = getattr(mcp, "resource", None)
    if not callable(resource_decorator):
        logger.info(
            "FastMCP build has no @mcp.resource decorator; skipping MCP App resource registration"
        )
        return False

    static_dir = apps_static_dir()
    if static_dir is None:
        logger.info(
            "apps_static/ not found (frontend not built); skipping MCP App resource registration"
        )
        return False

    registered = 0
    for uri, filename in _RESOURCE_FILES.items():

        def _make_handler(fname: str, resource_uri: str):
            def _handler() -> str:
                html = _read_resource_html(fname)
                if html is None:
                    logger.warning("MCP App artifact missing at request time: %s", fname)
                    return f"<!doctype html><title>{resource_uri}</title><p>view not built</p>"
                return html

            return _handler

        try:
            decorated = resource_decorator(uri, mime_type=RESOURCE_MIME_TYPE)(
                _make_handler(filename, uri)
            )
            # Reference the decorated handler so linters do not flag it unused;
            # FastMCP retains its own registration regardless.
            del decorated
            registered += 1
        except Exception:  # pragma: no cover - defensive: never crash startup
            logger.exception("Failed to register MCP App resource %s", uri)

    logger.info(
        "Registered %d/%d MCP App resources from %s", registered, len(_RESOURCE_FILES), static_dir
    )
    return registered > 0
