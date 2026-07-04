"""Tests for GET /events/history — feeds cao_fetch_history."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from cli_agent_orchestrator.services.event_log_service import (
    get_event_log,
    reset_event_log,
)


class TestEventsHistory:
    def setup_method(self) -> None:
        reset_event_log()

    def teardown_method(self) -> None:
        reset_event_log()

    def test_empty_log_returns_empty_list(self, client) -> None:  # type: ignore[no-untyped-def]
        resp = client.get("/events/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"events": [], "count": 0}

    def test_returns_recorded_events(self, client) -> None:  # type: ignore[no-untyped-def]
        log = get_event_log()
        log.append("launch", terminal_id="t1")
        log.append("handoff", terminal_id="t1")

        resp = client.get("/events/history")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        kinds = [e["kind"] for e in body["events"]]
        assert kinds == ["launch", "handoff"]

    def test_limit_clamps_results(self, client) -> None:  # type: ignore[no-untyped-def]
        log = get_event_log()
        for i in range(5):
            log.append("launch", detail={"i": i})

        resp = client.get("/events/history?limit=2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert [e["detail"]["i"] for e in body["events"]] == [3, 4]

    def test_since_filter(self, client) -> None:  # type: ignore[no-untyped-def]
        log = get_event_log()
        log.append("launch", timestamp=datetime.now(timezone.utc) - timedelta(hours=2))
        recent = log.append("launch")

        # ISO-8601 cutoff just before the recent event. Pass via params
        # so the `+` in the timezone offset is properly URL-encoded.
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        resp = client.get("/events/history", params={"since": cutoff})
        body = resp.json()
        assert body["count"] == 1
        assert body["events"][0]["id"] == recent["id"]

    def test_invalid_since_is_ignored(self, client) -> None:  # type: ignore[no-untyped-def]
        log = get_event_log()
        log.append("launch")

        resp = client.get("/events/history?since=not-a-date")
        body = resp.json()
        # Garbage `since` falls back to the default TTL window — record stays.
        assert body["count"] == 1
