"""Single-threaded write queue (Phase 3 / commit 11).

The Refinery is the only path through which state-mutating actions
reach the WAL + SQLAlchemy. Every ``submit`` runs under a single
``asyncio.Lock`` so writes are serialized — Cognition's "write
contention" failure mode is structurally impossible here.

Per-request flow:
  1. Rule-of-Two: deny outright if the action's classification has all
     three flags true (untrusted + sensitive + change_state).
  2. Policy: ``ALLOW`` continues, ``DENY`` returns immediately,
     ``ESCALATE`` emits an SSE event and (in v2.5.x) returns
     ``escalated`` for the caller to handle. Phase 5 wires actual
     blocking on operator acknowledgement.
  3. WAL append: if the caller registered the action with the existing
     WAL writer (commit 4), the request payload is durably persisted
     before the executor runs.
  4. Execute: the caller-supplied async ``executor`` runs the actual
     mutation. Its return value is propagated back as the result.
  5. SSE notify: a ``refinery.write`` event is published to the bus
     so the topology widget reflects the activity.

Every step records a span attribute on a ``cao.refinery.process`` span,
so post-hoc analysis can correlate refinery decisions with downstream
stability (Deacon, Phase 4).

The Refinery is intentionally a primitive in commit 11 — it doesn't
yet replace the direct ``db.commit()`` calls in ``clients/database.py``.
The Mayor's MCP dispatch path (commit 14) and the Polecat synthesis
path (also commit 14) are the first call sites; rewiring the existing
inline mutations is a deliberate later refactor to avoid regressing
the 9 mutation sites in one commit.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from opentelemetry import trace

from cli_agent_orchestrator.refinery import rule_of_two
from cli_agent_orchestrator.refinery.policy import (
    PermissivePolicy,
    Policy,
    PolicyOutcome,
)
from cli_agent_orchestrator.telemetry import semconv

logger = logging.getLogger(__name__)

_TRACER = trace.get_tracer("cao.refinery", "2.5.0")

# When true, any write submission that arrives without a WAL appender bound
# raises StrictWalModeViolation instead of silently skipping the WAL step.
# Implements the WAL-only cross-agent communication substrate from vision §8.
STRICT_WAL_MODE: bool = os.getenv("STRICT_WAL_MODE", "false").lower() == "true"


class StrictWalModeViolation(RuntimeError):
    """Raised when STRICT_WAL_MODE=true and no WAL appender is bound."""

    def __init__(self, action: str) -> None:
        super().__init__(
            f"STRICT_WAL_MODE: write '{action}' rejected — no WAL appender bound. "
            "Set a wal_appender on RefineryQueue or disable STRICT_WAL_MODE."
        )
        self.action = action


@dataclass(frozen=True)
class WriteRequest:
    """An action submitted to the Refinery for serialized execution.

    ``executor`` is an async callable that performs the actual mutation.
    The Refinery decides *whether* the executor runs (policy + Rule-of-Two)
    but doesn't peer inside it — that boundary keeps the Refinery
    domain-agnostic and makes it trivial to test without a database.
    """

    action: str
    payload: dict[str, Any]
    executor: Callable[[], Awaitable[Any]]
    actor: str = "unknown"
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass(frozen=True)
class SyncWriteRequest:
    """Synchronous variant of :class:`WriteRequest`.

    Used by callers that can't be made async (synchronous SQLAlchemy
    sessions in ``clients/database.py``, CLI commands, watchdog
    observers). The gate logic (Rule-of-Two + policy + WAL + execute +
    SSE) is identical; only the executor signature differs.
    """

    action: str
    payload: dict[str, Any]
    executor: Callable[[], Any]
    actor: str = "unknown"
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)


class RefineryResult:
    """Outcome of a Refinery submission. Carries the executor's return value
    when it ran, otherwise ``None`` and a reason."""

    __slots__ = ("status", "value", "reason", "request_id")

    def __init__(
        self,
        status: str,
        request_id: str,
        value: Any = None,
        reason: str = "",
    ) -> None:
        self.status = status
        self.request_id = request_id
        self.value = value
        self.reason = reason

    def __repr__(self) -> str:
        return (
            f"RefineryResult(status={self.status!r}, request_id={self.request_id!r}, "
            f"value={self.value!r}, reason={self.reason!r})"
        )


# Type aliases for caller-provided side-channels. Both are optional
# in commit 11 to keep tests tight; production wiring (commit 14) will
# pass real instances.
WalAppender = Callable[[str, dict[str, Any]], Optional[int]]
SseEmitter = Callable[[dict[str, Any]], None]


class RefineryQueue:
    """Serialized write gate. One instance per CAO process."""

    def __init__(
        self,
        policy: Policy | None = None,
        wal_appender: WalAppender | None = None,
        sse_emitter: SseEmitter | None = None,
    ) -> None:
        self._policy: Policy = policy or PermissivePolicy()
        self._wal: WalAppender | None = wal_appender
        self._sse: SseEmitter | None = sse_emitter
        self._lock = asyncio.Lock()
        # Sync writers (database.py callers) coordinate on a separate
        # threading.Lock — the asyncio.Lock above is unusable from sync
        # contexts. The two paths are individually serialized; in CAO
        # today, sync and async writers don't run truly concurrently
        # (FastAPI handlers + CLI + MCP tools are each per-request), so
        # this preserves the single-writer property in practice.
        self._sync_lock = threading.Lock()
        self._submitted = 0
        self._allowed = 0
        self._denied = 0
        self._escalated = 0

    @property
    def stats(self) -> dict[str, int]:
        """Counters for retrospective analysis. Useful in tests + dashboards."""
        return {
            "submitted": self._submitted,
            "allowed": self._allowed,
            "denied": self._denied,
            "escalated": self._escalated,
        }

    async def submit(self, request: WriteRequest) -> RefineryResult:
        """Enqueue a request, evaluate policy + Rule-of-Two, and run if allowed.

        Returns a ``RefineryResult`` describing the outcome. Never raises
        for policy denials — those are first-class results, not exceptions.
        Exceptions raised by the executor itself propagate up so the
        caller can handle them (the Refinery does not swallow them).
        """
        async with self._lock:
            self._submitted += 1
            with _TRACER.start_as_current_span("cao.refinery.process") as span:
                span.set_attribute(semconv.CAO_REFINERY_ACTOR, request.actor)
                span.set_attribute(semconv.CAO_REFINERY_ACTION, request.action)

                # 1. Rule-of-Two early reject.
                classification = rule_of_two.lookup(request.action)
                if classification.violates_rule_of_two:
                    span.set_attribute(semconv.CAO_REFINERY_POLICY_OUTCOME, "rule-of-two-violation")
                    span.add_event(
                        "rule-of-two-violation",
                        {"actor": request.actor, "action": request.action},
                    )
                    self._denied += 1
                    return RefineryResult(
                        status="denied",
                        request_id=request.request_id,
                        reason="rule-of-two-violation",
                    )

                # 2. Policy evaluation.
                outcome = self._policy.evaluate(request.action, request.payload)
                span.set_attribute(semconv.CAO_REFINERY_POLICY_OUTCOME, outcome.value)

                if outcome == PolicyOutcome.DENY:
                    self._denied += 1
                    return RefineryResult(
                        status="denied", request_id=request.request_id, reason="policy"
                    )

                if outcome == PolicyOutcome.ESCALATE:
                    self._escalated += 1
                    self._notify_sse(
                        {
                            "type": "refinery.escalated",
                            "request_id": request.request_id,
                            "actor": request.actor,
                            "action": request.action,
                        }
                    )
                    return RefineryResult(
                        status="escalated",
                        request_id=request.request_id,
                        reason="policy-escalate",
                    )

                # 3. WAL append before execute (durability before action).
                self._wal_append(request)

                # 4. Execute the caller-supplied mutation.
                try:
                    value = await request.executor()
                except Exception:
                    # Don't swallow — policy ALLOWED but the executor
                    # failed. The caller deserves the exception.
                    span.set_attribute(semconv.CAO_REFINERY_POLICY_OUTCOME, "execute-error")
                    raise

                self._allowed += 1

                # 5. Notify the SSE bus that the write completed.
                self._notify_sse(
                    {
                        "type": "refinery.completed",
                        "request_id": request.request_id,
                        "actor": request.actor,
                        "action": request.action,
                    }
                )

                return RefineryResult(
                    status="completed", request_id=request.request_id, value=value
                )

    def submit_sync(self, request: SyncWriteRequest) -> RefineryResult:
        """Synchronous twin of :meth:`submit` for sync DB callers.

        Same gate sequence as :meth:`submit` (Rule-of-Two → policy →
        WAL → execute → SSE), serialized through ``self._sync_lock``.
        Exceptions raised by the executor propagate up; policy denials
        come back as a non-raising ``RefineryResult``.
        """
        with self._sync_lock:
            self._submitted += 1
            with _TRACER.start_as_current_span("cao.refinery.process") as span:
                span.set_attribute(semconv.CAO_REFINERY_ACTOR, request.actor)
                span.set_attribute(semconv.CAO_REFINERY_ACTION, request.action)

                classification = rule_of_two.lookup(request.action)
                if classification.violates_rule_of_two:
                    span.set_attribute(semconv.CAO_REFINERY_POLICY_OUTCOME, "rule-of-two-violation")
                    span.add_event(
                        "rule-of-two-violation",
                        {"actor": request.actor, "action": request.action},
                    )
                    self._denied += 1
                    return RefineryResult(
                        status="denied",
                        request_id=request.request_id,
                        reason="rule-of-two-violation",
                    )

                outcome = self._policy.evaluate(request.action, request.payload)
                span.set_attribute(semconv.CAO_REFINERY_POLICY_OUTCOME, outcome.value)

                if outcome == PolicyOutcome.DENY:
                    self._denied += 1
                    return RefineryResult(
                        status="denied", request_id=request.request_id, reason="policy"
                    )

                if outcome == PolicyOutcome.ESCALATE:
                    self._escalated += 1
                    self._notify_sse(
                        {
                            "type": "refinery.escalated",
                            "request_id": request.request_id,
                            "actor": request.actor,
                            "action": request.action,
                        }
                    )
                    return RefineryResult(
                        status="escalated",
                        request_id=request.request_id,
                        reason="policy-escalate",
                    )

                self._wal_append_sync(request)

                try:
                    value = request.executor()
                except Exception:
                    span.set_attribute(semconv.CAO_REFINERY_POLICY_OUTCOME, "execute-error")
                    raise

                self._allowed += 1
                self._notify_sse(
                    {
                        "type": "refinery.completed",
                        "request_id": request.request_id,
                        "actor": request.actor,
                        "action": request.action,
                    }
                )
                return RefineryResult(
                    status="completed", request_id=request.request_id, value=value
                )

    def _wal_append(self, request: WriteRequest) -> None:
        if self._wal is None:
            if STRICT_WAL_MODE:
                raise StrictWalModeViolation(request.action)
            return
        try:
            self._wal(request.action, request.payload)
        except StrictWalModeViolation:
            raise
        except Exception:
            logger.warning("Refinery WAL append failed for %s", request.action, exc_info=True)

    def _wal_append_sync(self, request: SyncWriteRequest) -> None:
        if self._wal is None:
            if STRICT_WAL_MODE:
                raise StrictWalModeViolation(request.action)
            return
        try:
            self._wal(request.action, request.payload)
        except StrictWalModeViolation:
            raise
        except Exception:
            logger.warning("Refinery WAL append failed for %s", request.action, exc_info=True)

    def _notify_sse(self, event: dict[str, Any]) -> None:
        if self._sse is None:
            return
        try:
            self._sse(event)
        except Exception:
            logger.warning("Refinery SSE emit failed", exc_info=True)


# ---------------------------------------------------------------------------
# Module-level queue handle for sync callers
# ---------------------------------------------------------------------------
#
# FastAPI lifespan binds the live Refinery via :func:`set_refinery_queue`;
# sync callers (``clients/database.py``, CLI, watchdog) read it via
# :func:`get_refinery_queue`. When unset (tests, isolated CLI), sync
# callers fall back to running the executor directly — preserving v1.x
# behavior so the migration is backwards-compatible.

_QUEUE: Optional["RefineryQueue"] = None


def set_refinery_queue(queue: Optional["RefineryQueue"]) -> None:
    """Bind the process-wide Refinery for sync-mode callers."""
    global _QUEUE
    _QUEUE = queue


def get_refinery_queue() -> Optional["RefineryQueue"]:
    """Return the bound process-wide Refinery, or None if unset."""
    return _QUEUE


def submit_sync_or_run(
    action: str,
    payload: dict[str, Any],
    executor: Callable[[], Any],
    actor: str = "db",
) -> Any:
    """Refinery-gate ``executor`` if a queue is bound; otherwise run direct.

    The fallback path runs the executor unchanged so unit tests and CLI
    one-shots that don't initialize an app-level Refinery keep working.
    Production paths (FastAPI lifespan binds a queue) get the full
    policy + WAL + SSE pipeline.
    """
    queue = get_refinery_queue()
    if queue is None:
        return executor()
    result = queue.submit_sync(
        SyncWriteRequest(action=action, payload=payload, executor=executor, actor=actor)
    )
    if result.status == "denied":
        raise RefineryDenied(action, result.reason)
    if result.status == "escalated":
        raise RefineryEscalated(action, result.reason)
    return result.value


class RefineryDenied(RuntimeError):
    """Raised when a sync write is denied by Refinery policy / Rule-of-Two."""

    def __init__(self, action: str, reason: str) -> None:
        super().__init__(f"Refinery denied {action!r}: {reason}")
        self.action = action
        self.reason = reason


class RefineryEscalated(RuntimeError):
    """Raised when a sync write is escalated by Refinery policy.

    Sync callers can't wait for an operator decision, so escalations
    surface as exceptions. Async callers receive ``RefineryResult.status
    == 'escalated'`` instead.
    """

    def __init__(self, action: str, reason: str) -> None:
        super().__init__(f"Refinery escalated {action!r}: {reason}")
        self.action = action
        self.reason = reason
