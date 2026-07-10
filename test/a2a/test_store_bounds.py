"""InMemoryTaskStore bounds — the second blocking finding from the #387 review.

The store was an unbounded dict ("tasks live until explicitly deleted or
process restart"), which combined with a network-reachable ``task.send``
meant a remote peer could drive unbounded memory growth. The store is now
bounded two ways, both env-tunable:

* ``max_tasks`` (``CAO_A2A_MAX_TASKS``, default 1000) — on overflow the
  oldest *terminal* tasks are evicted first; if every stored task is still
  live, new inserts are refused (``TaskStoreFull`` → the RPC layer maps it to
  ``RESOURCE_EXHAUSTED`` at HTTP 429 + Retry-After) rather than silently
  dropping active work.
* ``ttl_seconds`` (``CAO_A2A_TASK_TTL``, default 3600) — tasks idle past the
  TTL are lazily swept on access.
"""

from __future__ import annotations

import pytest

from cli_agent_orchestrator.a2a import A2AErrorCode, InMemoryTaskStore, build_a2a_router
from cli_agent_orchestrator.a2a.store import TaskStoreFull
from cli_agent_orchestrator.a2a.types import Task, TaskState


def _task(task_id: str, state: str = TaskState.SUBMITTED) -> Task:
    return Task(id=task_id, state=state)


@pytest.mark.asyncio
class TestCapacity:
    async def test_evicts_oldest_terminal_first_on_overflow(self):
        store = InMemoryTaskStore(max_tasks=3)
        await store.upsert(_task("t1", TaskState.COMPLETED))
        await store.upsert(_task("t2", TaskState.SUBMITTED))
        await store.upsert(_task("t3", TaskState.CANCELED))

        await store.upsert(_task("t4"))  # over capacity → evict t1 (oldest terminal)
        assert await store.get("t1") is None
        assert await store.get("t2") is not None
        assert await store.get("t3") is not None
        assert await store.get("t4") is not None

    async def test_refuses_new_tasks_when_full_of_live_work(self):
        store = InMemoryTaskStore(max_tasks=2)
        await store.upsert(_task("t1"))
        await store.upsert(_task("t2"))
        with pytest.raises(TaskStoreFull):
            await store.upsert(_task("t3"))
        # Existing live tasks were not dropped.
        assert await store.get("t1") is not None
        assert await store.get("t2") is not None

    async def test_updating_an_existing_task_never_hits_the_cap(self):
        store = InMemoryTaskStore(max_tasks=1)
        await store.upsert(_task("t1"))
        updated = _task("t1", TaskState.WORKING)
        await store.upsert(updated)  # same id: update in place, no capacity check
        stored = await store.get("t1")
        assert stored is not None and stored.state == TaskState.WORKING


@pytest.mark.asyncio
class TestTTL:
    async def test_idle_tasks_are_swept_after_ttl(self, monkeypatch):
        store = InMemoryTaskStore(max_tasks=10, ttl_seconds=100)
        await store.upsert(_task("old"))
        # Age the task past the TTL by rewinding its updated_at.
        async with store._lock:  # test-only reach-in; the sweep is lazy-on-access
            store._tasks["old"].updated_at -= 101

        assert await store.get("old") is None
        assert await store.list_ids() == []

    async def test_fresh_tasks_survive_the_sweep(self):
        store = InMemoryTaskStore(max_tasks=10, ttl_seconds=100)
        await store.upsert(_task("fresh"))
        assert await store.get("fresh") is not None


class TestEnvConfig:
    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("CAO_A2A_MAX_TASKS", "7")
        monkeypatch.setenv("CAO_A2A_TASK_TTL", "42.5")
        store = InMemoryTaskStore.from_env()
        assert store.max_tasks == 7
        assert store.ttl_seconds == 42.5

    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("CAO_A2A_MAX_TASKS", raising=False)
        monkeypatch.delenv("CAO_A2A_TASK_TTL", raising=False)
        store = InMemoryTaskStore.from_env()
        assert store.max_tasks == 1000
        assert store.ttl_seconds == 3600.0


class TestRpcMapping:
    def test_task_send_when_full_returns_task_limit_exceeded(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        store = InMemoryTaskStore(max_tasks=1)
        app = FastAPI()
        app.include_router(build_a2a_router(store=store))
        client = TestClient(app)

        def send(task_id: str):
            return client.post(
                "/a2a/v1/rpc",
                json={
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "task.send",
                    "params": {"task": {"id": task_id, "messages": []}},
                },
            )

        assert send("t1").status_code == 200
        resp = send("t2")
        # Capacity refusal is a transport/backoff condition: HTTP 429 with a
        # Retry-After hint (so HTTP-native retry middleware backs off), plus
        # the JSON-RPC error body for clients that ignore transport status.
        assert resp.status_code == 429
        assert resp.headers.get("Retry-After") == "30"
        assert resp.json()["error"]["code"] == int(A2AErrorCode.RESOURCE_EXHAUSTED)
