"""Phase 3 orchestration primitives.

Currently exposes:
  * the static DAG description and AdaptOrch feature extractor (commit 9)
  * the topology router with stubbed ASI/budget oracles (commit 10)
  * the Polecat ephemeral read-only worker handle (commit 13)
  * the Polecat swarm dispatcher (commit 14)

Production wiring of the swarm into the Mayor's MCP dispatch path
(``_handoff_impl`` / ``_assign_impl``) lands in a follow-up commit.
"""

from cli_agent_orchestrator.orchestration.dag import (
    DagFeatures,
    TaskDAG,
    TaskEdge,
    TaskNode,
)
from cli_agent_orchestrator.orchestration.dispatch import (
    DispatchRequest,
    DispatchResult,
    KillSwitchEngaged,
    KillSwitchOracle,
    StaticExecutor,
    dispatch_task,
)
from cli_agent_orchestrator.orchestration.hybrid_cluster import (
    DEFAULT_MAX_CLUSTER_SIZE,
    Clusterer,
    LabelPropagationClusterer,
    cluster_dag,
)
from cli_agent_orchestrator.orchestration.polecat import (
    Polecat,
    PolecatSpec,
    TerminalKiller,
    TerminalSpawner,
)
from cli_agent_orchestrator.orchestration.polecat import spawn as spawn_polecat
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
    StubAsiOracle,
    StubBudgetOracle,
    TokenBudgetOracle,
    Topology,
    select_topology,
)

__all__ = [
    "AsiOracle",
    "Clusterer",
    "ConsolidationOracle",
    "DEFAULT_COUPLING_THRESHOLD",
    "DEFAULT_MAX_CLUSTER_SIZE",
    "DagFeatures",
    "DispatchRequest",
    "DispatchResult",
    "FindingsCollector",
    "KillSwitchEngaged",
    "KillSwitchOracle",
    "LabelPropagationClusterer",
    "Partition",
    "Polecat",
    "PolecatSpec",
    "StaticExecutor",
    "StubAsiOracle",
    "StubBudgetOracle",
    "SwarmRequest",
    "SwarmResult",
    "TaskDAG",
    "TaskEdge",
    "TaskNode",
    "TerminalKiller",
    "TerminalSpawner",
    "TokenBudgetOracle",
    "Topology",
    "cluster_dag",
    "dispatch_swarm",
    "dispatch_task",
    "partition_dag",
    "select_topology",
    "spawn_polecat",
]
