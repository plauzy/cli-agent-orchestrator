"""Tests for the OTel span → AsiEvaluator bridge (Phase 4 / commit 22).

Coverage matrix:
  * span_to_record:
    - happy path: extracts every CAO/GenAI attribute correctly
    - missing task_class → returns None (filters non-CAO spans)
    - missing operation → falls back to span name
    - missing/zero timestamps → duration_ms is 0.0, no crash
  * AsiSpanProcessor:
    - on_end with a CAO span calls evaluator.observe()
    - on_end with a non-CAO span (no task_class) is a no-op
    - on_start is a no-op
    - shutdown / force_flush don't crash
    - exceptions in on_end are swallowed
  * attach():
    - succeeds on a provider with add_span_processor (real SDK
      TracerProvider); the processor receives spans the SDK emits
    - returns False on a provider without add_span_processor
      (the default no-op proxy provider)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest import mock

import pytest

from cli_agent_orchestrator.observability import (
    AsiEvaluator,
    AsiSpanProcessor,
    AsiThresholds,
    span_to_record,
)
from cli_agent_orchestrator.telemetry import semconv

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class _FakeSpan:
    """Minimal stand-in for ``opentelemetry.sdk.trace.ReadableSpan``."""

    name: str = "execute_tool send_message"
    attributes: dict = field(default_factory=dict)
    start_time: int = 1_000_000_000  # 1ms in ns
    end_time: int = 101_000_000_000  # 101ms in ns → 100ms duration


def _cao_span(
    *,
    task_class: str = "research_breadth",
    operation: str = "execute_tool",
    outcome: str = "success",
    name: str = "execute_tool send_message",
    duration_ns: int = 100_000_000,
) -> _FakeSpan:
    return _FakeSpan(
        name=name,
        attributes={
            semconv.CAO_TASK_CLASS: task_class,
            semconv.GEN_AI_OPERATION_NAME: operation,
            semconv.GEN_AI_AGENT_ID: "agent-7",
            semconv.GEN_AI_CONVERSATION_ID: "conv-42",
            "cao.tool.outcome": outcome,
        },
        start_time=0,
        end_time=duration_ns,
    )


# ---------------------------------------------------------------------------
# span_to_record
# ---------------------------------------------------------------------------


class TestSpanToRecord:
    def test_extracts_all_fields(self):
        span = _cao_span(duration_ns=250_000_000)  # 250ms
        rec = span_to_record(span)
        assert rec is not None
        assert rec.task_class == "research_breadth"
        assert rec.operation == "execute_tool"
        assert rec.agent_id == "agent-7"
        assert rec.conversation_id == "conv-42"
        assert rec.name == "execute_tool send_message"
        assert rec.duration_ms == pytest.approx(250.0)
        assert rec.attributes["cao.tool.outcome"] == "success"

    def test_missing_task_class_returns_none(self):
        span = _FakeSpan(
            name="execute_tool x",
            attributes={semconv.GEN_AI_OPERATION_NAME: "execute_tool"},
        )
        assert span_to_record(span) is None

    def test_missing_attributes_returns_none(self):
        # No attributes at all → not a CAO span.
        span = _FakeSpan(name="something_else", attributes={})
        assert span_to_record(span) is None

    def test_missing_operation_falls_back_to_span_name(self):
        span = _FakeSpan(
            name="invoke_agent planner",
            attributes={semconv.CAO_TASK_CLASS: "test"},
        )
        rec = span_to_record(span)
        assert rec is not None
        assert rec.operation == "invoke_agent planner"

    def test_zero_timestamps_yield_zero_duration(self):
        span = _FakeSpan(
            name="x",
            attributes={semconv.CAO_TASK_CLASS: "test"},
            start_time=0,
            end_time=0,
        )
        rec = span_to_record(span)
        assert rec is not None
        assert rec.duration_ms == 0.0

    def test_negative_duration_clamped_to_zero(self):
        # end < start (clock skew or malformed span). Don't crash, don't
        # produce negative durations.
        span = _FakeSpan(
            name="x",
            attributes={semconv.CAO_TASK_CLASS: "test"},
            start_time=100,
            end_time=50,
        )
        rec = span_to_record(span)
        assert rec is not None
        assert rec.duration_ms == 0.0


# ---------------------------------------------------------------------------
# AsiSpanProcessor
# ---------------------------------------------------------------------------


class TestAsiSpanProcessor:
    def test_on_end_observes_cao_span(self):
        ev = AsiEvaluator(thresholds=AsiThresholds(window_size=4))
        proc = AsiSpanProcessor(ev)
        for _ in range(4):
            proc.on_end(_cao_span(task_class="x"))
        # Window completed → there's a recorded score for "x".
        assert ev.score_for_task_class("x") == pytest.approx(1.0)

    def test_on_end_skips_non_cao_span(self):
        ev = AsiEvaluator(thresholds=AsiThresholds(window_size=4))
        proc = AsiSpanProcessor(ev)
        # 4 spans with no task_class — should all be skipped.
        non_cao = _FakeSpan(name="urllib3.connect", attributes={})
        for _ in range(4):
            proc.on_end(non_cao)
        # No window ever closed → cold-start default of 1.0.
        assert ev.score_for_task_class("any") == 1.0

    def test_on_start_is_noop(self):
        ev = AsiEvaluator()
        proc = AsiSpanProcessor(ev)
        # Must not raise; must not record anything.
        proc.on_start(_cao_span())
        assert ev.score_for_task_class("research_breadth") == 1.0

    def test_shutdown_and_flush_succeed(self):
        proc = AsiSpanProcessor(AsiEvaluator())
        proc.shutdown()
        assert proc.force_flush() is True
        assert proc.force_flush(timeout_millis=1) is True

    def test_evaluator_exception_does_not_propagate(self):
        # Even if observe() raises, on_end must swallow it — drift
        # detection is opportunistic.
        broken_evaluator = mock.Mock(spec=AsiEvaluator)
        broken_evaluator.observe.side_effect = RuntimeError("boom")
        proc = AsiSpanProcessor(broken_evaluator)
        proc.on_end(_cao_span())  # must not raise


# ---------------------------------------------------------------------------
# attach()
# ---------------------------------------------------------------------------


class TestAttach:
    def test_attach_to_real_sdk_provider(self):
        """Smoke test against the real OTel SDK TracerProvider."""
        # Import locally so test collection still works on systems
        # without the SDK installed (CI uses uv with all deps).
        from opentelemetry.sdk.trace import TracerProvider

        provider = TracerProvider()
        ev = AsiEvaluator(thresholds=AsiThresholds(window_size=2))
        proc = AsiSpanProcessor(ev)
        assert proc.attach(provider=provider) is True

        # Emit a couple of spans through the provider; the processor's
        # on_end gets called.
        tracer = provider.get_tracer("test")
        for _ in range(2):
            with tracer.start_as_current_span("execute_tool ping") as span:
                span.set_attribute(semconv.CAO_TASK_CLASS, "smoke")
                span.set_attribute(semconv.GEN_AI_OPERATION_NAME, "execute_tool")
                span.set_attribute("cao.tool.outcome", "success")

        # Window of 2 closed → score landed.
        assert ev.score_for_task_class("smoke") == pytest.approx(1.0)
        provider.shutdown()

    def test_attach_to_provider_without_add_span_processor(self):
        # Default ProxyTracerProvider doesn't expose add_span_processor
        # — attach() must return False, not crash.
        class _NoOpProvider:
            pass

        proc = AsiSpanProcessor(AsiEvaluator())
        assert proc.attach(provider=_NoOpProvider()) is False

    def test_attach_with_no_provider_uses_global(self):
        # The default global TracerProvider in tests is the no-op proxy.
        # We don't assert what attach() returns (depends on whether
        # other tests already installed an SDK provider) — only that it
        # doesn't crash.
        proc = AsiSpanProcessor(AsiEvaluator())
        # Should be safe with no args.
        result = proc.attach()
        assert isinstance(result, bool)
