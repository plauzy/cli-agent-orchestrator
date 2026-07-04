"""Tests for the Refinery write queue (commit 11).

Coverage matrix:
  * Allow path: executor runs, value is propagated, WAL appended, SSE emitted.
  * Deny path: policy DENY → no executor run, no WAL append.
  * Escalate path: SSE escalation event emitted, no executor run.
  * Rule-of-Two: an action with an all-three-true classification is
    early-rejected before policy evaluation runs.
  * Serialization: many concurrent submits run strictly one-at-a-time.
  * Stats counters track submitted/allowed/denied/escalated.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from cli_agent_orchestrator.refinery import (
    PermissivePolicy,
    PolicyOutcome,
    RefineryQueue,
    WriteRequest,
    rule_of_two,
)


def _exec(value: Any = None):
    """Build a no-op async executor that returns ``value``."""

    async def _run() -> Any:
        return value

    return _run


# ---------------------------------------------------------------------------
# Policy-stub fixtures
# ---------------------------------------------------------------------------


class _DenyAll:
    def evaluate(self, action: str, payload: dict[str, Any]) -> PolicyOutcome:
        return PolicyOutcome.DENY


class _EscalateAll:
    def evaluate(self, action: str, payload: dict[str, Any]) -> PolicyOutcome:
        return PolicyOutcome.ESCALATE


# ---------------------------------------------------------------------------
# Allow path
# ---------------------------------------------------------------------------


class TestAllowPath:
    @pytest.mark.asyncio
    async def test_allow_runs_executor_and_returns_value(self):
        queue = RefineryQueue()
        result = await queue.submit(
            WriteRequest(
                action="create_terminal",
                payload={"id": "t-1"},
                executor=_exec({"row_id": 42}),
                actor="mayor",
            )
        )
        assert result.status == "completed"
        assert result.value == {"row_id": 42}
        assert queue.stats["allowed"] == 1
        assert queue.stats["denied"] == 0

    @pytest.mark.asyncio
    async def test_allow_appends_to_wal(self):
        wal_calls: list[tuple[str, dict[str, Any]]] = []

        def appender(action: str, payload: dict[str, Any]) -> int:
            wal_calls.append((action, payload))
            return 0

        queue = RefineryQueue(wal_appender=appender)
        await queue.submit(WriteRequest(action="x", payload={"k": "v"}, executor=_exec()))
        assert wal_calls == [("x", {"k": "v"})]

    @pytest.mark.asyncio
    async def test_allow_emits_sse_completed(self):
        emitted: list[dict[str, Any]] = []

        def emit(event: dict[str, Any]) -> None:
            emitted.append(event)

        queue = RefineryQueue(sse_emitter=emit)
        await queue.submit(WriteRequest(action="x", payload={}, executor=_exec(), actor="a"))
        assert any(e["type"] == "refinery.completed" for e in emitted)
        assert emitted[0]["actor"] == "a"


# ---------------------------------------------------------------------------
# Deny path
# ---------------------------------------------------------------------------


class TestDenyPath:
    @pytest.mark.asyncio
    async def test_policy_deny_skips_executor_and_wal(self):
        ran = False

        async def executor():
            nonlocal ran
            ran = True

        wal_calls: list = []

        def appender(action, payload):
            wal_calls.append((action, payload))
            return 0

        queue = RefineryQueue(policy=_DenyAll(), wal_appender=appender)
        result = await queue.submit(WriteRequest(action="x", payload={}, executor=executor))
        assert result.status == "denied"
        assert result.reason == "policy"
        assert ran is False
        assert wal_calls == []
        assert queue.stats["denied"] == 1


# ---------------------------------------------------------------------------
# Escalate path
# ---------------------------------------------------------------------------


class TestEscalatePath:
    @pytest.mark.asyncio
    async def test_escalate_emits_sse_event_and_returns_escalated(self):
        emitted: list[dict[str, Any]] = []

        def emit(event):
            emitted.append(event)

        queue = RefineryQueue(policy=_EscalateAll(), sse_emitter=emit)
        result = await queue.submit(
            WriteRequest(action="x", payload={}, executor=_exec(), actor="a")
        )
        assert result.status == "escalated"
        assert any(e["type"] == "refinery.escalated" for e in emitted)
        assert queue.stats["escalated"] == 1


# ---------------------------------------------------------------------------
# Rule-of-Two
# ---------------------------------------------------------------------------


class TestRuleOfTwo:
    @pytest.mark.asyncio
    async def test_rule_of_two_violation_denies_early(self):
        # Register a custom action with all three flags true.
        try:
            rule_of_two.classify(
                "dangerous_test_action",
                untrusted_input=True,
                sensitive_data=True,
                change_state=True,
            )
            ran = False

            async def executor():
                nonlocal ran
                ran = True

            queue = RefineryQueue()
            result = await queue.submit(
                WriteRequest(action="dangerous_test_action", payload={}, executor=executor)
            )
            assert result.status == "denied"
            assert result.reason == "rule-of-two-violation"
            assert ran is False
        finally:
            # Clean up so we don't pollute other tests.
            rule_of_two._REGISTRY.pop("dangerous_test_action", None)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    @pytest.mark.asyncio
    async def test_many_concurrent_submits_run_one_at_a_time(self):
        """Pinned invariant: writes serialize through a single asyncio.Lock."""
        active = 0
        max_active = 0

        async def executor():
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            # Yield so other coroutines could run if they could (they can't —
            # the lock should keep them blocked).
            await asyncio.sleep(0.001)
            active -= 1

        queue = RefineryQueue()
        coros = [
            queue.submit(WriteRequest(action="x", payload={}, executor=executor)) for _ in range(20)
        ]
        results = await asyncio.gather(*coros)
        assert all(r.status == "completed" for r in results)
        assert max_active == 1
        assert queue.stats["allowed"] == 20


# ---------------------------------------------------------------------------
# Executor exceptions propagate
# ---------------------------------------------------------------------------


class TestExecutorErrors:
    @pytest.mark.asyncio
    async def test_executor_exception_propagates(self):
        async def boom():
            raise RuntimeError("simulated failure")

        queue = RefineryQueue()
        with pytest.raises(RuntimeError, match="simulated failure"):
            await queue.submit(WriteRequest(action="x", payload={}, executor=boom))


# ---------------------------------------------------------------------------
# Side-channel error tolerance
# ---------------------------------------------------------------------------


class TestSideChannelErrors:
    @pytest.mark.asyncio
    async def test_wal_failure_does_not_block_executor(self):
        def broken_appender(action, payload):
            raise OSError("disk full")

        queue = RefineryQueue(wal_appender=broken_appender)
        result = await queue.submit(WriteRequest(action="x", payload={}, executor=_exec("ok")))
        assert result.status == "completed"
        assert result.value == "ok"

    @pytest.mark.asyncio
    async def test_sse_failure_does_not_block_executor(self):
        def broken_emit(event):
            raise OSError("nobody listening")

        queue = RefineryQueue(sse_emitter=broken_emit)
        result = await queue.submit(WriteRequest(action="x", payload={}, executor=_exec("ok")))
        assert result.status == "completed"
