"""Tests for the queryable materialized index (commit 5).

The index is a read-side projection of the WAL. These tests exercise the
schema, the per-record mutators, and the query helpers directly — without
going through replay (replay is tested separately in test_replay.py).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from cli_agent_orchestrator.persistence.materialized_index import (
    connect_index,
    delete_flow,
    delete_terminal,
    delete_terminals_by_session,
    query_flows,
    query_inbox,
    query_terminals,
    reset_index,
    update_flow_enabled,
    update_flow_run_times,
    update_inbox_status,
    upsert_flow,
    upsert_inbox_message,
    upsert_terminal,
)


@pytest.fixture
def conn(tmp_path: Path):
    db = tmp_path / "cao-index.db"
    c = connect_index(db)
    yield c
    c.close()


class TestSchema:
    def test_schema_creates_three_tables(self, conn):
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
        names = [row["name"] for row in rows]
        assert "terminals" in names
        assert "inbox_messages" in names
        assert "flows" in names

    def test_connect_index_is_idempotent(self, tmp_path: Path):
        db = tmp_path / "cao-index.db"
        c1 = connect_index(db)
        c1.close()
        # Re-open on the same file. Schema must apply cleanly with no errors.
        c2 = connect_index(db)
        c2.close()


class TestTerminals:
    def test_upsert_terminal_inserts_row(self, conn):
        upsert_terminal(
            conn,
            {
                "id": "term-1",
                "tmux_session": "session-A",
                "tmux_window": "win-0",
                "provider": "kiro_cli",
                "agent_profile": "developer",
                "allowed_tools": ["fs_read", "fs_write"],
            },
        )
        rows = query_terminals(conn)
        assert len(rows) == 1
        assert rows[0]["id"] == "term-1"
        assert rows[0]["agent_profile"] == "developer"
        # allowed_tools is stored as JSON.
        import json as _json

        assert _json.loads(rows[0]["allowed_tools"]) == ["fs_read", "fs_write"]

    def test_upsert_terminal_is_idempotent_on_id_collision(self, conn):
        payload = {
            "id": "term-1",
            "tmux_session": "session-A",
            "tmux_window": "win-0",
            "provider": "kiro_cli",
            "agent_profile": "developer",
            "allowed_tools": None,
        }
        upsert_terminal(conn, payload)
        # Same id, different provider → row updated, count unchanged.
        upsert_terminal(conn, {**payload, "provider": "claude_code"})
        rows = query_terminals(conn)
        assert len(rows) == 1
        assert rows[0]["provider"] == "claude_code"

    def test_delete_terminal_removes_row(self, conn):
        upsert_terminal(
            conn,
            {
                "id": "term-1",
                "tmux_session": "session-A",
                "tmux_window": "win-0",
                "provider": "kiro_cli",
            },
        )
        delete_terminal(conn, "term-1")
        assert query_terminals(conn) == []

    def test_delete_terminals_by_session_scoped_to_session(self, conn):
        for i, session in enumerate(["A", "A", "B"]):
            upsert_terminal(
                conn,
                {
                    "id": f"term-{i}",
                    "tmux_session": session,
                    "tmux_window": "w",
                    "provider": "kiro_cli",
                },
            )
        delete_terminals_by_session(conn, "A")
        rows = query_terminals(conn)
        assert len(rows) == 1
        assert rows[0]["tmux_session"] == "B"


class TestInbox:
    def test_upsert_inbox_message_persists_metadata_only(self, conn):
        upsert_inbox_message(
            conn,
            {
                "id": 42,
                "sender_id": "term-A",
                "receiver_id": "term-B",
                "status": "pending",
            },
        )
        rows = query_inbox(conn)
        assert len(rows) == 1
        # The schema must NOT have a message column.
        assert "message" not in rows[0]
        assert rows[0]["sender_id"] == "term-A"
        assert rows[0]["status"] == "pending"

    def test_update_inbox_status_changes_status(self, conn):
        upsert_inbox_message(
            conn,
            {"id": 1, "sender_id": "A", "receiver_id": "B", "status": "pending"},
        )
        update_inbox_status(conn, {"id": 1, "status": "delivered"})
        assert query_inbox(conn)[0]["status"] == "delivered"

    def test_query_inbox_by_receiver(self, conn):
        upsert_inbox_message(
            conn, {"id": 1, "sender_id": "A", "receiver_id": "B", "status": "pending"}
        )
        upsert_inbox_message(
            conn, {"id": 2, "sender_id": "A", "receiver_id": "C", "status": "pending"}
        )
        rows = query_inbox(conn, receiver_id="B")
        assert len(rows) == 1
        assert rows[0]["id"] == 1


class TestFlows:
    def test_upsert_flow_inserts_with_enabled_default_true(self, conn):
        upsert_flow(
            conn,
            {
                "name": "morning",
                "file_path": "/tmp/m.md",
                "schedule": "0 9 * * *",
                "agent_profile": "developer",
                "provider": "kiro_cli",
                "next_run": "2026-06-01T09:00:00",
            },
        )
        rows = query_flows(conn)
        assert len(rows) == 1
        assert rows[0]["enabled"] == 1  # boolean encoded as int
        assert rows[0]["last_run"] is None
        assert rows[0]["next_run"] == "2026-06-01T09:00:00"

    def test_update_flow_run_times(self, conn):
        upsert_flow(
            conn,
            {
                "name": "morning",
                "file_path": "/tmp/m.md",
                "schedule": "0 9 * * *",
                "agent_profile": "developer",
                "provider": "kiro_cli",
                "next_run": None,
            },
        )
        update_flow_run_times(
            conn,
            {
                "name": "morning",
                "last_run": "2026-06-02T09:00:00",
                "next_run": "2026-06-03T09:00:00",
            },
        )
        row = query_flows(conn)[0]
        assert row["last_run"] == "2026-06-02T09:00:00"
        assert row["next_run"] == "2026-06-03T09:00:00"

    def test_update_flow_enabled_with_next_run(self, conn):
        upsert_flow(
            conn,
            {
                "name": "f",
                "file_path": "/tmp/f.md",
                "schedule": "*",
                "agent_profile": "x",
                "provider": "kiro_cli",
                "next_run": None,
            },
        )
        update_flow_enabled(
            conn, {"name": "f", "enabled": False, "next_run": "2026-07-01T00:00:00"}
        )
        row = query_flows(conn)[0]
        assert row["enabled"] == 0
        assert row["next_run"] == "2026-07-01T00:00:00"

    def test_delete_flow_removes_row(self, conn):
        upsert_flow(
            conn,
            {
                "name": "f",
                "file_path": "/tmp/f.md",
                "schedule": "*",
                "agent_profile": "x",
                "provider": "kiro_cli",
                "next_run": None,
            },
        )
        delete_flow(conn, "f")
        assert query_flows(conn) == []


class TestResetIndex:
    def test_reset_truncates_all_three_tables(self, conn):
        upsert_terminal(
            conn,
            {"id": "t", "tmux_session": "s", "tmux_window": "w", "provider": "kiro_cli"},
        )
        upsert_inbox_message(
            conn, {"id": 1, "sender_id": "A", "receiver_id": "B", "status": "pending"}
        )
        upsert_flow(
            conn,
            {
                "name": "f",
                "file_path": "/tmp/f",
                "schedule": "*",
                "agent_profile": "x",
                "provider": "kiro_cli",
                "next_run": None,
            },
        )
        reset_index(conn)
        assert query_terminals(conn) == []
        assert query_inbox(conn) == []
        assert query_flows(conn) == []
