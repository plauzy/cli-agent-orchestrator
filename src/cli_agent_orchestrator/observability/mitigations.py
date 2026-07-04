"""Mitigation handlers for the Deacon (Phase 4 / commit 21).

When the ``AsiEvaluator`` detects a threshold breach (commit 19), it
fires a ``MitigationEvent``. This module ships the standard handlers
that respond to those events:

  * ``LoggingHandler`` — always-on baseline. Emits a structured WARN
    log on every event so operators can audit drift in production.
  * ``SseBroadcastHandler`` — republishes events on the in-process
    SSE bus (Phase 1, commit 7) so the topology widget surfaces
    drift visually.
  * ``WALPersistenceHandler`` — appends every mitigation event to
    the WAL (Phase 1, commit 4) so the post-mortem trail survives
    a CAO restart.
  * ``KillSwitchHandler`` — on ``severity == "kill"``, sets a
    process-wide flag that the dispatch layer consults to refuse new
    work for the affected task class until manually cleared.
  * ``MemoryConsolidationHandler`` — on sustained ``severity=="mitigate"``
    (≥ N consecutive windows below threshold), persists a "consolidate"
    marker into the WAL and flags the task class on
    ``ConsolidationState``. The topology router reads that state and
    prefers cached / lower-cost topologies for that class on the next
    dispatch (cooperates with the cache-aware budget oracle).
  * ``BehavioralAnchoringHandler`` — same trigger surface; appends a
    system-prompt anchor (e.g. "prefer read-only tools") into the
    process-wide ``AnchorRegistry``. The dispatch layer reads anchors
    from the registry via ``dispatch_task(anchors=...)`` and prepends
    them onto the next agent invocation for that task class.

Each handler is independent and pluggable — the Deacon doesn't care
which subset is wired. The standard wiring (instantiated by the
FastAPI lifespan in commit 22) registers all six.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from cli_agent_orchestrator.observability.asi_evaluator import (
    MitigationEvent,
    MitigationHandler,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LoggingHandler
# ---------------------------------------------------------------------------


class LoggingHandler:
    """Always-on baseline. Emits one structured log per mitigation event.

    Severity → log level:
        warn      → WARNING
        mitigate  → ERROR
        kill      → CRITICAL
        recover   → INFO
    """

    _LEVEL_MAP = {
        "warn": logging.WARNING,
        "mitigate": logging.ERROR,
        "kill": logging.CRITICAL,
        "recover": logging.INFO,
    }

    def __call__(self, event: MitigationEvent) -> None:
        level = self._LEVEL_MAP.get(event.severity, logging.WARNING)
        logger.log(
            level,
            "ASI %s task_class=%s overall=%.3f consec_below=%d",
            event.severity,
            event.score.task_class,
            event.score.overall,
            event.consecutive_below,
        )


# ---------------------------------------------------------------------------
# SseBroadcastHandler
# ---------------------------------------------------------------------------


class SseBroadcastHandler:
    """Republishes the event to the in-process SSE bus.

    The bus accepts ``dict`` payloads (see ``services/sse_bus.py``);
    we serialize the event into a flat shape the topology widget can
    render directly. The handler degrades to a no-op if the bus
    is unreachable for any reason — drift detection must never
    block on the SSE consumer being alive.
    """

    def __init__(self, bus: Optional[Any] = None) -> None:
        # Lazy import so observability can be tested without the full
        # services/ tree imported.
        if bus is None:
            from cli_agent_orchestrator.services.sse_bus import get_bus

            bus = get_bus()
        self._bus = bus

    def __call__(self, event: MitigationEvent) -> None:
        try:
            self._bus.publish(
                {
                    "type": "asi.mitigation",
                    "severity": event.severity,
                    "task_class": event.score.task_class,
                    "overall": event.score.overall,
                    "response_consistency": event.score.response_consistency,
                    "tool_usage_patterns": event.score.tool_usage_patterns,
                    "coordination": event.score.coordination,
                    "behavioral_boundaries": event.score.behavioral_boundaries,
                    "consecutive_below": event.consecutive_below,
                }
            )
        except Exception:
            logger.warning("SSE broadcast failed for ASI mitigation", exc_info=True)


# ---------------------------------------------------------------------------
# WALPersistenceHandler
# ---------------------------------------------------------------------------


class WALPersistenceHandler:
    """Appends every mitigation event to the WAL.

    The WAL (Phase 1 commit 4) treats this as just another mutation
    record under the ``asi.mitigation`` op name. Replay (Phase 1
    commit 5) doesn't currently rebuild any state from these — the
    materialized index has no ASI projection — but the durable
    audit trail is the point.
    """

    def __init__(
        self, wal_appender: Optional[Callable[[str, dict[str, Any]], Optional[int]]] = None
    ) -> None:
        if wal_appender is None:
            from cli_agent_orchestrator.persistence import wal_append

            wal_appender = wal_append
        self._append = wal_appender

    def __call__(self, event: MitigationEvent) -> None:
        try:
            self._append(
                "asi.mitigation",
                {
                    "severity": event.severity,
                    "task_class": event.score.task_class,
                    "overall": event.score.overall,
                    "consecutive_below": event.consecutive_below,
                    "dimensions": {
                        "response_consistency": event.score.response_consistency,
                        "tool_usage_patterns": event.score.tool_usage_patterns,
                        "coordination": event.score.coordination,
                        "behavioral_boundaries": event.score.behavioral_boundaries,
                    },
                },
            )
        except Exception:
            logger.warning("WAL append failed for ASI mitigation", exc_info=True)


# ---------------------------------------------------------------------------
# KillSwitchHandler
# ---------------------------------------------------------------------------


@dataclass
class KillSwitchState:
    """Process-wide kill-switch state. The dispatch layer (commit 14
    swarm + commit 17 dispatch_task) consults this to refuse new work
    for task classes the Deacon has flagged."""

    _killed: set[str] = field(default_factory=set)

    def is_killed(self, task_class: str) -> bool:
        return task_class in self._killed

    def kill(self, task_class: str) -> None:
        self._killed.add(task_class)

    def clear(self, task_class: str) -> None:
        self._killed.discard(task_class)

    def clear_all(self) -> None:
        self._killed.clear()

    def killed_classes(self) -> set[str]:
        return set(self._killed)


# Module-level singleton — one kill switch per CAO process. Operators
# clear via a future API endpoint (Phase 5) or by restarting the server.
_state = KillSwitchState()


def get_kill_switch() -> KillSwitchState:
    return _state


def reset_kill_switch_for_tests() -> None:
    """Test helper. Production code should never call this."""
    _state.clear_all()


class KillSwitchHandler:
    """On ``severity == "kill"``, marks the task class as killed in the
    process-wide ``KillSwitchState``. Operators clear via API or restart.
    On ``severity == "recover"``, automatically clears the kill flag —
    drift recovered, normal dispatch resumes.
    """

    def __init__(self, state: Optional[KillSwitchState] = None) -> None:
        self._state = state or _state

    def __call__(self, event: MitigationEvent) -> None:
        task_class = event.score.task_class
        if event.severity == "kill":
            self._state.kill(task_class)
            logger.critical(
                "ASI kill switch triggered for task_class=%s; new dispatches refused",
                task_class,
            )
        elif event.severity == "recover":
            if self._state.is_killed(task_class):
                self._state.clear(task_class)
                logger.info("ASI kill switch cleared for task_class=%s (recovered)", task_class)


# ---------------------------------------------------------------------------
# MemoryConsolidationHandler
# ---------------------------------------------------------------------------


@dataclass
class ConsolidationState:
    """Process-wide consolidation markers, indexed by task class.

    The topology router consults ``is_marked(task_class)`` and prefers
    cached / lower-cost topologies for marked classes. Markers are
    timestamped so an operator can age them out via a runbook (or a
    future expiry handler — out of scope for v2.5).
    """

    _marked: dict[str, float] = field(default_factory=dict)

    def mark(self, task_class: str, ts: Optional[float] = None) -> None:
        self._marked[task_class] = ts if ts is not None else time.time()

    def clear(self, task_class: str) -> None:
        self._marked.pop(task_class, None)

    def clear_all(self) -> None:
        self._marked.clear()

    def is_marked(self, task_class: str) -> bool:
        return task_class in self._marked

    def marked_classes(self) -> dict[str, float]:
        return dict(self._marked)


_consolidation_state = ConsolidationState()


def get_consolidation_state() -> ConsolidationState:
    return _consolidation_state


def reset_consolidation_state_for_tests() -> None:
    _consolidation_state.clear_all()


class MemoryConsolidationHandler:
    """Marks the task class for memory consolidation when the Deacon
    detects sustained drift (``severity == "mitigate"`` for ≥ N
    consecutive windows). The topology router reads the marker and
    prefers cached / lower-cost topologies on subsequent dispatches.

    Side effects:
      1. Persists a ``consolidation.request`` record to the WAL so the
         post-mortem trail survives a restart.
      2. Marks the task class on the shared :class:`ConsolidationState`.

    On ``severity == "recover"``, the marker is cleared automatically —
    drift recovered, normal cost projection resumes.
    """

    def __init__(
        self,
        *,
        state: Optional[ConsolidationState] = None,
        wal_appender: Optional[Callable[[str, dict[str, Any]], Optional[int]]] = None,
        consecutive_threshold: int = 3,
    ) -> None:
        self._state = state or _consolidation_state
        if wal_appender is None:
            from cli_agent_orchestrator.persistence import wal_append

            wal_appender = wal_append
        self._append = wal_appender
        self._threshold = consecutive_threshold

    def __call__(self, event: MitigationEvent) -> None:
        task_class = event.score.task_class
        if event.severity == "mitigate" and event.consecutive_below >= self._threshold:
            self._state.mark(task_class)
            try:
                self._append(
                    "consolidation.request",
                    {
                        "task_class": task_class,
                        "reason": "asi.mitigate.sustained",
                        "consecutive_below": event.consecutive_below,
                        "overall": event.score.overall,
                    },
                )
            except Exception:
                logger.warning("WAL append failed for consolidation.request", exc_info=True)
            logger.warning(
                "Memory consolidation marker set for task_class=%s "
                "(consecutive_below=%d, overall=%.3f)",
                task_class,
                event.consecutive_below,
                event.score.overall,
            )
        elif event.severity == "recover":
            if self._state.is_marked(task_class):
                self._state.clear(task_class)
                logger.info(
                    "Memory consolidation marker cleared for task_class=%s (recovered)",
                    task_class,
                )


# ---------------------------------------------------------------------------
# BehavioralAnchoringHandler
# ---------------------------------------------------------------------------


@dataclass
class AnchorRegistry:
    """Process-wide map of task class → list of system-prompt anchors.

    Dispatch reads ``anchors_for(task_class)`` and prepends those strings
    onto the next agent invocation. Order preserves insertion (oldest
    first); duplicates are silently de-duped.
    """

    _anchors: dict[str, list[str]] = field(default_factory=dict)

    def add(self, task_class: str, anchor: str) -> None:
        bucket = self._anchors.setdefault(task_class, [])
        if anchor not in bucket:
            bucket.append(anchor)

    def anchors_for(self, task_class: str) -> list[str]:
        return list(self._anchors.get(task_class, ()))

    def clear(self, task_class: str) -> None:
        self._anchors.pop(task_class, None)

    def clear_all(self) -> None:
        self._anchors.clear()

    def has_anchors(self, task_class: str) -> bool:
        return bool(self._anchors.get(task_class))


_anchor_registry = AnchorRegistry()


def get_anchor_registry() -> AnchorRegistry:
    return _anchor_registry


def reset_anchor_registry_for_tests() -> None:
    _anchor_registry.clear_all()


# Default anchor — pins the agent to a conservative, read-leaning
# behavior when the Deacon detects sustained drift.
DEFAULT_BEHAVIORAL_ANCHOR = (
    "Drift detected: prefer read-only tools, verify state before mutation, "
    "and surface uncertainty rather than guessing."
)


class BehavioralAnchoringHandler:
    """Appends a system-prompt anchor on sustained drift.

    Trigger surface mirrors :class:`MemoryConsolidationHandler` —
    ``severity == "mitigate"`` for ≥ N consecutive windows. On fire, a
    string is appended to :class:`AnchorRegistry` for the task class;
    the dispatch layer threads it through ``dispatch_task(anchors=...)``
    on the next invocation. On ``severity == "recover"``, the anchors
    for the task class are cleared.
    """

    def __init__(
        self,
        *,
        registry: Optional[AnchorRegistry] = None,
        anchor_text: Optional[str] = None,
        consecutive_threshold: int = 3,
    ) -> None:
        self._registry = registry or _anchor_registry
        self._anchor = anchor_text or DEFAULT_BEHAVIORAL_ANCHOR
        self._threshold = consecutive_threshold

    def __call__(self, event: MitigationEvent) -> None:
        task_class = event.score.task_class
        if event.severity == "mitigate" and event.consecutive_below >= self._threshold:
            self._registry.add(task_class, self._anchor)
            logger.warning(
                "Behavioral anchor installed for task_class=%s (anchor=%r)",
                task_class,
                self._anchor[:80],
            )
        elif event.severity == "recover":
            if self._registry.has_anchors(task_class):
                self._registry.clear(task_class)
                logger.info(
                    "Behavioral anchors cleared for task_class=%s (recovered)",
                    task_class,
                )


# ---------------------------------------------------------------------------
# Standard wiring
# ---------------------------------------------------------------------------


def standard_handlers(
    *,
    sse_bus: Optional[Any] = None,
    wal_appender: Optional[Callable[[str, dict[str, Any]], Optional[int]]] = None,
    kill_switch: Optional[KillSwitchState] = None,
    consolidation_state: Optional[ConsolidationState] = None,
    anchor_registry: Optional[AnchorRegistry] = None,
    consecutive_threshold: int = 3,
) -> list[MitigationHandler]:
    """The default set of handlers. Wire all six into a fresh
    ``AsiEvaluator`` to get the full Phase 4 control loop."""
    return [
        LoggingHandler(),
        SseBroadcastHandler(bus=sse_bus),
        WALPersistenceHandler(wal_appender=wal_appender),
        KillSwitchHandler(state=kill_switch),
        MemoryConsolidationHandler(
            state=consolidation_state,
            wal_appender=wal_appender,
            consecutive_threshold=consecutive_threshold,
        ),
        BehavioralAnchoringHandler(
            registry=anchor_registry,
            consecutive_threshold=consecutive_threshold,
        ),
    ]
