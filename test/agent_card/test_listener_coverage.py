"""Coverage for the dedicated Agent Card listener (:9890) assembly + lifecycle.

Targets ``agent_card/listener.py``: mounting the optional A2A JSON-RPC and
streaming routers onto the listener app, and the real
``start_agent_card_listener`` → ``AgentCardListener.stop()`` round-trip on a
loopback test port.
"""

from __future__ import annotations

import socket

import pytest
from fastapi import APIRouter

from cli_agent_orchestrator.agent_card.listener import (
    build_listener_app,
    start_agent_card_listener,
)
from cli_agent_orchestrator.agent_card.signing import Signer


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_build_listener_app_mounts_optional_a2a_routers(tmp_path) -> None:
    signer = Signer(tmp_path / "kd")
    a2a = APIRouter()

    @a2a.post("/a2a/v1/rpc")
    async def rpc() -> dict:  # pragma: no cover - only route registration matters
        return {}

    stream = APIRouter()

    @stream.get("/a2a/v1/stream/{task_id}")
    async def stream_route(task_id: str) -> dict:  # pragma: no cover
        return {}

    app = build_listener_app(
        signer, lambda: {"name": "cao"}, a2a_router=a2a, a2a_stream_router=stream
    )
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/.well-known/agent-card.json" in paths
    assert "/a2a/v1/rpc" in paths
    assert "/a2a/v1/stream/{task_id}" in paths


def test_build_listener_app_without_a2a_routers(tmp_path) -> None:
    signer = Signer(tmp_path / "kd")
    app = build_listener_app(signer, lambda: {"name": "cao"})
    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/.well-known/agent-card.json" in paths
    assert "/.well-known/jwks.json" in paths


@pytest.mark.asyncio
async def test_start_and_stop_listener(tmp_path) -> None:
    port = _free_port()
    listener = await start_agent_card_listener(
        tmp_path / "kd",
        lambda: {"name": "cao"},
        host="127.0.0.1",
        port=port,
    )
    try:
        assert listener.task is not None
        assert not listener.task.done()
    finally:
        await listener.stop()
    assert listener.server.should_exit is True
