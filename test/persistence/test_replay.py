"""Tests for WAL → materialized-index replay (commit 5).

Critical Phase 1 invariant: replaying the WAL produces a materialized
index whose contents match what SQLAlchemy would have written. This
test pins it via an end-to-end fixture: drive the database.py mutation
APIs (which write both SQLAlchemy and WAL), then replay the WAL into a
fresh index and assert the projected rows match.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cli_agent_orchestrator.clients.database import (
    Base,
    create_flow,
    create_inbox_message,
    create_terminal,
    delete_flow,
    delete_terminal,
    update_flow_enabled,
    update_flow_run_times,
    update_message_status,
)
from cli_agent_orchestrator.models.inbox import MessageStatus
from cli_agent_orchestrator.persistence import wal_writer
from cli_agent_orchestrator.persistence.materialized_index import (
    connect_index,
    query_flows,
    query_inbox,
    query_terminals,
)
from cli_agent_orchestrator.persistence.replay import replay_wal_into
from cli_agent_orchestrator.persistence.wal_writer import init_wal, shutdown_wal


@pytest.fixture
def wal_dir(tmp_path: Path):
    init_wal(tmp_path)
    yield tmp_path
    shutdown_wal()
    wal_writer._writer = None


@pytest.fixture
def inbox_db(tmp_path: Path):
    db_url = f"sqlite:///{tmp_path}/inbox.db"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with patch("cli_agent_orchestrator.clients.database.SessionLocal", Session):
        yield Session


@pytest.fixture
def index_conn(tmp_path: Path):
    conn = connect_index(tmp_path / "index.db")
    yield conn
    conn.close()


class TestReplayBasics:
    def test_empty_wal_dir_yields_zero_records(self, tmp_path: Path, index_conn):
        # Empty dir, no files.
        applied = replay_wal_into(index_conn, tmp_path)
        assert applied == 0
        assert query_terminals(index_conn) == []

    def test_missing_wal_dir_yields_zero_records(self, tmp_path: Path, index_conn):
        applied = replay_wal_into(index_conn, tmp_path / "does-not-exist")
        assert applied == 0


class TestReplayProjectsTerminalLifecycle:
    def test_create_then_delete_replays_to_empty_terminals(self, wal_dir, inbox_db, index_conn):
        create_terminal("term-1", "session-A", "win-0", "kiro_cli")
        create_terminal("term-2", "session-A", "win-1", "kiro_cli")
        delete_terminal("term-1")

        applied = replay_wal_into(index_conn, wal_dir)
        assert applied == 3
        rows = query_terminals(index_conn)
        assert [r["id"] for r in rows] == ["term-2"]


class TestReplayProjectsInboxLifecycle:
    def test_create_then_status_update_replays_correctly(self, wal_dir, inbox_db, index_conn):
        create_terminal("term-B", "session-A", "win-0", "kiro_cli")
        msg = create_inbox_message("term-A", "term-B", "sensitive body")
        update_message_status(msg.id, MessageStatus.DELIVERED)

        replay_wal_into(index_conn, wal_dir)
        rows = query_inbox(index_conn)
        assert len(rows) == 1
        assert rows[0]["sender_id"] == "term-A"
        assert rows[0]["receiver_id"] == "term-B"
        assert rows[0]["status"] == "delivered"
        # Critical invariant: the body never reaches the index.
        assert "message" not in rows[0]
        # And nowhere else either.
        assert "sensitive body" not in json.dumps(rows[0])


class TestReplayProjectsFlowLifecycle:
    def test_full_flow_lifecycle_replays_correctly(self, wal_dir, inbox_db, index_conn):
        next_run = datetime(2026, 6, 1, 9, 0, 0)
        create_flow(
            name="morning",
            file_path="/tmp/m.md",
            schedule="0 9 * * *",
            agent_profile="developer",
            provider="kiro_cli",
            script="hi",
            next_run=next_run,
        )
        last = datetime(2026, 6, 2, 9, 0, 0)
        nxt = datetime(2026, 6, 3, 9, 0, 0)
        update_flow_run_times("morning", last, nxt)
        update_flow_enabled("morning", enabled=False)

        replay_wal_into(index_conn, wal_dir)
        rows = query_flows(index_conn)
        assert len(rows) == 1
        assert rows[0]["enabled"] == 0
        assert rows[0]["last_run"] == last.isoformat()
        assert rows[0]["next_run"] == nxt.isoformat()

    def test_delete_flow_removes_from_index(self, wal_dir, inbox_db, index_conn):
        next_run = datetime(2026, 6, 1, 9, 0, 0)
        create_flow(
            name="dropme",
            file_path="/tmp/d.md",
            schedule="*",
            agent_profile="x",
            provider="kiro_cli",
            script="x",
            next_run=next_run,
        )
        delete_flow("dropme")
        replay_wal_into(index_conn, wal_dir)
        assert query_flows(index_conn) == []


class TestReplayIdempotence:
    def test_replay_twice_produces_same_state(self, wal_dir, inbox_db, index_conn):
        create_terminal("term-1", "session-A", "win-0", "kiro_cli")
        create_terminal("term-B", "session-A", "win-1", "kiro_cli")
        msg = create_inbox_message("term-A", "term-B", "ping")
        update_message_status(msg.id, MessageStatus.DELIVERED)

        replay_wal_into(index_conn, wal_dir)
        first_terminals = query_terminals(index_conn)
        first_inbox = query_inbox(index_conn)

        # Replay again on the same connection.
        replay_wal_into(index_conn, wal_dir)
        assert query_terminals(index_conn) == first_terminals
        assert query_inbox(index_conn) == first_inbox


class TestReplayResilience:
    def test_unknown_op_is_skipped(self, tmp_path: Path, index_conn):
        # Hand-craft a WAL file with an unknown op alongside a known op.
        log = tmp_path / "20260501.log"
        records = [
            {
                "op": "create_terminal",
                "ts": "2026-05-01T00:00:00+00:00",
                "payload": {
                    "id": "t1",
                    "tmux_session": "s",
                    "tmux_window": "w",
                    "provider": "kiro_cli",
                },
                "traceparent": None,
            },
            {
                "op": "this_op_does_not_exist",
                "ts": "2026-05-01T00:00:01+00:00",
                "payload": {"id": "t2"},
                "traceparent": None,
            },
            {
                "op": "create_terminal",
                "ts": "2026-05-01T00:00:02+00:00",
                "payload": {
                    "id": "t3",
                    "tmux_session": "s",
                    "tmux_window": "w",
                    "provider": "kiro_cli",
                },
                "traceparent": None,
            },
        ]
        log.write_text("\n".join(json.dumps(r) for r in records) + "\n")

        applied = replay_wal_into(index_conn, tmp_path)
        # Two known ops applied, one unknown skipped.
        assert applied == 2
        ids = [r["id"] for r in query_terminals(index_conn)]
        assert ids == ["t1", "t3"]

    def test_malformed_json_line_is_skipped(self, tmp_path: Path, index_conn):
        log = tmp_path / "20260501.log"
        log.write_text(
            json.dumps(
                {
                    "op": "create_terminal",
                    "ts": "2026-05-01T00:00:00+00:00",
                    "payload": {
                        "id": "ok",
                        "tmux_session": "s",
                        "tmux_window": "w",
                        "provider": "kiro_cli",
                    },
                    "traceparent": None,
                }
            )
            + "\n"
            + "{this is not valid json\n"
            + json.dumps(
                {
                    "op": "create_terminal",
                    "ts": "2026-05-01T00:00:01+00:00",
                    "payload": {
                        "id": "ok2",
                        "tmux_session": "s",
                        "tmux_window": "w",
                        "provider": "kiro_cli",
                    },
                    "traceparent": None,
                }
            )
            + "\n"
        )
        applied = replay_wal_into(index_conn, tmp_path)
        assert applied == 2
        ids = [r["id"] for r in query_terminals(index_conn)]
        assert ids == ["ok", "ok2"]
