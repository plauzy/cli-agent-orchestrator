"""Integration tests: AsiEvaluator → topology router (Phase 4 / commit 20).

The plan's commit 20 deliverable is "wire Deacon as topology router
AsiOracle (non-stub)". The wiring is structural — ``AsiEvaluator``
already exposes ``score_for_task_class(task_class) -> float``, which
is exactly the ``AsiOracle`` Protocol's only method. No adapter class
needed; just pass the evaluator as ``asi=`` to ``select_topology``.

These tests pin the integration end-to-end:

  * The router accepts an ``AsiEvaluator`` directly (duck typing works).
  * Cold-start (no observations yet) → ``score_for_task_class`` returns
    1.0 → router behaves identically to ``StubAsiOracle``.
  * After a low-ASI window for a task class, the router downgrades
    that task class's parallel topologies to ``SEQUENTIAL_REFINERY``.
  * The downgrade is per-task-class — a degraded class doesn't
    pessimize routing for unrelated classes.
  * Recovery: once the score climbs back above threshold, the router
    stops downgrading.
"""

from __future__ import annotations

from typing import Any

import pytest

from cli_agent_orchestrator.observability import (
    AsiEvaluator,
    AsiThresholds,
    SpanRecord,
)
from cli_agent_orchestrator.orchestration import (
    StubBudgetOracle,
    TaskDAG,
    TaskEdge,
    TaskNode,
    Topology,
    select_topology,
)


def _swarm_dag(task_class: str = "research_breadth") -> TaskDAG:
    """1 root → 8 parallel workers, low coupling. Routes to PARALLEL_POLECAT_SWARM
    when ASI is healthy, downgrades to SEQUENTIAL_REFINERY when ASI < threshold."""
    return TaskDAG(
        session_id="s1",
        task_class=task_class,
        nodes=tuple(TaskNode(n) for n in ["root", *(f"w-{i}" for i in range(8))]),
        edges=tuple(TaskEdge("root", f"w-{i}", 0.1) for i in range(8)),
    )


def _failing_span(task_class: str) -> SpanRecord:
    """Span shape that drags every dimension scorer toward zero."""
    return SpanRecord(
        name="execute_tool handoff",
        operation="execute_tool",
        agent_id="agent",
        conversation_id="conv-1",
        task_class=task_class,
        duration_ms=300_000.0,  # 300s → low coordination score
        attributes={"cao.tool.outcome": "error"},
    )


def _healthy_span(task_class: str) -> SpanRecord:
    return SpanRecord(
        name="execute_tool handoff",
        operation="execute_tool",
        agent_id="agent",
        conversation_id="conv-1",
        task_class=task_class,
        duration_ms=1_000.0,
        attributes={"cao.tool.outcome": "success"},
    )


# ---------------------------------------------------------------------------
# Duck-typing contract
# ---------------------------------------------------------------------------


class TestAsiOracleDuckTyping:
    def test_evaluator_satisfies_oracle_signature(self):
        """AsiEvaluator.score_for_task_class matches AsiOracle Protocol."""
        ev = AsiEvaluator()
        # The router's AsiOracle Protocol expects this exact signature.
        score = ev.score_for_task_class("any-class")
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Cold start → no behavior change
# ---------------------------------------------------------------------------


class TestColdStart:
    def test_unobserved_task_class_does_not_downgrade(self):
        ev = AsiEvaluator()
        choice = select_topology(_swarm_dag(), asi=ev, budget=StubBudgetOracle())
        # No history → 1.0 score → router picks SWARM exactly as with the stub.
        assert choice == Topology.PARALLEL_POLECAT_SWARM


# ---------------------------------------------------------------------------
# Low-ASI window triggers downgrade
# ---------------------------------------------------------------------------


class TestDegradedDowngrade:
    def test_low_score_downgrades_swarm_to_sequential(self):
        ev = AsiEvaluator(thresholds=AsiThresholds(window_size=10))
        # Fill a window for "research_breadth" with degenerate spans.
        for _ in range(10):
            ev.observe(_failing_span("research_breadth"))
        # Score should be well under the router's 0.75 threshold.
        score = ev.score_for_task_class("research_breadth")
        assert score < 0.75

        choice = select_topology(_swarm_dag(), asi=ev, budget=StubBudgetOracle())
        assert choice == Topology.SEQUENTIAL_REFINERY


# ---------------------------------------------------------------------------
# Per-task-class isolation
# ---------------------------------------------------------------------------


class TestPerTaskClassIsolation:
    def test_degraded_class_does_not_affect_others(self):
        ev = AsiEvaluator(thresholds=AsiThresholds(window_size=10))
        # Tank "research_breadth" specifically.
        for _ in range(10):
            ev.observe(_failing_span("research_breadth"))

        # An unrelated task class still routes normally.
        unrelated = _swarm_dag(task_class="code_review_breadth")
        choice = select_topology(unrelated, asi=ev, budget=StubBudgetOracle())
        assert choice == Topology.PARALLEL_POLECAT_SWARM


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------


class TestRecovery:
    def test_recovered_score_stops_downgrading(self):
        ev = AsiEvaluator(thresholds=AsiThresholds(window_size=10))
        # First window: degenerate.
        for _ in range(10):
            ev.observe(_failing_span("research_breadth"))
        assert ev.score_for_task_class("research_breadth") < 0.75
        # Confirm router downgrades.
        assert (
            select_topology(_swarm_dag(), asi=ev, budget=StubBudgetOracle())
            == Topology.SEQUENTIAL_REFINERY
        )

        # Second window: healthy.
        for _ in range(10):
            ev.observe(_healthy_span("research_breadth"))
        assert ev.score_for_task_class("research_breadth") > 0.85
        # Router stops downgrading.
        assert (
            select_topology(_swarm_dag(), asi=ev, budget=StubBudgetOracle())
            == Topology.PARALLEL_POLECAT_SWARM
        )
