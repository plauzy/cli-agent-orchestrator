"""SEP-2133 capability negotiation for the CAO MCP App surface.

SEP-2133 lets a server advertise the MCP App capabilities it supports so a host
can decide whether to render the ``ui://cao/*`` resources. CAO's negotiation is
intentionally minimal and **default-off**: ``negotiate_capabilities`` returns an
empty capability set (a no-op) unless ``CAO_MCP_APPS_ENABLED`` is set, preserving
the localhost-only posture for anyone who has not opted in.
"""

import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

# The MCP App capabilities CAO advertises when enabled. ``resources`` signals the
# ``ui://cao/*`` views; ``tools`` signals the App tool channel; ``ui`` carries the
# rendering hints the host honours (CSP-sandboxed iframe, no host-side eval).
_CAPABILITIES: Dict[str, Any] = {
    "resources": True,
    "tools": True,
    "ui": {
        "iframe": True,
        "allowUnsafeEval": False,
    },
}


def _is_enabled() -> bool:
    """Return whether the MCP App surface is enabled via ``CAO_MCP_APPS_ENABLED``."""

    return os.getenv("CAO_MCP_APPS_ENABLED", "false").lower() in ("1", "true", "yes")


def negotiate_capabilities(client_capabilities: Any = None) -> Dict[str, Any]:
    """Return the MCP App capabilities CAO offers given the client's capabilities.

    No-op (returns ``{}``) unless ``CAO_MCP_APPS_ENABLED`` is set. When enabled,
    returns CAO's advertised capability set; the ``client_capabilities`` argument
    is accepted for forward compatibility (future intersection logic) but does not
    yet narrow the result.
    """

    if not _is_enabled():
        return {}
    if client_capabilities is not None:
        logger.debug("SEP-2133 negotiation with client capabilities: %s", client_capabilities)
    return dict(_CAPABILITIES)
