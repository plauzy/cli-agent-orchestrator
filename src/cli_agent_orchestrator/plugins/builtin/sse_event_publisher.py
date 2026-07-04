"""Built-in plugin: republishes lifecycle events to the SSE bus.

Phase 1 / commit 7: every ``Post*`` lifecycle event is republished as a
JSON-serializable dict to the in-process SSE bus, so the topology widget
(or any other ``/events`` subscriber) sees the fleet evolve in real time.

This plugin owns the translation from typed CaoEvent dataclasses to the
flat dict shape that SSE consumers expect — keeping the bus payload
contract decoupled from the internal event class hierarchy.
"""

from __future__ import annotations

import logging
from typing import Any

from cli_agent_orchestrator.plugins.base import CaoPlugin, hook
from cli_agent_orchestrator.plugins.events import (
    PostCreateSessionEvent,
    PostCreateTerminalEvent,
    PostInterruptTerminalEvent,
    PostKillSessionEvent,
    PostKillTerminalEvent,
    PostPauseTerminalEvent,
    PostResumeTerminalEvent,
    PostSendMessageEvent,
)
from cli_agent_orchestrator.services.sse_bus import get_bus

logger = logging.getLogger(__name__)


def _envelope(event_type: str, payload: dict[str, Any], traceparent: str | None) -> dict[str, Any]:
    return {
        "type": event_type,
        "payload": payload,
        "traceparent": traceparent,
    }


class SseEventPublisherPlugin(CaoPlugin):
    """Mirrors lifecycle events onto the SSE bus."""

    async def setup(self) -> None:
        logger.debug("SseEventPublisherPlugin loaded")

    @hook("post_create_session")
    async def on_create_session(self, event: PostCreateSessionEvent) -> None:
        get_bus().publish(
            _envelope("session.created", {"session_name": event.session_name}, event.traceparent)
        )

    @hook("post_kill_session")
    async def on_kill_session(self, event: PostKillSessionEvent) -> None:
        get_bus().publish(
            _envelope("session.killed", {"session_name": event.session_name}, event.traceparent)
        )

    @hook("post_create_terminal")
    async def on_create_terminal(self, event: PostCreateTerminalEvent) -> None:
        get_bus().publish(
            _envelope(
                "terminal.created",
                {
                    "terminal_id": event.terminal_id,
                    "agent_name": event.agent_name,
                    "provider": event.provider,
                },
                event.traceparent,
            )
        )

    @hook("post_kill_terminal")
    async def on_kill_terminal(self, event: PostKillTerminalEvent) -> None:
        get_bus().publish(
            _envelope(
                "terminal.killed",
                {"terminal_id": event.terminal_id, "agent_name": event.agent_name},
                event.traceparent,
            )
        )

    @hook("post_send_message")
    async def on_send_message(self, event: PostSendMessageEvent) -> None:
        # Body is intentionally not republished — same privacy boundary as
        # the WAL: messages may contain sensitive payloads.
        get_bus().publish(
            _envelope(
                "message.sent",
                {
                    "sender": event.sender,
                    "receiver": event.receiver,
                    "orchestration_type": event.orchestration_type,
                },
                event.traceparent,
            )
        )

    @hook("post_interrupt_terminal")
    async def on_interrupt_terminal(self, event: PostInterruptTerminalEvent) -> None:
        get_bus().publish(
            _envelope(
                "terminal.interrupted",
                {"terminal_id": event.terminal_id},
                event.traceparent,
            )
        )

    @hook("post_pause_terminal")
    async def on_pause_terminal(self, event: PostPauseTerminalEvent) -> None:
        get_bus().publish(
            _envelope(
                "terminal.paused",
                {"terminal_id": event.terminal_id},
                event.traceparent,
            )
        )

    @hook("post_resume_terminal")
    async def on_resume_terminal(self, event: PostResumeTerminalEvent) -> None:
        get_bus().publish(
            _envelope(
                "terminal.resumed",
                {"terminal_id": event.terminal_id},
                event.traceparent,
            )
        )
