"""Coverage for the in-memory A2A task store lifecycle helpers.

Exercises the branches in ``a2a/store.py`` that the RPC tests don't hit
directly: ``list_ids``, ``delete``, ``upsert`` timestamp assignment, and
the atomic ``transition`` guard (normal, missing task, already-terminal).
"""

from __future__ import annotations

import pytest

from cli_agent_orchestrator.a2a.store import InMemoryTaskStore
from cli_agent_orchestrator.a2a.types import Task, TaskState


@pytest.mark.asyncio
async def test_upsert_sets_created_and_updated_at() -> None:
    store = InMemoryTaskStore()
    task = Task(id="t1")
    assert task.created_at is None
    await store.upsert(task)
    fetched = await store.get("t1")
    assert fetched is not None
    assert fetched.created_at is not None
    assert fetched.updated_at is not None
    first_created = fetched.created_at

    # Re-upsert preserves created_at, refreshes updated_at.
    await store.upsert(task)
    again = await store.get("t1")
    assert again is not None
    assert again.created_at == first_created


@pytest.mark.asyncio
async def test_list_ids_and_delete() -> None:
    store = InMemoryTaskStore()
    await store.upsert(Task(id="a"))
    await store.upsert(Task(id="b"))
    ids = await store.list_ids()
    assert set(ids) == {"a", "b"}

    await store.delete("a")
    assert await store.get("a") is None
    # Deleting a missing id is a no-op.
    await store.delete("does-not-exist")
    assert set(await store.list_ids()) == {"b"}


@pytest.mark.asyncio
async def test_transition_normal() -> None:
    store = InMemoryTaskStore()
    await store.upsert(Task(id="t", state=TaskState.SUBMITTED))
    updated = await store.transition("t", TaskState.WORKING)
    assert updated is not None
    assert updated.state == TaskState.WORKING
    assert updated.updated_at is not None


@pytest.mark.asyncio
async def test_transition_missing_returns_none() -> None:
    store = InMemoryTaskStore()
    assert await store.transition("nope", TaskState.WORKING) is None


@pytest.mark.asyncio
async def test_transition_terminal_is_rejected() -> None:
    store = InMemoryTaskStore()
    await store.upsert(Task(id="done", state=TaskState.COMPLETED))
    # Already terminal → transition refuses and returns None.
    assert await store.transition("done", TaskState.WORKING) is None
    unchanged = await store.get("done")
    assert unchanged is not None
    assert unchanged.state == TaskState.COMPLETED
