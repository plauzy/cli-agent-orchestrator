"""Tests for traceparent propagation through CAO surfaces.

Phase 1 / commit 3 invariant: the W3C ``traceparent`` carrying upstream OTel
context flows through the inbox column and the plugin event payload only —
**never** through the message body or environment variables that would
echo into terminal output. Provider status-detection regex (``IDLE_PROMPT_PATTERN``,
``WAITING_USER_ANSWER`` patterns, etc.) match against pane bytes; any
extra prefix or suffix added to the user's message will silently break
idle detection.

These tests pin the invariant.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cli_agent_orchestrator.clients.database import (
    Base,
    InboxModel,
    _migrate_add_inbox_traceparent,
    create_inbox_message,
    create_terminal,
    get_inbox_messages,
    get_pending_messages,
)
from cli_agent_orchestrator.models.inbox import MessageStatus
from cli_agent_orchestrator.plugins.events import (
    CaoEvent,
    PostSendMessageEvent,
)

# A fixed valid W3C traceparent: version-trace_id-parent_id-flags
_VALID_TRACEPARENT = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"


# ---------------------------------------------------------------------------
# CaoEvent + PostSendMessageEvent carry traceparent
# ---------------------------------------------------------------------------


class TestCaoEventTraceparent:
    def test_base_event_default_is_none(self):
        ev = CaoEvent()
        assert ev.traceparent is None

    def test_base_event_accepts_traceparent(self):
        ev = CaoEvent(traceparent=_VALID_TRACEPARENT)
        assert ev.traceparent == _VALID_TRACEPARENT

    def test_post_send_message_inherits_traceparent_field(self):
        ev = PostSendMessageEvent(
            sender="term-A",
            receiver="term-B",
            message="ping",
            orchestration_type="send_message",
            traceparent=_VALID_TRACEPARENT,
        )
        assert ev.traceparent == _VALID_TRACEPARENT

    def test_post_send_message_default_traceparent_is_none(self):
        ev = PostSendMessageEvent(
            sender="term-A",
            receiver="term-B",
            message="ping",
            orchestration_type="send_message",
        )
        assert ev.traceparent is None


# ---------------------------------------------------------------------------
# inbox.traceparent column migration
# ---------------------------------------------------------------------------


class TestInboxTraceparentMigration:
    def test_migration_adds_traceparent_column_when_missing(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        # Simulate a pre-migration schema (no traceparent column).
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("""
                CREATE TABLE inbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id TEXT NOT NULL,
                    receiver_id TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at DATETIME
                )
                """)

        with patch("cli_agent_orchestrator.constants.DATABASE_FILE", db_path):
            _migrate_add_inbox_traceparent()

        with sqlite3.connect(str(db_path)) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(inbox)")}
        assert "traceparent" in cols

    def test_migration_is_idempotent(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("""
                CREATE TABLE inbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_id TEXT NOT NULL,
                    receiver_id TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at DATETIME,
                    traceparent TEXT
                )
                """)

        with patch("cli_agent_orchestrator.constants.DATABASE_FILE", db_path):
            # Should not raise when column already exists.
            _migrate_add_inbox_traceparent()
            _migrate_add_inbox_traceparent()


# ---------------------------------------------------------------------------
# create_inbox_message round-trip
# ---------------------------------------------------------------------------


@pytest.fixture
def inbox_db(tmp_path: Path):
    """Real SQLite DB with the full schema, scoped to the test."""
    db_url = f"sqlite:///{tmp_path}/inbox.db"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with patch("cli_agent_orchestrator.clients.database.SessionLocal", Session):
        # create_inbox_message validates the receiver exists, so seed it.
        create_terminal("term-B", "session-A", "win-0", "kiro_cli")
        yield Session


class TestCreateInboxMessageTraceparent:
    def test_persists_provided_traceparent(self, inbox_db):
        msg = create_inbox_message(
            sender_id="term-A",
            receiver_id="term-B",
            message="hello",
            traceparent=_VALID_TRACEPARENT,
        )
        assert msg.traceparent == _VALID_TRACEPARENT

        # Round-trip: re-fetch via get_pending_messages and confirm value preserved.
        pending = get_pending_messages("term-B")
        assert len(pending) == 1
        assert pending[0].traceparent == _VALID_TRACEPARENT

    def test_persists_none_when_omitted(self, inbox_db):
        msg = create_inbox_message(sender_id="term-A", receiver_id="term-B", message="hello")
        assert msg.traceparent is None
        pending = get_pending_messages("term-B")
        assert pending[0].traceparent is None

    def test_traceparent_does_not_pollute_message_body(self, inbox_db):
        """Critical invariant: traceparent must NEVER be appended to the message.

        Provider status-detection regex matches on terminal output. Any extra
        bytes mixed into ``message`` will be echoed by the TUI and break idle
        detection silently. This test pins that the body is byte-identical to
        the input.
        """
        body = "Please review PR #42"
        msg = create_inbox_message(
            sender_id="term-A",
            receiver_id="term-B",
            message=body,
            traceparent=_VALID_TRACEPARENT,
        )
        assert msg.message == body, (
            "traceparent must not appear in message body — "
            f"got {msg.message!r}, expected {body!r}"
        )
        # And once more after round-tripping through the DB.
        pending = get_pending_messages("term-B")
        assert pending[0].message == body
        assert _VALID_TRACEPARENT not in pending[0].message
