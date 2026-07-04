"""Tests for the AdaptOrch topology router (commit 10).

Coverage matrix:
  * Each AdaptOrch branch is reachable for a representative DAG.
  * ASI feedback downgrades parallel topologies when the oracle
    reports a score below the threshold.
  * Budget guard degrades to STATIC_HIERARCHY when projected cost
    exceeds remaining budget.
  * Every routing decision records the input features, ASI score,
    budget figures, and chosen topology as span attributes — the
    Deacon (Phase 4) consumes these to correlate routing with
    downstream stability.
"""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from cli_agent_orchestrator.orchestration import (
    StubAsiOracle,
    StubBudgetOracle,
    TaskDAG,
    TaskEdge,
    TaskNode,
    Topology,
    select_topology,
)
from cli_agent_orchestrator.orchestration import topology_router as router_module
from cli_agent_orchestrator.telemetry import semconv

# ---------------------------------------------------------------------------
# Span fixture (shared session-scope provider — see test/telemetry/conftest.py
# for why we don't reset between tests)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _module_provider() -> InMemorySpanExporter:
    exporter = InMemorySpanExporter()
    current = trace.get_tracer_provider()
    if isinstance(current, TracerProvider):
        current.add_span_processor(SimpleSpanProcessor(exporter))
    else:
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
    # Refresh the router module's cached tracer.
    router_module._TRACER = trace.get_tracer("cao.orchestration.router", "2.5.0")
    return exporter


@pytest.fixture
def exporter(_module_provider: InMemorySpanExporter) -> InMemorySpanExporter:
    _module_provider.clear()
    return _module_provider


# ---------------------------------------------------------------------------
# DAG factories — short for readability
# ---------------------------------------------------------------------------


def _dag(nodes, edges=(), task_class="test") -> TaskDAG:
    return TaskDAG(
        session_id="s1",
        task_class=task_class,
        nodes=tuple(TaskNode(n) if isinstance(n, str) else n for n in nodes),
        edges=tuple(TaskEdge(e[0], e[1], e[2] if len(e) > 2 else 0.0) for e in edges),
    )


def _highly_coupled() -> TaskDAG:
    """γ = 0.6, forces SEQUENTIAL_REFINERY."""
    return _dag(["a", "b"], [("a", "b", 0.6)])


def _wide_fan_out(n: int = 8) -> TaskDAG:
    """ω = n, γ = 0.1, forces PARALLEL_POLECAT_SWARM (when ω > 5)."""
    workers = [f"w-{i}" for i in range(n)]
    return _dag(
        ["root", *workers],
        [("root", w, 0.1) for w in workers],
    )


def _huge_dag(k: int = 60) -> TaskDAG:
    """k > 50 with ω ≤ 5 and γ < 0.4 → HYBRID_HIERARCHICAL_CLUSTER.

    Build a chain-of-fans: 12 levels of 5 nodes each fan out to
    the next level's 5. Keeps ω = 5 (= threshold, NOT >) so the
    swarm branch doesn't fire, while k = 60 puts us over the
    hybrid threshold.
    """
    levels = 12
    width = 5
    nodes = [f"n-{lvl}-{w}" for lvl in range(levels) for w in range(width)]
    edges = [
        (f"n-{lvl}-{w}", f"n-{lvl+1}-{w}", 0.1) for lvl in range(levels - 1) for w in range(width)
    ]
    return _dag(nodes, edges)


def _small_dag() -> TaskDAG:
    """k = 3, ω = 1, γ = 0.1 → STATIC_HIERARCHY."""
    return _dag(["a", "b", "c"], [("a", "b", 0.1), ("b", "c", 0.1)])


# ---------------------------------------------------------------------------
# Each AdaptOrch branch is reachable
# ---------------------------------------------------------------------------


class TestBranches:
    def test_high_coupling_routes_sequential(self, exporter):
        choice = select_topology(_highly_coupled())
        assert choice == Topology.SEQUENTIAL_REFINERY

    def test_wide_fan_out_routes_swarm(self, exporter):
        choice = select_topology(_wide_fan_out(8))
        assert choice == Topology.PARALLEL_POLECAT_SWARM

    def test_large_dag_routes_hybrid(self, exporter):
        choice = select_topology(_huge_dag(60))
        assert choice == Topology.HYBRID_HIERARCHICAL_CLUSTER

    def test_small_dag_routes_static(self, exporter):
        choice = select_topology(_small_dag())
        assert choice == Topology.STATIC_HIERARCHY


# ---------------------------------------------------------------------------
# ASI feedback overrides parallelism
# ---------------------------------------------------------------------------


class _FixedAsi:
    def __init__(self, score: float) -> None:
        self._score = score

    def score_for_task_class(self, task_class: str) -> float:
        return self._score


class TestAsiFeedback:
    def test_low_asi_downgrades_swarm_to_sequential(self, exporter):
        choice = select_topology(_wide_fan_out(8), asi=_FixedAsi(0.5))
        assert choice == Topology.SEQUENTIAL_REFINERY

    def test_low_asi_downgrades_hybrid_to_sequential(self, exporter):
        choice = select_topology(_huge_dag(60), asi=_FixedAsi(0.5))
        assert choice == Topology.SEQUENTIAL_REFINERY

    def test_low_asi_does_not_change_already_sequential(self, exporter):
        choice = select_topology(_highly_coupled(), asi=_FixedAsi(0.1))
        assert choice == Topology.SEQUENTIAL_REFINERY

    def test_low_asi_does_not_change_static(self, exporter):
        # STATIC isn't a parallel topology so it's not subject to downgrade.
        choice = select_topology(_small_dag(), asi=_FixedAsi(0.1))
        assert choice == Topology.STATIC_HIERARCHY

    def test_threshold_is_strict(self, exporter):
        # Score == threshold → no downgrade.
        choice = select_topology(_wide_fan_out(8), asi=_FixedAsi(0.75))
        assert choice == Topology.PARALLEL_POLECAT_SWARM


# ---------------------------------------------------------------------------
# Budget guard
# ---------------------------------------------------------------------------


class TestBudgetGuard:
    def test_overrun_degrades_to_static(self, exporter):
        # Wide fan-out wants SWARM (cost 1.5 * 9 = 13.5), but budget is tiny.
        choice = select_topology(_wide_fan_out(8), budget=StubBudgetOracle(remaining_budget=1.0))
        assert choice == Topology.STATIC_HIERARCHY

    def test_sufficient_budget_keeps_choice(self, exporter):
        choice = select_topology(_wide_fan_out(8), budget=StubBudgetOracle(remaining_budget=1000.0))
        assert choice == Topology.PARALLEL_POLECAT_SWARM


# ---------------------------------------------------------------------------
# Span attributes pinned by tests — Deacon contract
# ---------------------------------------------------------------------------


class TestSpanAttributes:
    def test_select_emits_span_with_features_and_choice(self, exporter):
        select_topology(_wide_fan_out(8))
        spans = [s for s in exporter.get_finished_spans() if s.name == "cao.topology.select"]
        assert len(spans) == 1
        attrs = dict(spans[0].attributes)
        assert attrs[semconv.CAO_TOPOLOGY_FEATURES_OMEGA] == 8
        assert attrs[semconv.CAO_TOPOLOGY_FEATURES_GAMMA] == pytest.approx(0.1)
        assert attrs[semconv.CAO_TOPOLOGY_FEATURES_K] == 9
        assert attrs[semconv.CAO_TOPOLOGY_CHOICE] == Topology.PARALLEL_POLECAT_SWARM.value
        assert attrs[semconv.CAO_TASK_CLASS] == "test"
        assert attrs[semconv.CAO_ASI_SCORE] == pytest.approx(1.0)

    def test_asi_downgrade_emits_event(self, exporter):
        select_topology(_wide_fan_out(8), asi=_FixedAsi(0.5))
        span = next(s for s in exporter.get_finished_spans() if s.name == "cao.topology.select")
        event_names = [ev.name for ev in span.events]
        assert "asi-degraded-downgrade" in event_names

    def test_budget_overrun_emits_event(self, exporter):
        select_topology(_wide_fan_out(8), budget=StubBudgetOracle(remaining_budget=1.0))
        span = next(s for s in exporter.get_finished_spans() if s.name == "cao.topology.select")
        event_names = [ev.name for ev in span.events]
        assert "budget-exhaustion-degrade" in event_names


# ---------------------------------------------------------------------------
# Stub oracles
# ---------------------------------------------------------------------------


class TestStubOracles:
    def test_stub_asi_returns_one(self):
        assert StubAsiOracle().score_for_task_class("any") == 1.0

    def test_stub_budget_remaining_is_infinite_by_default(self):
        assert StubBudgetOracle().remaining() == float("inf")

    def test_stub_budget_projected_cost_scales_with_k(self):
        from cli_agent_orchestrator.orchestration.dag import DagFeatures

        budget = StubBudgetOracle()
        f = DagFeatures(omega=2, gamma=0.1, depth=2, k=4)
        assert budget.projected_cost(Topology.STATIC_HIERARCHY, f) == 4.0
        # Swarm has a 1.5x multiplier.
        assert budget.projected_cost(Topology.PARALLEL_POLECAT_SWARM, f) == 6.0
