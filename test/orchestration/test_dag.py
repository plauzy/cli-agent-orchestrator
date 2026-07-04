"""Table-driven tests for TaskDAG feature extraction (commit 9).

The four AdaptOrch features must be:
  * omega — max parallel width (largest topological generation)
  * gamma — max edge coupling
  * depth — critical-path length (number of generations)
  * k     — subtask count

These power the topology router's decision logic in commit 10, so
correctness here is load-bearing for every routing decision Phase 3
will make.
"""

from __future__ import annotations

import pytest

from cli_agent_orchestrator.orchestration.dag import (
    DagFeatures,
    TaskDAG,
    TaskEdge,
    TaskNode,
)


def _dag(nodes, edges=()) -> TaskDAG:
    """Concise fixture builder."""
    return TaskDAG(
        session_id="s1",
        task_class="test",
        nodes=tuple(TaskNode(n) if isinstance(n, str) else n for n in nodes),
        edges=tuple(
            (
                TaskEdge(*e)
                if isinstance(e, tuple) and len(e) == 2
                else TaskEdge(e[0], e[1], e[2]) if isinstance(e, tuple) else e
            )
            for e in edges
        ),
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_dag_yields_zeroes(self):
        f = _dag([]).extract_features()
        assert f == DagFeatures(omega=0, gamma=0.0, depth=0, k=0)

    def test_single_isolated_node(self):
        f = _dag(["a"]).extract_features()
        assert f == DagFeatures(omega=1, gamma=0.0, depth=1, k=1)

    def test_two_isolated_nodes_have_omega_two(self):
        # Both nodes are at generation 0 → ω = 2.
        f = _dag(["a", "b"]).extract_features()
        assert f.omega == 2
        assert f.depth == 1
        assert f.k == 2


# ---------------------------------------------------------------------------
# Standard topologies the router cares about
# ---------------------------------------------------------------------------


class TestLinearChain:
    def test_three_node_chain(self):
        # a → b → c. One node per generation.
        f = _dag(["a", "b", "c"], [("a", "b"), ("b", "c")]).extract_features()
        assert f.omega == 1
        assert f.depth == 3
        assert f.k == 3

    def test_chain_gamma_is_max_coupling(self):
        f = _dag(
            ["a", "b", "c"],
            [("a", "b", 0.2), ("b", "c", 0.7)],
        ).extract_features()
        assert f.gamma == pytest.approx(0.7)


class TestFanOut:
    def test_one_to_three_fan_out(self):
        # a → b, a → c, a → d. Generation 0: {a}, generation 1: {b, c, d}.
        f = _dag(["a", "b", "c", "d"], [("a", "b"), ("a", "c"), ("a", "d")]).extract_features()
        assert f.omega == 3
        assert f.depth == 2
        assert f.k == 4


class TestDiamond:
    def test_a_to_bc_to_d(self):
        # a → b, a → c, b → d, c → d. Generations {a}, {b, c}, {d}.
        f = _dag(
            ["a", "b", "c", "d"],
            [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")],
        ).extract_features()
        assert f.omega == 2
        assert f.depth == 3
        assert f.k == 4


class TestComplexDag:
    def test_research_breadth_topology(self):
        # 1 root → 5 parallel research workers → 1 synthesizer.
        # Mirrors the AdaptOrch "high omega, low gamma" research case
        # the router will route to PARALLEL_POLECAT_SWARM.
        nodes = ["root"] + [f"poll-{i}" for i in range(5)] + ["synth"]
        edges = [("root", f"poll-{i}", 0.1) for i in range(5)] + [
            (f"poll-{i}", "synth", 0.1) for i in range(5)
        ]
        f = _dag(nodes, edges).extract_features()
        assert f.omega == 5
        assert f.depth == 3
        assert f.k == 7
        assert f.gamma == pytest.approx(0.1)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    def test_cycle_raises_value_error(self):
        # a → b, b → a. No node has in-degree 0 → Kahn's algorithm
        # cannot start.
        dag = _dag(["a", "b"], [("a", "b"), ("b", "a")])
        with pytest.raises(ValueError, match="cycle"):
            dag.extract_features()

    def test_self_loop_is_a_cycle(self):
        dag = _dag(["a"], [("a", "a")])
        with pytest.raises(ValueError, match="cycle"):
            dag.extract_features()

    def test_dangling_edge_raises(self):
        dag = _dag(["a"], [("a", "ghost")])
        with pytest.raises(ValueError, match="unknown node"):
            dag.extract_features()


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestFromDict:
    def test_round_trips_minimal_dict(self):
        dag = TaskDAG.from_dict(
            {
                "session_id": "s1",
                "task_class": "test",
                "nodes": [{"id": "a"}, {"id": "b"}],
                "edges": [{"source": "a", "target": "b"}],
            }
        )
        f = dag.extract_features()
        assert f.k == 2
        assert f.depth == 2
        assert f.gamma == 0.0  # default coupling

    def test_round_trips_full_dict(self):
        dag = TaskDAG.from_dict(
            {
                "session_id": "s1",
                "task_class": "test",
                "nodes": [
                    {"id": "a", "description": "plan", "cost_estimate": 0.5},
                    {"id": "b", "description": "execute", "cost_estimate": 2.0},
                ],
                "edges": [{"source": "a", "target": "b", "coupling": 0.42}],
            }
        )
        assert dag.nodes[0].description == "plan"
        assert dag.nodes[1].cost_estimate == 2.0
        assert dag.edges[0].coupling == pytest.approx(0.42)

    def test_empty_nodes_default(self):
        dag = TaskDAG.from_dict({"session_id": "s1", "task_class": "test"})
        assert dag.nodes == ()
        assert dag.edges == ()
