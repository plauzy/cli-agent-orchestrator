"""Task store for A2A v1.0 endpoints.

The A2A spec mandates a task lifecycle: peers ``send`` a task, ``get``
its current state, and ``cancel`` it before it terminates. The lifecycle
requires a store that survives at least the lifetime of one HTTP request
→ next.

This module ships an in-memory store as the default backend. A SQLite
or libsql-backed store would be a drop-in replacement (the ``TaskStore``
Protocol is the seam) but is deferred — A2A peers typically poll on
short timeframes.

Bounds: the in-memory store is capped (``max_tasks``, default 1000,
``CAO_A2A_MAX_TASKS``) and time-windowed (``ttl_seconds``, default 3600,
``CAO_A2A_TASK_TTL``). Tasks idle past the TTL are lazily swept on access;
on overflow the oldest *terminal* tasks are evicted first, and when every
stored task is still live a new insert raises ``TaskLimitExceeded`` (the
RPC layer maps it to ``TASK_LIMIT_EXCEEDED``) instead of growing without
bound — a network-reachable ``task.send`` must never be a remote
memory-exhaustion vector.

Concurrency: ``InMemoryTaskStore`` uses an ``asyncio.Lock`` because
the A2A endpoints are async. Sync callers should not share an
instance across threads without external synchronization.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Optional, Protocol, runtime_checkable

from cli_agent_orchestrator.a2a.types import Task, TaskState

DEFAULT_MAX_TASKS = 1000
DEFAULT_TTL_SECONDS = 3600.0


class TaskLimitExceeded(Exception):
    """The store is at capacity with live (non-terminal) tasks only."""


@runtime_checkable
class TaskStore(Protocol):
    """Async storage contract for A2A tasks."""

    async def get(self, task_id: str) -> Optional[Task]: ...

    async def upsert(self, task: Task) -> None: ...

    async def delete(self, task_id: str) -> None: ...


class InMemoryTaskStore:
    """Default in-memory store. One instance per CAO process.

    Bounded by ``max_tasks`` + ``ttl_seconds`` (see module docstring);
    peers that track their own task ids should poll within the TTL.
    """

    def __init__(
        self,
        max_tasks: int = DEFAULT_MAX_TASKS,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.max_tasks = max_tasks
        self.ttl_seconds = ttl_seconds
        self._tasks: dict[str, Task] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def from_env(cls) -> "InMemoryTaskStore":
        """Build a store with ``CAO_A2A_MAX_TASKS`` / ``CAO_A2A_TASK_TTL`` applied."""
        return cls(
            max_tasks=int(os.environ.get("CAO_A2A_MAX_TASKS", str(DEFAULT_MAX_TASKS))),
            ttl_seconds=float(os.environ.get("CAO_A2A_TASK_TTL", str(DEFAULT_TTL_SECONDS))),
        )

    def _sweep_locked(self, now: float) -> None:
        """Drop tasks idle past the TTL. Caller holds the lock."""
        if self.ttl_seconds <= 0:
            return
        cutoff = now - self.ttl_seconds
        stale = [
            task_id
            for task_id, task in self._tasks.items()
            if (task.updated_at or task.created_at or now) < cutoff
        ]
        for task_id in stale:
            del self._tasks[task_id]

    def _evict_for_capacity_locked(self) -> None:
        """Make room for one insert. Caller holds the lock.

        Oldest terminal tasks go first (their lifecycle is finished; peers
        re-polling them would see TASK_NOT_FOUND, same as after a TTL sweep).
        Live tasks are never dropped — when the store is full of them the
        insert is refused instead.
        """
        while len(self._tasks) >= self.max_tasks:
            terminal = [
                (task.updated_at or task.created_at or 0.0, task_id)
                for task_id, task in self._tasks.items()
                if TaskState.is_terminal(task.state)
            ]
            if not terminal:
                raise TaskLimitExceeded(
                    f"store holds {len(self._tasks)} live tasks (max_tasks={self.max_tasks})"
                )
            _, oldest_id = min(terminal)
            del self._tasks[oldest_id]

    async def get(self, task_id: str) -> Optional[Task]:
        async with self._lock:
            self._sweep_locked(time.time())
            return self._tasks.get(task_id)

    async def upsert(self, task: Task) -> None:
        async with self._lock:
            now = time.time()
            self._sweep_locked(now)
            if task.id not in self._tasks:
                self._evict_for_capacity_locked()
            if task.created_at is None:
                task.created_at = now
            task.updated_at = now
            self._tasks[task.id] = task

    async def delete(self, task_id: str) -> None:
        async with self._lock:
            self._tasks.pop(task_id, None)

    async def list_ids(self) -> list[str]:
        async with self._lock:
            self._sweep_locked(time.time())
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
