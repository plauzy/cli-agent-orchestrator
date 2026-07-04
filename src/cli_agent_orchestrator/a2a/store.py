"""Task store for A2A v1.0 endpoints.

The A2A spec mandates a task lifecycle: peers ``send`` a task, ``get``
its current state, and ``cancel`` it before it terminates. The lifecycle
requires a store that survives at least the lifetime of one HTTP request
→ next.

This module ships an in-memory store as the default backend. A SQLite
or libsql-backed store would be a drop-in replacement (the ``TaskStore``
Protocol is the seam) but is deferred — A2A peers typically poll on
short timeframes.

Concurrency: ``InMemoryTaskStore`` uses an ``asyncio.Lock`` because
the A2A endpoints are async. Sync callers should not share an
instance across threads without external synchronization.
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional, Protocol, runtime_checkable

from cli_agent_orchestrator.a2a.types import Task, TaskState


@runtime_checkable
class TaskStore(Protocol):
    """Async storage contract for A2A tasks."""

    async def get(self, task_id: str) -> Optional[Task]: ...

    async def upsert(self, task: Task) -> None: ...

    async def delete(self, task_id: str) -> None: ...


class InMemoryTaskStore:
    """Default in-memory store. One instance per CAO process.

    Tasks live until either explicitly deleted or until the process
    restarts. This is fine for typical A2A usage where peers track
    their own task ids and prune by themselves.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = asyncio.Lock()

    async def get(self, task_id: str) -> Optional[Task]:
        async with self._lock:
            return self._tasks.get(task_id)

    async def upsert(self, task: Task) -> None:
        async with self._lock:
            now = time.time()
            if task.created_at is None:
                task.created_at = now
            task.updated_at = now
            self._tasks[task.id] = task

    async def delete(self, task_id: str) -> None:
        async with self._lock:
            self._tasks.pop(task_id, None)

    async def list_ids(self) -> list[str]:
        async with self._lock:
            return list(self._tasks.keys())

    async def transition(self, task_id: str, new_state: str) -> Optional[Task]:
        """Atomic state transition. Returns the updated task, or
        ``None`` if the task didn't exist or was already terminal."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None or TaskState.is_terminal(task.state):
                return None
            task.state = new_state
            task.updated_at = time.time()
            return task
