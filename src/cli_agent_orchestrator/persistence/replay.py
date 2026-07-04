"""Replay the WAL into the materialized index.

Phase 1 / commit 5: rebuilds the materialized index from the WAL on every
boot. Idempotent — replaying the same WAL files twice produces the same
final state. Used by the FastAPI lifespan to ensure the index reflects
whatever the WAL has recorded.

Records with unrecognised ``op`` values are logged and skipped — keeps the
replay forward-compatible when v2.6 introduces new mutation kinds.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Callable

from cli_agent_orchestrator.persistence import materialized_index as mi

logger = logging.getLogger(__name__)


# Map WAL op name → (conn, payload) handler. Keep this dispatch flat so a
# new mutation in v2.6 is one entry plus a corresponding mutator.
_HANDLERS: dict[str, Callable[[sqlite3.Connection, dict[str, Any]], None]] = {
    "create_terminal": mi.upsert_terminal,
    "delete_terminal": lambda c, p: mi.delete_terminal(c, p["id"]),
    "delete_terminals_by_session": lambda c, p: mi.delete_terminals_by_session(
        c, p["tmux_session"]
    ),
    "create_inbox_message": mi.upsert_inbox_message,
    "update_message_status": mi.update_inbox_status,
    "create_flow": mi.upsert_flow,
    "update_flow_run_times": mi.update_flow_run_times,
    "update_flow_enabled": mi.update_flow_enabled,
    "delete_flow": lambda c, p: mi.delete_flow(c, p["name"]),
}


def replay_wal_into(conn: sqlite3.Connection, wal_dir: Path) -> int:
    """Apply every WAL record in ``wal_dir`` to ``conn``. Returns the count.

    Truncates the projection tables first so the replay is from a clean
    slate — replays are full rebuilds in v2.5.x. Files are processed in
    name order (YYYYMMDD.log), and within a file in line order.

    Unknown ops are logged at WARNING and skipped.
    """
    mi.reset_index(conn)

    applied = 0
    if not wal_dir.exists():
        return 0

    for log_file in sorted(wal_dir.glob("*.log")):
        with open(log_file, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed WAL line %s:%d", log_file.name, line_no)
                    continue

                op = record.get("op")
                payload = record.get("payload", {})
                handler = _HANDLERS.get(op)
                if handler is None:
                    logger.warning(
                        "Skipping unknown WAL op %r at %s:%d", op, log_file.name, line_no
                    )
                    continue

                try:
                    handler(conn, payload)
                    applied += 1
                except Exception:
                    # An individual replay failure must not abort the whole
                    # rebuild — log and continue. The next boot will re-try.
                    logger.warning(
                        "WAL replay error op=%s at %s:%d",
                        op,
                        log_file.name,
                        line_no,
                        exc_info=True,
                    )

    conn.commit()
    return applied
