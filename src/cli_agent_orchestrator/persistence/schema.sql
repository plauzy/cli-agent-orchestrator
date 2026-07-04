-- CAO v2.5 materialized index schema (Phase 1 / commit 5).
--
-- This is a read-side projection of the WAL (commit 4). The WAL is the
-- primary ingest log; this DB is a queryable index rebuilt on boot from
-- WAL replay. Phase 1 / v2.5.x: SQLAlchemy at clients/database.py is the
-- authoritative writer; this index is internal-only, read-only, and not
-- yet exposed to API consumers.
--
-- File format is plain SQLite — wire-compatible with libsql, so the
-- libsql-experimental swap in v2.6 is a one-line change at the connect
-- site (see persistence/materialized_index.py:connect_index).

CREATE TABLE IF NOT EXISTS terminals (
    id            TEXT PRIMARY KEY,
    tmux_session  TEXT NOT NULL,
    tmux_window   TEXT NOT NULL,
    provider      TEXT NOT NULL,
    agent_profile TEXT,
    allowed_tools TEXT  -- JSON-encoded list, mirrors the SQLAlchemy column
);

CREATE INDEX IF NOT EXISTS idx_terminals_session ON terminals(tmux_session);

CREATE TABLE IF NOT EXISTS inbox_messages (
    id          INTEGER PRIMARY KEY,
    sender_id   TEXT NOT NULL,
    receiver_id TEXT NOT NULL,
    status      TEXT NOT NULL
    -- Body is intentionally NOT projected here. The WAL excludes message
    -- bodies (see clients/database.py:create_inbox_message), so the
    -- index can only ever hold metadata. This is a deliberate privacy
    -- boundary: the materialized index is for query-time observability,
    -- not message archival.
);

CREATE INDEX IF NOT EXISTS idx_inbox_receiver ON inbox_messages(receiver_id);

CREATE TABLE IF NOT EXISTS flows (
    name          TEXT PRIMARY KEY,
    file_path     TEXT NOT NULL,
    schedule      TEXT NOT NULL,
    agent_profile TEXT NOT NULL,
    provider      TEXT NOT NULL,
    enabled       INTEGER NOT NULL DEFAULT 1,  -- bool encoded as 0/1
    last_run      TEXT,                         -- ISO datetime
    next_run      TEXT                          -- ISO datetime
);
