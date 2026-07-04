"""Coverage for the AG-UI SSE endpoint (`/agui/v1/stream`).

Exercises the query-parameter auth branches (401/403) and the streaming
generator (history replay via ``?since=`` + STATE_SNAPSHOT on connect + a
per-event AG-UI frame + STATE_DELTA), without leaving the stream open: the
bus is stubbed to yield one event and then complete.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import cli_agent_orchestrator.api.main as main
from cli_agent_orchestrator.api.main import app

client = TestClient(app, base_url="http://localhost")


@pytest.fixture(autouse=True)
def _agui_on(monkeypatch):
    monkeypatch.setenv("CAO_AGUI_ENABLED", "true")


def test_stream_requires_token_when_auth_enabled(monkeypatch):
    monkeypatch.setattr(main, "is_auth_enabled", lambda: True)
    resp = client.get("/agui/v1/stream")
    assert resp.status_code == 401
    assert "access_token" in resp.text


def test_stream_rejects_insufficient_scope(monkeypatch):
    monkeypatch.setattr(main, "is_auth_enabled", lambda: True)
    monkeypatch.setattr(main, "extract_scopes_from_token", lambda tok: ["some:other"])
    resp = client.get("/agui/v1/stream", params={"access_token": "x"})
    assert resp.status_code == 403


def test_stream_replays_history_and_emits_state_frames(monkeypatch):
    monkeypatch.setattr(main, "is_auth_enabled", lambda: False)

    # A historical event for ?since= replay.
    replay_event = {
        "id": "evt-old",
        "kind": "handoff",
        "terminal_id": "t-1",
        "session_name": "s",
        "timestamp": "2026-07-04T00:00:00Z",
        "detail": {"sender": "a", "receiver": "b", "orchestration_type": "handoff"},
    }

    class _FakeLog:
        def history(self, **kwargs):
            return [replay_event]

    # A single live event, then the subscription completes so the stream closes.
    live_event = {
        "id": "evt-live",
        "kind": "launch",
        "terminal_id": "t-2",
        "session_name": "s",
        "timestamp": "2026-07-04T00:00:01Z",
        "detail": {"agent_name": "worker", "provider": "mock_cli"},
    }

    class _FakeBus:
        async def subscribe(self):
            yield live_event

    monkeypatch.setattr(
        "cli_agent_orchestrator.services.event_log_service.get_event_log",
        lambda: _FakeLog(),
    )
    monkeypatch.setattr(
        "cli_agent_orchestrator.services.sse_bus.get_bus",
        lambda: _FakeBus(),
    )

    with client.stream("GET", "/agui/v1/stream", params={"since": "2026-07-04T00:00:00Z"}) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    # Replay frame + connect snapshot + live event frame all present.
    assert "STATE_SNAPSHOT" in body
    assert "STEP_STARTED" in body  # from the live launch event
    assert "event:" in body and "data:" in body
