"""Hybrid hierarchical-cluster topology (Phase 3 / commit 15).

When the router selects ``HYBRID_HIERARCHICAL_CLUSTER`` (``k > 50``), the
Mayor needs to fan out polecats but the simple union-find partitioning
that the parallel-swarm uses (commit 14) can produce one giant partition
when even a few high-coupling edges chain across the DAG. The hybrid
strategy clusters on the *full* coupling graph (every edge weighted by
``coupling``) and produces *roughly equal-sized* polecat groups using
modularity-style community detection.

We don't pull in NetworkX for one algorithm — instead we ship a
self-contained label-propagation clusterer with deterministic tie-
breaking (sort by node id at each step). It's not as good as Louvain
on adversarial graphs, but it's:
  * O(iter · |E|), which is fast enough for k ~ 200,
  * deterministic (so tests can pin behavior),
  * dependency-free.

When the parent operator wants Louvain or another algorithm later, the
``Clusterer`` Protocol makes it a drop-in.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Protocol

from cli_agent_orchestrator.orchestration.dag import TaskDAG, TaskNode
from cli_agent_orchestrator.orchestration.swarm import Partition

logger = logging.getLogger(__name__)


# Maximum target polecats per cluster. The router can pass a different
# value (per-tenant tuning) but a sane default keeps clusters from
# growing past what one Polecat can credibly handle.
DEFAULT_MAX_CLUSTER_SIZE = 12

# Maximum label-propagation iterations. Convergence is typically <10
# even on graphs with k=200; the cap is a guardrail.
_MAX_ITERATIONS = 20


class Clusterer(Protocol):
    """Pluggable graph clusterer.

    Returns a mapping from node id → cluster label. Cluster labels can
    be any hashable; ``cluster_dag`` uses string labels so they can
    appear in span attributes.
    """

    def cluster(self, dag: TaskDAG) -> dict[str, str]: ...


# ---------------------------------------------------------------------------
# Label-propagation clusterer
# ---------------------------------------------------------------------------


class LabelPropagationClusterer:
    """Deterministic label-propagation community detection.

    Each node starts in its own cluster. On every iteration, each node
    adopts the label its neighbors most strongly prefer (weighted by
    edge coupling). Ties are broken by sorted node id so the algorithm
    is fully deterministic given the same input.

    Convergence: when no node's label changed in an iteration. Bounded
    by ``_MAX_ITERATIONS`` to avoid pathological oscillation.

    For a DAG with no edges, every node ends in its own cluster (one
    Polecat per node). This is intentional — without coupling edges
    there's no reason to group anything.
    """

    def cluster(self, dag: TaskDAG) -> dict[str, str]:
        if not dag.nodes:
            return {}

        # Build undirected adjacency with coupling weights summed.
        # (Two edges in opposite directions stack their weights.)
        weighted: dict[str, dict[str, float]] = defaultdict(dict)
        for edge in dag.edges:
            weighted[edge.source][edge.target] = (
                weighted[edge.source].get(edge.target, 0.0) + edge.coupling
            )
            weighted[edge.target][edge.source] = (
                weighted[edge.target].get(edge.source, 0.0) + edge.coupling
            )

        # Initial labels = node ids (everyone in their own cluster).
        labels: dict[str, str] = {node.id: node.id for node in dag.nodes}

        # Sorted node order for deterministic iteration.
        node_ids = sorted(labels.keys())

        for _ in range(_MAX_ITERATIONS):
            changed = False
            for node_id in node_ids:
                neighbors = weighted.get(node_id, {})
                if not neighbors:
                    continue
                # Weighted vote: sum coupling per neighbor label.
                vote: dict[str, float] = defaultdict(float)
                for neighbor_id, weight in neighbors.items():
                    vote[labels[neighbor_id]] += weight
                # Pick the highest-vote label; tie-break by sorted label
                # (matches "deterministic" promise).
                best_label = min(
                    sorted(vote.keys()),
                    key=lambda lbl: (-vote[lbl], lbl),
                )
                if labels[node_id] != best_label:
                    labels[node_id] = best_label
                    changed = True
            if not changed:
                break
        return labels


# ---------------------------------------------------------------------------
# cluster_dag: build Partitions
# ---------------------------------------------------------------------------


def cluster_dag(
    dag: TaskDAG,
    *,
    clusterer: Clusterer | None = None,
    max_cluster_size: int = DEFAULT_MAX_CLUSTER_SIZE,
) -> list[Partition]:
    """Cluster a large DAG into roughly equal-sized polecat partitions.

    Clusters that exceed ``max_cluster_size`` are split deterministically
    by sorting member nodes by id and chunking — this keeps the resulting
    polecats from inheriting unboundedly-large work units when a
    coupling-graph community happens to be enormous.

    Returns partitions in deterministic order (sorted by smallest node id).
    """
    if not dag.nodes:
        return []

    cl = clusterer or LabelPropagationClusterer()
    labels = cl.cluster(dag)

    # Group nodes by label.
    by_label: dict[str, list[TaskNode]] = defaultdict(list)
    by_id = {n.id: n for n in dag.nodes}
    for node_id, label in labels.items():
        by_label[label].append(by_id[node_id])

    # Split clusters that exceed max_cluster_size. Sort members by id
    # for deterministic chunking.
    chunked: list[list[TaskNode]] = []
    for cluster_nodes in by_label.values():
        cluster_nodes.sort(key=lambda n: n.id)
        if len(cluster_nodes) <= max_cluster_size:
            chunked.append(cluster_nodes)
            continue
        # Chunk into max_cluster_size groups.
        for i in range(0, len(cluster_nodes), max_cluster_size):
            chunked.append(cluster_nodes[i : i + max_cluster_size])

    # Sort partitions by smallest node id → deterministic order.
    chunked.sort(key=lambda group: min(n.id for n in group))

    partitions: list[Partition] = []
    for group in chunked:
        partition_id = f"cluster-{uuid.uuid4().hex[:8]}"
        partitions.append(Partition(partition_id=partition_id, nodes=tuple(group)))
    return partitions
