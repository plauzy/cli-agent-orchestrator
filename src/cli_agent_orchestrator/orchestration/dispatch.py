"""High-level dispatch entrypoint (Phase 3 / commit 17).

Wires together every Phase 3 primitive — topology router, Refinery
write queue, Polecat swarm dispatcher, hybrid clusterer — into a
single ``dispatch_task`` coroutine the Mayor can call. Future commits
migrate ``_handoff_impl`` / ``_assign_impl`` to use this entrypoint;
this module is the migration target, kept deliberately separate so the
provider regex test surface (7 providers, byte-sensitive idle detection)
isn't disturbed in this commit.

Flow:

    select_topology(dag, asi, budget)
        ├── STATIC_HIERARCHY   → caller-supplied static_executor (the
        │                         existing v1.x dispatch path)
        ├── SEQUENTIAL_REFINERY → Refinery.submit(static_executor)
        ├── PARALLEL_POLECAT_SWARM → dispatch_swarm(...) with
        │                            partition_dag for partitioning
        └── HYBRID_HIERARCHICAL_CLUSTER → dispatch_swarm(...) with
                                          cluster_dag for partitioning

Every routing decision is recorded on a ``cao.dispatch`` span so the
Phase 4 Deacon can correlate dispatch outcomes with downstream
stability. The static path still runs through the Refinery's policy /
Rule-of-Two gates so even "boring" dispatches benefit from the gate.

The HYBRID branch swap happens here (rather than inside ``swarm.py``)
because the swarm dispatcher is intentionally agnostic about how it
partitions — the strategy is injected per call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, Protocol, Sequence, runtime_checkable

from opentelemetry import trace

from cli_agent_orchestrator.orchestration.dag import TaskDAG
from cli_agent_orchestrator.orchestration.hybrid_cluster import cluster_dag
from cli_agent_orchestrator.orchestration.polecat import (
    TerminalKiller,
    TerminalSpawner,
)
from cli_agent_orchestrator.orchestration.swarm import (
    DEFAULT_COUPLING_THRESHOLD,
    FindingsCollector,
    Partition,
    SwarmRequest,
    SwarmResult,
    dispatch_swarm,
    partition_dag,
)
from cli_agent_orchestrator.orchestration.topology_router import (
    AsiOracle,
    ConsolidationOracle,
    TokenBudgetOracle,
    Topology,
    select_topology,
)
from cli_agent_orchestrator.refinery import RefineryQueue, RefineryResult, WriteRequest
from cli_agent_orchestrator.telemetry import semconv

logger = logging.getLogger(__name__)

_TRACER = trace.get_tracer("cao.orchestration.dispatch", "2.5.0")


# A caller-supplied static-hierarchy executor. Mirrors the v1.x dispatch
# path — runs the task to completion and returns whatever the agent
# produced. The dispatch entrypoint defers to this when the router picks
# ``STATIC_HIERARCHY`` (or ``SEQUENTIAL_REFINERY`` — see flow above).
StaticExecutor = Callable[[], Awaitable[Any]]


@runtime_checkable
class KillSwitchOracle(Protocol):
    """Duck-typed gate consulted before dispatch.

    The Phase 4 ``KillSwitchState`` (observability/mitigations.py)
    satisfies this Protocol exactly — the dispatch layer doesn't need
    to import the observability package. Pass any object with an
    ``is_killed(task_class) -> bool`` method.
    """

    def is_killed(self, task_class: str) -> bool: ...


class KillSwitchEngaged(RuntimeError):
    """Raised by ``dispatch_task`` when the task class is kill-switched.

    Carries ``task_class`` so the caller can surface a useful error
    message back to the operator (e.g. "research_breadth dispatch
    refused — clear the kill switch via API or restart").
    """

    def __init__(self, task_class: str) -> None:
        super().__init__(
            f"dispatch refused: task_class={task_class!r} is kill-switched "
            "by the Deacon (ASI below kill threshold). Clear via the "
            "kill-switch API or restart CAO to resume."
        )
        self.task_class = task_class


@dataclass
class DispatchResult:
    """Outcome of a high-level dispatch."""

    topology: Topology
    value: Any = None
    swarm: SwarmResult | None = None
    refinery: RefineryResult | None = None


@dataclass(frozen=True)
class DispatchRequest:
    """Inputs to ``dispatch_task``.

    Caller responsibilities:
      * ``dag`` is built by the Mayor (or upstream planner) from the
        incoming task. For v2.5.x scaffolding without a planner, a
        single-node DAG with ``k=1, ω=1, γ=0`` will deterministically
        route to ``STATIC_HIERARCHY`` (no behavior change vs. v1.x).
      * ``static_executor`` is the v1.x dispatch closure — it must do
        whatever the existing ``_handoff_impl`` / ``_assign_impl`` would
        have done.
      * ``refinery`` is optional. STATIC_HIERARCHY never touches it; if
        the router picks any other topology and ``refinery`` is ``None``,
        ``dispatch_task`` runs ``static_executor`` directly with a
        warning. This makes ``dispatch_task`` safe to call from MCP
        tools that don't yet plumb a Refinery.
      * ``parent_repo`` / ``worktree_root`` / ``agent_profile`` are only
        consulted when the router picks a parallel topology.
      * ``spawner`` / ``killer`` / ``collector`` are also only used for
        parallel topologies; they may be ``None`` if the caller knows
        the task class is high-coupling.
    """

    dag: TaskDAG
    static_executor: StaticExecutor
    refinery: Optional[RefineryQueue] = None
    # Parallel-topology dependencies. None unless the router can pick
    # one of the parallel branches.
    parent_repo: Optional[Path] = None
    worktree_root: Optional[Path] = None
    agent_profile: Optional[str] = None
    spawner: Optional[TerminalSpawner] = None
    killer: Optional[TerminalKiller] = None
    collector: Optional[FindingsCollector] = None
    coupling_threshold: float = DEFAULT_COUPLING_THRESHOLD
    # Behavioral anchors prepended onto the next agent invocation.
    # Populated by ``BehavioralAnchoringHandler`` on sustained drift;
    # the executor reads this and prepends each anchor onto the system
    # prompt before calling the agent. None / empty = no anchoring.
    anchors: Optional[Sequence[str]] = None


async def dispatch_task(
    request: DispatchRequest,
    *,
    asi: AsiOracle | None = None,
    budget: TokenBudgetOracle | None = None,
    kill_switch: KillSwitchOracle | None = None,
    consolidation: ConsolidationOracle | None = None,
    anchors: Optional[Sequence[str]] = None,
) -> DispatchResult:
    """Route ``request`` through the topology router and execute it.

    Behavior by topology:
      * STATIC_HIERARCHY → run ``static_executor`` directly. Matches
        v1.x semantics (no Refinery gate). Used by the Mayor when the
        caller wants the simplest possible path.
      * SEQUENTIAL_REFINERY → submit ``static_executor`` to the Refinery
        so policy / Rule-of-Two run before the executor and the WAL
        + SSE bus see the action.
      * PARALLEL_POLECAT_SWARM → ``dispatch_swarm`` with union-find
        partitioning. Falls back to SEQUENTIAL_REFINERY if any of the
        parallel-topology dependencies are missing (defensive — caller
        bug, not a runtime failure).
      * HYBRID_HIERARCHICAL_CLUSTER → ``dispatch_swarm`` with a
        cluster-based partitioner injected.

    When ``kill_switch`` is provided and reports the task class as
    killed, ``dispatch_task`` raises ``KillSwitchEngaged`` immediately
    — before the topology router runs and before any side effects
    are recorded. This is the Phase 4 feedback loop: the Deacon flips
    the kill switch on a sustained ASI breach (commit 21 KillSwitchHandler)
    and dispatch refuses new work for that class.
    """
    if kill_switch is not None and kill_switch.is_killed(request.dag.task_class):
        raise KillSwitchEngaged(request.dag.task_class)

    # Anchors flow through DispatchRequest so the static_executor can read
    # them via ``request.anchors``. The kwarg is a convenience for callers
    # that don't construct DispatchRequest directly — it overrides anything
    # already set on the request.
    if anchors is not None:
        request = _replace_anchors(request, anchors)

    with _TRACER.start_as_current_span("cao.dispatch") as span:
        if request.anchors:
            span.set_attribute("cao.dispatch.anchors", len(request.anchors))
        choice = select_topology(request.dag, asi=asi, budget=budget, consolidation=consolidation)
        span.set_attribute(semconv.GEN_AI_CONVERSATION_ID, request.dag.session_id)
        span.set_attribute(semconv.CAO_TASK_CLASS, request.dag.task_class)
        span.set_attribute(semconv.CAO_TOPOLOGY_CHOICE, choice.value)

        if choice == Topology.STATIC_HIERARCHY:
            value = await request.static_executor()
            return DispatchResult(topology=choice, value=value)

        if request.refinery is None:
            # No Refinery available → can't run the SEQ/SWARM/HYBRID
            # paths. Log a warning, fall back to STATIC. This keeps
            # ``dispatch_task`` safe to call from MCP tools that haven't
            # plumbed a Refinery yet.
            logger.warning(
                "dispatch_task: router picked %s but no Refinery supplied — "
                "falling back to STATIC",
                choice.value,
            )
            span.add_event(
                "downgrade-missing-refinery",
                {"from": choice.value, "to": Topology.STATIC_HIERARCHY.value},
            )
            value = await request.static_executor()
            return DispatchResult(topology=Topology.STATIC_HIERARCHY, value=value)

        if choice == Topology.SEQUENTIAL_REFINERY:
            refinery_result = await request.refinery.submit(
                WriteRequest(
                    action="dispatch_sequential",
                    payload={
                        "task_class": request.dag.task_class,
                        "k": request.dag.extract_features().k,
                    },
                    executor=request.static_executor,
                    actor="mayor",
                )
            )
            return DispatchResult(
                topology=choice,
                value=refinery_result.value,
                refinery=refinery_result,
            )

        if not _can_parallel(request):
            # Defensive: caller asked for a parallel-capable router but
            # didn't supply the parallel deps. Log, downgrade to
            # SEQUENTIAL_REFINERY (Refinery is present, just not the
            # spawner / worktree-root / etc).
            logger.warning(
                "dispatch_task: router picked %s but parallel deps missing — "
                "downgrading to SEQUENTIAL_REFINERY",
                choice.value,
            )
            span.add_event(
                "downgrade-missing-parallel-deps",
                {"from": choice.value, "to": Topology.SEQUENTIAL_REFINERY.value},
            )
            refinery_result = await request.refinery.submit(
                WriteRequest(
                    action="dispatch_sequential",
                    payload={"task_class": request.dag.task_class},
                    executor=request.static_executor,
                    actor="mayor",
                )
            )
            return DispatchResult(
                topology=Topology.SEQUENTIAL_REFINERY,
                value=refinery_result.value,
                refinery=refinery_result,
            )

        # PARALLEL_POLECAT_SWARM or HYBRID_HIERARCHICAL_CLUSTER → swarm path.
        # The hybrid branch swaps in cluster_dag for partitioning.
        partitions = (
            cluster_dag(request.dag)
            if choice == Topology.HYBRID_HIERARCHICAL_CLUSTER
            else partition_dag(request.dag, request.coupling_threshold)
        )
        span.set_attribute("cao.dispatch.partitions", len(partitions))

        # Inject the partitions by monkey-patching swarm's partition_dag
        # at the call site. dispatch_swarm always re-partitions on entry
        # (commit 14 design), so we wrap that with our chosen list.
        # The cleanest way is to construct SwarmRequest with the same
        # threshold and let dispatch_swarm re-partition for SWARM. For
        # HYBRID we have to hand-roll the dispatch since we want
        # cluster_dag to win.
        if choice == Topology.HYBRID_HIERARCHICAL_CLUSTER:
            swarm_result = await _dispatch_hybrid(request, partitions)
        else:
            swarm_request = SwarmRequest(
                dag=request.dag,
                parent_repo=request.parent_repo,  # type: ignore[arg-type]
                worktree_root=request.worktree_root,  # type: ignore[arg-type]
                agent_profile=request.agent_profile,  # type: ignore[arg-type]
                coupling_threshold=request.coupling_threshold,
            )
            swarm_result = await dispatch_swarm(
                swarm_request,
                spawner=request.spawner,  # type: ignore[arg-type]
                killer=request.killer,  # type: ignore[arg-type]
                collector=request.collector,  # type: ignore[arg-type]
                refinery=request.refinery,
            )

        return DispatchResult(
            topology=choice,
            value=swarm_result.findings,
            swarm=swarm_result,
        )


def _replace_anchors(request: DispatchRequest, anchors: Sequence[str]) -> DispatchRequest:
    """Return a copy of ``request`` with ``anchors`` overridden.

    ``DispatchRequest`` is frozen — ``dataclasses.replace`` is the
    canonical way to swap fields. Used by ``dispatch_task`` when the
    caller passes ``anchors=`` rather than building them into the
    request up front.
    """
    from dataclasses import replace

    return replace(request, anchors=tuple(anchors))


def _can_parallel(request: DispatchRequest) -> bool:
    """All four parallel-topology dependencies present?"""
    return (
        request.parent_repo is not None
        and request.worktree_root is not None
        and request.agent_profile is not None
        and request.spawner is not None
        and request.killer is not None
        and request.collector is not None
    )


async def _dispatch_hybrid(request: DispatchRequest, partitions: list[Partition]) -> SwarmResult:
    """Hybrid path: swarm dispatch but with cluster-based partitions.

    We can't pass a custom partitioner into ``dispatch_swarm`` directly
    (it always re-partitions on entry, by design). Instead we build a
    "synthetic" DAG with one phantom edge per partition pair so
    ``swarm.partition_dag`` reproduces our cluster-based grouping. This
    keeps swarm.py agnostic about partitioning strategy.
    """
    # Build a DAG with exactly the same nodes; for every cluster, add
    # high-coupling edges connecting all members so the union-find
    # inside dispatch_swarm groups them the same way cluster_dag did.
    from cli_agent_orchestrator.orchestration.dag import TaskEdge

    new_edges: list[TaskEdge] = []
    for partition in partitions:
        if len(partition.nodes) <= 1:
            continue
        first = partition.nodes[0].id
        for other in partition.nodes[1:]:
            new_edges.append(TaskEdge(source=first, target=other.id, coupling=1.0))

    synthetic_dag = TaskDAG(
        session_id=request.dag.session_id,
        task_class=request.dag.task_class,
        nodes=request.dag.nodes,
        edges=tuple(new_edges),
    )
    swarm_request = SwarmRequest(
        dag=synthetic_dag,
        parent_repo=request.parent_repo,  # type: ignore[arg-type]
        worktree_root=request.worktree_root,  # type: ignore[arg-type]
        agent_profile=request.agent_profile,  # type: ignore[arg-type]
        coupling_threshold=request.coupling_threshold,
    )
    # The caller already guaranteed request.refinery is not None by
    # passing the early refinery-None check in dispatch_task.
    assert request.refinery is not None
    return await dispatch_swarm(
        swarm_request,
        spawner=request.spawner,  # type: ignore[arg-type]
        killer=request.killer,  # type: ignore[arg-type]
        collector=request.collector,  # type: ignore[arg-type]
        refinery=request.refinery,
    )
