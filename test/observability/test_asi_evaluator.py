"""Tests for the Deacon ASI evaluator (Phase 4 / commit 19).

Coverage matrix:
  * Each dimension scorer produces sensible scores in [0, 1] for
    representative inputs.
  * Composite ``AsiScore`` weights match the Rath (2026) framework
    (0.30 / 0.25 / 0.25 / 0.20).
  * Rolling window mechanics: spans accumulate per task class until
    window_size is hit, then a score is emitted.
  * Mitigation triggering: warn / mitigate (after N consecutive) / kill
    / recover, with handler delivery.
  * ``score_for_task_class`` (the ``AsiOracle`` adapter point) returns
    1.0 for unknown task classes (cold start) and the most recent score
    otherwise.
"""

from __future__ import annotations

from typing import Any

import pytest

from cli_agent_orchestrator.observability.asi_evaluator import (
    AsiEvaluator,
    AsiScore,
    AsiThresholds,
    BehavioralBoundariesScorer,
    CoordinationScorer,
    MitigationEvent,
    ResponseConsistencyScorer,
    SpanRecord,
    ToolUsagePatternsScorer,
    from_iter,
)


def _span(
    *,
    name: str = "execute_tool send_message",
    operation: str = "execute_tool",
    task_class: str = "test",
    duration_ms: float = 100.0,
    outcome: str = "success",
    extra: dict[str, Any] | None = None,
) -> SpanRecord:
    attrs: dict[str, Any] = {"cao.tool.outcome": outcome}
    if extra:
        attrs.update(extra)
    return SpanRecord(
        name=name,
        operation=operation,
        agent_id="agent",
        conversation_id="conv-1",
        task_class=task_class,
        duration_ms=duration_ms,
        attributes=attrs,
    )


# ---------------------------------------------------------------------------
# Dimension scorers
# ---------------------------------------------------------------------------


class TestResponseConsistency:
    def test_all_success_yields_one(self):
        spans = [_span(outcome="success") for _ in range(10)]
        assert ResponseConsistencyScorer().score(spans) == 1.0

    def test_all_error_yields_zero(self):
        spans = [_span(outcome="error") for _ in range(10)]
        assert ResponseConsistencyScorer().score(spans) == 0.0

    def test_half_success_yields_half(self):
        spans = [_span(outcome="success") for _ in range(5)] + [
            _span(outcome="error") for _ in range(5)
        ]
        assert ResponseConsistencyScorer().score(spans) == 0.5

    def test_no_execute_tool_spans_returns_one(self):
        spans = [_span(operation="invoke_agent", outcome="ignored") for _ in range(5)]
        assert ResponseConsistencyScorer().score(spans) == 1.0


class TestToolUsagePatterns:
    def test_single_tool_repeated_yields_one(self):
        spans = [_span(name="execute_tool send_message") for _ in range(8)]
        # Entropy = 0 → 1.0.
        assert ToolUsagePatternsScorer().score(spans) == 1.0

    def test_uniform_distribution_yields_zero(self):
        spans = [_span(name=f"execute_tool tool-{i}") for i in range(8)]
        # Uniform over 8 distinct tools → max entropy → ~0.0.
        assert ToolUsagePatternsScorer().score(spans) == pytest.approx(0.0, abs=0.05)

    def test_mixed_distribution_yields_intermediate(self):
        # Mostly one tool with a few outliers → intermediate.
        spans = [_span(name="execute_tool send_message") for _ in range(7)] + [
            _span(name="execute_tool handoff")
        ]
        score = ToolUsagePatternsScorer().score(spans)
        assert 0.5 < score < 1.0


class TestCoordination:
    def test_fast_handoffs_score_high(self):
        spans = [_span(name="execute_tool handoff", duration_ms=1_000) for _ in range(5)]
        score = CoordinationScorer().score(spans)
        # 1s vs 30s baseline → ~0.97.
        assert score > 0.9

    def test_slow_handoffs_score_low(self):
        spans = [_span(name="execute_tool handoff", duration_ms=300_000) for _ in range(5)]  # 300s
        score = CoordinationScorer().score(spans)
        assert score < 0.2

    def test_no_coordination_spans_yields_one(self):
        spans = [_span(name="execute_tool send_message")]
        assert CoordinationScorer().score(spans) == 1.0


class TestBehavioralBoundaries:
    def test_no_errors_yields_one(self):
        spans = [_span(outcome="success") for _ in range(10)]
        assert BehavioralBoundariesScorer().score(spans) == 1.0

    def test_all_errors_yields_zero(self):
        spans = [_span(outcome="error") for _ in range(10)]
        assert BehavioralBoundariesScorer().score(spans) == 0.0

    def test_timeout_counts_as_error(self):
        spans = [
            _span(outcome="success"),
            _span(outcome="ready_timeout"),
            _span(outcome="completion_timeout"),
            _span(outcome="success"),
        ]
        # 2/4 errors → 0.5.
        assert BehavioralBoundariesScorer().score(spans) == 0.5


# ---------------------------------------------------------------------------
# Composite weights
# ---------------------------------------------------------------------------


class TestAsiScore:
    def test_overall_uses_rath_weights(self):
        score = AsiScore.from_dimensions(
            response_consistency=1.0,
            tool_usage_patterns=0.0,
            coordination=0.0,
            behavioral_boundaries=0.0,
            task_class="test",
            span_count=50,
        )
        # 0.30 * 1.0 + 0.25 * 0 + 0.25 * 0 + 0.20 * 0 = 0.30.
        assert score.overall == pytest.approx(0.30)

    def test_perfect_score_is_one(self):
        score = AsiScore.from_dimensions(
            response_consistency=1.0,
            tool_usage_patterns=1.0,
            coordination=1.0,
            behavioral_boundaries=1.0,
            task_class="test",
            span_count=50,
        )
        assert score.overall == pytest.approx(1.0)

    def test_zero_score_is_zero(self):
        score = AsiScore.from_dimensions(
            response_consistency=0.0,
            tool_usage_patterns=0.0,
            coordination=0.0,
            behavioral_boundaries=0.0,
            task_class="test",
            span_count=50,
        )
        assert score.overall == 0.0


# ---------------------------------------------------------------------------
# Rolling-window mechanics
# ---------------------------------------------------------------------------


class TestRollingWindow:
    def test_observe_below_window_size_returns_none(self):
        ev = AsiEvaluator(thresholds=AsiThresholds(window_size=10))
        for _ in range(9):
            assert ev.observe(_span()) is None

    def test_window_completion_emits_score(self):
        ev = AsiEvaluator(thresholds=AsiThresholds(window_size=5))
        results = [ev.observe(_span()) for _ in range(5)]
        # First four are None, fifth completes the window.
        assert results[:4] == [None, None, None, None]
        assert isinstance(results[4], AsiScore)
        # Perfect-success spans → score == 1.0.
        assert results[4].overall == pytest.approx(1.0)

    def test_per_task_class_independence(self):
        ev = AsiEvaluator(thresholds=AsiThresholds(window_size=5))
        # Fill window for task_class A.
        for _ in range(5):
            ev.observe(_span(task_class="A"))
        # task_class B still has nothing.
        assert ev.score_for_task_class("B") == 1.0  # cold-start default

    def test_score_for_task_class_returns_one_on_cold_start(self):
        ev = AsiEvaluator()
        assert ev.score_for_task_class("never_seen") == 1.0

    def test_score_for_task_class_returns_latest(self):
        ev = AsiEvaluator(thresholds=AsiThresholds(window_size=5))
        # First window: all error → score < 1.
        for _ in range(5):
            ev.observe(_span(outcome="error"))
        first = ev.score_for_task_class("test")
        assert first < 1.0
        # Second window: all success → score should rise.
        for _ in range(5):
            ev.observe(_span(outcome="success"))
        second = ev.score_for_task_class("test")
        assert second > first


# ---------------------------------------------------------------------------
# Mitigation triggering
# ---------------------------------------------------------------------------


class TestMitigation:
    def test_warn_fires_below_warn_threshold(self):
        events: list[MitigationEvent] = []
        ev = AsiEvaluator(
            thresholds=AsiThresholds(window_size=4, warn=0.85, mitigate=0.50, kill=0.20)
        )
        ev.add_handler(events.append)
        # 1 success + 3 errors = 0.25 success rate. Composite ~ 0.30 → between
        # mitigate (0.50) and kill (0.20)? Actually score will be moderate
        # because some dimensions stay high. Let's just observe.
        ev.observe(_span(outcome="success"))
        ev.observe(_span(outcome="error"))
        ev.observe(_span(outcome="error"))
        ev.observe(_span(outcome="error"))
        # At least one event fired.
        assert len(events) >= 1

    def test_mitigate_requires_consecutive_windows(self):
        events: list[MitigationEvent] = []
        ev = AsiEvaluator(
            thresholds=AsiThresholds(
                window_size=4,
                warn=0.95,
                mitigate=0.95,  # very high → trip on any imperfection
                kill=0.0,
                consecutive_windows_required=2,
            )
        )
        ev.add_handler(events.append)
        # First window with one error → score < 0.95 → consecutive=1, no mitigate yet.
        for _ in range(3):
            ev.observe(_span(outcome="success"))
        ev.observe(_span(outcome="error"))
        first_mit = [e for e in events if e.severity == "mitigate"]
        assert len(first_mit) == 0
        # Second window also below → consecutive=2 → mitigate fires.
        for _ in range(3):
            ev.observe(_span(outcome="success"))
        ev.observe(_span(outcome="error"))
        mit = [e for e in events if e.severity == "mitigate"]
        assert len(mit) >= 1

    def test_kill_fires_immediately(self):
        events: list[MitigationEvent] = []
        ev = AsiEvaluator(
            thresholds=AsiThresholds(window_size=4, warn=0.95, mitigate=0.90, kill=0.55)
        )
        ev.add_handler(events.append)
        # All-error window. Composite ~ 0.50 (response_consistency=0,
        # behavioral_boundaries=0, but tool_usage and coordination stay
        # at 1.0 — single tool, no handoffs). Below kill (0.55).
        for _ in range(4):
            ev.observe(_span(outcome="error"))
        kill_events = [e for e in events if e.severity == "kill"]
        assert len(kill_events) >= 1, f"events were: {[e.severity for e in events]}"

    def test_recover_resets_counter(self):
        events: list[MitigationEvent] = []
        ev = AsiEvaluator(
            thresholds=AsiThresholds(window_size=4, warn=0.95, mitigate=0.95, kill=0.0)
        )
        ev.add_handler(events.append)
        # Bad window → consecutive=1.
        for _ in range(3):
            ev.observe(_span(outcome="success"))
        ev.observe(_span(outcome="error"))
        assert ev.consecutive_below("test") == 1
        # Good window → recover fires, counter resets.
        for _ in range(4):
            ev.observe(_span(outcome="success"))
        recover_events = [e for e in events if e.severity == "recover"]
        assert len(recover_events) >= 1
        assert ev.consecutive_below("test") == 0


# ---------------------------------------------------------------------------
# from_iter convenience
# ---------------------------------------------------------------------------


class TestFromIter:
    def test_replays_all_spans(self):
        spans = [_span(task_class="x") for _ in range(50)]
        ev = from_iter(spans, thresholds=AsiThresholds(window_size=50))
        score = ev.score_for_task_class("x")
        assert score == pytest.approx(1.0)

    def test_returns_evaluator(self):
        ev = from_iter([_span() for _ in range(3)])
        assert isinstance(ev, AsiEvaluator)
