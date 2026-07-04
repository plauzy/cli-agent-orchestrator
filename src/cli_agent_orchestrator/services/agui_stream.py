"""AG-UI event-stream adapter for CAO.

Sibling RFC: ``docs/rfc/cao-agui-l2-dashboard-2026-05-11-v1.md``.

The L2 standalone dashboard PWA (under ``cao_pwa/``) consumes
``GET /agui/v1/stream`` as an SSE stream of AG-UI typed events. CAO's
own event taxonomy (session.created, terminal.created, message.sent,
terminal.interrupt/pause/resume, etc.) is mapped to the AG-UI protocol's
typed event names via the pure function in this module.

Map (v1 — 6 of the 16 AG-UI typed events):

| CAO event             | AG-UI type             |
|-----------------------|------------------------|
| session.created       | RUN_STARTED            |
| session.killed        | RUN_FINISHED           |
| terminal.created      | STEP_STARTED           |
| terminal.killed       | STEP_FINISHED          |
| message.sent          | TEXT_MESSAGE_CONTENT   |
| terminal.interrupt    | RAW                    |
| terminal.pause        | RAW                    |
| terminal.resume       | RAW                    |
| terminal.interrupted  | RAW                    |
| terminal.paused       | RAW                    |
| terminal.resumed      | RAW                    |
| (any other)           | RAW                    |

Privacy boundary: message bodies are NEVER carried on the wire (same
contract as the SSE bus + rolling event log). TEXT_MESSAGE_CONTENT
emits an empty ``delta`` field; the PWA renders the metadata only.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

# AG-UI typed-event names. Pinned at the v1 spec version — when AG-UI
# evolves, the mapping is the one-file change.
AGUI_RUN_STARTED = "RUN_STARTED"
AGUI_RUN_FINISHED = "RUN_FINISHED"
AGUI_STEP_STARTED = "STEP_STARTED"
AGUI_STEP_FINISHED = "STEP_FINISHED"
AGUI_TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
AGUI_RAW = "RAW"


def to_agui_event(cao_event: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Translate one CAO event envelope to an AG-UI (type, data) pair.

    Args:
        cao_event: The dict the SSE bus publishes — shape
            ``{"type": "session.created", "payload": {...}, "traceparent": "..."}``.

    Returns:
        ``(agui_type, data_payload)`` where ``agui_type`` is one of the
        AGUI_* constants and ``data_payload`` is the JSON-serializable
        dict carried under ``data:`` on the wire.

    Privacy: message bodies are NEVER included in the payload.
    """
    event_type = cao_event.get("type", "")
    payload = cao_event.get("payload") or {}
    traceparent = cao_event.get("traceparent")

    if event_type == "session.created":
        return AGUI_RUN_STARTED, {
            "thread_id": payload.get("session_name"),
            "run_id": payload.get("session_name"),
            "traceparent": traceparent,
        }

    if event_type == "session.killed":
        return AGUI_RUN_FINISHED, {
            "thread_id": payload.get("session_name"),
            "run_id": payload.get("session_name"),
            "status": "terminated",
            "traceparent": traceparent,
        }

    if event_type == "terminal.created":
        return AGUI_STEP_STARTED, {
            "step_id": payload.get("terminal_id"),
            "step_name": payload.get("agent_name"),
            "provider": payload.get("provider"),
            "traceparent": traceparent,
        }

    if event_type == "terminal.killed":
        return AGUI_STEP_FINISHED, {
            "step_id": payload.get("terminal_id"),
            "step_name": payload.get("agent_name"),
            "traceparent": traceparent,
        }

    if event_type == "message.sent":
        # Body is intentionally redacted — matches the WAL / SSE-bus
        # privacy boundary. The PWA renders the metadata; it never
        # sees the message text.
        return AGUI_TEXT_MESSAGE_CONTENT, {
            "message_id": payload.get("receiver"),
            "role": "assistant",
            "delta": "",
            "metadata": {
                "sender": payload.get("sender"),
                "receiver": payload.get("receiver"),
                "orchestration_type": payload.get("orchestration_type"),
            },
            "traceparent": traceparent,
        }

    # Everything else (terminal.interrupt/pause/resume, ASI mitigations,
    # plugin-defined events) falls through to RAW. The PWA's reducer
    # dispatches on the ``cao_type`` field so the original semantics
    # survive the wire.
    return AGUI_RAW, {
        "cao_type": event_type,
        "payload": payload,
        "traceparent": traceparent,
    }


__all__ = [
    "AGUI_RAW",
    "AGUI_RUN_FINISHED",
    "AGUI_RUN_STARTED",
    "AGUI_STEP_FINISHED",
    "AGUI_STEP_STARTED",
    "AGUI_TEXT_MESSAGE_CONTENT",
    "to_agui_event",
]
