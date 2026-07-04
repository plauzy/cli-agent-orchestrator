"""L2 keep-alive scheduler + ThreeLayerCache orchestrator (Phase 5 / commit 25).

Composes the L1 + L3 storage primitives (commit 24) with an
asyncio-based L2 scheduler that pings hot prefixes against Anthropic's
prompt cache. The 5-minute TTL is non-negotiable; a 4-minute keep-alive
interval keeps the prefix warm at ~10% of the original tokenization
cost.

CAO doesn't talk to Anthropic directly — providers (Claude Code, Kiro,
etc.) do. The scheduler is therefore pluggable: callers inject an
``async`` ``KeepAlivePinger`` that knows how to refresh the cache for
a given prefix payload. A ``NullPinger`` is provided for tests + for
deployments where keep-alive should be a no-op.

Orchestrator semantics:

  * ``get(envelope)`` checks L1 → L3. On L3 hit, value is promoted
    back into L1. On miss, returns ``None`` and the caller is expected
    to compute + ``put``.
  * ``put(envelope, value, prefix=...)`` writes to both L1 and L3.
    If ``prefix`` is supplied and an L2 scheduler is wired, the
    scheduler registers the key for periodic keep-alive.
  * ``invalidate(envelope)`` deletes from both layers and deregisters
    from L2.

The orchestrator is intentionally synchronous for storage operations
(L1 + L3 are sync); the L2 registration call is sync too because the
scheduler maintains its own asyncio task. Callers that want async
ergonomics can wrap with ``asyncio.to_thread`` — but the storage
primitives are fast enough that this is rarely needed.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Optional, Protocol, runtime_checkable

from cli_agent_orchestrator.cache.metrics import (
    init_cache_metrics,
    record_l1_hit,
    record_l3_hit,
    record_miss,
)
from cli_agent_orchestrator.cache.three_layer import (
    L1Cache,
    L3Cache,
    cache_key,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# L2 keep-alive
# ---------------------------------------------------------------------------


# Default ping interval per the v2.5 plan: 4 minutes against Anthropic's
# 5-minute prompt-cache TTL leaves a 1-minute safety margin for jitter
# and network latency.
DEFAULT_KEEP_ALIVE_INTERVAL_SECONDS = 240.0


@runtime_checkable
class KeepAlivePinger(Protocol):
    """Async callable that refreshes a prompt-cache entry.

    Implementations make a minimal completion against the Anthropic
    API with ``cache_control: ephemeral`` set on the prefix. The
    payload shape is provider-specific so the scheduler treats it as
    opaque.
    """

    async def __call__(self, prefix: Any) -> None: ...


class NullPinger:
    """No-op pinger. Default for tests and keep-alive-disabled deployments."""

    async def __call__(self, prefix: Any) -> None:
        return None


@dataclass
class _RegistryEntry:
    prefix: Any
    next_ping_at: float
    last_ping_at: Optional[float] = None
    ping_count: int = 0
    error_count: int = 0


@dataclass
class L2KeepAliveScheduler:
    """Asyncio task that walks a registry of hot prefixes and refreshes them.

    The scheduler holds a per-key entry with a ``next_ping_at`` deadline.
    A single coroutine sleeps until the earliest deadline, fires the
    ping, then re-schedules. Entries with too many consecutive errors
    are dropped from the registry — drift detection is opportunistic
    by design, mirroring the Phase 4 mitigation handlers.
    """

    pinger: KeepAlivePinger = field(default_factory=NullPinger)
    interval_seconds: float = DEFAULT_KEEP_ALIVE_INTERVAL_SECONDS
    max_consecutive_errors: int = 3
    _registry: dict[str, _RegistryEntry] = field(default_factory=dict)
    _task: Optional[asyncio.Task] = None
    _stop: Optional[asyncio.Event] = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _wake: Optional[asyncio.Event] = None

    def register(self, key: str, prefix: Any) -> None:
        """Add (or refresh) an entry. Safe to call from sync code paths."""
        now = time.monotonic()
        self._registry[key] = _RegistryEntry(
            prefix=prefix,
            next_ping_at=now + self.interval_seconds,
        )
        # Wake the scheduler so it picks up the new deadline immediately.
        if self._wake is not None and not self._wake.is_set():
            try:
                self._wake.set()
            except RuntimeError:
                # Loop closed during registration — best-effort.
                pass

    def deregister(self, key: str) -> None:
        self._registry.pop(key, None)

    def tracked_keys(self) -> set[str]:
        return set(self._registry.keys())

    @property
    def stats(self) -> dict[str, int]:
        return {
            "tracked": len(self._registry),
            "total_pings": sum(e.ping_count for e in self._registry.values()),
            "total_errors": sum(e.error_count for e in self._registry.values()),
        }

    async def start(self) -> None:
        """Start the background scheduler. Idempotent."""
        if self._task is not None and not self._task.done():
            return
        self._stop = asyncio.Event()
        self._wake = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="l2-keepalive")

    async def stop(self) -> None:
        """Stop the scheduler. Idempotent and bounded."""
        if self._task is None or self._stop is None:
            return
        self._stop.set()
        if self._wake is not None:
            self._wake.set()
        try:
            await asyncio.wait_for(self._task, timeout=2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            self._task.cancel()
        self._task = None
        self._stop = None
        self._wake = None

    async def _run(self) -> None:
        """Walk the registry, fire pings on entries past their deadline."""
        assert self._stop is not None
        assert self._wake is not None
        while not self._stop.is_set():
            now = time.monotonic()
            due_keys = [k for k, e in self._registry.items() if e.next_ping_at <= now]
            for key in due_keys:
                entry = self._registry.get(key)
                if entry is None:
                    continue
                try:
                    await self.pinger(entry.prefix)
                    entry.last_ping_at = now
                    entry.ping_count += 1
                    entry.error_count = 0
                    entry.next_ping_at = now + self.interval_seconds
                except Exception:
                    entry.error_count += 1
                    logger.warning(
                        "L2 keep-alive ping failed for key=%s (errors=%d)",
                        key,
                        entry.error_count,
                        exc_info=True,
                    )
                    if entry.error_count >= self.max_consecutive_errors:
                        # Drop this prefix; the caller can re-register
                        # on the next cache hit.
                        self._registry.pop(key, None)
                    else:
                        # Back off — wait the full interval before retry.
                        entry.next_ping_at = now + self.interval_seconds

            # Sleep until the next deadline (or wake event).
            if self._registry:
                next_deadline = min(e.next_ping_at for e in self._registry.values())
                sleep_for = max(next_deadline - time.monotonic(), 0.0)
            else:
                # Empty registry — wait indefinitely; register() will set _wake.
                sleep_for = self.interval_seconds

            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=sleep_for)
            except asyncio.TimeoutError:
                pass


# ---------------------------------------------------------------------------
# Three-layer orchestrator
# ---------------------------------------------------------------------------


@dataclass
class CacheStats:
    l1_hits: int = 0
    l3_hits: int = 0
    misses: int = 0
    puts: int = 0
    invalidations: int = 0


class ThreeLayerCache:
    """Composes L1 + L3 storage with an optional L2 keep-alive scheduler.

    Lookup order: L1 → L3 → miss. L3 hits are promoted into L1 so
    subsequent reads land in the fastest layer. ``put`` writes to both
    layers and (when wired) registers the key with L2 for keep-alive.

    The orchestrator holds references; it does not own the lifecycle of
    the underlying caches. The FastAPI lifespan is responsible for
    constructing L1 / L3 / L2 and tearing them down.
    """

    # Rolling 5-minute window for hit_rate_5m gauge. Bounded ring buffer
    # of (timestamp, hit_bool) — pruned lazily on each read.
    _HIT_WINDOW_SECONDS: float = 300.0

    def __init__(
        self,
        *,
        l1: L1Cache,
        l3: L3Cache,
        l2: Optional[L2KeepAliveScheduler] = None,
        default_ttl_seconds: Optional[float] = 3600.0,
        register_metrics: bool = True,
    ) -> None:
        self._l1 = l1
        self._l3 = l3
        self._l2 = l2
        self._default_ttl = default_ttl_seconds
        self._stats = CacheStats()
        # Rolling 5-min lookup history: (monotonic_ts, hit_bool).
        self._hit_history: Deque[tuple[float, bool]] = deque()
        if register_metrics:
            init_cache_metrics(self.hit_rate_5m)

    def _record_lookup(self, hit: bool) -> None:
        """Append a lookup outcome to the rolling window, pruning stale rows."""
        now = time.monotonic()
        self._hit_history.append((now, hit))
        cutoff = now - self._HIT_WINDOW_SECONDS
        while self._hit_history and self._hit_history[0][0] < cutoff:
            self._hit_history.popleft()

    def hit_rate_5m(self) -> float:
        """Return the rolling 5-minute hit rate as a percent in [0, 100].

        Returns 0.0 when no lookups have happened in the window — same
        convention as ``stats["hit_rate_percent"]`` for the lifetime view.
        """
        # Prune before reading so the window is fresh.
        cutoff = time.monotonic() - self._HIT_WINDOW_SECONDS
        while self._hit_history and self._hit_history[0][0] < cutoff:
            self._hit_history.popleft()
        if not self._hit_history:
            return 0.0
        hits = sum(1 for _, h in self._hit_history if h)
        return round(100.0 * hits / len(self._hit_history), 2)

    def get(self, envelope: dict[str, Any], *, prefix: Any = None) -> Optional[Any]:
        """Try L1 then L3. On L3 hit, promote into L1.

        When ``prefix`` is provided and an L2 scheduler is wired, a
        cache hit also (re)registers the prefix for keep-alive. Misses
        do not register — the caller will register on ``put``.
        """
        key = cache_key(envelope)
        v = self._l1.get(key)
        if v is not None:
            self._stats.l1_hits += 1
            self._record_lookup(hit=True)
            record_l1_hit()
            if self._l2 is not None and prefix is not None:
                self._l2.register(key, prefix)
            return v
        v = self._l3.get(key)
        if v is not None:
            self._stats.l3_hits += 1
            self._record_lookup(hit=True)
            record_l3_hit()
            # Promote into L1 so subsequent reads are fast.
            self._l1.put(key, v)
            if self._l2 is not None and prefix is not None:
                self._l2.register(key, prefix)
            return v
        self._stats.misses += 1
        self._record_lookup(hit=False)
        record_miss()
        return None

    def put(
        self,
        envelope: dict[str, Any],
        value: Any,
        *,
        prefix: Any = None,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        """Write through to both L1 and L3. Optionally register with L2."""
        key = cache_key(envelope)
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        self._l1.put(key, value, ttl_seconds=ttl)
        try:
            self._l3.put(key, value, ttl_seconds=ttl)
        except (TypeError, ValueError):
            # L3 round-trips through JSON; non-serializable values can't
            # be stored. Log + continue — L1 still has the entry.
            logger.warning("L3 put failed (non-serializable value); key=%s", key, exc_info=True)
        if self._l2 is not None and prefix is not None:
            self._l2.register(key, prefix)
        self._stats.puts += 1

    def invalidate(self, envelope: dict[str, Any]) -> None:
        """Remove the entry from L1 + L3 and deregister L2."""
        key = cache_key(envelope)
        self._l1.delete(key)
        self._l3.delete(key)
        if self._l2 is not None:
            self._l2.deregister(key)
        self._stats.invalidations += 1

    @property
    def stats(self) -> dict[str, float]:
        total_lookups = self._stats.l1_hits + self._stats.l3_hits + self._stats.misses
        return {
            "l1_hits": self._stats.l1_hits,
            "l3_hits": self._stats.l3_hits,
            "misses": self._stats.misses,
            "puts": self._stats.puts,
            "invalidations": self._stats.invalidations,
            "total_lookups": total_lookups,
            # Lifetime hit rate (helper for /health endpoints).
            "hit_rate_percent": round(
                100.0 * (self._stats.l1_hits + self._stats.l3_hits) / max(total_lookups, 1), 2
            ),
            # 5-minute rolling hit rate — same value the OTel observable
            # gauge ``cao.cache.hit_rate_5m`` emits.
            "hit_rate_5m_percent": self.hit_rate_5m(),
        }
