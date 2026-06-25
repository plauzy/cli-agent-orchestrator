"""MCP App (SEP-1865) resource package for CAO.

Exposes the three ``ui://cao/*`` single-file HTML resources, the ``_meta.ui``
annotation builder (``ui_meta``) used to tag App tools, the resource-registration
entry point (``register_apps``), and the SEP-2133 capability negotiation shim
(``negotiate_capabilities``).

Everything here is **default-off** and **degrades gracefully**: registration is a
no-op unless ``CAO_MCP_APPS_ENABLED`` is set, and it returns ``False`` (logging an
informational message) rather than raising on a FastMCP build that predates the
``@mcp.resource`` decorator.
"""

from cli_agent_orchestrator.ext_apps.apps import (
    AGENT_RESOURCE_URI,
    DASHBOARD_RESOURCE_URI,
    EVENT_STREAM_RESOURCE_URI,
    register_apps,
    ui_meta,
)
from cli_agent_orchestrator.ext_apps.sep2133 import negotiate_capabilities

__all__ = [
    "DASHBOARD_RESOURCE_URI",
    "AGENT_RESOURCE_URI",
    "EVENT_STREAM_RESOURCE_URI",
    "ui_meta",
    "register_apps",
    "negotiate_capabilities",
]
