"""Coverage for the A2A streaming/REST router + event bus back-pressure.

Targets ``a2a/stream.py`` branches: the REST 404 + hit paths, the SSE
``task.error`` (missing task) and ``task.terminal`` (already-terminal on
connect) frames, the ``InMemoryTaskEventBus`` drop-oldest behaviour when a
slow subscriber's queue is full, and the ``NullEventBus`` no-op.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cli_agent_orchestrator.a2a.store import InMemoryTaskStore
from cli_agent_orchestrator.a2a.stream import (
    InMemoryTaskEventBus,
    NullEventBus,
    build_stream_router,
)
from cli_agent_orchestrator.a2a.types import Task, TaskState


def _app_with(store: InMemoryTaskStore, **kwargs) -> TestClient:
    app = FastAPI()
    app.include_router(build_stream_router(store=store, **kwargs))
    return TestClient(app)


@pytest.mark.asyncio
async def test_rest_poll_found_and_missing() -> None:
    store = InMemoryTaskStore()
    await store.upsert(Task(id="present", state=TaskState.WORKING))
    client = _app_with(store)

    ok = client.get("/a2a/v1/tasks/present")
    assert ok.status_code == 200
    assert ok.json()["task"]["id"] == "present"

    missing = client.get("/a2a/v1/tasks/absent")
    assert missing.status_code == 404
    assert missing.json()["error"]["message"].startswith("task 'absent'")


@pytest.mark.asyncio
async def test_stream_missing_task_emits_error_frame() -> None:
    store = InMemoryTaskStore()
    client = _app_with(store)
    body = client.get("/a2a/v1/stream/ghost").text
    assert "event: task.error" in body
    assert "not found" in body


@pytest.mark.asyncio
async def test_stream_terminal_task_emits_update_then_terminal() -> None:
    store = InMemoryTaskStore()
    await store.upsert(Task(id="done", state=TaskState.COMPLETED))
    client = _app_with(store)
    body = client.get("/a2a/v1/stream/done").text
    assert "event: task.update" in body
    assert "event: task.terminal" in body


@pytest.mark.asyncio
async def test_event_bus_drops_oldest_when_subscriber_queue_full() -> None:
    bus = InMemoryTaskEventBus(queue_max=1)
    # Register a full subscriber queue directly so publish must evict.
    q: asyncio.Queue = asyncio.Queue(maxsize=1)
    q.put_nowait({"seq": 0})
    bus._subscribers["t"].append(q)

    await bus.publish("t", {"seq": 1})

    # Oldest ({"seq": 0}) was dropped; newest survives.
    assert q.get_nowait() == {"seq": 1}
    assert q.empty()


@pytest.mark.asyncio
async def test_event_bus_publish_to_no_subscribers_is_noop() -> None:
    bus = InMemoryTaskEventBus()
    await bus.publish("nobody", {"x": 1})  # should not raise


@pytest.mark.asyncio
async def test_null_event_bus_publish_and_subscribe() -> None:
    bus = NullEventBus()
    await bus.publish("t", {"x": 1})  # no-op
    seen = [payload async for payload in bus.subscribe("t")]
    assert seen == []
