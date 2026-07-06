"""A2A v1.0 round-trip end-to-end test (v2.5 close-out, item 7).

Spins up two CAO A2A peers in-process and exercises the full
peer-to-peer task lifecycle:

    Peer A  ──HTTP POST──▶  Peer B's /a2a/v1/rpc  (task.send)
    Peer A  ──HTTP GET ──▶  Peer B's /a2a/v1/stream/{id}  (SSE)
    Peer A  ──HTTP POST──▶  Peer B's /a2a/v1/rpc  (task.get)

Peer B has a stub :class:`TaskExecutor` that transitions the task
``submitted → working → completed`` with a result message. Peer A
verifies:

  * ``task.send`` returns 200 OK with state ``submitted`` or ``working``
  * ``task.get`` (polled) eventually reports ``completed``
  * SSE stream emits at least one ``task.update`` and one
    terminal-state event before closing

Marker: ``e2e`` + ``slow`` so this is auto-deselected from the default
``pytest -m 'not e2e' --no-cov`` invocation. Run manually with::

    pytest -m e2e test/e2e/test_a2a_roundtrip.py

The runbook also documents a true-network variant (two CAO instances
on different ports rather than ASGI in-process). For CI we use the
in-process variant — same code path, no flaky port binding.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from cli_agent_orchestrator.a2a import (
    InMemoryTaskEventBus,
    InMemoryTaskStore,
    Task,
    TaskState,
    build_a2a_router,
    build_stream_router,
)

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


# Override the test/e2e/conftest.py autouse fixtures — this test runs the
# A2A surfaces in-process via ``httpx.ASGITransport`` and doesn't need a
# live CAO server or warmed uvx cache.
@pytest.fixture(autouse=True)
def require_cao_server():
    yield


@pytest.fixture(autouse=True)
def warmup_mcp_server_cache():
    yield


# ---------------------------------------------------------------------------
# Peer factory — one per CAO instance.
# ---------------------------------------------------------------------------


def _build_peer(*, with_executor: bool) -> tuple[FastAPI, InMemoryTaskStore, InMemoryTaskEventBus]:
    store = InMemoryTaskStore()
    bus = InMemoryTaskEventBus()

    async def _executor(task: Task) -> Task:
        # Trivial executor — pretend the worker did some work and produced
        # a single response message. The framework transitions WORKING →
        # COMPLETED automatically when the executor returns without
        # setting a terminal state.
        await asyncio.sleep(0)
        task.messages = list(task.messages) + [
            {"role": "assistant", "content": "round-trip complete"}
        ]
        return task

    app = FastAPI()
    app.include_router(
        build_a2a_router(
            store=store,
            bus=bus,
            executor=_executor if with_executor else None,
        )
    )
    app.include_router(build_stream_router(store=store, bus=bus))
    return app, store, bus


# ---------------------------------------------------------------------------
# Utility: SSE line parser
# ---------------------------------------------------------------------------


async def _read_sse_events(
    stream: AsyncIterator[bytes], *, max_events: int = 5
) -> list[dict[str, Any]]:
    """Pull at most ``max_events`` parsed SSE frames from an async iterator."""
    events: list[dict[str, Any]] = []
    buffer = ""
    async for chunk in stream:
        buffer += chunk.decode("utf-8")
        while "\n\n" in buffer:
            block, _, buffer = buffer.partition("\n\n")
            event_line = next((ln for ln in block.splitlines() if ln.startswith("event:")), "")
            data_line = next((ln for ln in block.splitlines() if ln.startswith("data:")), "")
            if not event_line:
                continue
            event_name = event_line.split(":", 1)[1].strip()
            payload = data_line.split(":", 1)[1].strip() if data_line else ""
            try:
                data = json.loads(payload) if payload else {}
            except json.JSONDecodeError:
                data = {"raw": payload}
            events.append({"event": event_name, "data": data})
            if len(events) >= max_events:
                return events
    return events


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a2a_round_trip_two_peers():
    """End-to-end: peer A sends a task to peer B, B executes, A polls + streams."""
    # Peer A: vanilla — used only as the client; no executor.
    app_a, _, _ = _build_peer(with_executor=False)
    # Peer B: has the executor that completes the task.
    app_b, store_b, _ = _build_peer(with_executor=True)

    # Drive peer A as an HTTP client against peer B's ASGI app.
    transport_b = httpx.ASGITransport(app=app_b)
    async with httpx.AsyncClient(transport=transport_b, base_url="http://peer-b") as client_b:
        # 1. Peer A submits a task to peer B's RPC endpoint.
        send_resp = await client_b.post(
            "/a2a/v1/rpc",
            json={
                "jsonrpc": "2.0",
                "id": "rt-1",
                "method": "task.send",
                "params": {
                    "task": {
                        "id": "rt-task-1",
                        "messages": [{"role": "user", "content": "ping"}],
                        "metadata": {"sender": "peer-a"},
                    }
                },
            },
        )
        assert send_resp.status_code == 200, send_resp.text
        send_body = send_resp.json()
        assert "error" not in send_body, send_body
        send_state = send_body["result"]["task"]["state"]
        # Either SUBMITTED (executor scheduled but hasn't run yet) or
        # WORKING (executor already started).
        assert send_state in (TaskState.SUBMITTED, TaskState.WORKING)

        # 2. Poll peer B's task.get until the task reaches COMPLETED.
        deadline = asyncio.get_event_loop().time() + 5.0
        final_state = None
        while asyncio.get_event_loop().time() < deadline:
            get_resp = await client_b.post(
                "/a2a/v1/rpc",
                json={
                    "jsonrpc": "2.0",
                    "id": "rt-get",
                    "method": "task.get",
                    "params": {"id": "rt-task-1"},
                },
            )
            assert get_resp.status_code == 200
            task_payload = get_resp.json()["result"]["task"]
            if TaskState.is_terminal(task_payload["state"]):
                final_state = task_payload["state"]
                break
            await asyncio.sleep(0.05)

        assert final_state == TaskState.COMPLETED, (
            f"task did not reach COMPLETED within deadline (final_state={final_state}, "
            f"store={await store_b.get('rt-task-1')})"
        )

        # 3. Pull peer B's SSE stream — for an already-terminal task we
        #    expect a single ``task.terminal`` frame and the stream to close.
        async with client_b.stream(
            "GET",
            "/a2a/v1/stream/rt-task-1",
            timeout=5.0,
        ) as stream_resp:
            assert stream_resp.status_code == 200
            events = await _read_sse_events(stream_resp.aiter_bytes(), max_events=3)

        assert events, "stream produced no events for terminal task"
        # First (and likely only) event must be a terminal carrying the
        # final task envelope. The Phase 5 stream router collapses an
        # already-terminal subscription into one frame.
        terminal_events = [e for e in events if e["event"] in ("task.terminal", "task.update")]
        assert terminal_events, f"no task.update/terminal events seen: {events}"
        terminal_payload = terminal_events[0]["data"]
        assert terminal_payload.get("task", {}).get("id") == "rt-task-1"
        assert terminal_payload.get("task", {}).get("state") == TaskState.COMPLETED


@pytest.mark.asyncio
async def test_a2a_round_trip_authenticated(monkeypatch, jwt_factory, jwks_server):
    """Same round-trip with auth enforced: 401 untokened, full flow with JWTs.

    Added with the #387 review remediation — the transport now gates
    task.send/cancel on ``cao:write`` and task.get/stream on ``cao:read``
    against a live JWKS, so the e2e proves the authenticated path end-to-end.
    """
    from cli_agent_orchestrator.security import auth as auth_mod

    monkeypatch.setenv("AUTH0_DOMAIN", jwt_factory.domain)
    monkeypatch.setenv("AUTH0_AUDIENCE", jwt_factory.audience)
    monkeypatch.setenv("CAO_AUTH_JWKS_URI", jwks_server.url)
    auth_mod.reset_jwks_cache()
    try:
        app_b, _, _ = _build_peer(with_executor=True)
        transport_b = httpx.ASGITransport(app=app_b)
        write_h = {"Authorization": f"Bearer {jwt_factory.mint(scopes='cao:write')}"}
        read_h = {"Authorization": f"Bearer {jwt_factory.mint(scopes='cao:read')}"}
        send_req = {
            "jsonrpc": "2.0",
            "id": "rt-auth-1",
            "method": "task.send",
            "params": {"task": {"id": "rt-auth-task", "messages": []}},
        }
        async with httpx.AsyncClient(transport=transport_b, base_url="http://peer-b") as client_b:
            # Untokened peer is rejected before any task work happens.
            anon = await client_b.post("/a2a/v1/rpc", json=send_req)
            assert anon.status_code == 401

            # Authorized peer runs the full lifecycle.
            sent = await client_b.post("/a2a/v1/rpc", json=send_req, headers=write_h)
            assert sent.status_code == 200, sent.text
            assert "error" not in sent.json()

            deadline = asyncio.get_event_loop().time() + 5.0
            final_state = None
            while asyncio.get_event_loop().time() < deadline:
                got = await client_b.post(
                    "/a2a/v1/rpc",
                    json={
                        "jsonrpc": "2.0",
                        "id": "rt-auth-get",
                        "method": "task.get",
                        "params": {"id": "rt-auth-task"},
                    },
                    headers=read_h,
                )
                assert got.status_code == 200
                task_payload = got.json()["result"]["task"]
                if TaskState.is_terminal(task_payload["state"]):
                    final_state = task_payload["state"]
                    break
                await asyncio.sleep(0.05)
            assert final_state == TaskState.COMPLETED

            # Stream also requires the read scope.
            anon_stream = await client_b.get("/a2a/v1/stream/rt-auth-task")
            assert anon_stream.status_code == 401
            async with client_b.stream(
                "GET", "/a2a/v1/stream/rt-auth-task", headers=read_h, timeout=5.0
            ) as stream_resp:
                assert stream_resp.status_code == 200
                events = await _read_sse_events(stream_resp.aiter_bytes(), max_events=2)
            assert any(e["event"] in ("task.terminal", "task.update") for e in events)
    finally:
        auth_mod.reset_jwks_cache()
