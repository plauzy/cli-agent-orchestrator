"""Topology routing primitives (Phase 3).

Commit 9 ships only the static DAG description and the AdaptOrch
feature extractor. The router itself (which uses these features to
choose between {parallel-polecat-swarm, sequential-refinery,
hybrid-hierarchical-cluster, static-hierarchy}) lands in commit 10.

Design contract:
  * A ``TaskDAG`` is a directed acyclic graph of subtasks the Mayor
    has decomposed an incoming request into. Edges carry a numeric
    ``coupling`` (0..1) representing how tightly two subtasks share
    state — high coupling forces sequential ordering through the
    Refinery; low coupling permits parallel Polecat dispatch.
  * Feature extraction is O(|V|+|E|) and pure-Python — no model calls,
    no I/O. This makes it cheap to run on every dispatch and trivial
    to property-test.
  * Cycles raise. The Mayor is responsible for producing acyclic
    decompositions; a cycle is a bug, not a runtime concern.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TaskNode:
    """A single subtask in a Mayor-produced decomposition."""

    id: str
    description: str = ""
    # Relative cost weight. The router uses this to size budget
    # projections in commit 10; for now it's metadata only.
    cost_estimate: float = 1.0


@dataclass(frozen=True)
class TaskEdge:
    """A data dependency between two subtasks.

    ``coupling`` ∈ [0, 1] follows the AdaptOrch γ definition: 0 means
    the target only needs the source's signal-of-completion, 1 means
    every byte the source produced is consumed by the target. The
    Mayor sets this; routing thresholds (e.g. γ ≥ 0.4 → sequential)
    live in the router (commit 10).
    """

    source: str
    target: str
    coupling: float = 0.0


@dataclass(frozen=True)
class DagFeatures:
    """O(|V|+|E|) features extracted from a TaskDAG.

    These four are the AdaptOrch routing inputs. Names match the
    paper (Park et al., 2026, arxiv:2602.16873) so the topology
    router's decision logic in commit 10 can refer to them directly.
    """

    omega: int  # max parallel width (largest topological generation)
    gamma: float  # max edge coupling (0 if no edges)
    depth: int  # critical-path length (number of generations)
    k: int  # subtask count (|V|)


@dataclass(frozen=True)
class TaskDAG:
    """A planned task as decomposed by the Mayor."""

    session_id: str
    task_class: str
    nodes: tuple[TaskNode, ...]
    edges: tuple[TaskEdge, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskDAG":
        """Construct from a JSON-shaped dict (e.g. as the Mayor emits it).

        Schema:
            {
              "session_id": str,
              "task_class": str,
              "nodes": [{"id": str, "description": str?, "cost_estimate": float?}, ...],
              "edges": [{"source": str, "target": str, "coupling": float?}, ...]
            }
        """
        nodes = tuple(
            TaskNode(
                id=n["id"],
                description=n.get("description", ""),
                cost_estimate=float(n.get("cost_estimate", 1.0)),
            )
            for n in data.get("nodes", [])
        )
        edges = tuple(
            TaskEdge(
                source=e["source"],
                target=e["target"],
                coupling=float(e.get("coupling", 0.0)),
            )
            for e in data.get("edges", [])
        )
        return cls(
            session_id=data["session_id"],
            task_class=data["task_class"],
            nodes=nodes,
            edges=edges,
        )

    def extract_features(self) -> DagFeatures:
        """Extract AdaptOrch routing features in O(|V|+|E|).

        Algorithm: Kahn's topological sort grouped by generation.
          * generation = 0 for nodes with no incoming edge
          * generation[v] = 1 + max(generation[u] for u → v)
          * omega = max population across generations
          * depth = number of generations (= 0 for empty DAG, 1 for
            isolated nodes, n for a linear chain of length n)
          * gamma = max edge coupling
          * k = number of nodes

        Raises ``ValueError`` if the graph contains a cycle.
        """
        k = len(self.nodes)
        if k == 0:
            return DagFeatures(omega=0, gamma=0.0, depth=0, k=0)

        # Build in-degree map and adjacency list.
        node_ids = {n.id for n in self.nodes}
        in_degree: dict[str, int] = {nid: 0 for nid in node_ids}
        adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}
        for edge in self.edges:
            if edge.source not in node_ids or edge.target not in node_ids:
                # Dangling edge — treat as a planning error.
                raise ValueError(f"Edge references unknown node: {edge.source} -> {edge.target}")
            adjacency[edge.source].append(edge.target)
            in_degree[edge.target] += 1

        # Kahn's algorithm with generation tracking.
        generation: dict[str, int] = {}
        queue: deque[str] = deque()
        for nid, deg in in_degree.items():
            if deg == 0:
                generation[nid] = 0
                queue.append(nid)

        processed = 0
        while queue:
            nid = queue.popleft()
            processed += 1
            for child in adjacency[nid]:
                in_degree[child] -= 1
                # The child's generation is one past the latest parent
                # we've seen. Since we visit parents in topological
                # order, this converges to the longest-path depth.
                child_gen = generation[nid] + 1
                if child_gen > generation.get(child, -1):
                    generation[child] = child_gen
                if in_degree[child] == 0:
                    queue.append(child)

        if processed != k:
            raise ValueError("TaskDAG contains a cycle — Mayor must produce acyclic decompositions")

        # omega = max number of nodes sharing a generation
        gen_counts: dict[int, int] = {}
        for g in generation.values():
            gen_counts[g] = gen_counts.get(g, 0) + 1
        omega = max(gen_counts.values())

        # depth = (highest generation index) + 1, since gen-0 still counts as one level
        depth = max(generation.values()) + 1

        gamma = max((e.coupling for e in self.edges), default=0.0)

        return DagFeatures(omega=omega, gamma=gamma, depth=depth, k=k)
