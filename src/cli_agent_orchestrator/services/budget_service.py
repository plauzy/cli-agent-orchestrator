"""Cache-aware budget oracle (v2.5 close-out, item 8).

Promotes ``StubBudgetOracle`` (orchestration/topology_router.py:104) into
a real implementation backed by:

  * a fixed remaining-budget pool (per-tenant accounting can layer on
    top in v2.6 — the protocol surface stays unchanged)
  * the three-layer cache's *rolling 5-minute hit rate*

The cost model is the same shape the stub used — k * topology multiplier
— but multiplied by ``(1 - hit_rate)`` to discount cache-amortized work.
A topology with 90% hit rate effectively costs 10% of its uncached price,
so the router naturally prefers cheaper-with-cache topologies for warm
prefixes.

Shadow mode: ``CAO_CACHE_BUDGET_SHADOW=true`` runs both the cached and
the un-discounted projection, returns the un-discounted value (matching
the v1.x stub semantics) so operators can compare divergence in OTel
spans before flipping. The default (``"false"``) returns the discounted
value — the production behavior.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from opentelemetry import trace

from cli_agent_orchestrator.cache import ThreeLayerCache
from cli_agent_orchestrator.orchestration.dag import DagFeatures
from cli_agent_orchestrator.orchestration.topology_router import (
    StubBudgetOracle,
    Topology,
)

logger = logging.getLogger(__name__)
_TRACER = trace.get_tracer("cao.services.budget", "2.5.0")


class BudgetService:
    """Real ``TokenBudgetOracle`` for the topology router.

    Mirrors :class:`StubBudgetOracle`'s topology-shape multipliers (so
    the un-discounted projection matches the Phase 3 baseline exactly)
    and folds in the cache's rolling 5-minute hit rate.

    The hit rate is *global* — the cache doesn't currently attribute
    rates per task class, and the router's projected_cost is called
    once per dispatch so per-class attribution would require a deeper
    surface than v2.5 ships. v2.6 can extend by passing the task class
    through to ``ThreeLayerCache`` and tracking per-class windows.
    """

    _MULTIPLIERS = {
        Topology.STATIC_HIERARCHY: 1.0,
        Topology.SEQUENTIAL_REFINERY: 1.0,
        Topology.PARALLEL_POLECAT_SWARM: 1.5,
        Topology.HYBRID_HIERARCHICAL_CLUSTER: 1.75,
    }

    def __init__(
        self,
        *,
        cache: Optional[ThreeLayerCache] = None,
        remaining_budget: float = float("inf"),
        shadow_mode: Optional[bool] = None,
    ) -> None:
        self._cache = cache
        self._remaining = remaining_budget
        if shadow_mode is None:
            shadow_mode = os.environ.get("CAO_CACHE_BUDGET_SHADOW", "false").lower() == "true"
        self._shadow = shadow_mode

    def projected_cost(self, topology: Topology, features: DagFeatures) -> float:
        baseline = features.k * self._MULTIPLIERS[topology]
        hit_rate = 0.0
        if self._cache is not None:
            try:
                hit_rate = max(0.0, min(self._cache.hit_rate_5m() / 100.0, 1.0))
            except Exception:  # pragma: no cover - defensive
                logger.warning("hit_rate_5m read failed; treating as cold", exc_info=True)
                hit_rate = 0.0
        discounted = baseline * (1.0 - hit_rate)

        # Emit a small span so an operator can A/B baseline vs discounted.
        with _TRACER.start_as_current_span("cao.budget.project") as span:
            span.set_attribute("cao.budget.topology", topology.value)
            span.set_attribute("cao.budget.k", features.k)
            span.set_attribute("cao.budget.baseline_cost", baseline)
            span.set_attribute("cao.budget.cache_hit_rate", hit_rate)
            span.set_attribute("cao.budget.discounted_cost", discounted)
            if self._shadow:
                span.set_attribute("cao.budget.shadow", True)
                span.add_event(
                    "shadow-mode",
                    {
                        "baseline": baseline,
                        "discounted": discounted,
                        "diverged": baseline != discounted,
                    },
                )
                # Shadow returns the un-discounted projection; operators
                # compare via the span attributes.
                return baseline
            return discounted

    def remaining(self) -> float:
        return self._remaining

    @classmethod
    def fallback(cls) -> StubBudgetOracle:
        """Return a Phase-3 stub for callers that haven't wired a cache."""
        return StubBudgetOracle()
