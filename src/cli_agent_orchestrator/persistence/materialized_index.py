"""Queryable materialized index over CAO state.

Phase 1 / commit 5: a read-side projection of the WAL. The WAL is the
primary ingest log; this index is a SQLite-backed file rebuilt on boot
from WAL replay (see ``replay.py``). Wire-compatible with libsql so the
v2.6 swap to ``libsql-experimental`` is a one-line change at
``connect_index``.

API surface is intentionally narrow in v2.5.x:
  * ``connect_index(path)`` opens the index DB and applies the schema.
  * ``query_terminals``, ``query_inbox``, ``query_flows`` return plain
    dicts. No ORM coupling.

The index is **read-only** for everything outside the persistence package.
SQLAlchemy at ``clients/database.py`` remains the authoritative writer;
the index reflects whatever the WAL replay tells it to.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable, Optional

_SCHEMA_FILE = Path(__file__).with_name("schema.sql")


def connect_index(db_path: Path) -> sqlite3.Connection:
    """Open the materialized index DB and ensure the schema is applied.

    Returns a ``sqlite3.Connection`` configured with ``row_factory =
    sqlite3.Row`` so callers can use both index- and key-based access.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA_FILE.read_text(encoding="utf-8"))
    conn.commit()
    return conn


def reset_index(conn: sqlite3.Connection) -> None:
    """Truncate every projection table — used before a full replay."""
    conn.execute("DELETE FROM terminals")
    conn.execute("DELETE FROM inbox_messages")
    conn.execute("DELETE FROM flows")
    conn.commit()


# ---------------------------------------------------------------------------
# Mutators (called by replay.py when applying a WAL record)
# ---------------------------------------------------------------------------


def upsert_terminal(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    import json as _json

    allowed = payload.get("allowed_tools")
    allowed_json = _json.dumps(allowed) if allowed else None
    conn.execute(
        """
        INSERT INTO terminals (id, tmux_session, tmux_window, provider,
                               agent_profile, allowed_tools)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            tmux_session  = excluded.tmux_session,
            tmux_window   = excluded.tmux_window,
            provider      = excluded.provider,
            agent_profile = excluded.agent_profile,
            allowed_tools = excluded.allowed_tools
        """,
        (
            payload["id"],
            payload["tmux_session"],
            payload["tmux_window"],
            payload["provider"],
            payload.get("agent_profile"),
            allowed_json,
        ),
    )


def delete_terminal(conn: sqlite3.Connection, terminal_id: str) -> None:
    conn.execute("DELETE FROM terminals WHERE id = ?", (terminal_id,))


def delete_terminals_by_session(conn: sqlite3.Connection, tmux_session: str) -> None:
    conn.execute("DELETE FROM terminals WHERE tmux_session = ?", (tmux_session,))


def upsert_inbox_message(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO inbox_messages (id, sender_id, receiver_id, status)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            sender_id   = excluded.sender_id,
            receiver_id = excluded.receiver_id,
            status      = excluded.status
        """,
        (
            payload["id"],
            payload["sender_id"],
            payload["receiver_id"],
            payload["status"],
        ),
    )


def update_inbox_status(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    conn.execute(
        "UPDATE inbox_messages SET status = ? WHERE id = ?",
        (payload["status"], payload["id"]),
    )


def upsert_flow(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO flows (name, file_path, schedule, agent_profile,
                           provider, enabled, last_run, next_run)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            file_path     = excluded.file_path,
            schedule      = excluded.schedule,
            agent_profile = excluded.agent_profile,
            provider      = excluded.provider,
            enabled       = excluded.enabled,
            last_run      = excluded.last_run,
            next_run      = excluded.next_run
        """,
        (
            payload["name"],
            payload["file_path"],
            payload["schedule"],
            payload["agent_profile"],
            payload["provider"],
            1,  # newly created flows are enabled
            None,
            payload.get("next_run"),
        ),
    )


def update_flow_run_times(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    conn.execute(
        "UPDATE flows SET last_run = ?, next_run = ? WHERE name = ?",
        (payload["last_run"], payload["next_run"], payload["name"]),
    )


def update_flow_enabled(conn: sqlite3.Connection, payload: dict[str, Any]) -> None:
    enabled_int = 1 if payload["enabled"] else 0
    if payload.get("next_run") is not None:
        conn.execute(
            "UPDATE flows SET enabled = ?, next_run = ? WHERE name = ?",
            (enabled_int, payload["next_run"], payload["name"]),
        )
    else:
        conn.execute(
            "UPDATE flows SET enabled = ? WHERE name = ?",
            (enabled_int, payload["name"]),
        )


def delete_flow(conn: sqlite3.Connection, name: str) -> None:
    conn.execute("DELETE FROM flows WHERE name = ?", (name,))


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def query_terminals(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute("SELECT * FROM terminals ORDER BY id")]


def query_inbox(
    conn: sqlite3.Connection, receiver_id: Optional[str] = None
) -> list[dict[str, Any]]:
    if receiver_id is not None:
        cursor = conn.execute(
            "SELECT * FROM inbox_messages WHERE receiver_id = ? ORDER BY id",
            (receiver_id,),
        )
    else:
        cursor = conn.execute("SELECT * FROM inbox_messages ORDER BY id")
    return [dict(row) for row in cursor]


def query_flows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute("SELECT * FROM flows ORDER BY name")]
