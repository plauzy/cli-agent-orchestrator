"""Phase 4: Agent Stability Index (ASI) governance.

The Deacon is an out-of-band evaluator that consumes the OTel spans
CAO already emits (Phase 1 + Phase 3) and computes a rolling Agent
Stability Index per the Rath (2026) framework — four weighted
dimensions producing a single composite score in [0, 1]. When the
score falls below threshold over consecutive windows, the Deacon
triggers mitigation actions that feed back into the topology
router.

The plan file's Phase 4 forward look captured the full design. This
package ships the primitives in tractable commits:

  19. ``AsiEvaluator`` core — rolling-window mechanics + dimension
      scoring + threshold detection. Pluggable ``DimensionScorer``
      protocol so v2.6 can swap heuristics for ML-backed scoring.
  20. ``AsiEvaluator.score_for_task_class`` is the ``AsiOracle``
      adapter point — pass an evaluator straight to ``select_topology``
      via ``asi=evaluator`` (duck-typed; no adapter class needed).
  21. Mitigation hooks (memory consolidation, behavioral anchoring,
      kill switch) firing on threshold breach.
  22. OTel collector consumer that feeds the evaluator from the
      OTLP stream.
"""

from cli_agent_orchestrator.observability.asi_evaluator import (
    AsiEvaluator,
    AsiScore,
    AsiThresholds,
    BehavioralBoundariesScorer,
    CoordinationScorer,
    DimensionScorer,
    MitigationEvent,
    MitigationHandler,
    ResponseConsistencyScorer,
    SpanRecord,
    ToolUsagePatternsScorer,
    from_iter,
)
from cli_agent_orchestrator.observability.experiments import bucket, is_treatment
from cli_agent_orchestrator.observability.mitigations import (
    DEFAULT_BEHAVIORAL_ANCHOR,
    AnchorRegistry,
    BehavioralAnchoringHandler,
    ConsolidationState,
    KillSwitchHandler,
    KillSwitchState,
    LoggingHandler,
    MemoryConsolidationHandler,
    SseBroadcastHandler,
    WALPersistenceHandler,
    get_anchor_registry,
    get_consolidation_state,
    get_kill_switch,
    reset_anchor_registry_for_tests,
    reset_consolidation_state_for_tests,
    standard_handlers,
)
from cli_agent_orchestrator.observability.phantom_state import (
    PHANTOM_STATE_DETECTION_ENABLED,
    PHANTOM_STATE_THRESHOLD_SECONDS,
    PhantomStateIncident,
    check_terminals,
)
from cli_agent_orchestrator.observability.span_consumer import (
    AsiSpanProcessor,
    span_to_record,
)

__all__ = [
    "DEFAULT_BEHAVIORAL_ANCHOR",
    "PHANTOM_STATE_DETECTION_ENABLED",
    "PHANTOM_STATE_THRESHOLD_SECONDS",
    "PhantomStateIncident",
    "check_terminals",
    "AnchorRegistry",
    "AsiEvaluator",
    "AsiScore",
    "AsiSpanProcessor",
    "AsiThresholds",
    "BehavioralAnchoringHandler",
    "BehavioralBoundariesScorer",
    "ConsolidationState",
    "CoordinationScorer",
    "DimensionScorer",
    "KillSwitchHandler",
    "KillSwitchState",
    "LoggingHandler",
    "MemoryConsolidationHandler",
    "MitigationEvent",
    "MitigationHandler",
    "ResponseConsistencyScorer",
    "SpanRecord",
    "SseBroadcastHandler",
    "ToolUsagePatternsScorer",
    "WALPersistenceHandler",
    "bucket",
    "from_iter",
    "get_anchor_registry",
    "get_consolidation_state",
    "get_kill_switch",
    "is_treatment",
    "reset_anchor_registry_for_tests",
    "reset_consolidation_state_for_tests",
    "span_to_record",
    "standard_handlers",
]
