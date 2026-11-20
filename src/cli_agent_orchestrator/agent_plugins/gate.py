"""Execution gate for the agent-plugin management surface.

One predicate that the API routes and the CLI group both consult, so they cannot
disagree about whether the surface is live.

The surface graduated (#1393): the gate is **default-on**. With
``CAO_AGENT_PLUGINS_ENABLED`` unset, empty or truthy, ``cao plugin`` runs and the four
``/plugins*`` routes answer. Setting it to a falsy spelling (``0``, ``false``, ``no``,
``off``) keeps the old behaviour as a kill switch: the routes 404, byte-for-byte as an
unregistered path would, and the CLI group refuses every subcommand. Plugins are
untrusted content, so an operator who does not want the install path reachable has a
switch that needs no code change.

Before graduation the polarity was the reverse (default-off, modelled on the AG-UI
precedent in ``services/agui_enablement.py``). The truthy and falsy spellings are the
same ones ``CAO_AGUI_ENABLED`` and ``CAO_EAGER_INBOX_DELIVERY`` use.

Env-only on purpose: a ``settings.json`` knob would give a second place for the
setting to disagree with the environment. Read at call time rather than import time so
tests (and an operator exporting the variable into an already-running shell) see the
current value.

This gate carries no opinion about the verb or the route paths. The verb is decision
M1, recorded by the issue author in #573. The web UI's Plugins tab
(``PLUGINS_TAB_ENABLED``) and the TUI rows have their own switches and are not changed
by this gate.
"""

from __future__ import annotations

import os

#: Environment variable that enables the agent-plugin management surface.
ENV_VAR = "CAO_AGENT_PLUGINS_ENABLED"

_FALSY = ("0", "false", "no", "off")


def agent_plugins_surface_enabled() -> bool:
    """Return whether the agent-plugin management surface should be live.

    Default-on: only an explicitly falsy ``CAO_AGENT_PLUGINS_ENABLED`` closes it.
    """

    return os.environ.get(ENV_VAR, "").strip().lower() not in _FALSY
