"""A2A v1.0 JSON-RPC 2.0 endpoint.

Mounted on the Agent Card listener (:9890) so external A2A peers discover
and call CAO over the same boundary. The listener is otherwise read-only
(Agent Card + JWKS); this adds ``POST /a2a/v1/rpc`` for JSON-RPC 2.0 task
operations.

Methods:

  * ``task.send`` — peer submits a task. CAO assigns it the
    ``submitted`` state and returns the task envelope. Subsequent
    work transitions through ``working`` → terminal state. Binding
    accepted tasks to CAO's internal task dispatch is a follow-up;
    this ships the protocol surface only.

  * ``task.get`` — peer polls the current state of a previously sent
    task. Returns the full envelope including state + messages +
    artifacts.

  * ``task.cancel`` — peer requests cancellation. CAO transitions
    the task to ``canceled`` if it isn't terminal yet; otherwise
    returns ``TASK_ALREADY_TERMINAL``.

Authentication is enforced via the JWKS published at
``/.well-known/jwks.json`` once auth is enabled.

Per the JSON-RPC 2.0 spec:
  * Parse errors return id=null with code -32700.
  * Invalid request shapes return whatever id we managed to parse
    (or null) with code -32600.
  * Unknown methods return code -32601.
  * Application errors (task not found, etc.) use the A2A-specific
    positive codes from ``A2AErrorCode``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Awaitable, Callable, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from cli_agent_orchestrator.a2a.store import InMemoryTaskStore, TaskStore
from cli_agent_orchestrator.a2a.stream import NullEventBus, TaskEventBus
from cli_agent_orchestrator.a2a.types import (
    A2AErrorCode,
    JsonRpcError,
    JsonRpcId,
    JsonRpcRequest,
    JsonRpcResponse,
    Task,
    TaskState,
)

logger = logging.getLogger(__name__)


# A peer-supplied task → final-state task. The executor is responsible
# for running the work and returning the task with its terminal state
# set. Errors should not raise — the framework catches them and
# transitions to FAILED. The executor receives the *submitted* task
# and may mutate the messages / artifacts / metadata fields freely.
TaskExecutor = Callable[[Task], Awaitable[Task]]


# ---------------------------------------------------------------------------
# Method handlers
# ---------------------------------------------------------------------------


async def _run_task_in_background(
    task: Task,
    executor: TaskExecutor,
    store: TaskStore,
    bus: TaskEventBus,
) -> None:
    """Run the executor and publish state transitions to the bus.

    Always finishes with the task in a terminal state — COMPLETED if
    the executor returned cleanly, FAILED if it raised. Callers
    register this via ``asyncio.create_task`` so the HTTP response
    for ``task.send`` returns immediately with state=WORKING.
    """
    # Transition submitted → working before invoking the executor so
    # SSE consumers see the work start.
    task.state = TaskState.WORKING
    task.updated_at = time.time()
    await store.upsert(task)
    await bus.publish(task.id, {"task": task.to_dict()})
    try:
        result = await executor(task)
        # Honor whatever terminal state the executor set; default to
        # COMPLETED if the executor returned without setting one.
        if not TaskState.is_terminal(result.state):
            result.state = TaskState.COMPLETED
        result.updated_at = time.time()
        await store.upsert(result)
        await bus.publish(result.id, {"task": result.to_dict()})
    except Exception as exc:
        logger.warning("A2A task executor failed for id=%s", task.id, exc_info=True)
        task.state = TaskState.FAILED
        task.updated_at = time.time()
        # Surface the error in metadata so the peer can see why.
        task.metadata = {**task.metadata, "error": str(exc)}
        await store.upsert(task)
        await bus.publish(task.id, {"task": task.to_dict()})


async def _handle_task_send(
    store: TaskStore,
    bus: TaskEventBus,
    params: dict[str, Any],
    executor: Optional[TaskExecutor] = None,
) -> dict[str, Any]:
    """Accept a new task. Generates an id if the peer didn't provide one.

    When an ``executor`` is registered on the router, the task is
    scheduled in a background asyncio task — the HTTP response returns
    immediately with state=SUBMITTED, the SSE stream sees
    SUBMITTED → WORKING → terminal. Without an executor, the task
    stays in SUBMITTED until a peer or operator transitions it
    explicitly.
    """
    task_payload = params.get("task")
    if not isinstance(task_payload, dict):
        raise _invalid_params("'task' must be an object")

    task = Task.from_dict(task_payload)
    if not task.id:
        task.id = str(uuid.uuid4())
    if not task.state:
        task.state = TaskState.SUBMITTED
    if task.created_at is None:
        task.created_at = time.time()
    await store.upsert(task)
    await bus.publish(task.id, {"task": task.to_dict()})

    if executor is not None:
        # Fire-and-forget. The background task handles state
        # transitions + bus publishing; this handler returns quickly
        # so the peer isn't blocked on a long-running execution.
        asyncio.create_task(
            _run_task_in_background(task, executor, store, bus),
            name=f"a2a-task-{task.id}",
        )

    return {"task": task.to_dict()}


async def _handle_task_get(
    store: TaskStore, bus: TaskEventBus, params: dict[str, Any]
) -> dict[str, Any]:
    task_id = params.get("id") or params.get("taskId")
    if not isinstance(task_id, str) or not task_id:
        raise _invalid_params("'id' must be a non-empty string")
    task = await store.get(task_id)
    if task is None:
        raise _app_error(A2AErrorCode.TASK_NOT_FOUND, f"task {task_id!r} not found")
    return {"task": task.to_dict()}


async def _handle_task_cancel(
    store: TaskStore, bus: TaskEventBus, params: dict[str, Any]
) -> dict[str, Any]:
    task_id = params.get("id") or params.get("taskId")
    if not isinstance(task_id, str) or not task_id:
        raise _invalid_params("'id' must be a non-empty string")
    task = await store.get(task_id)
    if task is None:
        raise _app_error(A2AErrorCode.TASK_NOT_FOUND, f"task {task_id!r} not found")
    if TaskState.is_terminal(task.state):
        raise _app_error(
            A2AErrorCode.TASK_ALREADY_TERMINAL,
            f"task {task_id!r} is already {task.state}; cannot cancel",
        )
    task.state = TaskState.CANCELED
    task.updated_at = time.time()
    await store.upsert(task)
    await bus.publish(task.id, {"task": task.to_dict()})
    return {"task": task.to_dict()}


_METHODS: dict[
    str,
    Callable[
        [TaskStore, TaskEventBus, dict[str, Any], Optional[TaskExecutor]],
        Awaitable[dict[str, Any]],
    ],
] = {
    "task.send": _handle_task_send,
    # task.get / task.cancel ignore the executor — they're synchronous
    # state queries, not work dispatchers. Wrappers below.
    "task.get": lambda store, bus, params, _exec: _handle_task_get(store, bus, params),
    "task.cancel": lambda store, bus, params, _exec: _handle_task_cancel(store, bus, params),
}


# ---------------------------------------------------------------------------
# Error helpers
# ---------------------------------------------------------------------------


class _RpcException(Exception):
    """Raised by handlers to signal a JSON-RPC error response."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def _invalid_params(message: str) -> _RpcException:
    return _RpcException(int(A2AErrorCode.INVALID_PARAMS), message)


def _app_error(code: A2AErrorCode, message: str) -> _RpcException:
    return _RpcException(int(code), message)


def _error_response(req_id: JsonRpcId, code: int, message: str, data: Any = None) -> dict[str, Any]:
    return JsonRpcResponse(
        id=req_id, error=JsonRpcError(code=code, message=message, data=data)
    ).to_dict()


def _success_response(req_id: JsonRpcId, result: Any) -> dict[str, Any]:
    return JsonRpcResponse(id=req_id, result=result).to_dict()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def build_a2a_router(
    store: TaskStore | None = None,
    *,
    bus: TaskEventBus | None = None,
    executor: Optional[TaskExecutor] = None,
) -> APIRouter:
    """Construct an APIRouter that mounts the A2A v1.0 JSON-RPC endpoint.

    * ``store`` — task persistence. Defaults to an in-process
      ``InMemoryTaskStore``. Operators who want durable A2A task state
      can implement the ``TaskStore`` Protocol against their own
      backend (libsql, postgres, etc.) and pass it in.
    * ``bus`` — event bus that the SSE stream endpoint consumes
      from. RPC handlers publish state transitions on this
      bus so SSE subscribers see live updates. Defaults to
      ``NullEventBus`` (no streaming).
    * ``executor`` — async callable invoked when a peer ``task.send``s
      a new task. Receives the task with state=SUBMITTED, returns
      it with state set to a terminal value. Without an executor,
      tasks are stored but never dispatched — useful for testing
      the protocol surface in isolation. The CAO production wiring
      passes an executor that bridges to ``dispatch_task``.
    """
    task_store = store or InMemoryTaskStore()
    event_bus = bus or NullEventBus()
    router = APIRouter(prefix="/a2a/v1", tags=["a2a"])

    @router.post("/rpc")
    async def rpc(request: Request) -> JSONResponse:
        # Body parse — bare 400 with id=null per JSON-RPC 2.0 §5.
        try:
            raw = await request.body()
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError as exc:
            return JSONResponse(
                _error_response(None, int(A2AErrorCode.PARSE_ERROR), str(exc)),
                status_code=400,
            )

        # Single request only — batch support is a future commit.
        if not isinstance(payload, dict):
            return JSONResponse(
                _error_response(
                    None,
                    int(A2AErrorCode.INVALID_REQUEST),
                    "request body must be a JSON object",
                ),
                status_code=400,
            )

        req = JsonRpcRequest.from_dict(payload)
        if req.jsonrpc != "2.0":
            return JSONResponse(
                _error_response(
                    req.id,
                    int(A2AErrorCode.INVALID_REQUEST),
                    "jsonrpc must be '2.0'",
                ),
                status_code=400,
            )
        if not req.method:
            return JSONResponse(
                _error_response(
                    req.id,
                    int(A2AErrorCode.INVALID_REQUEST),
                    "method is required",
                ),
                status_code=400,
            )

        handler = _METHODS.get(req.method)
        if handler is None:
            return JSONResponse(
                _error_response(
                    req.id,
                    int(A2AErrorCode.METHOD_NOT_FOUND),
                    f"unknown method {req.method!r}",
                ),
                status_code=404,
            )

        try:
            result = await handler(task_store, event_bus, req.params, executor)
            return JSONResponse(_success_response(req.id, result))
        except _RpcException as exc:
            # Application-level errors are still 200 OK per JSON-RPC.
            return JSONResponse(_error_response(req.id, exc.code, exc.message, exc.data))
        except Exception as exc:  # pragma: no cover - defensive, internal bug
            logger.exception("A2A RPC handler crashed: method=%s", req.method)
            return JSONResponse(
                _error_response(
                    req.id,
                    int(A2AErrorCode.INTERNAL_ERROR),
                    f"internal error: {exc}",
                ),
                status_code=500,
            )

    # Stash the store + bus on the router for tests + downstream wiring.
    router.task_store = task_store  # type: ignore[attr-defined]
    router.event_bus = event_bus  # type: ignore[attr-defined]
    return router
