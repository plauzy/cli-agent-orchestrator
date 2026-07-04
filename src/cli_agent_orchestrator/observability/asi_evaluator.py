"""Agent Stability Index evaluator (Phase 4 / commit 19).

Computes a rolling ASI score per the Rath (2026) framework
(arxiv:2601.04170). Four weighted dimensions:

    Response Consistency      (0.30)
    Tool Usage Patterns       (0.25)
    Inter-Agent Coordination  (0.25)
    Behavioral Boundaries     (0.20)

Inputs are ``SpanRecord``s — a flat shape derived from CAO's existing
OTel GenAI v1.37+ semconv spans (Phase 1 + Phase 3 emissions). The
evaluator keeps per-task-class rolling windows and emits an
``AsiScore`` every time a window completes. When ``CONSECUTIVE_WINDOWS_REQUIRED``
windows fall below ``mitigate``, the registered mitigation handlers
fire (commit 21 wires actual handlers).

Threshold values are calibration parameters — the v2.5 plan explicitly
calls them out as "tune over the first month of operation". Defaults
follow the paper's published curves: warn at 0.85, mitigate at 0.75
over 3 consecutive windows, kill at 0.60.

Dimension scorers are pluggable via the ``DimensionScorer`` Protocol
so v2.6 can swap heuristics for ML-backed implementations without
touching the rolling-window mechanics. The default scorers in this
module are deterministic proxies derived from existing span attributes
(``cao.tool.outcome``, ``cao.topology.choice``, span duration, etc.).
"""

from __future__ import annotations

import logging
import math
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# Rath (2026) §4 weights — load-bearing per the plan.
_WEIGHT_RESPONSE_CONSISTENCY = 0.30
_WEIGHT_TOOL_USAGE_PATTERNS = 0.25
_WEIGHT_COORDINATION = 0.25
_WEIGHT_BEHAVIORAL_BOUNDARIES = 0.20


@dataclass(frozen=True)
class SpanRecord:
    """Flat representation of one OTel span the Deacon consumes.

    Mirrors what CAO already emits via Phase 1 + Phase 3 — operation
    name, tool name, agent id, conversation id, attributes dict, and
    duration. The OTel collector consumer (commit 22) builds these
    from ``opentelemetry.sdk.trace.ReadableSpan`` instances.
    """

    name: str
    operation: str  # gen_ai.operation.name (invoke_agent | execute_tool | chat)
    agent_id: str
    conversation_id: str
    task_class: str
    duration_ms: float
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AsiThresholds:
    """Per-deployment calibration parameters."""

    warn: float = 0.85
    mitigate: float = 0.75
    kill: float = 0.60
    consecutive_windows_required: int = 3
    window_size: int = 50  # spans per rolling window


@dataclass(frozen=True)
class AsiScore:
    """Composite ASI score with per-dimension breakdown."""

    overall: float  # weighted sum of the four dimensions
    response_consistency: float
    tool_usage_patterns: float
    coordination: float
    behavioral_boundaries: float
    task_class: str
    span_count: int

    @classmethod
    def from_dimensions(
        cls,
        *,
        response_consistency: float,
        tool_usage_patterns: float,
        coordination: float,
        behavioral_boundaries: float,
        task_class: str,
        span_count: int,
    ) -> "AsiScore":
        overall = (
            _WEIGHT_RESPONSE_CONSISTENCY * response_consistency
            + _WEIGHT_TOOL_USAGE_PATTERNS * tool_usage_patterns
            + _WEIGHT_COORDINATION * coordination
            + _WEIGHT_BEHAVIORAL_BOUNDARIES * behavioral_boundaries
        )
        return cls(
            overall=overall,
            response_consistency=response_consistency,
            tool_usage_patterns=tool_usage_patterns,
            coordination=coordination,
            behavioral_boundaries=behavioral_boundaries,
            task_class=task_class,
            span_count=span_count,
        )


# ---------------------------------------------------------------------------
# Dimension scorers (pluggable)
# ---------------------------------------------------------------------------


@runtime_checkable
class DimensionScorer(Protocol):
    """Compute one ASI dimension's score from a window of spans.

    Must return a value in [0, 1]. Pure function of the input window —
    no I/O, no shared state — so the evaluator can swap implementations
    deterministically.
    """

    def score(self, spans: list[SpanRecord]) -> float: ...


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


class ResponseConsistencyScorer:
    """Proxy: ratio of successful tool outcomes vs. all execute_tool spans.

    The Rath framework's "response consistency" measures output stability
    across similar prompts. We don't run a model in this scorer — instead
    we lean on the ``cao.tool.outcome`` attribute that every Phase 1
    MCP-tool-instrumented span already carries (success / failure /
    error / *_timeout). High success rate → consistent.
    """

    def score(self, spans: list[SpanRecord]) -> float:
        execute_tool_spans = [s for s in spans if s.operation == "execute_tool"]
        if not execute_tool_spans:
            # No execute_tool spans in the window → assume consistent.
            return 1.0
        successes = sum(
            1 for s in execute_tool_spans if s.attributes.get("cao.tool.outcome") == "success"
        )
        return _clamp(successes / len(execute_tool_spans))


class ToolUsagePatternsScorer:
    """Proxy: 1 − normalized entropy of tool selection within the window.

    The Rath framework's "tool usage patterns" tracks variance in tool
    selection / sequencing. Stable agents pick tools predictably; drifting
    agents thrash. We compute Shannon entropy over the tool name
    distribution and invert: low entropy → stable → high score.

    Bound: entropy of a uniform distribution over k distinct tools is
    log2(k). We normalize against log2(N+1) where N is span count so a
    single-call window scores 1.0 (no thrash possible).
    """

    def score(self, spans: list[SpanRecord]) -> float:
        tool_spans = [s for s in spans if s.operation == "execute_tool"]
        if not tool_spans:
            return 1.0
        # Bucket by tool name (extracted from span name "execute_tool <name>").
        counts: dict[str, int] = {}
        for s in tool_spans:
            tool = s.name[len("execute_tool ") :] if s.name.startswith("execute_tool ") else s.name
            counts[tool] = counts.get(tool, 0) + 1
        total = sum(counts.values())
        # Shannon entropy (base 2).
        entropy = -sum((c / total) * math.log2(c / total) for c in counts.values())
        # Max possible entropy for this window size.
        max_entropy = math.log2(max(total, 2))
        return _clamp(1.0 - (entropy / max_entropy))


class CoordinationScorer:
    """Proxy: handoff efficiency via inverse-median execute_tool span duration.

    The Rath framework's "inter-agent coordination" measures consensus
    rates and handoff efficiency. We approximate via the median duration
    of ``execute_tool delegate``-style spans — fast handoffs imply
    smooth coordination. The reference baseline is 30 seconds (matches
    Phase 1 plan §11 "p50 latency 10–40s for 3-agent flows").
    """

    REFERENCE_MS = 30_000.0  # 30s baseline → score 0.5

    def score(self, spans: list[SpanRecord]) -> float:
        # Delegate-shaped tools: handoff, assign. (send_message and
        # load_skill aren't agent-coordination events.)
        coord_spans = [
            s
            for s in spans
            if s.operation == "execute_tool"
            and s.name.startswith(("execute_tool handoff", "execute_tool assign"))
        ]
        if not coord_spans:
            return 1.0  # No coordination this window → no penalty.
        median_ms = statistics.median(s.duration_ms for s in coord_spans)
        # Logistic curve: median == REFERENCE → 0.5, median → 0 → 1.0,
        # median → ∞ → 0.0.
        score = 1.0 / (1.0 + median_ms / self.REFERENCE_MS)
        return _clamp(score)


class BehavioralBoundariesScorer:
    """Proxy: 1 − error rate across the window.

    The Rath framework's "behavioral boundaries" tracks output length
    anomalies, error pattern emergence, and human-intervention rate.
    The simplest proxy from existing CAO spans: rate of error
    outcomes (``cao.tool.outcome`` ∈ {error, http_error, connection_error,
    ready_timeout, completion_timeout}). Lower error rate → cleaner
    boundaries.
    """

    _ERROR_OUTCOMES = frozenset(
        {"error", "http_error", "connection_error", "ready_timeout", "completion_timeout"}
    )

    def score(self, spans: list[SpanRecord]) -> float:
        outcomes = [
            s.attributes.get("cao.tool.outcome") for s in spans if s.operation == "execute_tool"
        ]
        outcomes = [o for o in outcomes if o is not None]
        if not outcomes:
            return 1.0
        errors = sum(1 for o in outcomes if o in self._ERROR_OUTCOMES)
        return _clamp(1.0 - (errors / len(outcomes)))


# ---------------------------------------------------------------------------
# Mitigation hooks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MitigationEvent:
    """Emitted when a per-conversation rolling score crosses a threshold."""

    severity: str  # "warn" | "mitigate" | "kill" | "recover"
    score: AsiScore
    consecutive_below: int


MitigationHandler = Callable[[MitigationEvent], None]


# ---------------------------------------------------------------------------
# Rolling-window evaluator
# ---------------------------------------------------------------------------


class AsiEvaluator:
    """Per-task-class rolling-window ASI evaluator.

    Usage::

        evaluator = AsiEvaluator()
        evaluator.add_handler(my_mitigation_callback)

        # In the OTel consumer:
        for span in span_stream():
            evaluator.observe(SpanRecord.from_otel(span))

        # In the topology router (via AsiOracle adapter — commit 20):
        score = evaluator.score_for_task_class("research_breadth")
    """

    DEFAULT_SCORERS: dict[str, DimensionScorer] = {
        "response_consistency": ResponseConsistencyScorer(),
        "tool_usage_patterns": ToolUsagePatternsScorer(),
        "coordination": CoordinationScorer(),
        "behavioral_boundaries": BehavioralBoundariesScorer(),
    }

    def __init__(
        self,
        thresholds: Optional[AsiThresholds] = None,
        scorers: Optional[dict[str, DimensionScorer]] = None,
    ) -> None:
        self._thresholds = thresholds or AsiThresholds()
        self._scorers = dict(scorers or self.DEFAULT_SCORERS)
        # Per-task-class window of spans pending evaluation.
        self._pending: dict[str, deque[SpanRecord]] = defaultdict(
            lambda: deque(maxlen=self._thresholds.window_size)
        )
        # Per-task-class history of completed window scores. Bounded so
        # the evaluator's memory footprint is O(num_task_classes).
        self._scores: dict[str, deque[AsiScore]] = defaultdict(
            lambda: deque(maxlen=max(10, self._thresholds.consecutive_windows_required * 2))
        )
        # Per-task-class consecutive-below counters for mitigation.
        self._consecutive_below: dict[str, int] = defaultdict(int)
        self._handlers: list[MitigationHandler] = []

    # -- ingestion ---------------------------------------------------------

    def observe(self, span: SpanRecord) -> Optional[AsiScore]:
        """Append ``span`` to the matching task-class window. Returns the
        completed window's score if the window just filled."""
        if not span.task_class:
            return None
        pending = self._pending[span.task_class]
        pending.append(span)
        if len(pending) < self._thresholds.window_size:
            return None
        # Window full → score and reset.
        spans = list(pending)
        pending.clear()
        score = self._score_window(span.task_class, spans)
        self._scores[span.task_class].append(score)
        self._maybe_trigger(span.task_class, score)
        return score

    def _score_window(self, task_class: str, spans: list[SpanRecord]) -> AsiScore:
        return AsiScore.from_dimensions(
            response_consistency=self._scorers["response_consistency"].score(spans),
            tool_usage_patterns=self._scorers["tool_usage_patterns"].score(spans),
            coordination=self._scorers["coordination"].score(spans),
            behavioral_boundaries=self._scorers["behavioral_boundaries"].score(spans),
            task_class=task_class,
            span_count=len(spans),
        )

    # -- mitigation triggering --------------------------------------------

    def _maybe_trigger(self, task_class: str, score: AsiScore) -> None:
        t = self._thresholds
        if score.overall < t.kill:
            # Kill switch fires immediately.
            self._consecutive_below[task_class] += 1
            self._fire("kill", score, self._consecutive_below[task_class])
            return
        if score.overall < t.mitigate:
            self._consecutive_below[task_class] += 1
            if self._consecutive_below[task_class] >= t.consecutive_windows_required:
                self._fire("mitigate", score, self._consecutive_below[task_class])
            return
        if score.overall < t.warn:
            # Warning doesn't reset the counter — drift is drift.
            self._fire("warn", score, self._consecutive_below[task_class])
            return
        # Score recovered above warn threshold.
        if self._consecutive_below[task_class] > 0:
            self._consecutive_below[task_class] = 0
            self._fire("recover", score, 0)

    def _fire(self, severity: str, score: AsiScore, consecutive_below: int) -> None:
        event = MitigationEvent(severity=severity, score=score, consecutive_below=consecutive_below)
        for handler in self._handlers:
            try:
                handler(event)
            except Exception:
                logger.warning("ASI mitigation handler %s raised", handler, exc_info=True)

    # -- public API -------------------------------------------------------

    def add_handler(self, handler: MitigationHandler) -> None:
        self._handlers.append(handler)

    def score_for_task_class(self, task_class: str) -> float:
        """``AsiOracle`` interface — return the most recent ASI for ``task_class``.

        Returns 1.0 (perfect stability) when no history exists yet for
        that task class, so the topology router doesn't pessimize on
        cold start.
        """
        history = self._scores.get(task_class)
        if not history:
            return 1.0
        return history[-1].overall

    def history(self, task_class: str) -> list[AsiScore]:
        """Bounded score history for ``task_class``. Used by tests + dashboards."""
        return list(self._scores.get(task_class, ()))

    def consecutive_below(self, task_class: str) -> int:
        return self._consecutive_below.get(task_class, 0)


def from_iter(
    spans: Iterable[SpanRecord],
    *,
    thresholds: Optional[AsiThresholds] = None,
) -> AsiEvaluator:
    """Convenience: build an evaluator and replay an iterable of spans
    through it. Used by tests + the OTel collector consumer (commit 22).
    """
    evaluator = AsiEvaluator(thresholds=thresholds)
    for span in spans:
        evaluator.observe(span)
    return evaluator
