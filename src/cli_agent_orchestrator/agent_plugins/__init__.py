"""Agent Plugins (agent-plugins.org 1.0.0) client support.

This package is CAO's *agent plugin* implementation. It is deliberately
distinct from ``cli_agent_orchestrator.plugins``, which is CAO's unrelated
**event plugin** surface (``cao.plugins`` entry points, ``PluginRegistry``).
No symbol here shadows a symbol there and there is no import edge between
them; see the spec's decision D7.

Increment 1 is skills-only, which the specification's §11.2 establishes as a
conformant client. Nothing in this package expands ``${PLUGIN_ROOT}`` or
``${PLUGIN_DATA}``, validates against ``mcp.schema.json``, or launches a
subprocess on behalf of a plugin; those belong to Increment 2's
``mcp_mapping`` module and must not leak backwards into these modules.
"""
