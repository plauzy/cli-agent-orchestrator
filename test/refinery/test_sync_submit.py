"""Tests for the synchronous Refinery facade (v2.5 close-out, item 2).

Pins:
  * ``submit_sync`` runs the full Rule-of-Two + policy + WAL + execute +
    SSE pipeline (parity with the async ``submit``).
  * Sync writes are serialized through ``threading.Lock`` so two threads
    cannot race a commit.
  * ``submit_sync_or_run`` falls back to running the executor directly
    when no queue is bound (preserves v1.x semantics for tests / CLI).
  * The 10 ``clients/database.py`` mutations route through Refinery
    when the module-level queue is bound (regression coverage for the
    Refinery rewiring).
"""

from __future__ import annotations

import threading
from typing import Any

import pytest

from cli_agent_orchestrator.refinery import (
    Policy,
    PolicyOutcome,
    RefineryDenied,
    RefineryEscalated,
    RefineryQueue,
    SyncWriteRequest,
    get_refinery_queue,
    set_refinery_queue,
    submit_sync_or_run,
)


class _DenyingPolicy:
    def evaluate(self, action: str, payload: dict[str, Any]) -> PolicyOutcome:
        return PolicyOutcome.DENY


class _EscalatingPolicy:
    def evaluate(self, action: str, payload: dict[str, Any]) -> PolicyOutcome:
        return PolicyOutcome.ESCALATE


class _RecordingWal:
    def __init__(self) -> None:
        self.entries: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, op: str, payload: dict[str, Any]):
        self.entries.append((op, payload))
        return None


class _RecordingSse:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def __call__(self, event: dict[str, Any]) -> None:
        self.events.append(event)


@pytest.fixture(autouse=True)
def _isolate_queue():
    """Ensure module-level queue is None before/after each test."""
    set_refinery_queue(None)
    yield
    set_refinery_queue(None)


class TestSubmitSync:
    def test_runs_executor_when_policy_allows(self):
        wal = _RecordingWal()
        sse = _RecordingSse()
        queue = RefineryQueue(wal_appender=wal, sse_emitter=sse)

        ran = []

        def executor():
            ran.append(True)
            return "ok"

        result = queue.submit_sync(
            SyncWriteRequest(action="create_terminal", payload={"id": "t1"}, executor=executor)
        )

        assert result.status == "completed"
        assert result.value == "ok"
        assert ran == [True]
        assert wal.entries == [("create_terminal", {"id": "t1"})]
        assert any(e["type"] == "refinery.completed" for e in sse.events)

    def test_returns_denied_without_running_executor(self):
        wal = _RecordingWal()
        queue = RefineryQueue(policy=_DenyingPolicy(), wal_appender=wal)

        ran = []

        def executor():
            ran.append(True)
            return "should not run"

        result = queue.submit_sync(
            SyncWriteRequest(action="bad_action", payload={}, executor=executor)
        )

        assert result.status == "denied"
        assert ran == []
        assert wal.entries == []  # WAL only appends on allowed path

    def test_escalation_returns_without_running(self):
        sse = _RecordingSse()
        queue = RefineryQueue(policy=_EscalatingPolicy(), sse_emitter=sse)

        ran = []

        def executor():
            ran.append(True)

        result = queue.submit_sync(SyncWriteRequest(action="touchy", payload={}, executor=executor))

        assert result.status == "escalated"
        assert ran == []
        assert any(e["type"] == "refinery.escalated" for e in sse.events)

    def test_executor_exception_propagates(self):
        queue = RefineryQueue()

        def boom():
            raise RuntimeError("commit failed")

        with pytest.raises(RuntimeError, match="commit failed"):
            queue.submit_sync(SyncWriteRequest(action="create_flow", payload={}, executor=boom))

    def test_threading_lock_serializes_two_writers(self):
        queue = RefineryQueue()

        active = 0
        max_active = 0
        lock = threading.Lock()

        def executor():
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            # Force overlap window — without the sync_lock, two threads
            # could be inside this region simultaneously.
            import time

            time.sleep(0.01)
            with lock:
                active -= 1
            return None

        threads = [
            threading.Thread(
                target=lambda: queue.submit_sync(
                    SyncWriteRequest(action="create_terminal", payload={}, executor=executor)
                )
            )
            for _ in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert max_active == 1, f"sync writers raced ({max_active} > 1)"
        assert queue.stats["allowed"] == 8


class TestSubmitSyncOrRun:
    def test_falls_back_when_no_queue_bound(self):
        """Tests / CLI call sites that don't initialize a queue still work."""
        ran = []

        def executor():
            ran.append(True)
            return 42

        out = submit_sync_or_run("create_terminal", {}, executor)

        assert ran == [True]
        assert out == 42

    def test_routes_through_queue_when_bound(self):
        wal = _RecordingWal()
        queue = RefineryQueue(wal_appender=wal)
        set_refinery_queue(queue)

        ran = []

        def executor():
            ran.append(True)
            return "value"

        out = submit_sync_or_run(
            "update_message_status",
            {"id": 1, "status": "DELIVERED"},
            executor,
        )

        assert ran == [True]
        assert out == "value"
        assert queue.stats["allowed"] == 1
        assert wal.entries == [("update_message_status", {"id": 1, "status": "DELIVERED"})]

    def test_denied_raises(self):
        queue = RefineryQueue(policy=_DenyingPolicy())
        set_refinery_queue(queue)

        with pytest.raises(RefineryDenied):
            submit_sync_or_run("blocked_action", {}, lambda: None)

    def test_escalated_raises(self):
        queue = RefineryQueue(policy=_EscalatingPolicy())
        set_refinery_queue(queue)

        with pytest.raises(RefineryEscalated):
            submit_sync_or_run("touchy", {}, lambda: None)


class TestDatabaseRewiring:
    """Pin: every database.py mutation actually flows through Refinery
    when a queue is bound. Catches future regressions where someone
    re-introduces a direct ``db.commit()`` without the gate."""

    @pytest.fixture
    def isolated_db(self, tmp_path, monkeypatch):
        """Re-bind ``database.py`` to a per-test sqlite file."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from cli_agent_orchestrator.clients import database as db_mod

        engine = create_engine(
            f"sqlite:///{tmp_path / 'regression.db'}",
            connect_args={"check_same_thread": False},
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        monkeypatch.setattr(db_mod, "engine", engine)
        monkeypatch.setattr(db_mod, "SessionLocal", SessionLocal)
        db_mod.Base.metadata.create_all(bind=engine)
        return db_mod

    def test_create_terminal_routes_through_queue(self, isolated_db):
        wal = _RecordingWal()
        queue = RefineryQueue(wal_appender=wal)
        set_refinery_queue(queue)

        isolated_db.create_terminal(
            terminal_id="abc",
            tmux_session="s1",
            tmux_window="w1",
            provider="claude_code",
        )

        assert queue.stats["allowed"] >= 1
        assert any(action == "create_terminal" for action, _ in wal.entries)

    def test_all_ten_mutations_route_through_queue(self, isolated_db):
        """Smoke-test every wrapped site to catch silent bypasses."""
        from datetime import datetime

        from cli_agent_orchestrator.models.inbox import MessageStatus

        wal = _RecordingWal()
        queue = RefineryQueue(wal_appender=wal)
        set_refinery_queue(queue)

        # Terminal lifecycle: create → update_last_active → delete.
        isolated_db.create_terminal("t1", "s1", "w1", "claude_code")
        isolated_db.update_last_active("t1")
        isolated_db.delete_terminal("t1")

        # Session-level cleanup.
        isolated_db.create_terminal("t2", "s2", "w2", "claude_code")
        isolated_db.delete_terminals_by_session("s2")

        # Inbox flow.
        isolated_db.create_terminal("b", "s3", "w3", "claude_code")
        msg = isolated_db.create_inbox_message("a", "b", "hi")
        isolated_db.update_message_status(msg.id, MessageStatus.DELIVERED)

        # Flow lifecycle.
        next_run = datetime(2026, 6, 1, 12, 0, 0)
        isolated_db.create_flow(
            name="f1",
            file_path="/tmp/f1.yaml",
            schedule="@hourly",
            agent_profile="reviewer",
            provider="claude_code",
            script="echo hi",
            next_run=next_run,
        )
        isolated_db.update_flow_run_times("f1", datetime(2026, 6, 1), datetime(2026, 6, 2))
        isolated_db.update_flow_enabled("f1", False)
        isolated_db.delete_flow("f1")

        actions = {action for action, _ in wal.entries}
        # All 10 wrapped sites observed.
        assert {
            "create_terminal",
            "update_last_active",
            "delete_terminal",
            "delete_terminals_by_session",
            "create_inbox_message",
            "update_message_status",
            "create_flow",
            "update_flow_run_times",
            "update_flow_enabled",
            "delete_flow",
        } <= actions
