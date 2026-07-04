"""Append-only Write-Ahead Log for CAO state mutations.

Phase 1 / commit 4: WAL is **shadow** — SQLAlchemy stays the authoritative
writer; the WAL is appended after each successful ``db.commit()`` and never
read back at runtime in v2.5.x. The intent is that v2.6+ promotes the WAL to
"primary ingest" once the libsql materialized index (commit 5) and replay
path are confirmed byte-identical with the SQLAlchemy state.

Records are JSON-lines under ``WAL_DIR/{YYYYMMDD}.log``. Each record carries
the upstream W3C ``traceparent`` so a downstream replay can reconstruct the
full trace tree.

Initialization mirrors the OTel pattern:
  * ``init_wal(wal_dir)`` is called from the FastAPI lifespan.
  * Until called, ``wal_append`` is a no-op — keeping the existing test
    suite untouched and ensuring no filesystem writes during unit tests.
  * Errors during append are logged and swallowed; a WAL failure must
    never propagate to the caller (SQLAlchemy is authoritative).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from cli_agent_orchestrator.telemetry import inject_traceparent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WALRecord:
    """A single mutation appended to the WAL."""

    op: str
    payload: dict[str, Any]
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    traceparent: Optional[str] = None

    def to_json(self) -> str:
        """Serialize to a single JSON line (no trailing newline)."""
        return json.dumps(
            {
                "op": self.op,
                "ts": self.ts.isoformat(),
                "payload": self.payload,
                "traceparent": self.traceparent,
            },
            default=str,
            separators=(",", ":"),
        )


class WALWriter:
    """Thread-safe append-only writer with daily-rotated files + fsync."""

    def __init__(self, wal_dir: Path) -> None:
        self._wal_dir = wal_dir
        self._wal_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _current_path(self) -> Path:
        # UTC partitioning so a file's name uniquely identifies the local day.
        return self._wal_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%d')}.log"

    def append(self, record: WALRecord) -> int:
        """Append the record as a JSON line. Returns the byte offset of the line.

        Always fsyncs before returning so a successful return implies durable
        persistence. A successful SQLAlchemy commit followed by a WAL append
        failure is recoverable from SQLAlchemy on next boot — see the WAL
        coexistence note in the v2.5 plan.
        """
        line = record.to_json() + "\n"
        with self._lock:
            path = self._current_path()
            with open(path, "a", encoding="utf-8") as f:
                offset = f.tell()
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
            return offset

    def tail(self, since_offset: int = 0) -> Iterator[WALRecord]:
        """Yield records from today's file starting at ``since_offset``.

        Caller responsibility: ``since_offset`` must align to a record
        boundary (i.e. the offset returned by a prior ``append`` or 0). Used
        by tests today; the libsql tail-follower in commit 5 will be the
        first runtime consumer.
        """
        path = self._current_path()
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            f.seek(since_offset)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                yield WALRecord(
                    op=obj["op"],
                    payload=obj["payload"],
                    ts=datetime.fromisoformat(obj["ts"]),
                    traceparent=obj.get("traceparent"),
                )


# Module-level singleton — None until init_wal() is called.
_writer: Optional[WALWriter] = None


def init_wal(wal_dir: Path) -> None:
    """Activate the WAL writer at the given directory. Called from lifespan.

    Idempotent: only the first call installs a writer. Until called, the
    module-level ``wal_append`` is a no-op so the existing test suite
    doesn't accidentally write to the filesystem.
    """
    global _writer
    if _writer is not None:
        return
    _writer = WALWriter(wal_dir)
    logger.info("WAL writer initialized at %s", wal_dir)


def shutdown_wal() -> None:
    """Detach the WAL writer. Subsequent ``wal_append`` calls become no-ops."""
    global _writer
    _writer = None


def wal_append(op: str, payload: dict[str, Any]) -> Optional[int]:
    """Append a mutation record to the WAL. Returns the offset, or None if disabled.

    Automatically captures the active OTel ``traceparent`` so callers don't
    have to import telemetry helpers. Errors are logged and swallowed —
    SQLAlchemy is authoritative; a WAL append must never fail the request.
    """
    writer = _writer
    if writer is None:
        return None
    try:
        record = WALRecord(op=op, payload=payload, traceparent=inject_traceparent())
        return writer.append(record)
    except Exception:
        logger.warning("WAL append failed for op=%s", op, exc_info=True)
        return None
