"""Polecat swarm dispatch (Phase 3 / commit 14).

When the topology router (commit 10) selects ``PARALLEL_POLECAT_SWARM``,
the Mayor hands the resulting ``TaskDAG`` to ``dispatch_swarm``. This
module:

  1. Partitions the DAG nodes into groups connected by *high-coupling*
     edges (``gamma ≥ coupling_threshold``). Each group runs as one
     Polecat; nodes in different groups run in parallel.
  2. Spawns one Polecat per partition concurrently. Each Polecat lives
     in its own git worktree (commit 13) with read-only tools (commit 12).
  3. Collects each Polecat's findings via a caller-supplied async
     collector (in production: read the terminal's output stream;
     in tests: a stub).
  4. Submits a single ``WriteRequest`` to the Refinery so the synthesis
     of all polecat findings serializes through the same write gate as
     every other state mutation. **This is the parallel-write-isolation
     property pinned by the 1000-task burn-in test.**
  5. Tears down every Polecat (best-effort) before returning.

The dispatcher is deliberately small and dependency-injected — every
external interaction is a Protocol, so tests can drive thousands of
synthetic swarms in <1s without touching real git or tmux. Production
wiring (gluing into ``_handoff_impl`` / ``_assign_impl``) is a deliberate
later commit; this module ships the primitive only.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, Protocol

from opentelemetry import trace

from cli_agent_orchestrator.orchestration.dag import TaskDAG, TaskNode
from cli_agent_orchestrator.orchestration.polecat import (
    Polecat,
    PolecatSpec,
    TerminalKiller,
    TerminalSpawner,
)
from cli_agent_orchestrator.orchestration.polecat import spawn as spawn_polecat
from cli_agent_orchestrator.refinery import RefineryQueue, RefineryResult, WriteRequest
from cli_agent_orchestrator.telemetry import semconv

logger = logging.getLogger(__name__)

_TRACER = trace.get_tracer("cao.orchestration.swarm", "2.5.0")

# Default coupling threshold: nodes connected by an edge with γ ≥ this
# value must run in the same Polecat (they share too much state to
# parallelize). Matches the AdaptOrch γ_SEQUENTIAL_THRESHOLD in
# topology_router.py — the router uses the same value to decide whether
# the DAG goes to SEQUENTIAL_REFINERY in the first place.
DEFAULT_COUPLING_THRESHOLD = 0.4


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


class FindingsCollector(Protocol):
    """Caller-supplied: read findings from a finished Polecat.

    Production: tails the Polecat terminal's output until the read-only
    agent reports done, returning the structured findings the Polecat
    produced. Tests: a stub that returns a synthetic dict.
    """

    async def __call__(self, polecat: Polecat) -> Any: ...


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SwarmRequest:
    """Inputs the Mayor hands to ``dispatch_swarm``."""

    dag: TaskDAG
    parent_repo: Path
    worktree_root: Path
    agent_profile: str
    coupling_threshold: float = DEFAULT_COUPLING_THRESHOLD


@dataclass(frozen=True)
class Partition:
    """One Polecat's share of the DAG."""

    partition_id: str
    nodes: tuple[TaskNode, ...]


@dataclass(frozen=True)
class AggregatedFindings:
    """Structured aggregation of per-polecat findings.

    ``findings`` is the same list ``SwarmResult`` exposes — preserved for
    back-compat with existing consumers. ``by_polecat`` indexes the same
    entries by the partition id that produced them so callers can correlate
    a finding back to its polecat without scanning. ``unique`` drops
    duplicates (collectors that return the same canonical JSON twice
    fold to one entry); ``errors`` extracts the error rows.

    Equivalence property pinned by the correctness benchmark:
        swarm.aggregated.unique == sorted(union(single-polecat outputs))
    """

    findings: tuple[dict[str, Any], ...]
    by_polecat: dict[str, dict[str, Any]]
    unique: tuple[dict[str, Any], ...]
    errors: tuple[dict[str, Any], ...]


@dataclass
class SwarmResult:
    """Outcome of a swarm dispatch."""

    findings: list[Any]
    polecats_spawned: int
    synthesis: RefineryResult
    # Per-polecat error captured if the spawn failed; index-aligned with
    # ``findings`` (None when the corresponding polecat ran cleanly).
    polecat_errors: list[Optional[BaseException]] = field(default_factory=list)
    # Structured aggregation — populated from the same finding list.
    aggregated: Optional[AggregatedFindings] = None


# ---------------------------------------------------------------------------
# Partitioning
# ---------------------------------------------------------------------------


def partition_dag(dag: TaskDAG, coupling_threshold: float) -> list[Partition]:
    """Group DAG nodes by high-coupling connectivity.

    Two nodes connected by an edge with ``coupling >= coupling_threshold``
    end up in the same partition (they need to run together). Nodes
    connected only by low-coupling edges (or not at all) are free to
    parallelize.

    Implementation: union-find over the high-coupling edge subset.
    O(|V| + |E|·α(|V|)) — same complexity class as ``extract_features``.
    Returns partitions in deterministic order so tests can pin behavior.
    """
    # Union-find roots indexed by node id.
    parent: dict[str, str] = {n.id: n.id for n in dag.nodes}

    def find(x: str) -> str:
        # Iterative path compression.
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for edge in dag.edges:
        if edge.coupling >= coupling_threshold:
            union(edge.source, edge.target)

    # Group node objects by their root.
    by_root: dict[str, list[TaskNode]] = {}
    for node in dag.nodes:
        by_root.setdefault(find(node.id), []).append(node)

    # Stable sort by the smallest node id in each group → deterministic order.
    partitions: list[Partition] = []
    for nodes in sorted(by_root.values(), key=lambda ns: min(n.id for n in ns)):
        partition_id = f"partition-{uuid.uuid4().hex[:8]}"
        partitions.append(Partition(partition_id=partition_id, nodes=tuple(nodes)))
    return partitions


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


async def dispatch_swarm(
    request: SwarmRequest,
    spawner: TerminalSpawner,
    killer: TerminalKiller,
    collector: FindingsCollector,
    refinery: RefineryQueue,
) -> SwarmResult:
    """Fan out polecats per partition, collect findings, synthesize via Refinery.

    Critical invariant: every swarm produces exactly ONE Refinery write
    request, regardless of how many polecats it spawned. This keeps the
    synthesis under the same single-writer lock as every other state
    mutation, so a swarm of 100 polecats still cannot collide with a
    concurrent ``send_message`` write. Pinned by ``test_burn_in_zero_collisions``.
    """
    partitions = partition_dag(request.dag, request.coupling_threshold)

    with _TRACER.start_as_current_span("cao.swarm.dispatch") as span:
        span.set_attribute(semconv.GEN_AI_CONVERSATION_ID, request.dag.session_id)
        span.set_attribute(semconv.CAO_TASK_CLASS, request.dag.task_class)
        span.set_attribute("cao.swarm.polecats", len(partitions))
        span.set_attribute("cao.swarm.coupling_threshold", request.coupling_threshold)

        # Phase 1: spawn polecats in parallel.
        spawn_results = await asyncio.gather(
            *(_spawn_one(request, partition, spawner, killer) for partition in partitions),
            return_exceptions=True,
        )

        polecats: list[Polecat] = []
        polecat_errors: list[Optional[BaseException]] = []
        for entry in spawn_results:
            if isinstance(entry, BaseException):
                polecat_errors.append(entry)
            else:
                polecats.append(entry)
                polecat_errors.append(None)

        # Phase 2: collect findings in parallel. A collector exception is
        # captured per-polecat so one bad agent doesn't tank the swarm.
        collection = await asyncio.gather(*(collector(p) for p in polecats), return_exceptions=True)
        findings: list[Any] = []
        finding_records: list[dict[str, Any]] = []
        for polecat, entry in zip(polecats, collection):
            polecat_id = polecat.terminal_id
            if isinstance(entry, BaseException):
                logger.warning("Polecat findings collection failed: %s", entry)
                err = {"error": str(entry), "polecat_id": polecat_id}
                findings.append(err)
                # Dedup-key intentionally omits polecat_id so two polecats
                # reporting the same error fold to one unique entry.
                finding_records.append({**err, "dedup_key": _dedup_key({"error": err["error"]})})
            else:
                findings.append(entry)
                finding_records.append(
                    {
                        "polecat_id": polecat_id,
                        "value": entry,
                        "dedup_key": _dedup_key(entry),
                    }
                )

        aggregated = _aggregate(finding_records)
        span.set_attribute("cao.swarm.findings.unique", len(aggregated.unique))
        span.set_attribute("cao.swarm.findings.errors", len(aggregated.errors))

        # Phase 3: synthesis through the Refinery — one write per swarm.
        async def _synth() -> dict[str, Any]:
            return {
                "polecats": len(polecats),
                "findings": findings,
                "task_class": request.dag.task_class,
                "unique_findings": list(aggregated.unique),
                "errors": list(aggregated.errors),
            }

        synthesis = await refinery.submit(
            WriteRequest(
                action="swarm_synthesis",
                payload={"task_class": request.dag.task_class, "polecats": len(polecats)},
                executor=_synth,
                actor="mayor",
            )
        )

        # Phase 4: best-effort teardown.
        for polecat in polecats:
            try:
                polecat.terminate()
            except Exception:
                logger.warning("Polecat teardown failed: %s", polecat.terminal_id, exc_info=True)

        return SwarmResult(
            findings=findings,
            polecats_spawned=len(polecats),
            synthesis=synthesis,
            polecat_errors=polecat_errors,
            aggregated=aggregated,
        )


def _canonical_json(value: Any) -> str:
    """Stable JSON for hashing — sorted keys, no whitespace, defaulted."""
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return json.dumps(repr(value))


def _dedup_key(value: Any) -> str:
    """SHA-256 of the canonical JSON. Used to fold duplicate findings."""
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _aggregate(records: list[dict[str, Any]]) -> AggregatedFindings:
    """Build the structured aggregate from per-polecat finding records.

    Each input record is one of:
      * success: ``{"polecat_id", "value", "dedup_key"}``
      * error:   ``{"polecat_id", "error", "dedup_key"}``

    The aggregator preserves order in ``findings`` and ``by_polecat``;
    ``unique`` is order-preserving by first-occurrence of the dedup key.
    """
    findings_t = tuple(records)
    by_polecat: dict[str, dict[str, Any]] = {}
    seen_keys: set[str] = set()
    unique: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for r in records:
        pid = r.get("polecat_id")
        if pid is not None:
            by_polecat[pid] = r
        key = r["dedup_key"]
        if key not in seen_keys:
            seen_keys.add(key)
            unique.append(r)
        if "error" in r:
            errors.append(r)
    return AggregatedFindings(
        findings=findings_t,
        by_polecat=by_polecat,
        unique=tuple(unique),
        errors=tuple(errors),
    )


async def _spawn_one(
    request: SwarmRequest,
    partition: Partition,
    spawner: TerminalSpawner,
    killer: TerminalKiller,
) -> Polecat:
    """Spawn a single Polecat for a partition. Runs the synchronous
    ``spawn_polecat`` in a thread so the swarm can concurrently spawn
    N of them without serializing on the GIL during git's subprocess.
    """
    spec = PolecatSpec(
        task=" ".join(node.description or node.id for node in partition.nodes),
        agent_profile=request.agent_profile,
        parent_repo=request.parent_repo,
        worktree_root=request.worktree_root,
    )
    return await asyncio.to_thread(spawn_polecat, spec, spawner, killer)
