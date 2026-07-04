"""Tests for the AG-UI HTTP+SSE endpoint.

Sibling RFC: docs/rfc/cao-agui-l2-dashboard-2026-05-11-v1.md.

The endpoint is open-ended (subscribed to an in-process SSE bus that
never closes), which doesn't compose with FastAPI TestClient's
`iter_text` blocking semantics. We test the auth gate via a normal
GET, and verify the replay-path mapping by calling the inner
generator directly with the bus replaced by an empty stub.
"""

from __future__ import annotations

import asyncio
import json
import re
from unittest.mock import patch

import pytest

from cli_agent_orchestrator.api.main import agui_stream
from cli_agent_orchestrator.services.event_log_service import (
    get_event_log,
    reset_event_log,
)


@pytest.fixture(autouse=True)
def _reset_event_log():
    reset_event_log()
    yield
    reset_event_log()


def _parse_sse_events(text: str) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    event_re = re.compile(r"^event: (?P<type>\S+)\ndata: (?P<data>.+)$", re.MULTILINE)
    for match in event_re.finditer(text):
        out.append((match.group("type"), json.loads(match.group("data"))))
    return out


async def _empty_bus_subscribe():
    """An async generator that closes immediately — stand-in for the
    long-lived SSE bus subscription so the endpoint's gen() drains
    only the replay buffer."""
    if False:
        yield  # pragma: no cover — empty async generator marker


async def _drain_response(response, *, max_bytes: int = 64 * 1024) -> str:
    """Consume a FastAPI StreamingResponse's body iterator until either
    it finishes naturally (our test stubs the bus to close) or until
    we've collected max_bytes worth of output."""
    chunks: list[str] = []
    total = 0
    async for chunk in response.body_iterator:
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8")
        chunks.append(chunk)
        total += len(chunk)
        if total > max_bytes:
            break
    return "".join(chunks)


class TestReplayPath:
    @pytest.mark.asyncio
    async def test_replay_translates_history_to_agui_typed_events(self) -> None:
        log = get_event_log()
        log.append("session.created", session_name="cao-x")
        log.append(
            "terminal.created",
            terminal_id="abc12345",
            detail={"agent_name": "developer", "provider": "claude_code"},
        )
        log.append("session.killed", session_name="cao-x")

        # Stub the SSE bus so the live-stream branch yields nothing.
        with patch("cli_agent_orchestrator.api.main.get_bus") as mock_bus:
            mock_bus.return_value.subscribe.return_value = _empty_bus_subscribe()
            response = await agui_stream(since=None, access_token=None)
            text = await _drain_response(response)

        events = _parse_sse_events(text)
        types = [t for t, _ in events]
        assert "RUN_STARTED" in types
        assert "STEP_STARTED" in types
        assert "RUN_FINISHED" in types

    @pytest.mark.asyncio
    async def test_since_filter_skips_earlier_events(self) -> None:
        from datetime import datetime, timedelta, timezone

        log = get_event_log()
        log.append(
            "session.created",
            session_name="cao-old",
            timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        log.append("session.created", session_name="cao-new")

        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        with patch("cli_agent_orchestrator.api.main.get_bus") as mock_bus:
            mock_bus.return_value.subscribe.return_value = _empty_bus_subscribe()
            response = await agui_stream(since=cutoff, access_token=None)
            text = await _drain_response(response)

        events = _parse_sse_events(text)
        thread_ids = {data.get("thread_id") for _, data in events}
        assert "cao-new" in thread_ids
        assert "cao-old" not in thread_ids


class TestAuthGating:
    @pytest.mark.asyncio
    async def test_default_off_mode_skips_auth_check(self, monkeypatch) -> None:
        monkeypatch.delenv("AUTH0_DOMAIN", raising=False)
        with patch("cli_agent_orchestrator.api.main.get_bus") as mock_bus:
            mock_bus.return_value.subscribe.return_value = _empty_bus_subscribe()
            # Should not raise.
            response = await agui_stream(since=None, access_token=None)
            assert response.status_code == 200
            await _drain_response(response)

    @pytest.mark.asyncio
    async def test_missing_token_when_auth_enabled_returns_401(self, monkeypatch) -> None:
        from fastapi import HTTPException

        monkeypatch.setenv("AUTH0_DOMAIN", "test.local")
        monkeypatch.setenv("AUTH0_AUDIENCE", "cao://test")
        with pytest.raises(HTTPException) as ex:
            await agui_stream(since=None, access_token=None)
        assert ex.value.status_code == 401
        assert "access_token" in ex.value.detail
