"""Auth enforcement + bounded-store tests for the A2A transport.

These are the security properties the PR #387 review flagged as blocking:

  * Per-method scope enforcement on the JSON-RPC endpoint — the review
    reproduced an anonymous ``task.send`` returning 200 with auth enabled.
    Matrix: send/get/cancel x {no token, malformed token, cao:read, cao:write}
    -> 401 / 403 / 200, as JSON-RPC error bodies with the *matching* HTTP status
    (auth failures are not tunnelled through 200).
  * The read-only stream/REST routes require cao:read.
  * The fail-closed mount guard: non-loopback bind + auth off -> not mounted.
  * The bounded task store: capped + TTL-evicting, with a full store of live
    tasks refusing ``task.send`` (RESOURCE_EXHAUSTED / HTTP 429) instead of
    growing without limit (the unbounded-store DoS finding).

Default-off is unchanged: with the auth layer disabled no token is required
(covered here + by the pre-existing test_rpc.py suite).
"""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import cli_agent_orchestrator.a2a.rpc as rpc_mod
import cli_agent_orchestrator.security.auth as auth_mod
from cli_agent_orchestrator.a2a import (
    A2AErrorCode,
    InMemoryTaskEventBus,
    InMemoryTaskStore,
    TaskState,
    TaskStoreFull,
    build_a2a_router,
    build_stream_router,
)
from cli_agent_orchestrator.a2a.types import Task
from cli_agent_orchestrator.api.main import _should_mount_a2a

# token string -> granted scopes; any other (non-empty) token is "malformed".
_TOKEN_SCOPES = {
    "tok-read": ["cao:read"],
    "tok-write": ["cao:write"],
    "tok-admin": ["cao:admin"],
}


def _fake_extract(token: str):
    if token in _TOKEN_SCOPES:
        return list(_TOKEN_SCOPES[token])
    raise ValueError("malformed or unknown token")


@pytest.fixture
def auth_on(monkeypatch):
    """Enable the auth layer for both the RPC path (rpc module namespace) and
    the stream path (require_any_scope -> get_current_scopes in the auth
    module namespace)."""
    monkeypatch.setattr(rpc_mod, "is_auth_enabled", lambda: True)
    monkeypatch.setattr(rpc_mod, "extract_scopes_from_token", _fake_extract)
    monkeypatch.setattr(auth_mod, "is_auth_enabled", lambda: True)
    monkeypatch.setattr(auth_mod, "extract_scopes_from_token", _fake_extract)


@pytest.fixture
def client():
    app = FastAPI()
    store = InMemoryTaskStore()
    bus = InMemoryTaskEventBus()
    app.include_router(build_a2a_router(store=store, bus=bus))
    app.include_router(build_stream_router(store=store, bus=bus))
    return TestClient(app)


def _rpc(method: str, params: dict, req_id="1") -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}


def _hdr(token: str | None) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


def _send(client: TestClient, token: str | None, task=None):
    task = task or {"id": "", "messages": [{"role": "user", "content": "hi"}]}
    return client.post("/a2a/v1/rpc", json=_rpc("task.send", {"task": task}), headers=_hdr(token))


# ---------------------------------------------------------------------------
# task.send — write scope
# ---------------------------------------------------------------------------


class TestTaskSendAuth:
    def test_no_token_401(self, client, auth_on):
        resp = _send(client, None)
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == int(A2AErrorCode.UNAUTHENTICATED)

    def test_malformed_token_401(self, client, auth_on):
        resp = _send(client, "garbage")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == int(A2AErrorCode.UNAUTHENTICATED)

    def test_read_scope_403(self, client, auth_on):
        resp = _send(client, "tok-read")
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == int(A2AErrorCode.PERMISSION_DENIED)

    def test_write_scope_200(self, client, auth_on):
        resp = _send(client, "tok-write")
        assert resp.status_code == 200
        assert "error" not in resp.json()
        assert resp.json()["result"]["task"]["state"] == TaskState.SUBMITTED

    def test_admin_scope_200(self, client, auth_on):
        resp = _send(client, "tok-admin")
        assert resp.status_code == 200
        assert "error" not in resp.json()

    def test_default_off_allows_no_token(self, client):
        # No auth_on fixture => auth layer disabled => no token required.
        resp = _send(client, None)
        assert resp.status_code == 200
        assert "error" not in resp.json()


# ---------------------------------------------------------------------------
# task.get / task.cancel — read / write scope
# ---------------------------------------------------------------------------


class TestTaskGetCancelAuth:
    def test_get_no_token_401(self, client, auth_on):
        resp = client.post("/a2a/v1/rpc", json=_rpc("task.get", {"id": "x"}), headers=_hdr(None))
        assert resp.status_code == 401

    def test_get_read_scope_ok(self, client, auth_on):
        created = _send(client, "tok-write").json()["result"]["task"]["id"]
        resp = client.post(
            "/a2a/v1/rpc", json=_rpc("task.get", {"id": created}), headers=_hdr("tok-read")
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["task"]["id"] == created

    def test_cancel_read_scope_403(self, client, auth_on):
        created = _send(client, "tok-write").json()["result"]["task"]["id"]
        resp = client.post(
            "/a2a/v1/rpc", json=_rpc("task.cancel", {"id": created}), headers=_hdr("tok-read")
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == int(A2AErrorCode.PERMISSION_DENIED)

    def test_cancel_write_scope_ok(self, client, auth_on):
        created = _send(client, "tok-write").json()["result"]["task"]["id"]
        resp = client.post(
            "/a2a/v1/rpc", json=_rpc("task.cancel", {"id": created}), headers=_hdr("tok-write")
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["task"]["state"] == TaskState.CANCELED

    def test_unknown_method_authenticated_still_404(self, client, auth_on):
        # A valid reader hitting an unknown method gets METHOD_NOT_FOUND, not a
        # scope leak; an anonymous caller would have been 401 before dispatch.
        resp = client.post("/a2a/v1/rpc", json=_rpc("task.bogus", {}), headers=_hdr("tok-read"))
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == int(A2AErrorCode.METHOD_NOT_FOUND)


# ---------------------------------------------------------------------------
# stream / REST routes — read scope
# ---------------------------------------------------------------------------


class TestStreamAuth:
    def test_rest_poll_no_token_401(self, client, auth_on):
        resp = client.get("/a2a/v1/tasks/anything")
        assert resp.status_code == 401

    def test_rest_poll_read_scope_ok(self, client, auth_on):
        created = _send(client, "tok-write").json()["result"]["task"]["id"]
        resp = client.get("/a2a/v1/tasks/" + created, headers=_hdr("tok-read"))
        assert resp.status_code == 200
        assert resp.json()["task"]["id"] == created

    def test_rest_poll_default_off_ok(self, client):
        resp = client.get("/a2a/v1/tasks/missing")
        # Auth off => route reachable; task simply not found.
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# fail-closed mount guard
# ---------------------------------------------------------------------------


class TestMountGuard:
    @pytest.mark.parametrize(
        "bind_host, a2a_disabled, auth_enabled, expected",
        [
            ("127.0.0.1", False, False, True),  # loopback + no auth: OK (dev)
            ("localhost", False, False, True),  # loopback alias
            ("::1", False, False, True),  # ipv6 loopback
            ("0.0.0.0", False, False, False),  # non-loopback + no auth: REFUSED
            ("0.0.0.0", False, True, True),  # non-loopback + auth: OK
            ("10.0.0.5", False, False, False),  # arbitrary external + no auth: REFUSED
            ("0.0.0.0", True, True, False),  # explicitly disabled always wins
            ("127.0.0.1", True, False, False),  # disabled wins on loopback too
        ],
    )
    def test_mount_decision(self, bind_host, a2a_disabled, auth_enabled, expected):
        assert (
            _should_mount_a2a(
                bind_host=bind_host, a2a_disabled=a2a_disabled, auth_enabled=auth_enabled
            )
            is expected
        )


# ---------------------------------------------------------------------------
# bounded store
# ---------------------------------------------------------------------------


class TestBoundedStore:
    @pytest.mark.asyncio
    async def test_evicts_oldest_terminal_on_overflow(self):
        store = InMemoryTaskStore(max_tasks=2, ttl_seconds=0)
        await store.upsert(Task(id="a", state=TaskState.COMPLETED))
        await store.upsert(Task(id="b", state=TaskState.COMPLETED))
        # Third new task: store full, oldest terminal ("a") evicted.
        await store.upsert(Task(id="c", state=TaskState.SUBMITTED))
        ids = set(await store.list_ids())
        assert ids == {"b", "c"}
        assert await store.get("a") is None

    @pytest.mark.asyncio
    async def test_rejects_when_full_of_nonterminal(self):
        store = InMemoryTaskStore(max_tasks=2, ttl_seconds=0)
        await store.upsert(Task(id="a", state=TaskState.WORKING))
        await store.upsert(Task(id="b", state=TaskState.SUBMITTED))
        with pytest.raises(TaskStoreFull):
            await store.upsert(Task(id="c", state=TaskState.SUBMITTED))
        # The rejected task was not stored; the live ones survive.
        assert set(await store.list_ids()) == {"a", "b"}

    @pytest.mark.asyncio
    async def test_update_existing_when_full_is_ok(self):
        store = InMemoryTaskStore(max_tasks=1, ttl_seconds=0)
        await store.upsert(Task(id="a", state=TaskState.SUBMITTED))
        # Updating an existing key is not a new insert -> no rejection.
        await store.upsert(Task(id="a", state=TaskState.WORKING))
        got = await store.get("a")
        assert got is not None and got.state == TaskState.WORKING

    @pytest.mark.asyncio
    async def test_ttl_sweep_drops_stale(self):
        store = InMemoryTaskStore(max_tasks=0, ttl_seconds=3600)
        await store.upsert(Task(id="a", state=TaskState.SUBMITTED))
        # Backdate past the TTL; the next access sweeps it.
        store._tasks["a"].updated_at = time.time() - 7200
        assert await store.get("a") is None

    @pytest.mark.asyncio
    async def test_ttl_disabled_keeps_everything(self):
        store = InMemoryTaskStore(max_tasks=0, ttl_seconds=0)
        await store.upsert(Task(id="a", state=TaskState.SUBMITTED))
        store._tasks["a"].updated_at = time.time() - 10**9
        assert await store.get("a") is not None


class TestSendWhenFull:
    """End-to-end: task.send against a full-of-live-tasks store -> 429."""

    def test_send_full_returns_resource_exhausted_429(self, monkeypatch):
        app = FastAPI()
        store = InMemoryTaskStore(max_tasks=1, ttl_seconds=0)
        app.include_router(build_a2a_router(store=store))
        c = TestClient(app)
        # First send fills the single slot with a non-terminal task.
        first = c.post(
            "/a2a/v1/rpc", json=_rpc("task.send", {"task": {"id": "keep", "messages": []}})
        )
        assert first.status_code == 200
        # Second send: store full of a live task -> RESOURCE_EXHAUSTED / 429.
        second = c.post(
            "/a2a/v1/rpc", json=_rpc("task.send", {"task": {"id": "overflow", "messages": []}})
        )
        assert second.status_code == 429
        assert second.json()["error"]["code"] == int(A2AErrorCode.RESOURCE_EXHAUSTED)
