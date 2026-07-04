"""Tests for the Phase 5 three-layer cache primitives (commit 24).

Coverage matrix:
  * cache_key: deterministic, order-independent, stable across processes
  * L1Cache:
    - get on a missing key returns None
    - put then get returns the value
    - LRU eviction: oldest entries evicted when over max_size
    - TTL eviction: expired entries return None on get and are deleted
    - delete removes a key
    - put on existing key updates value + refreshes LRU position
    - stats track hits / misses / evictions / size
    - thread-safe under concurrent put/get
    - max_size <= 0 raises
  * L3Cache:
    - get on a missing key returns None
    - put then get returns the value (round-trip JSON)
    - TTL eviction is enforced lazily on get
    - delete removes a row
    - vacuum() reaps expired entries
    - size() reports total row count
    - schema is created in a fresh DB
    - survives reopen (durability)
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from cli_agent_orchestrator.cache import (
    CacheBackend,
    L1Cache,
    L3Cache,
    cache_key,
)

# ---------------------------------------------------------------------------
# cache_key
# ---------------------------------------------------------------------------


class TestCacheKey:
    def test_deterministic_for_identical_input(self):
        env = {"messages": ["hello"], "model": "claude-opus-4-7"}
        assert cache_key(env) == cache_key(env)

    def test_order_independent(self):
        a = {"messages": ["hi"], "model": "x", "temperature": 0.5}
        b = {"temperature": 0.5, "model": "x", "messages": ["hi"]}
        assert cache_key(a) == cache_key(b)

    def test_distinct_for_distinct_input(self):
        a = {"messages": ["hi"]}
        b = {"messages": ["bye"]}
        assert cache_key(a) != cache_key(b)

    def test_returns_hex_sha256(self):
        # 64 hex chars = 256 bits.
        key = cache_key({"x": 1})
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


# ---------------------------------------------------------------------------
# L1Cache
# ---------------------------------------------------------------------------


class TestL1Cache:
    def test_get_missing_returns_none(self):
        cache = L1Cache(max_size=10)
        assert cache.get("nope") is None

    def test_put_then_get_returns_value(self):
        cache = L1Cache(max_size=10)
        cache.put("k", "v")
        assert cache.get("k") == "v"

    def test_lru_eviction_when_over_max_size(self):
        cache = L1Cache(max_size=3, default_ttl_seconds=None)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        cache.put("d", 4)  # Evicts "a".
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_get_refreshes_lru_position(self):
        cache = L1Cache(max_size=3, default_ttl_seconds=None)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)
        # Touch "a" so it becomes most-recent.
        assert cache.get("a") == 1
        cache.put("d", 4)  # Should evict "b" (now least-recent), not "a".
        assert cache.get("a") == 1
        assert cache.get("b") is None
        assert cache.get("c") == 3
        assert cache.get("d") == 4

    def test_put_on_existing_key_updates_value(self):
        cache = L1Cache(max_size=10)
        cache.put("k", "first")
        cache.put("k", "second")
        assert cache.get("k") == "second"

    def test_ttl_eviction_returns_none(self, monkeypatch: pytest.MonkeyPatch):
        # Advance the monotonic clock past the TTL.
        cache = L1Cache(max_size=10, default_ttl_seconds=1.0)
        cache.put("k", "v")
        assert cache.get("k") == "v"

        # Advance time past TTL.
        original = time.monotonic()
        monkeypatch.setattr(
            "cli_agent_orchestrator.cache.three_layer.time.monotonic",
            lambda: original + 2.0,
        )
        assert cache.get("k") is None

    def test_explicit_ttl_overrides_default(self, monkeypatch: pytest.MonkeyPatch):
        cache = L1Cache(max_size=10, default_ttl_seconds=300.0)
        cache.put("k", "v", ttl_seconds=0.5)

        original = time.monotonic()
        monkeypatch.setattr(
            "cli_agent_orchestrator.cache.three_layer.time.monotonic",
            lambda: original + 1.0,
        )
        assert cache.get("k") is None

    def test_no_ttl_means_no_expiration(self, monkeypatch: pytest.MonkeyPatch):
        cache = L1Cache(max_size=10, default_ttl_seconds=None)
        cache.put("k", "v")

        original = time.monotonic()
        monkeypatch.setattr(
            "cli_agent_orchestrator.cache.three_layer.time.monotonic",
            lambda: original + 1_000_000.0,
        )
        assert cache.get("k") == "v"

    def test_delete_removes_key(self):
        cache = L1Cache(max_size=10)
        cache.put("k", "v")
        cache.delete("k")
        assert cache.get("k") is None

    def test_delete_missing_key_is_noop(self):
        cache = L1Cache(max_size=10)
        cache.delete("never-set")  # Must not raise.

    def test_clear_empties_cache(self):
        cache = L1Cache(max_size=10)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.stats["size"] == 0

    def test_stats_track_hits_misses_evictions(self):
        cache = L1Cache(max_size=2, default_ttl_seconds=None)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)  # Evicts "a".
        cache.get("b")  # Hit.
        cache.get("missing")  # Miss.
        cache.get("a")  # Miss (was evicted).
        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 2
        assert stats["evictions"] == 1
        assert stats["size"] == 2

    def test_max_size_zero_raises(self):
        with pytest.raises(ValueError):
            L1Cache(max_size=0)

    def test_max_size_negative_raises(self):
        with pytest.raises(ValueError):
            L1Cache(max_size=-1)

    def test_thread_safety(self):
        # Hammer the cache from multiple threads. The lock should keep
        # internal state consistent.
        cache = L1Cache(max_size=100, default_ttl_seconds=None)
        N_THREADS = 8
        N_OPS = 500

        def worker(tid: int) -> None:
            for i in range(N_OPS):
                key = f"t{tid}-{i % 50}"
                cache.put(key, (tid, i))
                cache.get(key)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(N_THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No assertion on exact stats — just that we got here without
        # deadlock or crash, and the size hasn't blown past the cap.
        assert cache.stats["size"] <= 100

    def test_satisfies_protocol(self):
        cache = L1Cache(max_size=10)
        assert isinstance(cache, CacheBackend)


# ---------------------------------------------------------------------------
# L3Cache
# ---------------------------------------------------------------------------


@pytest.fixture
def l3_db(tmp_path: Path) -> Path:
    return tmp_path / "cache.db"


class TestL3Cache:
    def test_get_missing_returns_none(self, l3_db: Path):
        cache = L3Cache(l3_db)
        assert cache.get("nope") is None

    def test_put_then_get_round_trips(self, l3_db: Path):
        cache = L3Cache(l3_db)
        cache.put("k", {"answer": 42, "items": [1, 2, 3]})
        assert cache.get("k") == {"answer": 42, "items": [1, 2, 3]}

    def test_put_on_existing_key_replaces_value(self, l3_db: Path):
        cache = L3Cache(l3_db)
        cache.put("k", "first")
        cache.put("k", "second")
        assert cache.get("k") == "second"

    def test_ttl_eviction_is_lazy(self, l3_db: Path):
        cache = L3Cache(l3_db)
        cache.put("k", "v", ttl_seconds=0.1)
        time.sleep(0.2)
        # Get must return None and reap the row.
        assert cache.get("k") is None
        # Followup vacuum is a no-op since lazy eviction already removed it.
        assert cache.vacuum() == 0

    def test_no_ttl_persists_indefinitely(self, l3_db: Path):
        cache = L3Cache(l3_db)
        cache.put("k", "v")
        time.sleep(0.05)
        assert cache.get("k") == "v"

    def test_delete_removes_key(self, l3_db: Path):
        cache = L3Cache(l3_db)
        cache.put("k", "v")
        cache.delete("k")
        assert cache.get("k") is None

    def test_vacuum_reaps_expired(self, l3_db: Path):
        cache = L3Cache(l3_db)
        cache.put("expired", "x", ttl_seconds=0.05)
        cache.put("alive", "a")
        time.sleep(0.1)
        reaped = cache.vacuum()
        assert reaped == 1
        assert cache.get("alive") == "a"
        assert cache.get("expired") is None

    def test_size_reports_count(self, l3_db: Path):
        cache = L3Cache(l3_db)
        assert cache.size() == 0
        cache.put("a", 1)
        cache.put("b", 2)
        assert cache.size() == 2

    def test_durability_across_reopen(self, l3_db: Path):
        cache1 = L3Cache(l3_db)
        cache1.put("k", "persistent")

        # Open a fresh instance against the same file.
        cache2 = L3Cache(l3_db)
        assert cache2.get("k") == "persistent"

    def test_creates_parent_directory(self, tmp_path: Path):
        nested = tmp_path / "a" / "b" / "cache.db"
        L3Cache(nested)
        assert nested.parent.exists()

    def test_satisfies_protocol(self, l3_db: Path):
        cache = L3Cache(l3_db)
        assert isinstance(cache, CacheBackend)
