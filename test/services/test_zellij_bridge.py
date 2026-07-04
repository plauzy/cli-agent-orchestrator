"""Tests for the Zellij hook bridge (Phase 2)."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cli_agent_orchestrator.services import zellij_bridge as zb_module
from cli_agent_orchestrator.services.sse_bus import SSEBus, reset_bus
from cli_agent_orchestrator.services.zellij_bridge import ZellijBridge, _band


@pytest.fixture(autouse=True)
def _reset_bus():
    reset_bus()
    yield
    reset_bus()


def _make_proc(returncode: int = 0) -> MagicMock:
    """Build a mock asyncio.subprocess.Process whose stdin captures bytes."""
    proc = MagicMock()
    proc.stdin = MagicMock()
    proc.stdin.write = MagicMock()
    proc.stdin.drain = AsyncMock()
    proc.stdin.close = MagicMock()
    proc.wait = AsyncMock(return_value=returncode)
    return proc


class TestBandThresholds:
    def test_high_score_is_green(self):
        assert _band(0.9) == "green"

    def test_mid_score_is_yellow(self):
        assert _band(0.5) == "yellow"

    def test_low_score_is_red(self):
        assert _band(0.1) == "red"


class TestStateAggregation:
    def test_session_lifecycle_updates_count(self):
        bus = SSEBus()
        bridge = ZellijBridge(bus)
        bridge._apply({"type": "session.created", "session_name": "cao-a"})
        bridge._apply({"type": "session.created", "session_name": "cao-b"})
        bridge._apply({"type": "session.killed", "session_name": "cao-a"})
        snap = bridge._state.snapshot()
        assert snap["sessions"] == 1

    def test_asi_kill_severity_adds_to_kill_switched(self):
        bus = SSEBus()
        bridge = ZellijBridge(bus)
        bridge._apply(
            {
                "type": "asi.mitigation",
                "task_class": "code-review",
                "overall": 0.2,
                "severity": "kill",
            }
        )
        snap = bridge._state.snapshot()
        assert snap["kill_switched"] == ["code-review"]
        assert snap["asi"] == {
            "task_class": "code-review",
            "score": 0.2,
            "band": "red",
        }

    def test_recover_clears_kill_switched(self):
        bus = SSEBus()
        bridge = ZellijBridge(bus)
        bridge._apply(
            {"type": "asi.mitigation", "task_class": "x", "overall": 0.2, "severity": "kill"}
        )
        bridge._apply(
            {"type": "asi.mitigation", "task_class": "x", "overall": 0.8, "severity": "recover"}
        )
        snap = bridge._state.snapshot()
        assert snap["kill_switched"] == []
        assert snap["asi"]["band"] == "green"


class TestSubscribeAndPipe:
    @pytest.mark.asyncio
    async def test_publish_triggers_pipe_with_snapshot_json(self):
        bus = SSEBus()
        bridge = ZellijBridge(bus)
        proc = _make_proc()

        with patch.object(
            zb_module.asyncio,
            "create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ) as mock_spawn:
            await bridge.start()
            await asyncio.sleep(0)  # let the subscribe loop enter the iterator
            bus.publish({"type": "session.created", "session_name": "cao-x"})
            # Allow the bridge loop to process the event and pipe.
            for _ in range(50):
                if mock_spawn.await_count >= 1:
                    break
                await asyncio.sleep(0.01)
            await bridge.stop()

        assert mock_spawn.await_count >= 1
        argv = mock_spawn.call_args.args
        assert argv[0] == "zellij"
        assert argv[1] == "pipe"
        assert "--name" in argv and "zellaude" in argv
        # The snapshot was written to stdin.
        write_call = proc.stdin.write.call_args
        payload: dict[str, Any] = json.loads(write_call.args[0].decode())
        assert payload["sessions"] == 1
        assert payload["kill_switched"] == []

    @pytest.mark.asyncio
    async def test_missing_zellij_binary_disables_bridge(self):
        bus = SSEBus()
        bridge = ZellijBridge(bus)

        with patch.object(
            zb_module.asyncio,
            "create_subprocess_exec",
            new=AsyncMock(side_effect=FileNotFoundError()),
        ) as mock_spawn:
            await bridge.start()
            await asyncio.sleep(0)
            bus.publish({"type": "session.created", "session_name": "cao-x"})
            for _ in range(50):
                if mock_spawn.await_count >= 1:
                    break
                await asyncio.sleep(0.01)
            # Once disabled, further events must NOT spawn zellij again.
            bus.publish({"type": "session.created", "session_name": "cao-y"})
            await asyncio.sleep(0.05)
            await bridge.stop()

        assert mock_spawn.await_count == 1
        assert bridge._zellij_disabled is True

    @pytest.mark.asyncio
    async def test_pipe_throttling_skips_back_to_back_events(self):
        bus = SSEBus()
        bridge = ZellijBridge(bus)
        proc = _make_proc()

        with patch.object(
            zb_module.asyncio,
            "create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ) as mock_spawn:
            await bridge.start()
            await asyncio.sleep(0)
            for _ in range(5):
                bus.publish({"type": "session.created", "session_name": f"cao-{_}"})
            await asyncio.sleep(0.05)
            await bridge.stop()

        # Throttle is 1s; we should have piped at most once for the burst.
        assert mock_spawn.await_count <= 1

    @pytest.mark.asyncio
    async def test_nonzero_exit_disables_bridge(self):
        bus = SSEBus()
        bridge = ZellijBridge(bus)
        proc = _make_proc(returncode=2)

        with patch.object(
            zb_module.asyncio,
            "create_subprocess_exec",
            new=AsyncMock(return_value=proc),
        ):
            await bridge.start()
            await asyncio.sleep(0)
            bus.publish({"type": "session.created", "session_name": "cao-x"})
            for _ in range(50):
                if bridge._zellij_disabled:
                    break
                await asyncio.sleep(0.01)
            await bridge.stop()

        assert bridge._zellij_disabled is True


class TestCachePolling:
    @pytest.mark.asyncio
    async def test_rolling_window_computed_from_two_samples(self):
        bus = SSEBus()
        bridge = ZellijBridge(bus, api_base="http://x")
        # Seed two samples directly to avoid needing a real HTTP server.
        with patch.object(
            ZellijBridge,
            "_fetch_cache_stats",
            staticmethod(lambda url: {"cache": {"l1_hits": 10, "l3_hits": 0, "misses": 0}}),
        ):
            await bridge._poll_cache_once()
        with patch.object(
            ZellijBridge,
            "_fetch_cache_stats",
            staticmethod(lambda url: {"cache": {"l1_hits": 18, "l3_hits": 0, "misses": 2}}),
        ):
            await bridge._poll_cache_once()
        # Δhits=8, Δmisses=2 → 0.8
        assert bridge._state.cache_hit_rate_60s == pytest.approx(0.8)

    @pytest.mark.asyncio
    async def test_unreachable_endpoint_is_no_op(self):
        bus = SSEBus()
        bridge = ZellijBridge(bus, api_base="http://nope.invalid")
        with patch.object(
            ZellijBridge,
            "_fetch_cache_stats",
            staticmethod(lambda url: None),
        ):
            await bridge._poll_cache_once()
        assert bridge._state.cache_hit_rate_60s is None
