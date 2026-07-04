"""OTel metric instruments for the three-layer cache (v2.5 close-out, item 5).

Four metrics tracked on every cache lookup:

  * ``cao.cache.l1.hits_total``    — Counter
  * ``cao.cache.l3.hits_total``    — Counter
  * ``cao.cache.misses_total``     — Counter
  * ``cao.cache.hit_rate_5m``      — Observable gauge (5-minute window)

When the OTel SDK is disabled (``OTEL_SDK_DISABLED`` not ``"false"``),
``opentelemetry.metrics.get_meter`` returns a no-op meter and the
counter calls are essentially free. The observable gauge callback is
also invoked only by an active SDK reader, so the gauge has zero cost
in the off-by-default mode.

Hit-rate-5m is computed from a bounded ring buffer maintained by
:class:`ThreeLayerCache.record_lookup`. The gauge callback prunes
entries older than 300 seconds and returns the resulting rate.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Iterable, Optional

logger = logging.getLogger(__name__)

_l1_hits: Optional[Any] = None
_l3_hits: Optional[Any] = None
_misses: Optional[Any] = None
_gauge_callback: Optional[Callable[[], float]] = None


def _meter() -> Any:
    """Return the global meter, fetching lazily so import order doesn't matter."""
    from opentelemetry import metrics

    return metrics.get_meter("cao.cache", "2.5.0")


def init_cache_metrics(hit_rate_callback: Callable[[], float]) -> None:
    """Register the four cache metrics against the global meter.

    Idempotent across calls — re-registration replaces the gauge
    callback. The callback returns the current 5-minute hit-rate as a
    float in [0, 100] (percent).
    """
    global _l1_hits, _l3_hits, _misses, _gauge_callback
    _gauge_callback = hit_rate_callback
    try:
        m = _meter()
        if _l1_hits is None:
            _l1_hits = m.create_counter(
                "cao.cache.l1.hits_total", unit="1", description="L1 cache hits"
            )
        if _l3_hits is None:
            _l3_hits = m.create_counter(
                "cao.cache.l3.hits_total", unit="1", description="L3 cache hits"
            )
        if _misses is None:
            _misses = m.create_counter(
                "cao.cache.misses_total", unit="1", description="Cache misses (all layers)"
            )
        # Observable gauge — callback is called by the metrics reader.
        m.create_observable_gauge(
            "cao.cache.hit_rate_5m",
            callbacks=[_observe_hit_rate],
            unit="%",
            description="Rolling 5-minute cache hit rate",
        )
    except Exception:
        # SDK extras may not be present, or the meter API may have
        # changed under us. Fall back to no-op increments.
        logger.info("Cache metric registration failed; running uninstrumented", exc_info=True)


def record_l1_hit() -> None:
    if _l1_hits is not None:
        try:
            _l1_hits.add(1)
        except Exception:  # pragma: no cover - defensive
            pass


def record_l3_hit() -> None:
    if _l3_hits is not None:
        try:
            _l3_hits.add(1)
        except Exception:  # pragma: no cover - defensive
            pass


def record_miss() -> None:
    if _misses is not None:
        try:
            _misses.add(1)
        except Exception:  # pragma: no cover - defensive
            pass


def _observe_hit_rate(_options: Any) -> Iterable[Any]:
    """Observable-gauge callback. Returns one Observation per call."""
    from opentelemetry.metrics import Observation

    if _gauge_callback is None:
        return [Observation(0.0)]
    try:
        return [Observation(float(_gauge_callback()))]
    except Exception:  # pragma: no cover - defensive
        return [Observation(0.0)]
