"""Tests for the hybrid hierarchical-cluster topology (commit 15).

Coverage:
  * empty / single-node / no-edge inputs
  * label-propagation clusters densely-connected nodes together
  * cluster_dag splits oversized clusters at max_cluster_size
  * deterministic ordering
  * pluggable Clusterer Protocol
"""

from __future__ import annotations

from typing import Any

import pytest

from cli_agent_orchestrator.orchestration import (
    DEFAULT_MAX_CLUSTER_SIZE,
    Clusterer,
    LabelPropagationClusterer,
    Partition,
    TaskDAG,
    TaskEdge,
    TaskNode,
    cluster_dag,
)


def _dag(nodes, edges=()) -> TaskDAG:
    return TaskDAG(
        session_id="s1",
        task_class="test",
        nodes=tuple(TaskNode(n) for n in nodes),
        edges=tuple(TaskEdge(e[0], e[1], e[2]) for e in edges),
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_dag(self):
        assert cluster_dag(_dag([])) == []

    def test_single_node(self):
        partitions = cluster_dag(_dag(["a"]))
        assert len(partitions) == 1
        assert {n.id for n in partitions[0].nodes} == {"a"}

    def test_no_edges_each_node_is_own_partition(self):
        partitions = cluster_dag(_dag(["a", "b", "c"]))
        assert len(partitions) == 3


# ---------------------------------------------------------------------------
# Clustering produces correct groups
# ---------------------------------------------------------------------------


class TestLabelPropagation:
    def test_two_strongly_connected_groups(self):
        # {a-b-c} all coupled, {x-y-z} all coupled, no cross-edges.
        partitions = cluster_dag(
            _dag(
                ["a", "b", "c", "x", "y", "z"],
                [
                    ("a", "b", 0.9),
                    ("b", "c", 0.9),
                    ("a", "c", 0.9),
                    ("x", "y", 0.9),
                    ("y", "z", 0.9),
                    ("x", "z", 0.9),
                ],
            )
        )
        # Two clusters of three.
        assert len(partitions) == 2
        sizes = sorted(len(p.nodes) for p in partitions)
        assert sizes == [3, 3]

    def test_chain_with_one_weak_link(self):
        # a-b (strong) — c (weak link to b) — d-e (strong).
        # We expect 2 clusters: {a,b} and {c,d,e} OR {a,b,c} and {d,e}
        # depending on label propagation; both are reasonable. Just
        # assert no single giant cluster and no isolated nodes.
        partitions = cluster_dag(
            _dag(
                ["a", "b", "c", "d", "e"],
                [
                    ("a", "b", 0.9),
                    ("b", "c", 0.05),
                    ("c", "d", 0.9),
                    ("d", "e", 0.9),
                ],
            )
        )
        # No partition should contain all 5 nodes (the weak link
        # should not collapse everything into one cluster).
        assert max(len(p.nodes) for p in partitions) < 5
        # Every node accounted for exactly once.
        all_ids = [n.id for p in partitions for n in p.nodes]
        assert sorted(all_ids) == ["a", "b", "c", "d", "e"]


# ---------------------------------------------------------------------------
# Oversized cluster splitting
# ---------------------------------------------------------------------------


class TestMaxClusterSize:
    def test_oversized_cluster_is_split(self):
        # 30 nodes all pairwise strongly coupled → label propagation
        # converges to one cluster of 30. cluster_dag must split it.
        n = 30
        nodes = [f"n-{i:02d}" for i in range(n)]
        # Strongly coupled "ring" — every node coupled to its neighbor.
        edges = [(nodes[i], nodes[(i + 1) % n], 0.9) for i in range(n)]
        partitions = cluster_dag(_dag(nodes, edges), max_cluster_size=10)
        # 30 / 10 = 3 partitions.
        assert len(partitions) == 3
        for p in partitions:
            assert len(p.nodes) <= 10

    def test_deterministic_split_order(self):
        nodes = [f"n-{i:02d}" for i in range(20)]
        edges = [(nodes[i], nodes[(i + 1) % 20], 0.9) for i in range(20)]
        d = _dag(nodes, edges)
        first = cluster_dag(d, max_cluster_size=5)
        second = cluster_dag(d, max_cluster_size=5)
        # Same input → same partition node-id sets.
        first_groups = sorted(tuple(sorted(n.id for n in p.nodes)) for p in first)
        second_groups = sorted(tuple(sorted(n.id for n in p.nodes)) for p in second)
        assert first_groups == second_groups


# ---------------------------------------------------------------------------
# Pluggable Clusterer
# ---------------------------------------------------------------------------


class TestPluggableClusterer:
    def test_custom_clusterer_is_used(self):
        class _AllInOne:
            """Dumb clusterer: everything in one label."""

            def cluster(self, dag: TaskDAG) -> dict[str, str]:
                return {n.id: "single" for n in dag.nodes}

        # 8 nodes, all in one cluster, but max_cluster_size=3 → split into 3.
        partitions = cluster_dag(
            _dag([f"n-{i}" for i in range(8)]),
            clusterer=_AllInOne(),
            max_cluster_size=3,
        )
        # 8 nodes / 3 per cluster = 3 partitions (3+3+2).
        assert len(partitions) == 3
        sizes = sorted(len(p.nodes) for p in partitions)
        assert sizes == [2, 3, 3]


# ---------------------------------------------------------------------------
# Default integration with the public surface
# ---------------------------------------------------------------------------


class TestPublicSurface:
    def test_cluster_dag_returns_partitions(self):
        partitions = cluster_dag(_dag(["a", "b"], [("a", "b", 0.9)]))
        assert all(isinstance(p, Partition) for p in partitions)
        assert isinstance(partitions[0].partition_id, str)
        assert partitions[0].partition_id.startswith("cluster-")

    def test_default_max_cluster_size_constant(self):
        # Sanity — the constant exists and is sensible.
        assert DEFAULT_MAX_CLUSTER_SIZE > 0
