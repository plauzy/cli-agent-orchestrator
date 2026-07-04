"""Three-layer cache for CAO agent calls (Phase 5).

Storage primitives:
  * ``L1Cache`` — in-process LRU + TTL (commit 24)
  * ``L3Cache`` — SQLite-backed cross-session cache (commit 24)

Orchestrator + L2 keep-alive (commit 25):
  * ``ThreeLayerCache`` — composes L1 + L3 + optional L2 with hit promotion
  * ``L2KeepAliveScheduler`` — asyncio task that pings hot prefixes against
    Anthropic's 5-minute prompt cache TTL (default 4-minute interval)
  * ``KeepAlivePinger`` Protocol — pluggable async ping callable
  * ``NullPinger`` — no-op pinger for tests + keep-alive-disabled deployments
"""

from cli_agent_orchestrator.cache.orchestrator import (
    DEFAULT_KEEP_ALIVE_INTERVAL_SECONDS,
    CacheStats,
    KeepAlivePinger,
    L2KeepAliveScheduler,
    NullPinger,
    ThreeLayerCache,
)
from cli_agent_orchestrator.cache.three_layer import (
    CacheBackend,
    L1Cache,
    L3Cache,
    cache_key,
)

__all__ = [
    "CacheBackend",
    "CacheStats",
    "DEFAULT_KEEP_ALIVE_INTERVAL_SECONDS",
    "KeepAlivePinger",
    "L1Cache",
    "L2KeepAliveScheduler",
    "L3Cache",
    "NullPinger",
    "ThreeLayerCache",
    "cache_key",
]
