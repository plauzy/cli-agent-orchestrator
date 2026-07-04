"""Tests for the append-only WAL writer.

Phase 1 / commit 4 invariants:
  * ``wal_append`` is a no-op until ``init_wal`` is called (matches the
    OTel opt-in pattern). The existing 1554-test suite must stay green
    without a single line written to disk.
  * Every record persists as a JSON line under ``WAL_DIR/{YYYYMMDD}.log``
    and is durable on the file before ``append`` returns (fsync).
  * ``WALWriter.tail`` round-trips a record byte-identically — required by
    commit 5's libsql replay path.
  * Errors during append are swallowed; SQLAlchemy is authoritative and a
    WAL append failure must never propagate to the caller.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from cli_agent_orchestrator.persistence import wal_writer
from cli_agent_orchestrator.persistence.wal_writer import (
    WALRecord,
    WALWriter,
    init_wal,
    shutdown_wal,
    wal_append,
)

_VALID_TRACEPARENT = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"


@pytest.fixture(autouse=True)
def _reset_writer_singleton():
    """Each test starts with no installed writer (mirrors the OTel pattern)."""
    wal_writer._writer = None
    yield
    wal_writer._writer = None


# ---------------------------------------------------------------------------
# Default no-op behaviour
# ---------------------------------------------------------------------------


class TestNoopByDefault:
    def test_wal_append_returns_none_when_not_initialized(self):
        # init_wal has not been called.
        assert wal_writer._writer is None
        assert wal_append("create_terminal", {"id": "abc"}) is None

    def test_shutdown_without_init_is_noop(self):
        shutdown_wal()
        assert wal_writer._writer is None


# ---------------------------------------------------------------------------
# init_wal / shutdown_wal lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_init_installs_writer(self, tmp_path: Path):
        init_wal(tmp_path)
        assert isinstance(wal_writer._writer, WALWriter)

    def test_init_is_idempotent(self, tmp_path: Path):
        init_wal(tmp_path)
        first = wal_writer._writer
        init_wal(tmp_path)
        assert wal_writer._writer is first

    def test_shutdown_clears_writer(self, tmp_path: Path):
        init_wal(tmp_path)
        shutdown_wal()
        assert wal_writer._writer is None
        # And subsequent appends become no-ops again.
        assert wal_append("noop", {}) is None


# ---------------------------------------------------------------------------
# Record format + round-trip
# ---------------------------------------------------------------------------


class TestRecordFormat:
    def test_to_json_includes_required_fields(self):
        rec = WALRecord(
            op="create_terminal",
            payload={"id": "abc"},
            ts=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
            traceparent=_VALID_TRACEPARENT,
        )
        decoded = json.loads(rec.to_json())
        assert decoded["op"] == "create_terminal"
        assert decoded["payload"] == {"id": "abc"}
        assert decoded["ts"] == "2026-05-01T12:00:00+00:00"
        assert decoded["traceparent"] == _VALID_TRACEPARENT

    def test_to_json_with_no_traceparent_emits_null(self):
        rec = WALRecord(op="x", payload={})
        decoded = json.loads(rec.to_json())
        assert decoded["traceparent"] is None


# ---------------------------------------------------------------------------
# WALWriter direct tests (separate from the module-level singleton)
# ---------------------------------------------------------------------------


class TestWALWriter:
    def test_append_writes_jsonl_line_to_dated_file(self, tmp_path: Path):
        writer = WALWriter(tmp_path)
        rec = WALRecord(op="create_terminal", payload={"id": "abc"})
        writer.append(rec)

        files = list(tmp_path.glob("*.log"))
        assert len(files) == 1
        # File name matches the YYYYMMDD UTC pattern.
        assert files[0].stem == datetime.now(timezone.utc).strftime("%Y%m%d")

        content = files[0].read_text(encoding="utf-8")
        assert content.endswith("\n")
        # Exactly one record on disk.
        lines = [ln for ln in content.splitlines() if ln]
        assert len(lines) == 1
        decoded = json.loads(lines[0])
        assert decoded["op"] == "create_terminal"
        assert decoded["payload"] == {"id": "abc"}

    def test_multiple_appends_are_each_a_separate_line(self, tmp_path: Path):
        writer = WALWriter(tmp_path)
        for i in range(5):
            writer.append(WALRecord(op="x", payload={"i": i}))

        path = next(tmp_path.glob("*.log"))
        lines = [json.loads(ln) for ln in path.read_text().splitlines() if ln]
        assert [r["payload"]["i"] for r in lines] == [0, 1, 2, 3, 4]

    def test_append_returns_strictly_increasing_offsets(self, tmp_path: Path):
        writer = WALWriter(tmp_path)
        offsets = [writer.append(WALRecord(op="x", payload={"i": i})) for i in range(3)]
        assert offsets[0] < offsets[1] < offsets[2]
        # First append starts at offset 0.
        assert offsets[0] == 0

    def test_tail_yields_records_in_order(self, tmp_path: Path):
        writer = WALWriter(tmp_path)
        for i in range(3):
            writer.append(WALRecord(op="op", payload={"i": i}))

        records = list(writer.tail())
        assert [r.payload["i"] for r in records] == [0, 1, 2]
        assert all(r.op == "op" for r in records)

    def test_tail_from_offset_yields_only_subsequent_records(self, tmp_path: Path):
        writer = WALWriter(tmp_path)
        writer.append(WALRecord(op="op", payload={"i": 0}))
        offset = writer.append(WALRecord(op="op", payload={"i": 1}))
        writer.append(WALRecord(op="op", payload={"i": 2}))

        records = list(writer.tail(since_offset=offset))
        # The second record (at `offset`) and onward.
        assert [r.payload["i"] for r in records] == [1, 2]

    def test_tail_on_empty_dir_yields_nothing(self, tmp_path: Path):
        writer = WALWriter(tmp_path)
        assert list(writer.tail()) == []


# ---------------------------------------------------------------------------
# Module-level wal_append integration
# ---------------------------------------------------------------------------


class TestModuleAppend:
    def test_wal_append_persists_when_initialized(self, tmp_path: Path):
        init_wal(tmp_path)
        offset = wal_append("create_terminal", {"id": "abc"})
        assert offset == 0
        # File exists and contains the record.
        path = next(tmp_path.glob("*.log"))
        decoded = json.loads(path.read_text().splitlines()[0])
        assert decoded["op"] == "create_terminal"
        assert decoded["payload"] == {"id": "abc"}

    def test_wal_append_swallows_writer_errors(self, tmp_path: Path):
        """A WAL append failure must never propagate to the caller."""
        init_wal(tmp_path)

        with patch.object(wal_writer._writer, "append", side_effect=OSError("disk full")):
            # Must not raise.
            result = wal_append("create_terminal", {"id": "abc"})
        assert result is None
