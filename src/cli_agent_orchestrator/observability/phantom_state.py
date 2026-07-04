"""Phantom-state incident detector (vision addendum §12.3).

A phantom-state incident is a terminal stuck in PROCESSING or
WAITING_USER_ANSWER beyond a configurable threshold with no sign of
progress (no new log output). The WAL-only substrate makes true
phantom state nearly definitionally zero, but this detector surfaces
any leaks so they can be investigated rather than silently rotting.

Detection is edge-triggered: a snapshot poll compares the last-known
``updated_at`` timestamp of each active terminal against the current
clock. Terminals that exceed ``threshold_seconds`` emit:

  * an OTel span (``cao.phantom_state.detected``) with terminal_id +
    duration attributes so the Deacon can correlate with ASI scores
  * an SSE event (``phantom_state_detected``) so the web UI can flag
    the terminal visually

Gated on ``CAO_PHANTOM_STATE_DETECTION=true`` (default off in v2.5 to
keep the existing polling contract unchanged).
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from opentelemetry import trace

logger = logging.getLogger(__name__)

_TRACER = trace.get_tracer("cao.observability.phantom_state", "2.5.0")

PHANTOM_STATE_DETECTION_ENABLED: bool = (
    os.getenv("CAO_PHANTOM_STATE_DETECTION", "false").lower() == "true"
)

# Seconds a terminal may stay in PROCESSING/WAITING_USER_ANSWER before
# being flagged as a phantom-state candidate. Tunable via env var.
PHANTOM_STATE_THRESHOLD_SECONDS: float = float(
    os.getenv("CAO_PHANTOM_STATE_THRESHOLD_SECONDS", "300")
)

_STUCK_STATUSES: frozenset[str] = frozenset({"processing", "waiting_user_answer"})

SseEmitter = Callable[[dict[str, Any]], None]


@dataclass
class PhantomStateIncident:
    """A single detected incident."""

    terminal_id: str
    status: str
    stuck_seconds: float
    detected_at: float = field(default_factory=time.time)


def check_terminals(
    terminals: Sequence[Any],
    *,
    now: float | None = None,
    threshold: float = PHANTOM_STATE_THRESHOLD_SECONDS,
    sse_emitter: SseEmitter | None = None,
) -> list[PhantomStateIncident]:
    """Inspect ``terminals`` and return any phantom-state incidents.

    Each item in ``terminals`` must expose ``.terminal_id``,
    ``.status`` (a string or enum with a ``.value``), and
    ``.updated_at`` (a ``datetime`` or ``None``).

    Side effects: emits OTel spans + SSE events for each incident
    found (when ``sse_emitter`` is provided).
    """
    if not PHANTOM_STATE_DETECTION_ENABLED:
        return []

    ts = now if now is not None else time.time()
    incidents: list[PhantomStateIncident] = []

    for terminal in terminals:
        status_str = (
            terminal.status.value if hasattr(terminal.status, "value") else str(terminal.status)
        ).lower()

        if status_str not in _STUCK_STATUSES:
            continue

        updated_at = terminal.updated_at
        if updated_at is None:
            continue

        updated_ts = (
            updated_at.timestamp() if hasattr(updated_at, "timestamp") else float(updated_at)
        )
        stuck_seconds = ts - updated_ts

        if stuck_seconds < threshold:
            continue

        incident = PhantomStateIncident(
            terminal_id=terminal.terminal_id,
            status=status_str,
            stuck_seconds=stuck_seconds,
        )
        incidents.append(incident)

        with _TRACER.start_as_current_span("cao.phantom_state.detected") as span:
            span.set_attribute("cao.terminal.id", incident.terminal_id)
            span.set_attribute("cao.phantom_state.status", incident.status)
            span.set_attribute("cao.phantom_state.stuck_seconds", round(incident.stuck_seconds, 1))
            span.set_attribute("cao.phantom_state.threshold_seconds", threshold)

        logger.warning(
            "Phantom-state detected: terminal %s stuck in %s for %.0fs",
            incident.terminal_id,
            incident.status,
            incident.stuck_seconds,
        )

        if sse_emitter is not None:
            try:
                sse_emitter(
                    {
                        "type": "phantom_state_detected",
                        "terminal_id": incident.terminal_id,
                        "status": incident.status,
                        "stuck_seconds": round(incident.stuck_seconds, 1),
                    }
                )
            except Exception:
                logger.warning("Phantom-state SSE emit failed", exc_info=True)

    return incidents
