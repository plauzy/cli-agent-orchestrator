"""Tests for the Phase 5 A2A v1.0 JSON-RPC endpoint (commit 26).

Coverage matrix:
  * task.send: assigns id when missing; round-trips messages + metadata;
    starts in ``submitted`` state
  * task.get: returns the task envelope; ``TASK_NOT_FOUND`` when missing
  * task.cancel: transitions non-terminal tasks; ``TASK_ALREADY_TERMINAL``
    on already-canceled / completed tasks
  * Protocol errors:
    - parse error → -32700, id=null, 400 status
    - non-object body → -32600
    - missing method → -32600
    - unknown method → -32601, 404 status
    - wrong jsonrpc version → -32600
  * Application errors: TASK_NOT_FOUND (1) is returned as 200 OK with
    error in body, per JSON-RPC 2.0
  * Round-trip: a peer's ``extra`` fields on Task survive send → get
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cli_agent_orchestrator.a2a import (
    A2AErrorCode,
    InMemoryTaskStore,
    TaskState,
    build_a2a_router,
)


@pytest.fixture
def store() -> InMemoryTaskStore:
    return InMemoryTaskStore()


@pytest.fixture
def client(store: InMemoryTaskStore) -> TestClient:
    app = FastAPI()
    app.include_router(build_a2a_router(store=store))
    return TestClient(app)


def _rpc(method: str, params: dict, *, req_id: str | int | None = "1") -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}


# ---------------------------------------------------------------------------
# task.send
# ---------------------------------------------------------------------------


class TestTaskSend:
    def test_assigns_id_when_missing(self, client: TestClient):
        resp = client.post(
            "/a2a/v1/rpc",
            json=_rpc(
                "task.send", {"task": {"id": "", "messages": [{"role": "user", "content": "hi"}]}}
            ),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "1"
        assert "error" not in body
        task = body["result"]["task"]
        assert task["id"]  # Auto-generated.
        assert task["state"] == TaskState.SUBMITTED
        assert task["messages"] == [{"role": "user", "content": "hi"}]

    def test_preserves_caller_supplied_id(self, client: TestClient):
        resp = client.post(
            "/a2a/v1/rpc",
            json=_rpc("task.send", {"task": {"id": "task-abc", "messages": []}}),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"]["task"]["id"] == "task-abc"

    def test_default_state_is_submitted(self, client: TestClient):
        resp = client.post(
            "/a2a/v1/rpc",
            json=_rpc("task.send", {"task": {"id": "t1"}}),
        )
        assert resp.json()["result"]["task"]["state"] == TaskState.SUBMITTED

    def test_metadata_round_trips(self, client: TestClient):
        resp = client.post(
            "/a2a/v1/rpc",
            json=_rpc(
                "task.send",
                {"task": {"id": "t1", "metadata": {"priority": "high", "tenant": "x"}}},
            ),
        )
        assert resp.json()["result"]["task"]["metadata"] == {"priority": "high", "tenant": "x"}

    def test_extra_fields_round_trip(self, client: TestClient):
        # A2A peers may send fields CAO doesn't recognize. They should
        # round-trip on get.
        resp = client.post(
            "/a2a/v1/rpc",
            json=_rpc(
                "task.send",
                {"task": {"id": "t1", "customField": "preserved"}},
            ),
        )
        assert resp.json()["result"]["task"]["customField"] == "preserved"

    def test_missing_task_field_is_invalid_params(self, client: TestClient):
        resp = client.post("/a2a/v1/rpc", json=_rpc("task.send", {}))
        body = resp.json()
        assert body["error"]["code"] == int(A2AErrorCode.INVALID_PARAMS)


# ---------------------------------------------------------------------------
# task.get
# ---------------------------------------------------------------------------


class TestTaskGet:
    def test_returns_existing_task(self, client: TestClient):
        client.post("/a2a/v1/rpc", json=_rpc("task.send", {"task": {"id": "t1"}}))
        resp = client.post("/a2a/v1/rpc", json=_rpc("task.get", {"id": "t1"}))
        assert resp.json()["result"]["task"]["id"] == "t1"

    def test_unknown_task_returns_task_not_found(self, client: TestClient):
        resp = client.post("/a2a/v1/rpc", json=_rpc("task.get", {"id": "nope"}))
        body = resp.json()
        # Application-level errors are 200 OK with error in the body.
        assert resp.status_code == 200
        assert body["error"]["code"] == int(A2AErrorCode.TASK_NOT_FOUND)

    def test_missing_id_is_invalid_params(self, client: TestClient):
        resp = client.post("/a2a/v1/rpc", json=_rpc("task.get", {}))
        assert resp.json()["error"]["code"] == int(A2AErrorCode.INVALID_PARAMS)

    def test_taskId_alias_works(self, client: TestClient):
        # Some peers use the camelCase form; accept both.
        client.post("/a2a/v1/rpc", json=_rpc("task.send", {"task": {"id": "t1"}}))
        resp = client.post("/a2a/v1/rpc", json=_rpc("task.get", {"taskId": "t1"}))
        assert resp.json()["result"]["task"]["id"] == "t1"


# ---------------------------------------------------------------------------
# task.cancel
# ---------------------------------------------------------------------------


class TestTaskCancel:
    def test_cancels_non_terminal_task(self, client: TestClient):
        client.post("/a2a/v1/rpc", json=_rpc("task.send", {"task": {"id": "t1"}}))
        resp = client.post("/a2a/v1/rpc", json=_rpc("task.cancel", {"id": "t1"}))
        assert resp.json()["result"]["task"]["state"] == TaskState.CANCELED

    def test_cannot_cancel_already_canceled(self, client: TestClient):
        client.post("/a2a/v1/rpc", json=_rpc("task.send", {"task": {"id": "t1"}}))
        client.post("/a2a/v1/rpc", json=_rpc("task.cancel", {"id": "t1"}))
        resp = client.post("/a2a/v1/rpc", json=_rpc("task.cancel", {"id": "t1"}))
        assert resp.json()["error"]["code"] == int(A2AErrorCode.TASK_ALREADY_TERMINAL)

    def test_cancel_unknown_returns_task_not_found(self, client: TestClient):
        resp = client.post("/a2a/v1/rpc", json=_rpc("task.cancel", {"id": "nope"}))
        assert resp.json()["error"]["code"] == int(A2AErrorCode.TASK_NOT_FOUND)


# ---------------------------------------------------------------------------
# Protocol errors
# ---------------------------------------------------------------------------


class TestProtocolErrors:
    def test_parse_error_returns_neg_32700_with_null_id(self, client: TestClient):
        resp = client.post("/a2a/v1/rpc", content=b"this is not json")
        body = resp.json()
        assert resp.status_code == 400
        assert body["id"] is None
        assert body["error"]["code"] == int(A2AErrorCode.PARSE_ERROR)

    def test_non_object_body_returns_invalid_request(self, client: TestClient):
        resp = client.post("/a2a/v1/rpc", json=[1, 2, 3])
        assert resp.json()["error"]["code"] == int(A2AErrorCode.INVALID_REQUEST)

    def test_missing_method_returns_invalid_request(self, client: TestClient):
        resp = client.post("/a2a/v1/rpc", json={"jsonrpc": "2.0", "id": "1"})
        assert resp.json()["error"]["code"] == int(A2AErrorCode.INVALID_REQUEST)

    def test_wrong_jsonrpc_version_returns_invalid_request(self, client: TestClient):
        resp = client.post(
            "/a2a/v1/rpc",
            json={"jsonrpc": "1.0", "id": "1", "method": "task.get", "params": {"id": "x"}},
        )
        assert resp.json()["error"]["code"] == int(A2AErrorCode.INVALID_REQUEST)

    def test_unknown_method_returns_method_not_found(self, client: TestClient):
        resp = client.post("/a2a/v1/rpc", json=_rpc("totally.fake", {}))
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == int(A2AErrorCode.METHOD_NOT_FOUND)


# ---------------------------------------------------------------------------
# Listener mount integration
# ---------------------------------------------------------------------------


class TestListenerMount:
    def test_a2a_router_mounts_alongside_agent_card(self, tmp_path):
        # Smoke test: build_listener_app with the A2A router mounted
        # serves both /.well-known/agent-card.json AND /a2a/v1/rpc
        # off the same FastAPI app.
        from cli_agent_orchestrator.agent_card.listener import build_listener_app
        from cli_agent_orchestrator.agent_card.signing import Signer

        signer = Signer(tmp_path)
        store = InMemoryTaskStore()
        router = build_a2a_router(store=store)

        def metadata_provider() -> dict:
            return {"description": "test"}

        app = build_listener_app(signer, metadata_provider, a2a_router=router)
        client = TestClient(app)

        # Agent Card still works.
        resp = client.get("/.well-known/agent-card.json")
        assert resp.status_code == 200

        # A2A RPC works.
        resp = client.post(
            "/a2a/v1/rpc",
            json=_rpc("task.send", {"task": {"id": "t1"}}),
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["task"]["id"] == "t1"


# ---------------------------------------------------------------------------
# Executor bridge (Phase 5 follow-up)
# ---------------------------------------------------------------------------


class TestExecutorBridge:
    """task.send with a registered executor schedules the work in a
    background asyncio task and publishes state transitions to the
    bus. Without an executor, tasks stay in SUBMITTED — current
    behavior preserved."""

    @pytest.mark.asyncio
    async def test_executor_runs_in_background_and_publishes_terminal(self):
        from cli_agent_orchestrator.a2a import (
            InMemoryTaskEventBus,
            InMemoryTaskStore,
            Task,
            TaskState,
            build_a2a_router,
        )

        store = InMemoryTaskStore()
        bus = InMemoryTaskEventBus()
        executed: list[Task] = []

        async def executor(task: Task) -> Task:
            executed.append(task)
            task.artifacts = [{"kind": "result", "value": "ok"}]
            task.state = TaskState.COMPLETED
            return task

        # Subscribe before submitting so we capture all events.
        events: list[dict] = []

        async def reader() -> None:
            async for payload in bus.subscribe("t1"):
                events.append(payload)
                state = payload.get("task", {}).get("state")
                if state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED):
                    return

        reader_task = asyncio.create_task(reader())
        await asyncio.sleep(0.01)

        # Submit via the RPC endpoint.
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(build_a2a_router(store=store, bus=bus, executor=executor))

        # TestClient is sync; run it in a thread so we don't block
        # the event loop.
        def post() -> dict:
            client = TestClient(app)
            resp = client.post(
                "/a2a/v1/rpc",
                json={
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "task.send",
                    "params": {
                        "task": {"id": "t1", "messages": [{"role": "user", "content": "hi"}]}
                    },
                },
            )
            return resp.json()

        body = await asyncio.to_thread(post)
        # The HTTP response returns immediately with the submitted task.
        assert body["result"]["task"]["id"] == "t1"

        # Wait for the background executor to complete.
        await asyncio.wait_for(reader_task, timeout=2.0)

        # Final stored state is COMPLETED.
        final = await store.get("t1")
        assert final is not None
        assert final.state == TaskState.COMPLETED
        assert final.artifacts == [{"kind": "result", "value": "ok"}]

        # Bus saw the SUBMITTED→WORKING→COMPLETED progression.
        states = [e["task"]["state"] for e in events]
        assert TaskState.WORKING in states
        assert TaskState.COMPLETED in states

        # Executor was called once.
        assert len(executed) == 1

    @pytest.mark.asyncio
    async def test_executor_failure_transitions_to_failed(self):
        from cli_agent_orchestrator.a2a import (
            InMemoryTaskEventBus,
            InMemoryTaskStore,
            Task,
            TaskState,
            build_a2a_router,
        )

        store = InMemoryTaskStore()
        bus = InMemoryTaskEventBus()

        async def executor(task: Task) -> Task:
            raise RuntimeError("boom")

        events: list[dict] = []

        async def reader() -> None:
            async for payload in bus.subscribe("t-fail"):
                events.append(payload)
                if payload["task"]["state"] in (TaskState.FAILED, TaskState.COMPLETED):
                    return

        reader_task = asyncio.create_task(reader())
        await asyncio.sleep(0.01)

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(build_a2a_router(store=store, bus=bus, executor=executor))

        def post() -> dict:
            client = TestClient(app)
            resp = client.post(
                "/a2a/v1/rpc",
                json={
                    "jsonrpc": "2.0",
                    "id": "1",
                    "method": "task.send",
                    "params": {"task": {"id": "t-fail"}},
                },
            )
            return resp.json()

        await asyncio.to_thread(post)
        await asyncio.wait_for(reader_task, timeout=2.0)

        final = await store.get("t-fail")
        assert final is not None
        assert final.state == TaskState.FAILED
        # Error captured in metadata so the peer can read it back.
        assert "boom" in final.metadata.get("error", "")

    def test_no_executor_keeps_task_submitted(self, client: TestClient):
        # With no executor wired, task.send returns the task in
        # SUBMITTED and it stays that way (existing behavior).
        resp = client.post(
            "/a2a/v1/rpc",
            json=_rpc("task.send", {"task": {"id": "t-no-exec"}}),
        )
        assert resp.json()["result"]["task"]["state"] == "submitted"

        resp = client.post(
            "/a2a/v1/rpc",
            json=_rpc("task.get", {"id": "t-no-exec"}),
        )
        assert resp.json()["result"]["task"]["state"] == "submitted"
