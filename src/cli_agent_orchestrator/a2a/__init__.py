"""A2A v1.0 transport endpoints.

Layered on top of the Agent Card listener (`:9890`). Implements the
JSON-RPC 2.0 RPC method surface (`task.send`, `task.get`, `task.cancel`)
alongside SSE streaming and a REST polling fallback.
"""

from cli_agent_orchestrator.a2a.rpc import TaskExecutor, build_a2a_router
from cli_agent_orchestrator.a2a.store import InMemoryTaskStore, TaskStore, TaskStoreFull
from cli_agent_orchestrator.a2a.stream import (
    InMemoryTaskEventBus,
    NullEventBus,
    TaskEventBus,
    build_stream_router,
)
from cli_agent_orchestrator.a2a.types import (
    A2AErrorCode,
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
    Task,
    TaskState,
)

__all__ = [
    "A2AErrorCode",
    "InMemoryTaskEventBus",
    "InMemoryTaskStore",
    "JsonRpcError",
    "JsonRpcRequest",
    "JsonRpcResponse",
    "NullEventBus",
    "Task",
    "TaskEventBus",
    "TaskExecutor",
    "TaskState",
    "TaskStore",
    "TaskStoreFull",
    "build_a2a_router",
    "build_stream_router",
]
