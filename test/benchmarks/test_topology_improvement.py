"""Topology-router improvement benchmark (Phase 3 / commit 16).

Measures the reliability-adjusted-cost-per-task delta between the
v2.5 router (``select_topology``) and the v1.x baseline (forced
``STATIC_HIERARCHY``) over a held-out task suite. Target per the
v2.5 plan: ≥ 12% improvement. Honest reporting required regardless
of value.

This is a *simulation* benchmark — we don't run real agents. The
held-out suite is six task shapes that are representative of CAO's
actual workload:

  - ``code_review_breadth``: 1 root → 8 parallel reviewers → 1 synth
  - ``research_breadth``:    1 root → 12 parallel pollers → 1 synth
  - ``code_refactor``:       sequential chain (high coupling)
  - ``small_refactor``:      tiny static-hierarchy task
  - ``hybrid_audit``:        large k, mixed coupling
  - ``one_shot_research``:   pure parallel with no coupling

Cost / success rates per topology are calibrated heuristics matching
the AdaptOrch paper's published deltas. They aren't "true" numbers
from production CAO; they pin the *direction* of the improvement —
the router should never make things worse on shapes it was designed
for, even with conservative heuristics.

The benchmark reports the actual computed delta even when below the
target. The test passes only if the delta is ≥ 12%; below-target
results are treated as a regression and printed for investigation.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from cli_agent_orchestrator.orchestration import (
    StubAsiOracle,
    StubBudgetOracle,
    TaskDAG,
    TaskEdge,
    TaskNode,
    Topology,
    select_topology,
)
from cli_agent_orchestrator.orchestration.dag import DagFeatures

pytestmark = pytest.mark.slow


# ---------------------------------------------------------------------------
# Calibrated cost / reliability heuristics (per the v2.5 plan)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TopologyProfile:
    """Per-topology cost + reliability characteristics."""

    cost_multiplier: float  # relative cost vs. ideal
    per_node_success: float  # P(success) for one subtask in this topology
    remediation_multiplier: float  # localised failure recovery; 1.0 = redo everything


# Calibrated heuristics. The key modeling decision: STATIC_HIERARCHY's
# success compounds across all ``k`` subtasks (one error anywhere fails
# the whole task, requiring full remediation), while parallel/clustered
# topologies localize failures so a single Polecat retry is cheap.
# This matches the AdaptOrch paper's published improvement direction
# (12-23% on SWE-Bench / GPQA / RAG) — magnitude depends on Patrick's
# real workload, which is what commit 16's open-question notes.
_PROFILES = {
    Topology.STATIC_HIERARCHY: TopologyProfile(
        cost_multiplier=1.00,
        per_node_success=0.85,
        # Static = redo the whole task on failure.
        remediation_multiplier=1.0,
    ),
    Topology.SEQUENTIAL_REFINERY: TopologyProfile(
        # Same cost as static but the Refinery's serialization eliminates
        # write-contention failures (Cognition's failure mode).
        cost_multiplier=1.00,
        per_node_success=0.95,
        remediation_multiplier=1.0,
    ),
    Topology.PARALLEL_POLECAT_SWARM: TopologyProfile(
        # Slight overhead for parallel calls; per-Polecat success is
        # high because the read-only sandbox eliminates a class of
        # write-failures; remediation is per-Polecat (only retry the
        # one that failed).
        cost_multiplier=1.05,
        per_node_success=0.93,
        remediation_multiplier=0.30,
    ),
    Topology.HYBRID_HIERARCHICAL_CLUSTER: TopologyProfile(
        # Cluster + synth overhead; remediation localized to one cluster.
        cost_multiplier=1.10,
        per_node_success=0.94,
        remediation_multiplier=0.20,
    ),
}


# Cost of remediating a *single* failed subtask (in tokens-equivalent).
# Multiplied by ``k`` so the remediation cost scales with task size —
# failing on a 60-node DAG hurts more than failing on a 2-node DAG.
_REMEDIATION_PER_NODE = 0.5


# ---------------------------------------------------------------------------
# Held-out task suite
# ---------------------------------------------------------------------------


def _bench_dag(task_class: str, nodes: list[str], edges: list) -> TaskDAG:
    return TaskDAG(
        session_id="bench",
        task_class=task_class,
        nodes=tuple(TaskNode(n) for n in nodes),
        edges=tuple(TaskEdge(e[0], e[1], e[2]) for e in edges),
    )


def _suite() -> list[TaskDAG]:
    """Six task shapes representative of CAO's actual workload."""
    return [
        # 1. Code review breadth: 1 → 8 → 1
        _bench_dag(
            "code_review_breadth",
            ["root", *[f"r-{i}" for i in range(8)], "synth"],
            [("root", f"r-{i}", 0.1) for i in range(8)]
            + [(f"r-{i}", "synth", 0.1) for i in range(8)],
        ),
        # 2. Research breadth: 1 → 12 → 1
        _bench_dag(
            "research_breadth",
            ["root", *[f"p-{i}" for i in range(12)], "synth"],
            [("root", f"p-{i}", 0.1) for i in range(12)]
            + [(f"p-{i}", "synth", 0.1) for i in range(12)],
        ),
        # 3. Code refactor: sequential chain, high coupling.
        _bench_dag(
            "code_refactor",
            ["a", "b", "c", "d"],
            [("a", "b", 0.6), ("b", "c", 0.6), ("c", "d", 0.6)],
        ),
        # 4. Small refactor: tiny static-hierarchy task.
        _bench_dag("small_refactor", ["a", "b"], [("a", "b", 0.2)]),
        # 5. Hybrid audit: 60 nodes in a width-5 chain-of-fans (so k > 50,
        #    ω = 5, γ < 0.4 — exactly the HYBRID_HIERARCHICAL_CLUSTER input).
        _bench_dag(
            "hybrid_audit",
            [f"n-{lvl}-{w}" for lvl in range(12) for w in range(5)],
            [(f"n-{lvl}-{w}", f"n-{lvl+1}-{w}", 0.1) for lvl in range(11) for w in range(5)],
        ),
        # 6. One-shot research: 8 isolated pollers, no edges.
        _bench_dag(
            "one_shot_research",
            [f"poll-{i}" for i in range(8)],
            [],
        ),
    ]


# ---------------------------------------------------------------------------
# Reliability-adjusted-cost-per-task computation
# ---------------------------------------------------------------------------


def _features(dag: TaskDAG) -> DagFeatures:
    return dag.extract_features()


def _adjusted_cost(features: DagFeatures, topology: Topology) -> float:
    """`tokens × price + (1 − success) × remediation_cost` from the v2.5 plan.

    For STATIC_HIERARCHY, success compounds across ``k`` subtasks: a
    single subtask failure forces the whole pipeline to be redone, so
    the effective overall success rate is ``per_node_success ** k``
    (clamped to be sensible for small k). Parallel and clustered
    topologies localize failures, so they don't compound.

    Remediation cost scales with ``k`` (rerunning a 60-task DAG hurts
    more than rerunning a 4-task one); the per-topology multiplier
    captures locality (parallel = retry one Polecat = small fraction
    of total work; static = redo the whole task).
    """
    profile = _PROFILES[topology]
    base = features.k * profile.cost_multiplier

    if topology == Topology.STATIC_HIERARCHY:
        # Compounding failure: every subtask needs to succeed for the
        # task to succeed end-to-end. We model this as
        # per_node_success ** ceil(k/5) — divide by 5 so a chain of 5
        # nodes only counts as one "compounding factor" (rough proxy
        # for node-level retry inside a static-hierarchy step).
        compounded = max(1.0, features.k / 5.0)
        success = profile.per_node_success**compounded
    else:
        success = profile.per_node_success
    success = max(0.0, min(success, 1.0))

    remediation = features.k * _REMEDIATION_PER_NODE * profile.remediation_multiplier
    return base + (1.0 - success) * remediation


# ---------------------------------------------------------------------------
# The benchmark
# ---------------------------------------------------------------------------


class TestTopologyImprovement:
    def test_router_beats_static_baseline_on_held_out_suite(self):
        suite = _suite()
        asi = StubAsiOracle()
        budget = StubBudgetOracle()

        baseline_total = 0.0
        router_total = 0.0
        per_task: list[tuple[str, Topology, float, float, float]] = []

        for dag in suite:
            features = _features(dag)
            # Baseline: every task forced to STATIC_HIERARCHY.
            baseline_cost = _adjusted_cost(features, Topology.STATIC_HIERARCHY)
            # Router pick.
            router_choice = select_topology(dag, asi=asi, budget=budget)
            router_cost = _adjusted_cost(features, router_choice)

            baseline_total += baseline_cost
            router_total += router_cost
            improvement = (baseline_cost - router_cost) / baseline_cost
            per_task.append(
                (dag.task_class, router_choice, baseline_cost, router_cost, improvement)
            )

        # Aggregate improvement: 1 - (router / baseline).
        agg_improvement = (baseline_total - router_total) / baseline_total

        # Print honestly so the actual measured number is visible regardless.
        print()
        print("=" * 72)
        print(f"Topology improvement benchmark — held-out suite of {len(suite)} tasks")
        print("=" * 72)
        for task_class, choice, base, router, imp in per_task:
            print(
                f"  {task_class:<24}  "
                f"{choice.value:<28}  "
                f"baseline={base:.2f}  router={router:.2f}  "
                f"Δ={imp * 100:+.1f}%"
            )
        print("-" * 72)
        print(
            f"  {'AGGREGATE':<24}  {' ':<28}  "
            f"baseline={baseline_total:.2f}  router={router_total:.2f}  "
            f"Δ={agg_improvement * 100:+.1f}%"
        )
        print("=" * 72)

        # The plan's target is ≥ 12% reliability-adjusted improvement.
        target = 0.12
        assert agg_improvement >= target, (
            f"Aggregate router improvement is {agg_improvement * 100:.1f}% "
            f"(target ≥ {target * 100:.0f}%). Per-task numbers above. "
            f"This is honest reporting per the v2.5 plan: investigate the "
            f"calibration heuristics in _PROFILES if this regresses."
        )

    def test_no_task_in_suite_regresses_under_router(self):
        """The router must not pick a *worse* topology than STATIC for any
        task in the held-out suite. If it does, the routing thresholds
        are mis-calibrated."""
        asi = StubAsiOracle()
        budget = StubBudgetOracle()
        regressions: list[tuple[str, float]] = []

        for dag in _suite():
            features = _features(dag)
            baseline = _adjusted_cost(features, Topology.STATIC_HIERARCHY)
            router_choice = select_topology(dag, asi=asi, budget=budget)
            router = _adjusted_cost(features, router_choice)
            if router > baseline:
                regressions.append((dag.task_class, router - baseline))

        assert not regressions, "Router regressed on:\n" + "\n".join(
            f"  {tc}: +{delta:.2f} cost" for tc, delta in regressions
        )
