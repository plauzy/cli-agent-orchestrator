"""A2A v1.0 streaming + REST polling endpoints.

Layered on top of the JSON-RPC endpoint. Two routes:

  * ``GET /a2a/v1/stream/{taskId}`` — Server-Sent Events stream of
    task lifecycle updates. Each event has ``event: task.update`` with
    a JSON ``data:`` payload containing the current task envelope.
    The stream stays open until the task reaches a terminal state,
    then sends a final ``event: task.terminal`` and closes.

  * ``GET /a2a/v1/tasks/{taskId}`` — REST polling fallback. Returns
    the current task envelope as plain JSON. Peers without SSE
    support poll this endpoint instead.

The stream consumes from a per-task event queue. ``TaskEventBus``
ships an in-process pub-sub primitive: callers post state transitions,
the SSE handler forwards them. A ``NullBus`` is provided for tests +
deployments where streaming isn't wired.

The bus + store + transport endpoints together form the full A2A
v1.0 server side. Authentication via the JWKS published at
``/.well-known/jwks.json`` is enforced once auth is enabled.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any, AsyncIterator, Optional, Protocol, runtime_checkable

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from cli_agent_orchestrator.a2a.store import TaskStore
from cli_agent_orchestrator.a2a.types import A2AErrorCode, TaskState

logger = logging.getLogger(__name__)


# Cap per-task subscriber queue size so a slow consumer can't OOM CAO.
# When the queue is full, oldest events are dropped — task.update is
# idempotent so a client missing an intermediate update isn't fatal as
# long as terminal-state events get through.
_DEFAULT_QUEUE_MAX = 64


# ---------------------------------------------------------------------------
# Event bus
# ---------------------------------------------------------------------------


@runtime_checkable
class TaskEventBus(Protocol):
    """Async pub-sub for task lifecycle events.

    Producers call ``publish(task_id, payload)`` whenever a task state
    transitions. Consumers (the SSE handler) call ``subscribe(task_id)``
    to get an async generator of payloads.
    """

    async def publish(self, task_id: str, payload: dict[str, Any]) -> None: ...

    def subscribe(self, task_id: str) -> AsyncIterator[dict[str, Any]]: ...


class InMemoryTaskEventBus:
    """Per-process bus. One queue per (task_id, subscriber) pair.

    Concurrency: a per-task list of subscriber queues, guarded by a
    single lock. Publish is fire-and-forget — slow subscribers drop
    old events rather than blocking the producer.
    """

    def __init__(self, *, queue_max: int = _DEFAULT_QUEUE_MAX) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._queue_max = queue_max

    async def publish(self, task_id: str, payload: dict[str, Any]) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(task_id, ()))
        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                # Drop oldest, push newest — keeps the stream alive
                # under back-pressure without blocking the producer.
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:  # pragma: no cover - vanishingly rare
                    pass

    async def subscribe(self, task_id: str) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._queue_max)
        async with self._lock:
            self._subscribers[task_id].append(queue)
        try:
            while True:
                payload = await queue.get()
                yield payload
        finally:
            async with self._lock:
                if queue in self._subscribers.get(task_id, []):
                    self._subscribers[task_id].remove(queue)
                if not self._subscribers[task_id]:
                    self._subscribers.pop(task_id, None)


class NullEventBus:
    """No-op bus for tests + deployments where streaming isn't wired."""

    async def publish(self, task_id: str, payload: dict[str, Any]) -> None:
        return None

    async def subscribe(self, task_id: str) -> AsyncIterator[dict[str, Any]]:
        # Yields nothing — the consumer's outer ``async for`` exits
        # immediately. Yields once unreachable to satisfy the
        # async-generator runtime.
        if False:  # pragma: no cover
            yield {}


# ---------------------------------------------------------------------------
# Stream + REST router
# ---------------------------------------------------------------------------


def _sse_event(event: str, payload: dict[str, Any]) -> bytes:
    """Format one Server-Sent Event frame. The blank line is the
    record terminator per the SSE spec."""
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n".encode("utf-8")


def build_stream_router(
    *,
    store: TaskStore,
    bus: Optional[TaskEventBus] = None,
    poll_initial: bool = True,
) -> APIRouter:
    """Construct a router exposing the SSE + REST polling endpoints.

    * ``store`` — resolves task ids on REST polling + sends the
      initial state on SSE connect.
    * ``bus`` — produces the SSE stream's update events. Defaults to
      ``NullEventBus`` (the stream sends only the initial state +
      terminal frame and closes).
    * ``poll_initial`` — when True (default), the SSE handler emits
      one ``task.update`` event with the current state right after
      the connect handshake. Disable for tests that want to verify
      bus-driven events in isolation.
    """
    event_bus = bus or NullEventBus()
    router = APIRouter(prefix="/a2a/v1", tags=["a2a"])

    @router.get("/tasks/{task_id}")
    async def get_task(task_id: str) -> JSONResponse:
        task = await store.get(task_id)
        if task is None:
            return JSONResponse(
                {
                    "error": {
                        "code": int(A2AErrorCode.TASK_NOT_FOUND),
                        "message": f"task {task_id!r} not found",
                    }
                },
                status_code=404,
            )
        return JSONResponse({"task": task.to_dict()})

    @router.get("/stream/{task_id}")
    async def stream(task_id: str) -> StreamingResponse:
        async def gen() -> AsyncIterator[bytes]:
            # 1. Initial state (or 404-equivalent + close).
            task = await store.get(task_id)
            if task is None:
                yield _sse_event(
                    "task.error",
                    {
                        "code": int(A2AErrorCode.TASK_NOT_FOUND),
                        "message": f"task {task_id!r} not found",
                    },
                )
                return
            if poll_initial:
                yield _sse_event("task.update", {"task": task.to_dict()})
                if TaskState.is_terminal(task.state):
                    yield _sse_event("task.terminal", {"task": task.to_dict()})
                    return

            # 2. Subscribe to bus + relay events until terminal.
            async for payload in event_bus.subscribe(task_id):
                event_name = "task.update"
                task_payload = payload.get("task")
                if isinstance(task_payload, dict) and TaskState.is_terminal(
                    task_payload.get("state", "")
                ):
                    event_name = "task.terminal"
                yield _sse_event(event_name, payload)
                if event_name == "task.terminal":
                    return

        return StreamingResponse(gen(), media_type="text/event-stream")

    # Stash the bus on the router so callers can publish events without
    # holding a separate reference.
    router.event_bus = event_bus  # type: ignore[attr-defined]
    return router
