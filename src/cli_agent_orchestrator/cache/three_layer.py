"""Three-layer cache for CAO agent calls (Phase 5 / commit 24+).

The v2.5 plan specifies a three-layer cache to reduce latency and cost
on repeated agent calls:

  L1  In-process LRU + TTL  — request-level dedup within a single CAO
                              process. Plain functools.lru_cache can't
                              handle TTL eviction, so we ship a small
                              dict-based primitive with bounded size
                              and per-entry TTL.

  L2  Anthropic prompt-cache  — periodic keep-alive pings against
      keep-alive               Anthropic's 5-minute prompt cache TTL.
                               A 4-minute interval keeps hot prefixes
                               warm at the ~10% prompt-cache read cost
                               instead of full recompute. Lands in the
                               next commit alongside the orchestrator.

  L3  Cross-session SQLite    — durable cache across CAO restarts.
                               Keyed by a canonical hash of the request
                               envelope (messages + system + tools +
                               model). The Phase 1 WAL replay logic
                               doesn't touch this; L3 is best-effort
                               and lossy by design.

This module ships L1 + L3 as independent primitives with a clean
``CacheBackend`` Protocol. The orchestrator that composes them with
the L2 keep-alive scheduler lands in the next commit; this one is a
pure data-structures commit so it stays trivial to review.

Cache keys are derived from a request envelope via ``cache_key``,
which canonicalizes JSON before hashing. Two requests with reordered
keys, or differing whitespace, hash identically — the right semantics
for a content-addressed cache.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Cache key derivation
# ---------------------------------------------------------------------------


def cache_key(envelope: dict[str, Any]) -> str:
    """Stable content-addressed key for a request envelope.

    Canonicalizes the JSON (sorted keys, no whitespace) before hashing
    so two callers that build the same logical request get the same
    key regardless of dict ordering.
    """
    canonical = json.dumps(envelope, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Backend protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class CacheBackend(Protocol):
    """Minimal contract a cache layer must satisfy.

    All methods are synchronous; async wrappers belong in the
    orchestrator layer (commit 25). ``get`` returns ``None`` on miss
    rather than raising — callers always treat misses as a normal
    code path.
    """

    def get(self, key: str) -> Optional[Any]: ...

    def put(self, key: str, value: Any, *, ttl_seconds: Optional[float] = None) -> None: ...

    def delete(self, key: str) -> None: ...


# ---------------------------------------------------------------------------
# L1 — In-process LRU + TTL
# ---------------------------------------------------------------------------


@dataclass
class _L1Entry:
    value: Any
    expires_at: Optional[float]  # None → no TTL

    def is_expired(self, now: float) -> bool:
        return self.expires_at is not None and self.expires_at <= now


class L1Cache:
    """Bounded LRU with per-entry TTL.

    Eviction order (LRU) is determined by access time; ``get`` and
    ``put`` both touch the entry. TTL is enforced lazily on ``get`` —
    expired entries are deleted on access rather than eagerly. This
    is the simplest correct semantics; an active reaper would need a
    background task and adds no value at L1's expected size.

    Thread-safe: a single lock guards the ordered dict. CAO is
    asyncio-first but the WAL writer (Phase 1) and several plugin
    paths are sync, so the lock matters.
    """

    def __init__(
        self, *, max_size: int = 1024, default_ttl_seconds: Optional[float] = 300.0
    ) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        self._max_size = max_size
        self._default_ttl = default_ttl_seconds
        self._store: "OrderedDict[str, _L1Entry]" = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> Optional[Any]:
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.is_expired(now):
                # Lazy expiration. Treat as miss + delete.
                del self._store[key]
                self._misses += 1
                return None
            # LRU touch.
            self._store.move_to_end(key)
            self._hits += 1
            return entry.value

    def put(self, key: str, value: Any, *, ttl_seconds: Optional[float] = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expires_at = time.monotonic() + ttl if ttl is not None else None
        with self._lock:
            if key in self._store:
                # Refresh in place — keeps LRU order at end.
                self._store.move_to_end(key)
                self._store[key] = _L1Entry(value=value, expires_at=expires_at)
                return
            self._store[key] = _L1Entry(value=value, expires_at=expires_at)
            # Evict the oldest entries until we're back under cap.
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)
                self._evictions += 1

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    @property
    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "size": len(self._store),
            }


# ---------------------------------------------------------------------------
# L3 — SQLite-backed cross-session cache
# ---------------------------------------------------------------------------


_L3_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache_entries (
    key         TEXT PRIMARY KEY,
    value       BLOB NOT NULL,
    expires_at  REAL,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_expires_at ON cache_entries(expires_at);
"""


class L3Cache:
    """SQLite-backed cache that survives CAO restarts.

    Values are JSON-serialized; non-JSON-serializable inputs raise on
    ``put``, which is the right behavior — the caller has built a bad
    cache value. Expired entries are deleted lazily on ``get`` and via
    ``vacuum()`` (called from the lifespan during boot).

    Connection management: SQLite's per-connection-per-thread rule
    means we open a fresh connection on each call rather than keeping
    a long-lived handle. This is fine at L3's expected throughput
    (cache misses, occasional puts).
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_L3_SCHEMA)

    def get(self, key: str) -> Optional[Any]:
        now = time.time()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value, expires_at FROM cache_entries WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            value_blob, expires_at = row
            if expires_at is not None and expires_at <= now:
                conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                return None
            return json.loads(value_blob)

    def put(self, key: str, value: Any, *, ttl_seconds: Optional[float] = None) -> None:
        now = time.time()
        expires_at = now + ttl_seconds if ttl_seconds is not None else None
        value_blob = json.dumps(value, default=str)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache_entries (key, value, expires_at, created_at) "
                "VALUES (?, ?, ?, ?)",
                (key, value_blob, expires_at, now),
            )

    def delete(self, key: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))

    def vacuum(self) -> int:
        """Delete all expired entries. Returns the number reaped."""
        now = time.time()
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM cache_entries WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (now,),
            )
            return cursor.rowcount

    def size(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM cache_entries").fetchone()
            return int(row[0]) if row else 0
