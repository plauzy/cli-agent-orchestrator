"""AdaptOrch topology router with ASI-feedback loop (Phase 3 / commit 10).

Inputs:
  * a ``TaskDAG`` from the Mayor's planning pass
  * an ``AsiOracle`` reporting recent stability for the DAG's task class
    (stubbed to a constant 1.0 in Phase 3 — the Deacon arrives in Phase 4)
  * a ``TokenBudgetOracle`` reporting projected cost vs. remaining budget

Output: a ``Topology`` enum value naming one of four execution shapes.
The Mayor's dispatch path (commit 11) consumes this to decide whether
work goes through the Refinery write queue, fans out to a Polecat read
swarm, etc.

The decision logic mirrors §10.3 of the v2.5 vision doc:

  γ ≥ 0.4              → SEQUENTIAL_REFINERY        (high coupling)
  γ < 0.4 ∧ ω > 5      → PARALLEL_POLECAT_SWARM     (high parallelism, low coupling)
  k > 50               → HYBRID_HIERARCHICAL_CLUSTER (large fan-out)
  else                 → STATIC_HIERARCHY           (default two-level)

Feedback overrides applied after the base decision:

  ASI < 0.75 → downgrade SWARM/HYBRID to SEQUENTIAL_REFINERY
  projected > remaining → degrade gracefully to STATIC_HIERARCHY

Every input feature, the ASI score, and the chosen topology are
recorded as span attributes on a ``cao.topology.select`` span so the
Phase 4 Deacon can correlate routing decisions with downstream stability.
"""

from __future__ import annotations

import os
import re
from enum import Enum
from typing import Protocol

from opentelemetry import trace

from cli_agent_orchestrator.orchestration.dag import DagFeatures, TaskDAG
from cli_agent_orchestrator.telemetry import semconv

_TRACER = trace.get_tracer("cao.orchestration.router", "2.5.0")

# Calibration thresholds. These match the AdaptOrch paper / v2.5 plan.
# Surfaced as module constants so tests can monkey-patch them when
# exercising adjacent regimes without rebuilding the routing logic.
GAMMA_SEQUENTIAL_THRESHOLD = 0.4
OMEGA_SWARM_THRESHOLD = 5
K_HYBRID_THRESHOLD = 50

# ASI threshold below which the router downgrades parallelism. Default
# matches the Rath (2026) framework's mitigation trigger. Per the plan,
# this is a calibration parameter to be tuned per deployment over the
# first month of operation.
ASI_DOWNGRADE_THRESHOLD = 0.75


class Topology(str, Enum):
    PARALLEL_POLECAT_SWARM = "parallel-polecat-swarm"
    SEQUENTIAL_REFINERY = "sequential-refinery"
    HYBRID_HIERARCHICAL_CLUSTER = "hybrid-hierarchical-cluster"
    STATIC_HIERARCHY = "static-hierarchy"


# ---------------------------------------------------------------------------
# Oracle protocols
# ---------------------------------------------------------------------------


class AsiOracle(Protocol):
    """Source of recent Agent Stability Index per task class.

    Concrete implementation arrives with the Deacon sidecar in Phase 4.
    Phase 3 ships a stub that returns 1.0 always.
    """

    def score_for_task_class(self, task_class: str) -> float: ...


class TokenBudgetOracle(Protocol):
    """Source of projected vs. remaining token budget for a dispatch.

    Phase 3 ships a stub that reports infinite budget. The real budget
    accounting (against per-tenant settings + the three-layer cache)
    arrives in Phase 5.
    """

    def projected_cost(self, topology: Topology, features: DagFeatures) -> float: ...

    def remaining(self) -> float: ...


class ConsolidationOracle(Protocol):
    """Source of consolidation markers per task class.

    The Phase 4 ``ConsolidationState`` (observability/mitigations.py)
    satisfies this Protocol exactly. The router uses it to prefer
    cached / lower-cost topologies for marked classes — sustained drift
    is a signal that the agent's working memory has grown noisy and
    falling back to a smaller, simpler topology helps it recover.
    """

    def is_marked(self, task_class: str) -> bool: ...


# ---------------------------------------------------------------------------
# Phase 3 stubs
# ---------------------------------------------------------------------------


class StubAsiOracle:
    """Always-stable oracle. Replaced by the Deacon sidecar in Phase 4."""

    def score_for_task_class(self, task_class: str) -> float:
        return 1.0


class StubBudgetOracle:
    """Unbounded-budget oracle. Replaced by per-tenant accounting in Phase 5.

    ``projected_cost`` is a coarse heuristic — sum of node ``cost_estimate``
    weights times a topology-shape multiplier. Useful only for shape;
    Phase 5 replaces it with cache-aware token-counted projections.
    """

    _MULTIPLIERS = {
        Topology.STATIC_HIERARCHY: 1.0,
        Topology.SEQUENTIAL_REFINERY: 1.0,
        Topology.PARALLEL_POLECAT_SWARM: 1.5,  # parallel call overhead
        Topology.HYBRID_HIERARCHICAL_CLUSTER: 1.75,  # cluster + synth overhead
    }

    def __init__(self, remaining_budget: float = float("inf")) -> None:
        self._remaining = remaining_budget

    def projected_cost(self, topology: Topology, features: DagFeatures) -> float:
        # k * 1.0 default (since DagFeatures doesn't carry per-node costs;
        # those live on TaskNode.cost_estimate which the router doesn't
        # see by design — features are intentionally minimal).
        return features.k * self._MULTIPLIERS[topology]

    def remaining(self) -> float:
        return self._remaining


# ---------------------------------------------------------------------------
# Smart-Friend capability-and-difficulty-aware routing (addendum §11)
# ---------------------------------------------------------------------------
#
# The Smart-Friend pattern extends AdaptOrch with per-sub-task model routing.
# Default is all-frontier (conservative); opt-in via SMART_FRIEND_ROUTING=true.
# When enabled, classify the sub-task and recommend a preferred provider.
# The Mayor's dispatch path consumes the recommendation; it is advisory only.

SMART_FRIEND_ROUTING_ENABLED: bool = os.getenv("SMART_FRIEND_ROUTING", "false").lower() == "true"


class SubTaskType(str, Enum):
    DEBUG = "debug"
    VISUAL_REASONING = "visual_reasoning"
    TEST_GENERATION = "test_generation"
    REFACTOR = "refactor"
    REVIEW = "review"
    GENERAL = "general"


# Keyword patterns that classify a task description into a sub-task type.
# Order matters — first match wins.
_SUBTASK_PATTERNS: list[tuple[re.Pattern[str], SubTaskType]] = [
    (re.compile(r"\b(debug|traceback|stack.?trace|exception|error)\b", re.I), SubTaskType.DEBUG),
    (
        re.compile(r"\b(screenshot|diagram|chart|visual|image|ui|layout)\b", re.I),
        SubTaskType.VISUAL_REASONING,
    ),
    (
        re.compile(r"\b(test|spec|unittest|pytest|coverage|assert)\b", re.I),
        SubTaskType.TEST_GENERATION,
    ),
    (re.compile(r"\b(refactor|rename|extract|move|restructure)\b", re.I), SubTaskType.REFACTOR),
    (re.compile(r"\b(review|audit|check|lint|quality)\b", re.I), SubTaskType.REVIEW),
]

# Provider recommendations per sub-task type.
# "reviewer_differs" means the Reviewer Polecat should use a DIFFERENT
# provider from the coder (cross-frontier diversity boosts review value).
_SUBTASK_PROVIDER_MAP: dict[SubTaskType, str] = {
    SubTaskType.DEBUG: "claude_code",
    SubTaskType.VISUAL_REASONING: "gemini_cli",
    SubTaskType.TEST_GENERATION: "claude_code",
    SubTaskType.REFACTOR: "claude_code",
    SubTaskType.REVIEW: "claude_code",
    SubTaskType.GENERAL: "claude_code",
}

# Default coder provider (used for cross-frontier diversity in Review tasks)
_DEFAULT_CODER_PROVIDER: str = os.getenv("CAO_DEFAULT_CODER_PROVIDER", "kiro_cli")


def classify_subtask(description: str) -> SubTaskType:
    """Return the sub-task type for a free-form task description."""
    for pattern, subtask_type in _SUBTASK_PATTERNS:
        if pattern.search(description):
            return subtask_type
    return SubTaskType.GENERAL


def recommend_provider(subtask_type: SubTaskType, coder_provider: str | None = None) -> str:
    """Return the recommended provider for a sub-task type.

    For REVIEW tasks, returns a provider that differs from ``coder_provider``
    to maximize cross-frontier diversity. When not enabled, returns the
    coder's own provider unchanged.
    """
    if not SMART_FRIEND_ROUTING_ENABLED:
        return coder_provider or _DEFAULT_CODER_PROVIDER

    recommended = _SUBTASK_PROVIDER_MAP[subtask_type]

    if subtask_type == SubTaskType.REVIEW and coder_provider and coder_provider == recommended:
        # Ensure cross-frontier diversity: reviewer must differ from coder.
        alternatives = [p for p in _SUBTASK_PROVIDER_MAP.values() if p != coder_provider]
        return alternatives[0] if alternatives else recommended

    return recommended


# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------


def _base_topology(features: DagFeatures) -> Topology:
    """Decide topology from DAG features alone, before any feedback."""
    if features.gamma >= GAMMA_SEQUENTIAL_THRESHOLD:
        return Topology.SEQUENTIAL_REFINERY
    if features.omega > OMEGA_SWARM_THRESHOLD:
        return Topology.PARALLEL_POLECAT_SWARM
    if features.k > K_HYBRID_THRESHOLD:
        return Topology.HYBRID_HIERARCHICAL_CLUSTER
    return Topology.STATIC_HIERARCHY


def select_topology(
    dag: TaskDAG,
    asi: AsiOracle | None = None,
    budget: TokenBudgetOracle | None = None,
    consolidation: ConsolidationOracle | None = None,
) -> Topology:
    """Choose an execution topology for ``dag``.

    Records the decision and every input on a ``cao.topology.select``
    span so the Deacon (Phase 4) and any retrospective analysis can
    correlate routing choices with outcomes.

    Both oracles default to their Phase 3 stubs (``StubAsiOracle`` /
    ``StubBudgetOracle``) so callers that don't yet have the Deacon
    or per-tenant budget wiring still get sensible behavior.

    When ``consolidation`` reports the task class as marked, the router
    prefers a lower-cost topology — Deacon's signal that the agent's
    working memory is noisy. This downgrade fires before the budget
    guard so it shows up as ``consolidation-downgrade`` in the span.
    """
    asi = asi or StubAsiOracle()
    budget = budget or StubBudgetOracle()

    with _TRACER.start_as_current_span("cao.topology.select") as span:
        features = dag.extract_features()
        span.set_attribute(semconv.GEN_AI_CONVERSATION_ID, dag.session_id)
        span.set_attribute(semconv.CAO_TASK_CLASS, dag.task_class)
        span.set_attribute(semconv.CAO_TOPOLOGY_FEATURES_OMEGA, features.omega)
        span.set_attribute(semconv.CAO_TOPOLOGY_FEATURES_GAMMA, features.gamma)
        span.set_attribute(semconv.CAO_TOPOLOGY_FEATURES_DEPTH, features.depth)
        span.set_attribute(semconv.CAO_TOPOLOGY_FEATURES_K, features.k)

        choice = _base_topology(features)

        # ASI feedback: a stability dip downgrades parallel topologies.
        asi_score = asi.score_for_task_class(dag.task_class)
        span.set_attribute(semconv.CAO_ASI_SCORE, asi_score)
        if asi_score < ASI_DOWNGRADE_THRESHOLD and choice in (
            Topology.PARALLEL_POLECAT_SWARM,
            Topology.HYBRID_HIERARCHICAL_CLUSTER,
        ):
            span.add_event(
                "asi-degraded-downgrade",
                {"from": choice.value, "to": Topology.SEQUENTIAL_REFINERY.value, "asi": asi_score},
            )
            choice = Topology.SEQUENTIAL_REFINERY

        # Consolidation feedback: marked task classes prefer the cheapest
        # topology. The Deacon set the marker on sustained drift; the
        # cooperating mitigation is a lower-cost dispatch on the next
        # round. Marker is cleared automatically on recover.
        if consolidation is not None and consolidation.is_marked(dag.task_class):
            span.set_attribute("cao.consolidation.marked", True)
            if choice in (
                Topology.PARALLEL_POLECAT_SWARM,
                Topology.HYBRID_HIERARCHICAL_CLUSTER,
            ):
                span.add_event(
                    "consolidation-downgrade",
                    {"from": choice.value, "to": Topology.SEQUENTIAL_REFINERY.value},
                )
                choice = Topology.SEQUENTIAL_REFINERY

        # Budget guard: degrade gracefully if projected cost exceeds budget.
        projected = budget.projected_cost(choice, features)
        remaining = budget.remaining()
        span.set_attribute(semconv.CAO_BUDGET_PROJECTED_COST, projected)
        span.set_attribute(semconv.CAO_BUDGET_REMAINING, remaining)
        if projected > remaining:
            span.add_event(
                "budget-exhaustion-degrade",
                {
                    "from": choice.value,
                    "to": Topology.STATIC_HIERARCHY.value,
                    "projected": projected,
                    "remaining": remaining,
                },
            )
            choice = Topology.STATIC_HIERARCHY

        span.set_attribute(semconv.CAO_TOPOLOGY_CHOICE, choice.value)
        return choice
