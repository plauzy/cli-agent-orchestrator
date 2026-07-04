"""Integration tests asserting that database.py state mutations append to the WAL.

These tests confirm the full chain: a successful ``db.commit()`` is followed
by a ``wal_append`` with the expected ``op`` and a payload that excludes
sensitive fields (e.g., inbox message body).
"""

from __future__ import annotations

import json
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
    delete_terminals_by_session,
    update_flow_enabled,
    update_flow_run_times,
    update_message_status,
)
from cli_agent_orchestrator.models.inbox import MessageStatus
from cli_agent_orchestrator.persistence import wal_writer
from cli_agent_orchestrator.persistence.wal_writer import init_wal, shutdown_wal


@pytest.fixture
def wal_dir(tmp_path: Path):
    """Initialise the WAL writer at a tmp path for the duration of the test."""
    init_wal(tmp_path)
    yield tmp_path
    shutdown_wal()
    wal_writer._writer = None


@pytest.fixture
def inbox_db(tmp_path: Path):
    """Real SQLite DB with the full schema, scoped to the test."""
    db_url = f"sqlite:///{tmp_path}/inbox.db"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with patch("cli_agent_orchestrator.clients.database.SessionLocal", Session):
        yield Session


def _read_wal_ops(wal_dir: Path) -> list[dict]:
    """Read every JSON record from the dated WAL files in ``wal_dir``."""
    records: list[dict] = []
    for log_file in sorted(wal_dir.glob("*.log")):
        for line in log_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


class TestTerminalLifecycleAppendsToWAL:
    def test_create_terminal_writes_create_terminal_op(self, wal_dir, inbox_db):
        create_terminal("term-1", "session-A", "win-0", "kiro_cli")
        recs = _read_wal_ops(wal_dir)
        assert len(recs) == 1
        assert recs[0]["op"] == "create_terminal"
        assert recs[0]["payload"]["id"] == "term-1"
        assert recs[0]["payload"]["provider"] == "kiro_cli"

    def test_delete_terminal_writes_delete_terminal_op_only_when_deleted(self, wal_dir, inbox_db):
        create_terminal("term-2", "session-B", "win-0", "kiro_cli")
        # Sanity: a create record exists.
        before = _read_wal_ops(wal_dir)
        assert before[-1]["op"] == "create_terminal"

        delete_terminal("term-2")
        after = _read_wal_ops(wal_dir)
        assert after[-1]["op"] == "delete_terminal"
        assert after[-1]["payload"] == {"id": "term-2"}

    def test_delete_terminal_does_not_write_when_no_match(self, wal_dir, inbox_db):
        delete_terminal("does-not-exist")
        recs = _read_wal_ops(wal_dir)
        assert recs == []

    def test_delete_terminals_by_session_writes_aggregate_op(self, wal_dir, inbox_db):
        create_terminal("term-3", "session-C", "win-0", "kiro_cli")
        create_terminal("term-4", "session-C", "win-1", "kiro_cli")
        delete_terminals_by_session("session-C")

        delete_recs = [
            r for r in _read_wal_ops(wal_dir) if r["op"] == "delete_terminals_by_session"
        ]
        assert len(delete_recs) == 1
        assert delete_recs[0]["payload"] == {"tmux_session": "session-C", "count": 2}


class TestInboxAppendsToWAL:
    def test_create_inbox_message_writes_metadata_only(self, wal_dir, inbox_db):
        create_terminal("term-B", "session-A", "win-0", "kiro_cli")
        secret_body = "PASSWORD=hunter2 — please do not log me"
        create_inbox_message("term-A", "term-B", secret_body)

        recs = [r for r in _read_wal_ops(wal_dir) if r["op"] == "create_inbox_message"]
        assert len(recs) == 1
        payload = recs[0]["payload"]
        # The body must NOT appear in the WAL.
        assert "message" not in payload
        assert secret_body not in json.dumps(payload)
        # But the metadata is recorded.
        assert payload["sender_id"] == "term-A"
        assert payload["receiver_id"] == "term-B"
        assert payload["status"] == MessageStatus.PENDING.value

    def test_update_message_status_writes_status_op(self, wal_dir, inbox_db):
        create_terminal("term-B", "session-A", "win-0", "kiro_cli")
        msg = create_inbox_message("term-A", "term-B", "ping")
        update_message_status(msg.id, MessageStatus.DELIVERED)

        recs = [r for r in _read_wal_ops(wal_dir) if r["op"] == "update_message_status"]
        assert len(recs) == 1
        assert recs[0]["payload"] == {"id": msg.id, "status": "delivered"}


class TestFlowAppendsToWAL:
    def test_create_flow_writes_create_flow_op(self, wal_dir, inbox_db):
        next_run = datetime(2026, 6, 1, 12, 0, 0)
        create_flow(
            name="morning-trivia",
            file_path="/tmp/morning-trivia.md",
            schedule="0 9 * * *",
            agent_profile="developer",
            provider="kiro_cli",
            script="hello",
            next_run=next_run,
        )
        recs = [r for r in _read_wal_ops(wal_dir) if r["op"] == "create_flow"]
        assert len(recs) == 1
        assert recs[0]["payload"]["name"] == "morning-trivia"
        assert recs[0]["payload"]["next_run"] == next_run.isoformat()

    def test_update_flow_run_times_writes_op(self, wal_dir, inbox_db):
        next_run = datetime(2026, 6, 1, 12, 0, 0)
        create_flow(
            name="recurring",
            file_path="/tmp/recurring.md",
            schedule="0 9 * * *",
            agent_profile="developer",
            provider="kiro_cli",
            script="hi",
            next_run=next_run,
        )
        last = datetime(2026, 6, 2, 9, 0, 0)
        nxt = datetime(2026, 6, 3, 9, 0, 0)
        update_flow_run_times("recurring", last, nxt)

        recs = [r for r in _read_wal_ops(wal_dir) if r["op"] == "update_flow_run_times"]
        assert len(recs) == 1
        assert recs[0]["payload"]["last_run"] == last.isoformat()
        assert recs[0]["payload"]["next_run"] == nxt.isoformat()

    def test_update_flow_enabled_writes_op(self, wal_dir, inbox_db):
        next_run = datetime(2026, 6, 1, 12, 0, 0)
        create_flow(
            name="paused",
            file_path="/tmp/paused.md",
            schedule="0 9 * * *",
            agent_profile="developer",
            provider="kiro_cli",
            script="hi",
            next_run=next_run,
        )
        update_flow_enabled("paused", enabled=False)

        recs = [r for r in _read_wal_ops(wal_dir) if r["op"] == "update_flow_enabled"]
        assert len(recs) == 1
        assert recs[0]["payload"]["enabled"] is False

    def test_delete_flow_writes_op_only_when_deleted(self, wal_dir, inbox_db):
        next_run = datetime(2026, 6, 1, 12, 0, 0)
        create_flow(
            name="removable",
            file_path="/tmp/removable.md",
            schedule="0 9 * * *",
            agent_profile="developer",
            provider="kiro_cli",
            script="hi",
            next_run=next_run,
        )
        delete_flow("removable")
        delete_flow("does-not-exist")

        recs = [r for r in _read_wal_ops(wal_dir) if r["op"] == "delete_flow"]
        assert len(recs) == 1
        assert recs[0]["payload"] == {"name": "removable"}
