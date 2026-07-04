"""Built-in plugin that observes lifecycle events for OTel-side correlation.

In Phase 1 / commit 2 the plugin's role is intentionally narrow:
  * it registers via the ``cao.plugins`` entry point so the registry wiring
    is exercised on every CAO startup, and
  * it logs each ``Post*`` event at debug level under the
    ``cli_agent_orchestrator.plugins.builtin.otel_sidecar`` logger.

It deliberately does not emit OTel spans yet. The plugin dispatch path
schedules hooks as background tasks (see ``services/plugin_dispatch.py``),
which means the span context that was active when the event was originally
*emitted* is no longer current when the hook runs. Commit 3 adds a
``traceparent`` field to ``CaoEvent`` so this plugin can reattach to the
upstream context and emit child spans correctly. Until then, keeping the
plugin span-free avoids producing orphan spans that would break the trace
hierarchy in downstream observability backends.
"""

from __future__ import annotations

import logging

from cli_agent_orchestrator.plugins.base import CaoPlugin, hook
from cli_agent_orchestrator.plugins.events import (
    PostCreateSessionEvent,
    PostCreateTerminalEvent,
    PostKillSessionEvent,
    PostKillTerminalEvent,
    PostSendMessageEvent,
)

logger = logging.getLogger(__name__)


class OtelSidecarPlugin(CaoPlugin):
    """Observes lifecycle events for future OTel correlation.

    Registered via ``cao.plugins`` entry point in ``pyproject.toml``:
        otel_sidecar = cli_agent_orchestrator.plugins.builtin.otel_sidecar:OtelSidecarPlugin
    """

    async def setup(self) -> None:
        logger.debug("OtelSidecarPlugin loaded")

    @hook("post_create_session")
    async def on_create_session(self, event: PostCreateSessionEvent) -> None:
        logger.debug("post_create_session session=%s", event.session_name)

    @hook("post_kill_session")
    async def on_kill_session(self, event: PostKillSessionEvent) -> None:
        logger.debug("post_kill_session session=%s", event.session_name)

    @hook("post_create_terminal")
    async def on_create_terminal(self, event: PostCreateTerminalEvent) -> None:
        logger.debug(
            "post_create_terminal terminal=%s agent=%s provider=%s",
            event.terminal_id,
            event.agent_name,
            event.provider,
        )

    @hook("post_kill_terminal")
    async def on_kill_terminal(self, event: PostKillTerminalEvent) -> None:
        logger.debug(
            "post_kill_terminal terminal=%s agent=%s",
            event.terminal_id,
            event.agent_name,
        )

    @hook("post_send_message")
    async def on_send_message(self, event: PostSendMessageEvent) -> None:
        logger.debug(
            "post_send_message sender=%s receiver=%s orchestration=%s",
            event.sender,
            event.receiver,
            event.orchestration_type,
        )
