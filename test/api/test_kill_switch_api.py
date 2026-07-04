"""Tests for the Phase 4 kill-switch operator API.

Covers GET /asi/kill-switch and POST /asi/kill-switch/clear.
Both endpoints are guarded by app.state.kill_switch — when the Deacon
is disabled (CAO_ASI_DISABLED=true), the GET reports unavailable and
the POST returns 404.
"""

from __future__ import annotations

from cli_agent_orchestrator.api.main import app
from cli_agent_orchestrator.observability import KillSwitchState


class TestGetKillSwitchState:
    def test_returns_killed_classes(self, client):
        state = KillSwitchState()
        state.kill("research_breadth")
        state.kill("code_review")
        app.state.kill_switch = state
        try:
            resp = client.get("/asi/kill-switch")
            assert resp.status_code == 200
            body = resp.json()
            assert body["available"] is True
            assert sorted(body["killed"]) == ["code_review", "research_breadth"]
        finally:
            del app.state.kill_switch

    def test_returns_empty_when_no_kills(self, client):
        app.state.kill_switch = KillSwitchState()
        try:
            resp = client.get("/asi/kill-switch")
            assert resp.status_code == 200
            assert resp.json() == {"killed": [], "available": True}
        finally:
            del app.state.kill_switch

    def test_returns_unavailable_when_deacon_disabled(self, client):
        # No app.state.kill_switch attribute → Deacon is off.
        if hasattr(app.state, "kill_switch"):
            del app.state.kill_switch
        resp = client.get("/asi/kill-switch")
        assert resp.status_code == 200
        assert resp.json() == {"killed": [], "available": False}


class TestClearKillSwitch:
    def test_clear_single_task_class(self, client):
        state = KillSwitchState()
        state.kill("research_breadth")
        state.kill("code_review")
        app.state.kill_switch = state
        try:
            resp = client.post("/asi/kill-switch/clear?task_class=research_breadth")
            assert resp.status_code == 200
            body = resp.json()
            assert body["killed"] == ["code_review"]
            assert body["available"] is True
            assert state.killed_classes() == {"code_review"}
        finally:
            del app.state.kill_switch

    def test_clear_all_when_no_task_class(self, client):
        state = KillSwitchState()
        state.kill("a")
        state.kill("b")
        state.kill("c")
        app.state.kill_switch = state
        try:
            resp = client.post("/asi/kill-switch/clear")
            assert resp.status_code == 200
            body = resp.json()
            assert body["killed"] == []
            assert state.killed_classes() == set()
        finally:
            del app.state.kill_switch

    def test_clear_unknown_class_is_noop(self, client):
        # Clearing a class that was never killed is a no-op (matches
        # KillSwitchState.clear semantics).
        state = KillSwitchState()
        state.kill("research")
        app.state.kill_switch = state
        try:
            resp = client.post("/asi/kill-switch/clear?task_class=never_killed")
            assert resp.status_code == 200
            body = resp.json()
            # research_breadth still killed.
            assert body["killed"] == ["research"]
        finally:
            del app.state.kill_switch

    def test_404_when_deacon_disabled(self, client):
        if hasattr(app.state, "kill_switch"):
            del app.state.kill_switch
        resp = client.post("/asi/kill-switch/clear")
        assert resp.status_code == 404
        assert "CAO_ASI_DISABLED" in resp.json()["detail"]
