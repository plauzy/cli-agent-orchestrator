"""Persistence primitives for CAO v2.5.

Phase 1 ships:
  * the append-only WAL writer (commit 4)
  * a SQLite-backed materialized index that mirrors the WAL via
    boot-time replay (commit 5)
"""

from cli_agent_orchestrator.persistence.materialized_index import (
    connect_index,
    query_flows,
    query_inbox,
    query_terminals,
    reset_index,
)
from cli_agent_orchestrator.persistence.replay import replay_wal_into
from cli_agent_orchestrator.persistence.wal_writer import (
    WALRecord,
    WALWriter,
    init_wal,
    shutdown_wal,
    wal_append,
)

__all__ = [
    "WALRecord",
    "WALWriter",
    "connect_index",
    "init_wal",
    "query_flows",
    "query_inbox",
    "query_terminals",
    "replay_wal_into",
    "reset_index",
    "shutdown_wal",
    "wal_append",
]
