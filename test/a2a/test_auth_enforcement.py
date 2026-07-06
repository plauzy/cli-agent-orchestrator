"""A2A transport auth enforcement — the blocking finding from the #387 review.

The A2A JSON-RPC endpoint (``POST /a2a/v1/rpc``: task.send/get/cancel) and the
stream/REST routes were mounted with **no authentication at all** while their
docstrings claimed JWKS enforcement. This suite pins the fixed contract:

* auth disabled (default-off, loopback dev) → everything works untokened,
  byte-for-byte as before;
* auth enabled → per-method scope enforcement:
    - ``task.send`` / ``task.cancel`` → ``cao:write``
    - ``task.get`` and the stream/REST reads → ``cao:read``
  with 401 (missing/malformed/expired bearer) and 403 (insufficient scope)
  carried BOTH as the HTTP status and as a JSON-RPC error body
  (``UNAUTHENTICATED`` / ``PERMISSION_DENIED``) so JSON-RPC clients that
  ignore transport status still see the failure.

Tokens are real RS256 JWTs validated against a live in-process JWKS endpoint
(``jwt_factory`` + ``jwks_server`` fixtures) — nothing in the auth path is
stubbed.
"""

from __future__ import annotations

from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cli_agent_orchestrator.a2a import (
    A2AErrorCode,
    InMemoryTaskStore,
    build_a2a_router,
    build_stream_router,
)
from cli_agent_orchestrator.security import auth as auth_mod


@pytest.fixture
def store() -> InMemoryTaskStore:
    return InMemoryTaskStore()


@pytest.fixture
def client(store: InMemoryTaskStore) -> TestClient:
    app = FastAPI()
    app.include_router(build_a2a_router(store=store))
    app.include_router(build_stream_router(store=store))
    return TestClient(app)


@pytest.fixture
def auth_on(monkeypatch, jwt_factory, jwks_server) -> Iterator[None]:
    """Enable real JWT validation against the in-process JWKS server."""
    monkeypatch.setenv("AUTH0_DOMAIN", jwt_factory.domain)
    monkeypatch.setenv("AUTH0_AUDIENCE", jwt_factory.audience)
    monkeypatch.setenv("CAO_AUTH_JWKS_URI", jwks_server.url)
    auth_mod.reset_jwks_cache()
    yield
    auth_mod.reset_jwks_cache()


def _rpc(method: str, params: dict, *, req_id: str | int | None = "1") -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _send(client: TestClient, headers: dict | None = None):
    return client.post(
        "/a2a/v1/rpc",
        json=_rpc(
            "task.send", {"task": {"id": "", "messages": [{"role": "user", "content": "hi"}]}}
        ),
        headers=headers or {},
    )


class TestAuthDisabledIsUnchanged:
    """Default-off (no AUTH0_DOMAIN / CAO_AUTH_JWKS_URI): no token required."""

    def test_send_get_cancel_work_untokened(self, client: TestClient):
        resp = _send(client)
        assert resp.status_code == 200
        task_id = resp.json()["result"]["task"]["id"]

        got = client.post("/a2a/v1/rpc", json=_rpc("task.get", {"id": task_id}))
        assert got.status_code == 200
        assert got.json()["result"]["task"]["id"] == task_id

        rest = client.get(f"/a2a/v1/tasks/{task_id}")
        assert rest.status_code == 200


class TestRpcAuthEnabled:
    def test_missing_token_is_401_unauthenticated(self, client: TestClient, auth_on):
        resp = _send(client)
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"]["code"] == int(A2AErrorCode.UNAUTHENTICATED)

    def test_malformed_token_is_401(self, client: TestClient, auth_on):
        resp = _send(client, headers=_bearer("not-a-jwt"))
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == int(A2AErrorCode.UNAUTHENTICATED)

    def test_expired_token_is_401(self, client: TestClient, auth_on, jwt_factory):
        resp = _send(client, headers=_bearer(jwt_factory.mint_expired()))
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == int(A2AErrorCode.UNAUTHENTICATED)

    def test_read_scope_cannot_send_or_cancel(self, client: TestClient, auth_on, jwt_factory):
        read_token = jwt_factory.mint(scopes="cao:read")
        resp = _send(client, headers=_bearer(read_token))
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == int(A2AErrorCode.PERMISSION_DENIED)

        cancel = client.post(
            "/a2a/v1/rpc",
            json=_rpc("task.cancel", {"id": "whatever"}),
            headers=_bearer(read_token),
        )
        assert cancel.status_code == 403

    def test_write_scope_sends_and_read_scope_gets(self, client: TestClient, auth_on, jwt_factory):
        write_token = jwt_factory.mint(scopes="cao:write")
        sent = _send(client, headers=_bearer(write_token))
        assert sent.status_code == 200
        task_id = sent.json()["result"]["task"]["id"]

        read_token = jwt_factory.mint(scopes="cao:read")
        got = client.post(
            "/a2a/v1/rpc",
            json=_rpc("task.get", {"id": task_id}),
            headers=_bearer(read_token),
        )
        assert got.status_code == 200
        assert got.json()["result"]["task"]["id"] == task_id

    def test_write_scope_implies_read_like_the_rest_of_cao(
        self, client: TestClient, auth_on, jwt_factory
    ):
        # Repo-wide convention (see require_any_scope call sites in api/main.py):
        # read endpoints accept any of read/write/admin — write implies read.
        write_only = jwt_factory.mint(scopes="cao:write")
        sent = _send(client, headers=_bearer(write_only))
        task_id = sent.json()["result"]["task"]["id"]
        got = client.post(
            "/a2a/v1/rpc",
            json=_rpc("task.get", {"id": task_id}),
            headers=_bearer(write_only),
        )
        assert got.status_code == 200

    def test_auth_failure_beats_method_dispatch(self, client: TestClient, auth_on):
        # No credential leakage about which methods exist: unauthenticated
        # requests get 401 even for unknown methods.
        resp = client.post("/a2a/v1/rpc", json=_rpc("task.exfiltrate", {}))
        assert resp.status_code == 401


class TestStreamRoutesAuthEnabled:
    def test_rest_poll_requires_read(self, client: TestClient, auth_on, jwt_factory):
        assert client.get("/a2a/v1/tasks/some-id").status_code == 401
        wrong = jwt_factory.mint(scopes="some:other")
        assert client.get("/a2a/v1/tasks/some-id", headers=_bearer(wrong)).status_code == 403
        read = jwt_factory.mint(scopes="cao:read")
        # Authorized but unknown id → 404 (auth cleared, resource missing).
        assert client.get("/a2a/v1/tasks/some-id", headers=_bearer(read)).status_code == 404

    def test_sse_stream_requires_read(self, client: TestClient, auth_on, jwt_factory):
        assert client.get("/a2a/v1/stream/some-id").status_code == 401
        wrong = jwt_factory.mint(scopes="some:other")
        assert client.get("/a2a/v1/stream/some-id", headers=_bearer(wrong)).status_code == 403


class TestDocstringsTellTheTruth:
    def test_rpc_module_documents_actual_enforcement(self):
        import cli_agent_orchestrator.a2a.rpc as rpc_mod

        doc = rpc_mod.__doc__ or ""
        assert "once auth is enabled" not in doc  # the old false claim
        assert "cao:write" in doc and "cao:read" in doc

    def test_stream_module_documents_actual_enforcement(self):
        import cli_agent_orchestrator.a2a.stream as stream_mod

        doc = stream_mod.__doc__ or ""
        assert "is enforced once auth is enabled" not in doc
        assert "cao:read" in doc
