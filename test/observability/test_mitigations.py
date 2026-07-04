"""Tests for the Phase 4 mitigation handlers (commit 21).

Coverage matrix:
  * LoggingHandler emits the expected log level per severity
  * SseBroadcastHandler republishes events to the bus; bus failures
    don't propagate
  * WALPersistenceHandler appends events to the WAL appender; failures
    don't propagate
  * KillSwitchHandler:
    - sets kill flag on severity=kill
    - clears kill flag on severity=recover
    - is a no-op for severity=warn / severity=mitigate
  * standard_handlers() returns all four wired together
  * Integration: AsiEvaluator + standard_handlers correctly fires
    each handler on a threshold breach
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from cli_agent_orchestrator.observability import (
    DEFAULT_BEHAVIORAL_ANCHOR,
    AnchorRegistry,
    AsiEvaluator,
    AsiScore,
    AsiThresholds,
    BehavioralAnchoringHandler,
    ConsolidationState,
    KillSwitchHandler,
    KillSwitchState,
    LoggingHandler,
    MemoryConsolidationHandler,
    MitigationEvent,
    SpanRecord,
    SseBroadcastHandler,
    WALPersistenceHandler,
    standard_handlers,
)
from cli_agent_orchestrator.observability.mitigations import reset_kill_switch_for_tests

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event(
    severity: str,
    *,
    task_class: str = "test",
    overall: float = 0.5,
    consecutive_below: int = 1,
) -> MitigationEvent:
    score = AsiScore(
        overall=overall,
        response_consistency=overall,
        tool_usage_patterns=overall,
        coordination=overall,
        behavioral_boundaries=overall,
        task_class=task_class,
        span_count=10,
    )
    return MitigationEvent(severity=severity, score=score, consecutive_below=consecutive_below)


# ---------------------------------------------------------------------------
# LoggingHandler
# ---------------------------------------------------------------------------


class TestLoggingHandler:
    def test_warn_logs_at_warning_level(self, caplog):
        with caplog.at_level(logging.WARNING):
            LoggingHandler()(_event("warn"))
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_mitigate_logs_at_error_level(self, caplog):
        with caplog.at_level(logging.ERROR):
            LoggingHandler()(_event("mitigate"))
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_kill_logs_at_critical_level(self, caplog):
        with caplog.at_level(logging.CRITICAL):
            LoggingHandler()(_event("kill"))
        assert any(r.levelno == logging.CRITICAL for r in caplog.records)

    def test_recover_logs_at_info_level(self, caplog):
        with caplog.at_level(logging.INFO):
            LoggingHandler()(_event("recover"))
        assert any(r.levelno == logging.INFO for r in caplog.records)


# ---------------------------------------------------------------------------
# SseBroadcastHandler
# ---------------------------------------------------------------------------


class _StubBus:
    def __init__(self) -> None:
        self.published: list[dict] = []

    def publish(self, event: dict) -> None:
        self.published.append(event)


class _BrokenBus:
    def publish(self, event: dict) -> None:
        raise RuntimeError("bus down")


class TestSseBroadcastHandler:
    def test_publishes_event_to_bus(self):
        bus = _StubBus()
        SseBroadcastHandler(bus=bus)(_event("warn", task_class="research_breadth", overall=0.82))
        assert len(bus.published) == 1
        msg = bus.published[0]
        assert msg["type"] == "asi.mitigation"
        assert msg["severity"] == "warn"
        assert msg["task_class"] == "research_breadth"
        assert msg["overall"] == pytest.approx(0.82)
        assert "response_consistency" in msg
        assert "tool_usage_patterns" in msg

    def test_bus_failure_does_not_propagate(self):
        # Must not raise even when the bus blows up.
        SseBroadcastHandler(bus=_BrokenBus())(_event("warn"))


# ---------------------------------------------------------------------------
# WALPersistenceHandler
# ---------------------------------------------------------------------------


class TestWALPersistenceHandler:
    def test_appends_event_to_wal(self):
        appended: list[tuple[str, dict[str, Any]]] = []

        def fake_append(op: str, payload: dict[str, Any]):
            appended.append((op, payload))
            return 0

        WALPersistenceHandler(wal_appender=fake_append)(
            _event("mitigate", task_class="code_review", overall=0.6)
        )
        assert len(appended) == 1
        op, payload = appended[0]
        assert op == "asi.mitigation"
        assert payload["severity"] == "mitigate"
        assert payload["task_class"] == "code_review"
        assert payload["overall"] == pytest.approx(0.6)
        assert "dimensions" in payload
        assert payload["dimensions"]["coordination"] == pytest.approx(0.6)

    def test_wal_failure_does_not_propagate(self):
        def broken_appender(op: str, payload: dict[str, Any]):
            raise RuntimeError("wal down")

        # Must not raise.
        WALPersistenceHandler(wal_appender=broken_appender)(_event("warn"))


# ---------------------------------------------------------------------------
# KillSwitchHandler
# ---------------------------------------------------------------------------


class TestKillSwitchHandler:
    def setup_method(self):
        # Each test starts with a fresh switch state.
        self.state = KillSwitchState()
        self.handler = KillSwitchHandler(state=self.state)

    def test_kill_severity_marks_class(self):
        assert not self.state.is_killed("research")
        self.handler(_event("kill", task_class="research"))
        assert self.state.is_killed("research")

    def test_recover_severity_clears_class(self):
        self.state.kill("research")
        assert self.state.is_killed("research")
        self.handler(_event("recover", task_class="research"))
        assert not self.state.is_killed("research")

    def test_recover_on_unkilled_class_is_noop(self):
        # Recover for a class that was never killed: no-op, no error.
        self.handler(_event("recover", task_class="never_killed"))
        assert not self.state.is_killed("never_killed")

    def test_warn_severity_does_not_kill(self):
        self.handler(_event("warn", task_class="research"))
        assert not self.state.is_killed("research")

    def test_mitigate_severity_does_not_kill(self):
        self.handler(_event("mitigate", task_class="research"))
        assert not self.state.is_killed("research")

    def test_kill_is_per_task_class(self):
        self.handler(_event("kill", task_class="research"))
        assert self.state.is_killed("research")
        assert not self.state.is_killed("code_review")

    def test_killed_classes_returns_set(self):
        self.handler(_event("kill", task_class="a"))
        self.handler(_event("kill", task_class="b"))
        assert self.state.killed_classes() == {"a", "b"}


class TestKillSwitchModuleSingleton:
    def test_get_kill_switch_returns_singleton(self):
        from cli_agent_orchestrator.observability import get_kill_switch

        first = get_kill_switch()
        second = get_kill_switch()
        assert first is second

    def test_reset_for_tests_clears_state(self):
        from cli_agent_orchestrator.observability import get_kill_switch

        switch = get_kill_switch()
        switch.kill("test_class")
        assert switch.is_killed("test_class")
        reset_kill_switch_for_tests()
        assert not switch.is_killed("test_class")


# ---------------------------------------------------------------------------
# standard_handlers
# ---------------------------------------------------------------------------


class TestStandardHandlers:
    def test_returns_six_handlers(self):
        bus = _StubBus()
        appended: list = []

        def fake_append(op, payload):
            appended.append((op, payload))
            return 0

        state = KillSwitchState()
        handlers = standard_handlers(sse_bus=bus, wal_appender=fake_append, kill_switch=state)
        # 4 baseline (Logging / Sse / WAL / KillSwitch) +
        # 2 v2.5 close-out (MemoryConsolidation / BehavioralAnchoring).
        assert len(handlers) == 6

    def test_all_handlers_fire_on_one_event(self):
        bus = _StubBus()
        appended: list = []

        def fake_append(op, payload):
            appended.append((op, payload))
            return 0

        state = KillSwitchState()
        handlers = standard_handlers(sse_bus=bus, wal_appender=fake_append, kill_switch=state)
        for h in handlers:
            h(_event("kill", task_class="research"))
        # SSE got the event.
        assert len(bus.published) == 1
        # WAL got the event.
        assert len(appended) == 1
        # Kill switch flipped.
        assert state.is_killed("research")


# ---------------------------------------------------------------------------
# End-to-end with AsiEvaluator
# ---------------------------------------------------------------------------


class TestEvaluatorWithStandardHandlers:
    def test_kill_threshold_fires_all_handlers(self):
        bus = _StubBus()
        appended: list = []

        def fake_append(op, payload):
            appended.append((op, payload))
            return 0

        state = KillSwitchState()
        ev = AsiEvaluator(
            thresholds=AsiThresholds(window_size=4, warn=0.95, mitigate=0.90, kill=0.55)
        )
        for h in standard_handlers(sse_bus=bus, wal_appender=fake_append, kill_switch=state):
            ev.add_handler(h)

        # All-error window → score ~0.50 → kill fires.
        for _ in range(4):
            ev.observe(
                SpanRecord(
                    name="execute_tool x",
                    operation="execute_tool",
                    agent_id="a",
                    conversation_id="c",
                    task_class="research",
                    duration_ms=100.0,
                    attributes={"cao.tool.outcome": "error"},
                )
            )

        # SSE bus saw at least one asi.mitigation event.
        kill_msgs = [m for m in bus.published if m["severity"] == "kill"]
        assert len(kill_msgs) >= 1
        # WAL saw at least one asi.mitigation entry.
        kill_appends = [
            (op, p) for (op, p) in appended if op == "asi.mitigation" and p["severity"] == "kill"
        ]
        assert len(kill_appends) >= 1
        # Kill switch flipped for research class.
        assert state.is_killed("research")


# ---------------------------------------------------------------------------
# MemoryConsolidationHandler (v2.5 close-out)
# ---------------------------------------------------------------------------


class TestMemoryConsolidationHandler:
    def test_marks_after_threshold_consecutive_mitigates(self):
        wal: list = []
        state = ConsolidationState()
        h = MemoryConsolidationHandler(
            state=state,
            wal_appender=lambda op, p: wal.append((op, p)) or 0,
            consecutive_threshold=3,
        )

        # Below threshold → no mark, no WAL.
        h(_event("mitigate", task_class="search", consecutive_below=2))
        assert not state.is_marked("search")
        assert wal == []

        # At threshold → mark + WAL append.
        h(_event("mitigate", task_class="search", consecutive_below=3))
        assert state.is_marked("search")
        assert len(wal) == 1
        assert wal[0][0] == "consolidation.request"
        assert wal[0][1]["task_class"] == "search"
        assert wal[0][1]["consecutive_below"] == 3

    def test_recover_clears_mark(self):
        state = ConsolidationState()
        state.mark("search")
        h = MemoryConsolidationHandler(
            state=state,
            wal_appender=lambda op, p: 0,
        )

        h(_event("recover", task_class="search"))
        assert not state.is_marked("search")

    def test_warn_does_not_mark(self):
        state = ConsolidationState()
        h = MemoryConsolidationHandler(state=state, wal_appender=lambda op, p: 0)

        h(_event("warn", task_class="search", consecutive_below=10))
        assert not state.is_marked("search")

    def test_kill_does_not_mark(self):
        state = ConsolidationState()
        h = MemoryConsolidationHandler(state=state, wal_appender=lambda op, p: 0)

        h(_event("kill", task_class="search", consecutive_below=10))
        # KillSwitchHandler owns kill events; consolidation only fires on
        # sustained mitigate. Kept distinct so mitigation responses can
        # compose without stepping on each other.
        assert not state.is_marked("search")

    def test_wal_failure_swallowed(self):
        def boom(op, p):
            raise RuntimeError("wal disk full")

        state = ConsolidationState()
        h = MemoryConsolidationHandler(state=state, wal_appender=boom)

        # Should not raise; mark must still happen (WAL is best-effort).
        h(_event("mitigate", task_class="search", consecutive_below=3))
        assert state.is_marked("search")


# ---------------------------------------------------------------------------
# BehavioralAnchoringHandler (v2.5 close-out)
# ---------------------------------------------------------------------------


class TestBehavioralAnchoringHandler:
    def test_installs_anchor_after_threshold(self):
        registry = AnchorRegistry()
        h = BehavioralAnchoringHandler(registry=registry, consecutive_threshold=3)

        h(_event("mitigate", task_class="research", consecutive_below=2))
        assert registry.anchors_for("research") == []

        h(_event("mitigate", task_class="research", consecutive_below=3))
        anchors = registry.anchors_for("research")
        assert len(anchors) == 1
        assert anchors[0] == DEFAULT_BEHAVIORAL_ANCHOR

    def test_anchor_dedupes_on_repeated_mitigate(self):
        registry = AnchorRegistry()
        h = BehavioralAnchoringHandler(registry=registry, consecutive_threshold=3)

        for cb in (3, 4, 5, 6):
            h(_event("mitigate", task_class="research", consecutive_below=cb))

        # The same anchor isn't re-added every window.
        assert len(registry.anchors_for("research")) == 1

    def test_recover_clears_anchors(self):
        registry = AnchorRegistry()
        registry.add("research", "manual anchor")
        h = BehavioralAnchoringHandler(registry=registry)

        h(_event("recover", task_class="research"))
        assert registry.anchors_for("research") == []

    def test_custom_anchor_text(self):
        registry = AnchorRegistry()
        h = BehavioralAnchoringHandler(
            registry=registry,
            anchor_text="prefer single-shot read",
            consecutive_threshold=1,
        )

        h(_event("mitigate", task_class="research", consecutive_below=1))
        assert registry.anchors_for("research") == ["prefer single-shot read"]


# ---------------------------------------------------------------------------
# Auto-rollback path: kill threshold trumps mitigate.
# ---------------------------------------------------------------------------


class TestAutoRollback:
    """Pin Pattern D from the v2.5 plan — when the treatment variant's ASI
    crosses the kill threshold, the kill switch fires within one
    evaluator window. This is observed via :class:`KillSwitchHandler`,
    not a new mechanism. The MemoryConsolidation + BehavioralAnchoring
    handlers must NOT fire on a kill event, so they don't fight the
    rollback."""

    def test_kill_event_does_not_trigger_consolidation_or_anchor(self):
        cstate = ConsolidationState()
        registry = AnchorRegistry()
        kstate = KillSwitchState()

        ev = _event("kill", task_class="research", consecutive_below=5, overall=0.4)
        MemoryConsolidationHandler(state=cstate, wal_appender=lambda *_: 0)(ev)
        BehavioralAnchoringHandler(registry=registry)(ev)
        KillSwitchHandler(state=kstate)(ev)

        # Kill switch fired (auto-rollback infrastructure).
        assert kstate.is_killed("research")
        # Other handlers stayed quiet — the variant is force-flipped to
        # control via the kill switch, not via consolidation or anchoring.
        assert not cstate.is_marked("research")
        assert registry.anchors_for("research") == []
