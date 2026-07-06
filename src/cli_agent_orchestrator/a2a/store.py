"""Task store for A2A v1.0 endpoints.

The A2A spec mandates a task lifecycle: peers ``send`` a task, ``get``
its current state, and ``cancel`` it before it terminates. The lifecycle
requires a store that survives at least the lifetime of one HTTP request
→ next.

This module ships an in-memory store as the default backend. A SQLite
or libsql-backed store would be a drop-in replacement (the ``TaskStore``
Protocol is the seam) but is deferred — A2A peers typically poll on
short timeframes.

**Bounded by construction.** The store is capped (``max_tasks``) and
TTL-evicting (``ttl_seconds``) so a peer that submits tasks faster than it
prunes them cannot drive unbounded memory growth. Both are env-tunable
(``CAO_A2A_MAX_TASKS`` / ``CAO_A2A_TASK_TTL``). On overflow the oldest
*terminal* task is evicted first (its lifecycle is done); if every slot is a
live, non-terminal task, a new ``task.send`` is refused with
``RESOURCE_EXHAUSTED`` rather than evicting in-flight work or growing without
limit. This bound is what makes the A2A surface safe to expose to an
authenticated remote peer.

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

# Defaults when neither the constructor arg nor the env var is set.
_DEFAULT_MAX_TASKS = 1000
_DEFAULT_TTL_SECONDS = 3600.0


class TaskStoreFull(Exception):
    """Raised by ``upsert`` when a *new* task cannot be stored because the
    store is at capacity and holds no evictable (terminal) task.

    The RPC layer maps this to an ``A2AErrorCode.RESOURCE_EXHAUSTED`` JSON-RPC
    error (HTTP 429) so a peer flooding ``task.send`` gets a clean, bounded
    rejection instead of driving the process out of memory.
    """


@runtime_checkable
class TaskStore(Protocol):
    """Async storage contract for A2A tasks."""

    async def get(self, task_id: str) -> Optional[Task]: ...

    async def upsert(self, task: Task) -> None: ...

    async def delete(self, task_id: str) -> None: ...


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class InMemoryTaskStore:
    """Default in-memory store. One instance per CAO process.

    Bounded and TTL-evicting (see the module docstring). Insertion order is
    preserved (``dict`` is ordered on 3.7+), so "oldest" for eviction/sweep
    purposes is iteration order.

    Args:
        max_tasks: hard cap on stored tasks. ``<= 0`` disables the cap.
            Defaults to ``CAO_A2A_MAX_TASKS`` env or ``1000``.
        ttl_seconds: entries whose ``updated_at`` is older than this are
            swept lazily on access. ``<= 0`` disables TTL eviction.
            Defaults to ``CAO_A2A_TASK_TTL`` env or ``3600``.
    """

    def __init__(
        self,
        *,
        max_tasks: Optional[int] = None,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = asyncio.Lock()
        self._max_tasks = (
            max_tasks
            if max_tasks is not None
            else _env_int("CAO_A2A_MAX_TASKS", _DEFAULT_MAX_TASKS)
        )
        self._ttl_seconds = (
            ttl_seconds
            if ttl_seconds is not None
            else _env_float("CAO_A2A_TASK_TTL", _DEFAULT_TTL_SECONDS)
        )

    # -- internal helpers (call under self._lock) --------------------------

    def _sweep_expired_locked(self, now: float) -> None:
        """Drop entries past their TTL. No-op when TTL disabled."""
        if self._ttl_seconds <= 0:
            return
        expired = [
            tid
            for tid, t in self._tasks.items()
            if t.updated_at is not None and (now - t.updated_at) > self._ttl_seconds
        ]
        for tid in expired:
            del self._tasks[tid]

    def _evict_one_terminal_locked(self) -> bool:
        """Evict the oldest terminal task. Returns True if one was evicted."""
        for tid, t in self._tasks.items():
            if TaskState.is_terminal(t.state):
                del self._tasks[tid]
                return True
        return False

    # -- public API --------------------------------------------------------

    async def get(self, task_id: str) -> Optional[Task]:
        async with self._lock:
            self._sweep_expired_locked(time.time())
            return self._tasks.get(task_id)

    async def upsert(self, task: Task) -> None:
        async with self._lock:
            now = time.time()
            self._sweep_expired_locked(now)
            is_new = task.id not in self._tasks
            if is_new and self._max_tasks > 0 and len(self._tasks) >= self._max_tasks:
                # At capacity for a brand-new task: reclaim a finished one
                # first; if everything in the store is still in-flight, refuse
                # rather than evict live work or grow unbounded.
                if not self._evict_one_terminal_locked():
                    raise TaskStoreFull(
                        f"task store is full ({self._max_tasks} tasks, all non-terminal); "
                        "cannot accept a new task"
                    )
            if task.created_at is None:
                task.created_at = now
            task.updated_at = now
            self._tasks[task.id] = task

    async def delete(self, task_id: str) -> None:
        async with self._lock:
            self._tasks.pop(task_id, None)

    async def list_ids(self) -> list[str]:
        async with self._lock:
            self._sweep_expired_locked(time.time())
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
