"""Cache-aware budget oracle benchmark (v2.5 close-out, item 8).

Pattern A — held-out improvement benchmark with paired bootstrap CI.

Asserts that with a *warmed* cache, the topology router's per-task
cost estimate is materially lower than the equivalent un-cached
projection. Both arms use the same task suite + the same topology
choices, so the per-task delta is paired and bootstrap CI is well-
defined.

Marker: ``slow`` (auto-deselected from the default suite).
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from cli_agent_orchestrator.cache import L1Cache, L3Cache, ThreeLayerCache
from cli_agent_orchestrator.orchestration import (
    StubBudgetOracle,
    Topology,
)
from cli_agent_orchestrator.orchestration.dag import DagFeatures
from cli_agent_orchestrator.services.budget_service import BudgetService

pytestmark = pytest.mark.slow


def _warm_cache(cache: ThreeLayerCache, n_hits: int) -> None:
    """Drive ``n_hits`` consecutive cache hits so hit_rate_5m climbs."""
    cache.put({"k": "warm"}, "v")
    for _ in range(n_hits):
        cache.get({"k": "warm"})


def _suite() -> list[tuple[Topology, DagFeatures]]:
    """50 deterministic (topology, features) pairs — fixed seed."""
    rng = random.Random(0xC0FFEE)
    out: list[tuple[Topology, DagFeatures]] = []
    topologies = list(Topology)
    for _ in range(50):
        topo = topologies[rng.randint(0, len(topologies) - 1)]
        out.append(
            (
                topo,
                DagFeatures(
                    k=rng.randint(1, 30),
                    omega=rng.randint(1, 10),
                    gamma=rng.random(),
                    depth=rng.randint(1, 5),
                ),
            )
        )
    return out


def _bootstrap_ci(
    deltas: list[float], n_resamples: int = 1000, seed: int = 1
) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(deltas)
    means: list[float] = []
    for _ in range(n_resamples):
        sample = [deltas[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    return means[int(0.025 * n_resamples)], means[int(0.975 * n_resamples)]


def test_cache_aware_oracle_reduces_projected_cost(tmp_path: Path):
    """With a warmed cache, the discounted projection is below the stub baseline."""
    cache = ThreeLayerCache(
        l1=L1Cache(max_size=8),
        l3=L3Cache(tmp_path / "bench-cache.db"),
        register_metrics=False,  # Don't double-register metrics.
    )
    _warm_cache(cache, n_hits=20)
    assert cache.hit_rate_5m() > 80.0  # Confirms the warm-up worked.

    aware = BudgetService(cache=cache, remaining_budget=float("inf"))
    stub = StubBudgetOracle()

    suite = _suite()
    deltas: list[float] = []
    for topo, features in suite:
        baseline = stub.projected_cost(topo, features)
        discounted = aware.projected_cost(topo, features)
        deltas.append(baseline - discounted)  # > 0 means cost reduced

    mean_delta = sum(deltas) / len(deltas)
    lo, hi = _bootstrap_ci(deltas)

    # 95% CI must exclude zero from below (improvement, not regression).
    assert lo > 0, (
        f"cache-aware oracle did not reduce projected cost: "
        f"mean_delta={mean_delta:+.3f}, 95% CI=({lo:+.3f}, {hi:+.3f})"
    )
    # Quality floor: > 50% baseline cost reduction with hit_rate > 80%.
    avg_baseline = sum(stub.projected_cost(t, f) for t, f in suite) / len(suite)
    avg_reduction = mean_delta / avg_baseline
    assert avg_reduction > 0.5, f"cache-aware reduction below 50% floor (got {avg_reduction:.1%})"


def test_cold_cache_matches_baseline(tmp_path: Path):
    """Without any hits, the discounted projection equals the baseline."""
    cache = ThreeLayerCache(
        l1=L1Cache(max_size=8),
        l3=L3Cache(tmp_path / "bench-cache.db"),
        register_metrics=False,
    )
    # Drive a few misses only so hit_rate_5m == 0.
    cache.get({"k": 1})
    cache.get({"k": 2})
    assert cache.hit_rate_5m() == 0.0

    aware = BudgetService(cache=cache)
    stub = StubBudgetOracle()

    for topo, features in _suite()[:5]:
        assert aware.projected_cost(topo, features) == stub.projected_cost(topo, features)


def test_shadow_mode_returns_baseline(tmp_path: Path):
    """Shadow mode emits both projections to spans but returns the baseline."""
    cache = ThreeLayerCache(
        l1=L1Cache(max_size=8),
        l3=L3Cache(tmp_path / "bench-cache.db"),
        register_metrics=False,
    )
    _warm_cache(cache, n_hits=20)

    aware = BudgetService(cache=cache, shadow_mode=True)
    stub = StubBudgetOracle()

    for topo, features in _suite()[:5]:
        # In shadow mode, the returned projection matches the stub
        # (un-discounted) — operators rely on span attributes for the
        # discounted comparison.
        assert aware.projected_cost(topo, features) == stub.projected_cost(topo, features)
