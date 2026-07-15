"""Peer-supplied task ids must never overwrite existing tasks.

``task.send`` once accepted a peer-supplied
``id`` verbatim and the store upserted it — any peer could replace or
effectively cancel another peer's in-flight task by resubmitting its id
(state-integrity injection), and an *omitted* id crashed ``Task.from_dict``
with a ``KeyError``. This suite pins the fixed contract:

* ``task.send`` is idempotent-create — an existing id is refused with
  ``INVALID_PARAMS`` and the stored task is untouched;
* an omitted or empty id takes the server-generated-UUID path.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cli_agent_orchestrator.a2a import InMemoryTaskStore, build_a2a_router
from cli_agent_orchestrator.a2a.types import A2AErrorCode


@pytest.fixture
def store() -> InMemoryTaskStore:
    return InMemoryTaskStore()


@pytest.fixture
def client(store: InMemoryTaskStore) -> TestClient:
    app = FastAPI()
    app.include_router(build_a2a_router(store=store))
    return TestClient(app)


def _send(client: TestClient, task: dict, req_id: str = "1"):
    return client.post(
        "/a2a/v1/rpc",
        json={"jsonrpc": "2.0", "id": req_id, "method": "task.send", "params": {"task": task}},
    )


def test_resubmitted_id_is_refused_and_original_task_survives(client: TestClient):
    first = _send(client, {"id": "peer-task-1", "messages": [{"role": "user", "content": "a"}]})
    assert first.status_code == 200
    assert "error" not in first.json()

    # A second send with the same id — as another peer would do to stomp the
    # first — must be refused, not upserted.
    attack = _send(
        client,
        {"id": "peer-task-1", "messages": [{"role": "user", "content": "overwritten"}]},
        req_id="2",
    )
    assert attack.status_code == 200  # JSON-RPC application error rides 200
    assert attack.json()["error"]["code"] == int(A2AErrorCode.INVALID_PARAMS)
    assert "already exists" in attack.json()["error"]["message"]

    # The original task is untouched.
    got = client.post(
        "/a2a/v1/rpc",
        json={
            "jsonrpc": "2.0",
            "id": "3",
            "method": "task.get",
            "params": {"id": "peer-task-1"},
        },
    )
    task = got.json()["result"]["task"]
    assert task["messages"][0]["content"] == "a"


def test_omitted_id_gets_a_server_uuid(client: TestClient):
    # No "id" key at all: previously a KeyError inside Task.from_dict.
    resp = _send(client, {"messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 200
    body = resp.json()
    assert "error" not in body
    assert body["result"]["task"]["id"]  # server generated


def test_empty_id_gets_a_server_uuid(client: TestClient):
    resp = _send(client, {"id": "", "messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 200
    body = resp.json()
    assert "error" not in body
    assert body["result"]["task"]["id"]


def test_distinct_ids_do_not_collide(client: TestClient):
    a = _send(client, {"id": "task-a", "messages": []})
    b = _send(client, {"id": "task-b", "messages": []}, req_id="2")
    assert "error" not in a.json() and "error" not in b.json()
