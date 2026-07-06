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


def _make_fakes(replay_events):
    """Build (FakeLogCls, FakeBusCls, seen) where FakeLog.history honors the
    ``since`` kwarg — so the endpoint's replay wiring is exercised end-to-end
    (not stubbed) — and the bus yields one live launch event then completes so
    the stream closes. ``seen`` captures the ``since`` value the endpoint
    forwarded into ``event_log.history``."""
    seen: dict = {}

    class _FakeLog:
        def history(self, since=None, **kwargs):
            seen["since"] = since
            events = list(replay_events)
            if since is not None:
                # Replay only events strictly after ``since`` (ISO-8601 sorts
                # lexically), matching the real event-log semantics.
                events = [e for e in events if e["timestamp"] > since]
            return events

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

    return _FakeLog, _FakeBus, seen


# A distinctive historical event (error -> RUN_ERROR) for ?since= replay, so its
# presence/absence in the stream is unambiguous vs. the live launch frame.
_REPLAY_ERROR_EVENT = {
    "id": "evt-old",
    "kind": "error",
    "terminal_id": "t-1",
    "session_name": "s",
    "timestamp": "2026-07-04T00:00:00Z",
    "detail": {"event_type": "boom_error"},
}


def test_stream_replays_history_and_emits_state_frames(monkeypatch):
    monkeypatch.setattr(main, "is_auth_enabled", lambda: False)
    fake_log_cls, fake_bus_cls, seen = _make_fakes([_REPLAY_ERROR_EVENT])
    monkeypatch.setattr(
        "cli_agent_orchestrator.services.event_log_service.get_event_log",
        lambda: fake_log_cls(),
    )
    monkeypatch.setattr(
        "cli_agent_orchestrator.services.sse_bus.get_bus",
        lambda: fake_bus_cls(),
    )

    # ``since`` earlier than the historical event => it is replayed.
    with client.stream("GET", "/agui/v1/stream", params={"since": "2026-07-03T00:00:00Z"}) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    # The endpoint forwarded the query value into event_log.history(since=...).
    assert seen["since"] == "2026-07-03T00:00:00Z"
    # Replayed error frame + connect snapshot + live launch frame all present.
    assert "RUN_ERROR" in body  # from the replayed historical event
    assert "STATE_SNAPSHOT" in body
    assert "STEP_STARTED" in body  # from the live launch event
    assert "event:" in body and "data:" in body


def test_stream_since_excludes_older_history(monkeypatch):
    """``since`` newer than the historical event => it is filtered out, proving
    the value reaches event_log.history rather than being ignored (the previous
    stub returned the event regardless of ``since``)."""
    monkeypatch.setattr(main, "is_auth_enabled", lambda: False)
    fake_log_cls, fake_bus_cls, seen = _make_fakes([_REPLAY_ERROR_EVENT])
    monkeypatch.setattr(
        "cli_agent_orchestrator.services.event_log_service.get_event_log",
        lambda: fake_log_cls(),
    )
    monkeypatch.setattr(
        "cli_agent_orchestrator.services.sse_bus.get_bus",
        lambda: fake_bus_cls(),
    )

    with client.stream("GET", "/agui/v1/stream", params={"since": "2026-07-04T12:00:00Z"}) as resp:
        assert resp.status_code == 200
        body = "".join(resp.iter_text())

    assert seen["since"] == "2026-07-04T12:00:00Z"
    assert "RUN_ERROR" not in body  # historical event filtered out by since
    assert "STATE_SNAPSHOT" in body  # connect snapshot still emitted
    assert "STEP_STARTED" in body  # live launch frame still present


def test_stream_rejects_malformed_token(monkeypatch):
    """A malformed/expired JWT must fail closed as a clean 401, not a 500."""
    import jwt

    monkeypatch.setattr(main, "is_auth_enabled", lambda: True)

    def _raise(_tok):
        raise jwt.InvalidTokenError("malformed")

    monkeypatch.setattr(main, "extract_scopes_from_token", _raise)
    resp = client.get("/agui/v1/stream", params={"access_token": "not-a-jwt"})
    assert resp.status_code == 401
    assert "invalid or expired" in resp.text.lower()


def test_extract_ws_scopes_malformed_token_returns_none(monkeypatch):
    """_extract_ws_scopes fails closed (None -> caller closes 4401) on a bad
    bearer-subprotocol token rather than surfacing an opaque handshake error."""
    import jwt

    monkeypatch.setattr(main, "is_auth_enabled", lambda: True)

    def _raise(_tok):
        raise jwt.ExpiredSignatureError("expired")

    monkeypatch.setattr(main, "extract_scopes_from_token", _raise)

    class _WS:
        def __init__(self, protos):
            self.scope = {"subprotocols": protos}

    ws = _WS([f"{main._SUBPROTOCOL_BEARER_PREFIX}deadbeef"])
    assert main._extract_ws_scopes(ws) is None


@pytest.mark.parametrize(
    "agui_flag, mcp_apps_on, expected",
    [
        (None, False, False),  # neither flag => default-off (byte-identical contract)
        ("true", False, True),  # dedicated AG-UI flag
        ("1", False, True),  # dedicated flag, alternate truthy spelling
        (None, True, True),  # enabled via the shared MCP Apps surface
        ("false", False, False),  # explicit off, MCP Apps also off
    ],
)
def test_agui_enabled_both_paths(monkeypatch, agui_flag, mcp_apps_on, expected):
    """_agui_enabled() is true via either CAO_AGUI_ENABLED or the shared MCP
    Apps surface, and false when neither is set (default-off)."""
    if agui_flag is None:
        monkeypatch.delenv("CAO_AGUI_ENABLED", raising=False)
    else:
        monkeypatch.setenv("CAO_AGUI_ENABLED", agui_flag)
    monkeypatch.setattr(main, "_mcp_apps_enabled", lambda: mcp_apps_on)
    assert main._agui_enabled() is expected
