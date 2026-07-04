"""Tests for the L2 keep-alive scheduler + ThreeLayerCache orchestrator.

Coverage matrix:
  * L2KeepAliveScheduler:
    - register adds an entry; deregister removes it
    - start/stop are idempotent and bounded
    - pinger is invoked once per registered key per interval
    - pinger errors don't crash the scheduler; entry retained until
      max_consecutive_errors then dropped
    - tracked_keys / stats reflect registry state
    - register from sync code wakes the scheduler
  * ThreeLayerCache:
    - get on a fresh cache returns None and records a miss
    - put writes to both L1 and L3
    - get hits L1 first, then L3 with promotion
    - L3 hit promotes into L1 (subsequent get is L1 hit)
    - invalidate removes from both layers
    - L2 registration: get-on-hit and put register; miss does not
    - non-JSON-serializable values: L1 still works, L3 logs + skips
    - stats track lookups / hit rate / invalidations
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from cli_agent_orchestrator.cache import (
    DEFAULT_KEEP_ALIVE_INTERVAL_SECONDS,
    L1Cache,
    L2KeepAliveScheduler,
    L3Cache,
    NullPinger,
    ThreeLayerCache,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def l3_db(tmp_path: Path) -> Path:
    return tmp_path / "cache.db"


@pytest.fixture
def cache(l3_db: Path) -> ThreeLayerCache:
    return ThreeLayerCache(l1=L1Cache(max_size=10), l3=L3Cache(l3_db))


class _RecordingPinger:
    def __init__(self) -> None:
        self.calls: list[object] = []

    async def __call__(self, prefix: object) -> None:
        self.calls.append(prefix)


class _BrokenPinger:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, prefix: object) -> None:
        self.calls += 1
        raise RuntimeError("pinger down")


# ---------------------------------------------------------------------------
# L2KeepAliveScheduler
# ---------------------------------------------------------------------------


class TestL2Registry:
    async def test_register_adds_entry(self):
        sched = L2KeepAliveScheduler()
        sched.register("k1", {"prefix": 1})
        assert "k1" in sched.tracked_keys()
        assert sched.stats["tracked"] == 1

    async def test_deregister_removes_entry(self):
        sched = L2KeepAliveScheduler()
        sched.register("k1", {"prefix": 1})
        sched.deregister("k1")
        assert "k1" not in sched.tracked_keys()

    async def test_register_overwrites_same_key(self):
        sched = L2KeepAliveScheduler()
        sched.register("k1", {"v": 1})
        sched.register("k1", {"v": 2})
        assert sched.stats["tracked"] == 1

    async def test_default_interval_is_four_minutes(self):
        sched = L2KeepAliveScheduler()
        assert sched.interval_seconds == DEFAULT_KEEP_ALIVE_INTERVAL_SECONDS == 240.0


class TestL2Lifecycle:
    async def test_start_stop_idempotent(self):
        sched = L2KeepAliveScheduler(pinger=NullPinger())
        await sched.start()
        await sched.start()  # No-op.
        await sched.stop()
        await sched.stop()  # No-op.

    async def test_pinger_fires_after_interval(self):
        pinger = _RecordingPinger()
        sched = L2KeepAliveScheduler(pinger=pinger, interval_seconds=0.05)
        await sched.start()
        sched.register("k1", "prefix-A")
        # Wait long enough for at least one ping to fire.
        await asyncio.sleep(0.2)
        await sched.stop()
        assert len(pinger.calls) >= 1
        assert pinger.calls[0] == "prefix-A"

    async def test_pinger_errors_drop_after_threshold(self):
        pinger = _BrokenPinger()
        sched = L2KeepAliveScheduler(pinger=pinger, interval_seconds=0.02, max_consecutive_errors=2)
        await sched.start()
        sched.register("k1", "prefix")
        # Wait for enough ticks to exceed the error threshold.
        await asyncio.sleep(0.2)
        await sched.stop()
        # Entry should have been dropped after 2 consecutive errors.
        assert "k1" not in sched.tracked_keys()
        assert pinger.calls >= 2

    async def test_register_wakes_scheduler(self):
        # When the registry was empty, the scheduler sleeps for the
        # full interval. Registering a new key must wake it so the
        # initial ping doesn't wait the entire interval.
        pinger = _RecordingPinger()
        sched = L2KeepAliveScheduler(pinger=pinger, interval_seconds=0.05)
        await sched.start()
        # Register after start, with empty initial registry.
        sched.register("k1", "p")
        await asyncio.sleep(0.15)
        await sched.stop()
        assert len(pinger.calls) >= 1


# ---------------------------------------------------------------------------
# ThreeLayerCache (no L2)
# ---------------------------------------------------------------------------


class TestOrchestratorBasics:
    async def test_get_on_miss_returns_none(self, cache: ThreeLayerCache):
        assert cache.get({"x": 1}) is None
        assert cache.stats["misses"] == 1

    async def test_put_then_get_returns_value(self, cache: ThreeLayerCache):
        cache.put({"x": 1}, "value-1")
        assert cache.get({"x": 1}) == "value-1"
        assert cache.stats["l1_hits"] == 1

    async def test_put_writes_to_both_layers(self, l3_db: Path):
        l1 = L1Cache(max_size=10)
        l3 = L3Cache(l3_db)
        cache = ThreeLayerCache(l1=l1, l3=l3)
        cache.put({"x": 1}, "v")
        # Drop L1 manually to verify L3 was also written.
        l1.clear()
        assert cache.get({"x": 1}) == "v"
        assert cache.stats["l3_hits"] == 1

    async def test_l3_hit_promotes_into_l1(self, l3_db: Path):
        l1 = L1Cache(max_size=10)
        l3 = L3Cache(l3_db)
        cache = ThreeLayerCache(l1=l1, l3=l3)
        cache.put({"x": 1}, "v")
        l1.clear()
        # First get: L3 hit, promoted into L1.
        cache.get({"x": 1})
        # Second get: L1 hit.
        cache.get({"x": 1})
        assert cache.stats["l1_hits"] == 1
        assert cache.stats["l3_hits"] == 1

    async def test_invalidate_removes_from_both_layers(self, cache: ThreeLayerCache):
        cache.put({"x": 1}, "v")
        cache.invalidate({"x": 1})
        assert cache.get({"x": 1}) is None
        assert cache.stats["invalidations"] == 1

    async def test_stats_compute_hit_rate(self, cache: ThreeLayerCache):
        cache.put({"x": 1}, "v")
        cache.get({"x": 1})  # hit
        cache.get({"x": 2})  # miss
        cache.get({"x": 1})  # hit
        stats = cache.stats
        assert stats["l1_hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate_percent"] == pytest.approx(66.67, abs=0.01)

    async def test_envelope_order_independence(self, cache: ThreeLayerCache):
        # Different dict ordering must hit the same cache entry.
        cache.put({"a": 1, "b": 2}, "v")
        assert cache.get({"b": 2, "a": 1}) == "v"

    async def test_default_ttl_applied_to_put(self, l3_db: Path):
        # The orchestrator's default TTL flows through to both layers.
        l1 = L1Cache(max_size=10, default_ttl_seconds=None)
        l3 = L3Cache(l3_db)
        cache = ThreeLayerCache(l1=l1, l3=l3, default_ttl_seconds=0.1)
        cache.put({"x": 1}, "v")
        await asyncio.sleep(0.2)
        # Both layers should expire the entry.
        assert cache.get({"x": 1}) is None

    async def test_non_serializable_value_still_stored_in_l1(self, l3_db: Path, caplog):
        l1 = L1Cache(max_size=10)
        l3 = L3Cache(l3_db)
        cache = ThreeLayerCache(l1=l1, l3=l3)

        # Object dict with a non-JSON value (a class). default=str in
        # L3 will stringify it but the round-trip won't equal — we test
        # that the call doesn't raise and L1 has the original object.
        sentinel = object()
        cache.put({"x": 1}, sentinel)
        # L1 still has the original object identity.
        assert cache.get({"x": 1}) is sentinel


# ---------------------------------------------------------------------------
# ThreeLayerCache + L2 wiring
# ---------------------------------------------------------------------------


class TestOrchestratorWithL2:
    async def test_put_with_prefix_registers_with_l2(self, cache: ThreeLayerCache):
        sched = L2KeepAliveScheduler()
        cache_with_l2 = ThreeLayerCache(
            l1=L1Cache(max_size=10),
            l3=L3Cache(Path(":memory:")) if False else cache._l3,
            l2=sched,
        )
        cache_with_l2.put({"x": 1}, "v", prefix={"system": "you are helpful"})
        assert len(sched.tracked_keys()) == 1

    async def test_put_without_prefix_skips_l2(self, l3_db: Path):
        sched = L2KeepAliveScheduler()
        cache = ThreeLayerCache(l1=L1Cache(max_size=10), l3=L3Cache(l3_db), l2=sched)
        cache.put({"x": 1}, "v")  # No prefix.
        assert sched.tracked_keys() == set()

    async def test_get_on_hit_with_prefix_registers_with_l2(self, l3_db: Path):
        sched = L2KeepAliveScheduler()
        cache = ThreeLayerCache(l1=L1Cache(max_size=10), l3=L3Cache(l3_db), l2=sched)
        cache.put({"x": 1}, "v")  # No prefix yet.
        assert sched.tracked_keys() == set()
        cache.get({"x": 1}, prefix={"system": "x"})  # Hit + register.
        assert len(sched.tracked_keys()) == 1

    async def test_get_on_miss_does_not_register(self, l3_db: Path):
        sched = L2KeepAliveScheduler()
        cache = ThreeLayerCache(l1=L1Cache(max_size=10), l3=L3Cache(l3_db), l2=sched)
        cache.get({"x": 1}, prefix="some-prefix")  # Miss.
        assert sched.tracked_keys() == set()

    async def test_invalidate_deregisters_from_l2(self, l3_db: Path):
        sched = L2KeepAliveScheduler()
        cache = ThreeLayerCache(l1=L1Cache(max_size=10), l3=L3Cache(l3_db), l2=sched)
        cache.put({"x": 1}, "v", prefix="p")
        assert len(sched.tracked_keys()) == 1
        cache.invalidate({"x": 1})
        assert sched.tracked_keys() == set()


# ---------------------------------------------------------------------------
# OTel metrics + hit_rate_5m (v2.5 close-out, item 5)
# ---------------------------------------------------------------------------


class TestHitRate5m:
    async def test_initial_rate_is_zero(self, cache: ThreeLayerCache):
        assert cache.hit_rate_5m() == 0.0

    async def test_rate_after_mixed_lookups(self, cache: ThreeLayerCache):
        # 3 hits, 1 miss → 75%.
        cache.put({"k": 1}, "v")
        cache.put({"k": 2}, "v")
        cache.get({"k": 1})  # hit
        cache.get({"k": 1})  # hit
        cache.get({"k": 2})  # hit
        cache.get({"k": 3})  # miss

        assert cache.hit_rate_5m() == 75.0
        # Lifetime stats agree because no time has passed.
        assert cache.stats["hit_rate_percent"] == 75.0
        assert cache.stats["hit_rate_5m_percent"] == 75.0

    async def test_rate_prunes_old_entries(self, cache: ThreeLayerCache):
        # Stuff some old entries into the buffer manually.
        import time
        from collections import deque

        # Push entries 600 seconds in the past (twice the 5-min window).
        # Using ``time.monotonic() - 600`` rather than ``0.0`` because
        # ``monotonic`` is reference-point-undefined: on a freshly-booted
        # CI runner it can be < 300, so entries at timestamp 0.0 may
        # actually fall *inside* the 5-min window.
        old = time.monotonic() - 600.0
        cache._hit_history = deque([(old, True), (old, True), (old, False)])
        rate = cache.hit_rate_5m()
        assert rate == 0.0
        assert len(cache._hit_history) == 0


# ---------------------------------------------------------------------------
# L2 failure isolation pin (v2.5 close-out, item 6)
# ---------------------------------------------------------------------------


class _AlwaysRaisingPinger:
    """Like ``_BrokenPinger`` but keeps raising — never recovers.

    Used to pin the invariant that a misbehaving L2 pinger never escapes
    into the cache request path. This is the strongest version of the
    isolation guarantee — drift detection is opportunistic by design,
    so an always-broken pinger must not block reads or writes.
    """

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, prefix):
        self.calls += 1
        raise RuntimeError("pinger fundamentally broken")


class TestL2FailureIsolation:
    async def test_request_path_never_sees_pinger_failures(self, l3_db: Path):
        """Block C.6: the cache request path completes cleanly even when
        the L2 pinger raises on every call.
        """
        pinger = _AlwaysRaisingPinger()
        sched = L2KeepAliveScheduler(
            pinger=pinger,
            interval_seconds=0.02,
            max_consecutive_errors=2,
        )
        cache = ThreeLayerCache(
            l1=L1Cache(max_size=10),
            l3=L3Cache(l3_db),
            l2=sched,
        )

        await sched.start()
        try:
            # Drive a sequence of get/put — each may trigger an L2 ping.
            # The cache call must not propagate the pinger's exception.
            cache.put({"k": 1}, "v1", prefix="hot-prefix")
            cache.get({"k": 1}, prefix="hot-prefix")
            cache.get({"k": 2}, prefix="cold")  # miss
            cache.put({"k": 2}, "v2", prefix="another")
            cache.get({"k": 2}, prefix="another")

            # Wait for the scheduler to attempt + drop entries. Poll
            # rather than sleep a fixed duration — slow CI runners can
            # starve the asyncio loop and miss a 0.25s deadline even
            # though the scheduler interval is 0.02s.
            deadline = asyncio.get_event_loop().time() + 5.0
            while sched.tracked_keys() and asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(0.01)
        finally:
            await sched.stop()

        # Counters reflect actual lookups (no exceptions swallowed reads).
        s = cache.stats
        assert s["l1_hits"] >= 2  # at least the two confirmed hits
        assert s["misses"] == 1  # the cold lookup
        # Tracked-keys bounded — entries dropped after threshold.
        assert pinger.calls > 0
        # By the end, the failing prefixes should have been dropped (their
        # error_count exceeded max_consecutive_errors=2).
        assert len(sched.tracked_keys()) == 0


# ---------------------------------------------------------------------------
# Metric registration (smoke-test that init_cache_metrics doesn't blow up)
# ---------------------------------------------------------------------------


class TestMetricRegistration:
    async def test_register_metrics_default(self, l3_db: Path):
        # ThreeLayerCache(register_metrics=True) is the default; ensure
        # construction doesn't raise even when the SDK is off (no-op meter).
        cache = ThreeLayerCache(
            l1=L1Cache(max_size=4),
            l3=L3Cache(l3_db),
            register_metrics=True,
        )
        # Drive a few lookups so the counters get exercised.
        cache.put({"k": 1}, "v")
        cache.get({"k": 1})
        cache.get({"k": 2})
        # No exception means counters/observable-gauge wiring is sound.
        assert cache.stats["l1_hits"] == 1
        assert cache.stats["misses"] == 1

    async def test_register_metrics_can_be_disabled(self, l3_db: Path):
        # Explicitly opt out — useful for libraries that drive multiple
        # caches and don't want duplicate metric registrations.
        cache = ThreeLayerCache(
            l1=L1Cache(max_size=4),
            l3=L3Cache(l3_db),
            register_metrics=False,
        )
        cache.put({"k": 1}, "v")
        assert cache.stats["puts"] == 1
