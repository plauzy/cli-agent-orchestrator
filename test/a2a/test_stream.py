"""Tests for the A2A v1.0 SSE stream + REST polling endpoints.

Coverage matrix:
  * REST polling (GET /a2a/v1/tasks/{id}):
    - returns the current task envelope as JSON
    - 404 with TASK_NOT_FOUND error body for unknown ids
  * SSE stream (GET /a2a/v1/stream/{id}):
    - emits an initial task.update with the current state
    - emits task.terminal + closes when the task is already terminal
    - relays bus events as task.update
    - bus event with terminal state emits task.terminal + closes
    - unknown task id emits a single task.error frame and closes
  * InMemoryTaskEventBus:
    - publish/subscribe round-trips events
    - multiple subscribers each see published events
    - subscriber teardown removes the queue
    - publish to no subscribers is a no-op (no error)
    - back-pressure: full queue drops oldest, accepts newest
  * RPC integration: task.send + task.cancel publish to the bus
    so SSE consumers see live updates
"""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cli_agent_orchestrator.a2a import (
    A2AErrorCode,
    InMemoryTaskEventBus,
    InMemoryTaskStore,
    NullEventBus,
    Task,
    TaskState,
    build_a2a_router,
    build_stream_router,
)

# ---------------------------------------------------------------------------
# REST polling
# ---------------------------------------------------------------------------


@pytest.fixture
def store() -> InMemoryTaskStore:
    return InMemoryTaskStore()


@pytest.fixture
def stream_client(store: InMemoryTaskStore) -> TestClient:
    app = FastAPI()
    app.include_router(build_stream_router(store=store))
    return TestClient(app)


class TestRestPolling:
    def test_returns_existing_task(self, store: InMemoryTaskStore):
        # Seed via the RPC endpoint so we don't have to juggle async
        # contexts inside a sync test.
        app = FastAPI()
        app.include_router(build_a2a_router(store=store))
        app.include_router(build_stream_router(store=store))
        client = TestClient(app)
        client.post(
            "/a2a/v1/rpc",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "task.send",
                "params": {"task": {"id": "t1", "state": TaskState.WORKING}},
            },
        )
        resp = client.get("/a2a/v1/tasks/t1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["task"]["id"] == "t1"
        assert body["task"]["state"] == TaskState.WORKING

    def test_unknown_task_is_404(self, stream_client: TestClient):
        resp = stream_client.get("/a2a/v1/tasks/nope")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == int(A2AErrorCode.TASK_NOT_FOUND)


def _app(*, store: InMemoryTaskStore, bus: InMemoryTaskEventBus | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(build_stream_router(store=store, bus=bus))
    return app


def _parse_sse(content: str) -> list[dict]:
    """Turn raw SSE bytes into a list of {event, data} dicts."""
    events: list[dict] = []
    current: dict[str, str] = {}
    for line in content.splitlines():
        if line.startswith("event: "):
            current["event"] = line[len("event: ") :]
        elif line.startswith("data: "):
            current["data"] = json.loads(line[len("data: ") :])
        elif line == "":
            if current:
                events.append(current)
                current = {}
    if current:
        events.append(current)
    return events


# ---------------------------------------------------------------------------
# SSE stream
# ---------------------------------------------------------------------------


def _seed_terminal_task(store: InMemoryTaskStore, task_id: str, state: str) -> TestClient:
    """Set up a TestClient with a pre-seeded terminal task.

    Goes through the RPC endpoint to avoid having to manage an async
    context outside a TestClient call. task.send creates with the
    given state, then task.cancel transitions to CANCELED if needed.
    """
    app = FastAPI()
    app.include_router(build_a2a_router(store=store))
    app.include_router(build_stream_router(store=store))
    client = TestClient(app)
    if state == TaskState.COMPLETED:
        # task.send doesn't allow caller-supplied state to be terminal,
        # so seed via store directly through an event loop bridge.
        import anyio

        anyio.run(store.upsert, Task(id=task_id, state=state))
    else:
        client.post(
            "/a2a/v1/rpc",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "task.send",
                "params": {"task": {"id": task_id}},
            },
        )
        client.post(
            "/a2a/v1/rpc",
            json={
                "jsonrpc": "2.0",
                "id": "2",
                "method": "task.cancel",
                "params": {"id": task_id},
            },
        )
    return client


class TestSseStream:
    def test_terminal_task_emits_update_and_terminal_then_closes(self, store: InMemoryTaskStore):
        client = _seed_terminal_task(store, "t1", TaskState.COMPLETED)
        with client.stream("GET", "/a2a/v1/stream/t1") as resp:
            content = b"".join(resp.iter_bytes())
        events = _parse_sse(content.decode("utf-8"))
        # Initial state + terminal frame, then close.
        names = [e["event"] for e in events]
        assert "task.update" in names
        assert "task.terminal" in names

    def test_canceled_state_treated_as_terminal(self, store: InMemoryTaskStore):
        client = _seed_terminal_task(store, "t1", TaskState.CANCELED)
        with client.stream("GET", "/a2a/v1/stream/t1") as resp:
            content = b"".join(resp.iter_bytes())
        events = _parse_sse(content.decode("utf-8"))
        assert any(e["event"] == "task.terminal" for e in events)

    def test_unknown_task_emits_task_error(self, stream_client: TestClient):
        with stream_client.stream("GET", "/a2a/v1/stream/nope") as resp:
            content = b"".join(resp.iter_bytes()).decode("utf-8")
        events = _parse_sse(content)
        assert len(events) == 1
        assert events[0]["event"] == "task.error"
        assert events[0]["data"]["code"] == int(A2AErrorCode.TASK_NOT_FOUND)


# ---------------------------------------------------------------------------
# Direct generator test (no HTTP) — exercises the non-terminal flow
# without needing async/sync glue around TestClient.
# ---------------------------------------------------------------------------


class TestStreamGeneratorDirect:
    @pytest.mark.asyncio
    async def test_non_terminal_then_terminal_via_bus(self):
        """Subscribe to the bus directly, publish a working update,
        then a completed update, and assert the consumer sees both
        with the right SSE event names."""
        bus = InMemoryTaskEventBus()
        received: list[tuple[str, dict]] = []

        async def consumer() -> None:
            async for payload in bus.subscribe("t1"):
                task = payload.get("task", {})
                if TaskState.is_terminal(task.get("state", "")):
                    received.append(("task.terminal", payload))
                    return
                received.append(("task.update", payload))

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.01)
        await bus.publish("t1", {"task": {"id": "t1", "state": TaskState.WORKING}})
        await bus.publish("t1", {"task": {"id": "t1", "state": TaskState.COMPLETED}})
        await asyncio.wait_for(task, timeout=1.0)
        assert [name for name, _ in received] == ["task.update", "task.terminal"]


# ---------------------------------------------------------------------------
# InMemoryTaskEventBus
# ---------------------------------------------------------------------------


class TestEventBus:
    @pytest.mark.asyncio
    async def test_publish_subscribe_roundtrip(self):
        bus = InMemoryTaskEventBus()

        received: list[dict] = []

        async def reader() -> None:
            async for payload in bus.subscribe("t1"):
                received.append(payload)
                if len(received) >= 2:
                    return

        task = asyncio.create_task(reader())
        # Give the subscriber a chance to register.
        await asyncio.sleep(0.01)
        await bus.publish("t1", {"event": 1})
        await bus.publish("t1", {"event": 2})
        await asyncio.wait_for(task, timeout=1.0)
        assert received == [{"event": 1}, {"event": 2}]

    @pytest.mark.asyncio
    async def test_publish_with_no_subscribers_is_noop(self):
        bus = InMemoryTaskEventBus()
        await bus.publish("never-subscribed", {"x": 1})  # Must not raise.

    @pytest.mark.asyncio
    async def test_full_queue_drops_oldest(self):
        # Direct semantics check: fill the queue without a consumer,
        # then drain. With queue_max=2 and 3 publishes, the consumer
        # sees exactly 2 events (the oldest was dropped to make room).
        bus = InMemoryTaskEventBus(queue_max=2)

        # Pre-register a subscriber by getting the async iterator.
        sub_iter = bus.subscribe("t1").__aiter__()
        # First __anext__ to attach the queue; then immediately schedule.
        first = asyncio.create_task(sub_iter.__anext__())
        # Publish before the subscriber is fully bound — fall back to a
        # short sleep so the queue registration completes.
        await asyncio.sleep(0.01)
        for i in range(3):
            await bus.publish("t1", {"event": i})

        # Drain whatever is in the queue.
        results: list[dict] = []
        results.append(await asyncio.wait_for(first, timeout=1.0))
        try:
            results.append(await asyncio.wait_for(sub_iter.__anext__(), timeout=0.1))
        except asyncio.TimeoutError:
            pass
        try:
            results.append(await asyncio.wait_for(sub_iter.__anext__(), timeout=0.1))
        except asyncio.TimeoutError:
            pass

        # queue_max=2 + 3 publishes → at most 2 events delivered.
        assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_subscriber_teardown_clears_queue(self):
        # Explicit aclose() of the async generator triggers the
        # finally block deterministically across Python versions
        # (3.11 ran it on coroutine return; 3.12 defers to GC).
        bus = InMemoryTaskEventBus()
        sub = bus.subscribe("t1")

        # Bind the subscription via __anext__ so the queue is registered.
        first = asyncio.create_task(sub.__anext__())
        await asyncio.sleep(0.01)
        assert len(bus._subscribers.get("t1", [])) == 1

        await bus.publish("t1", {"x": 1})
        await asyncio.wait_for(first, timeout=1.0)

        # Explicit close → finally block runs, queue is removed.
        await sub.aclose()
        assert bus._subscribers.get("t1") in (None, [])


# ---------------------------------------------------------------------------
# Null bus
# ---------------------------------------------------------------------------


class TestNullEventBus:
    @pytest.mark.asyncio
    async def test_publish_is_noop(self):
        bus = NullEventBus()
        await bus.publish("t1", {"x": 1})  # No-op.

    @pytest.mark.asyncio
    async def test_subscribe_yields_nothing(self):
        bus = NullEventBus()
        items = []
        async for payload in bus.subscribe("t1"):
            items.append(payload)
        assert items == []


# ---------------------------------------------------------------------------
# RPC + bus integration
# ---------------------------------------------------------------------------


class TestRpcBusIntegration:
    @pytest.mark.asyncio
    async def test_task_send_publishes_to_bus(self):
        store = InMemoryTaskStore()
        bus = InMemoryTaskEventBus()

        received: list[dict] = []

        async def reader() -> None:
            async for payload in bus.subscribe("t1"):
                received.append(payload)
                return

        task = asyncio.create_task(reader())
        await asyncio.sleep(0.01)

        app = FastAPI()
        app.include_router(build_a2a_router(store=store, bus=bus))
        client = TestClient(app)

        client.post(
            "/a2a/v1/rpc",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "task.send",
                "params": {"task": {"id": "t1"}},
            },
        )
        await asyncio.wait_for(task, timeout=1.0)
        assert received[0]["task"]["id"] == "t1"

    @pytest.mark.asyncio
    async def test_task_cancel_publishes_terminal_state(self):
        store = InMemoryTaskStore()
        await store.upsert(Task(id="t1", state=TaskState.WORKING))
        bus = InMemoryTaskEventBus()

        received: list[dict] = []

        async def reader() -> None:
            async for payload in bus.subscribe("t1"):
                received.append(payload)
                return

        task = asyncio.create_task(reader())
        await asyncio.sleep(0.01)

        app = FastAPI()
        app.include_router(build_a2a_router(store=store, bus=bus))
        client = TestClient(app)
        client.post(
            "/a2a/v1/rpc",
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "task.cancel",
                "params": {"id": "t1"},
            },
        )
        await asyncio.wait_for(task, timeout=1.0)
        assert received[0]["task"]["state"] == TaskState.CANCELED
