"""Unit tests for W6 pending features (vision addendum §2, §8, §10, §11, §12.3)."""

from __future__ import annotations

import datetime
import types
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Feature 1: WAL-only enforcement (STRICT_WAL_MODE)
# ---------------------------------------------------------------------------


class TestStrictWalMode:
    def test_no_wal_appender_strict_mode_raises(self) -> None:
        import cli_agent_orchestrator.refinery.queue as q

        queue = q.RefineryQueue(wal_appender=None)
        request = q.SyncWriteRequest(action="test.write", payload={}, executor=lambda: "ok")

        with patch.object(q, "STRICT_WAL_MODE", True):
            with pytest.raises(q.StrictWalModeViolation) as exc_info:
                queue.submit_sync(request)
            assert "test.write" in str(exc_info.value)

    def test_no_wal_appender_permissive_mode_succeeds(self) -> None:
        import cli_agent_orchestrator.refinery.queue as q

        queue = q.RefineryQueue(wal_appender=None)
        request = q.SyncWriteRequest(action="test.write", payload={}, executor=lambda: "ok")

        with patch.object(q, "STRICT_WAL_MODE", False):
            result = queue.submit_sync(request)
        assert result.status == "completed"
        assert result.value == "ok"

    def test_with_wal_appender_strict_mode_passes(self) -> None:
        import cli_agent_orchestrator.refinery.queue as q

        appended: list[tuple[str, dict]] = []
        queue = q.RefineryQueue(wal_appender=lambda a, p: appended.append((a, p)) or 1)
        request = q.SyncWriteRequest(action="test.write", payload={"x": 1}, executor=lambda: "done")

        with patch.object(q, "STRICT_WAL_MODE", True):
            result = queue.submit_sync(request)
        assert result.status == "completed"
        assert appended == [("test.write", {"x": 1})]


# ---------------------------------------------------------------------------
# Feature 2: Phantom-state detector
# ---------------------------------------------------------------------------


@dataclass
class _FakeTerminal:
    terminal_id: str
    status: str
    updated_at: datetime.datetime | None


class _FakeStatus:
    def __init__(self, value: str) -> None:
        self.value = value


class TestPhantomStateDetector:
    def _terminal(self, tid: str, status: str, seconds_ago: float) -> _FakeTerminal:
        import time

        ts = datetime.datetime.fromtimestamp(time.time() - seconds_ago, tz=datetime.timezone.utc)
        return _FakeTerminal(terminal_id=tid, status=_FakeStatus(status), updated_at=ts)  # type: ignore[arg-type]

    def test_detects_stuck_processing(self) -> None:
        from cli_agent_orchestrator.observability import phantom_state as ps

        t = self._terminal("abc123", "processing", seconds_ago=400)
        with patch.object(ps, "PHANTOM_STATE_DETECTION_ENABLED", True):
            incidents = ps.check_terminals([t], threshold=300)
        assert len(incidents) == 1
        assert incidents[0].terminal_id == "abc123"
        assert incidents[0].stuck_seconds >= 400

    def test_ignores_short_duration(self) -> None:
        from cli_agent_orchestrator.observability import phantom_state as ps

        t = self._terminal("abc123", "processing", seconds_ago=100)
        with patch.object(ps, "PHANTOM_STATE_DETECTION_ENABLED", True):
            incidents = ps.check_terminals([t], threshold=300)
        assert incidents == []

    def test_ignores_idle_terminals(self) -> None:
        from cli_agent_orchestrator.observability import phantom_state as ps

        t = self._terminal("abc123", "idle", seconds_ago=9999)
        with patch.object(ps, "PHANTOM_STATE_DETECTION_ENABLED", True):
            incidents = ps.check_terminals([t], threshold=300)
        assert incidents == []

    def test_disabled_returns_empty(self) -> None:
        from cli_agent_orchestrator.observability import phantom_state as ps

        t = self._terminal("abc123", "processing", seconds_ago=9999)
        with patch.object(ps, "PHANTOM_STATE_DETECTION_ENABLED", False):
            incidents = ps.check_terminals([t], threshold=300)
        assert incidents == []

    def test_emits_sse_event(self) -> None:
        from cli_agent_orchestrator.observability import phantom_state as ps

        t = self._terminal("abc123", "processing", seconds_ago=400)
        emitted: list[dict] = []
        with patch.object(ps, "PHANTOM_STATE_DETECTION_ENABLED", True):
            ps.check_terminals([t], threshold=300, sse_emitter=emitted.append)
        assert emitted[0]["type"] == "phantom_state_detected"
        assert emitted[0]["terminal_id"] == "abc123"


# ---------------------------------------------------------------------------
# Feature 3: SEP-2133 capability negotiation
# ---------------------------------------------------------------------------


class TestSep2133:
    def test_advertise_capability_patches_create_init(self) -> None:
        from cli_agent_orchestrator.ext_apps import sep2133

        mock_mcp = MagicMock()
        original = MagicMock(return_value=MagicMock())
        mock_mcp._mcp_server.create_initialization_options = original

        with patch.object(sep2133, "CAO_MCP_APPS_ENABLED", True):
            sep2133.advertise_capability(mock_mcp)
            mock_mcp._mcp_server.create_initialization_options()

            # The patched function calls original with experimental_capabilities
        original.assert_called_once()
        caps = original.call_args.kwargs.get("experimental_capabilities", {})
        assert sep2133.EXTENSION_ID in caps

    def test_advertise_noop_when_disabled(self) -> None:
        from cli_agent_orchestrator.ext_apps import sep2133

        mock_mcp = MagicMock()
        original = mock_mcp._mcp_server.create_initialization_options

        with patch.object(sep2133, "CAO_MCP_APPS_ENABLED", False):
            sep2133.advertise_capability(mock_mcp)

        # No patching happened
        assert mock_mcp._mcp_server.create_initialization_options is original

    def test_client_supports_mcp_apps_returns_false_when_disabled(self) -> None:
        from cli_agent_orchestrator.ext_apps import sep2133

        with patch.object(sep2133, "CAO_MCP_APPS_ENABLED", False):
            assert sep2133.client_supports_mcp_apps(MagicMock()) is False

    def test_client_supports_mcp_apps_true_when_cap_present(self) -> None:
        from cli_agent_orchestrator.ext_apps import sep2133

        mock_mcp = MagicMock()
        ctx = MagicMock()
        ctx.session.client_params.capabilities.experimental = {sep2133.EXTENSION_ID: {}}
        mock_mcp.get_context.return_value = ctx

        with patch.object(sep2133, "CAO_MCP_APPS_ENABLED", True):
            assert sep2133.client_supports_mcp_apps(mock_mcp) is True

    def test_client_supports_mcp_apps_false_when_cap_absent(self) -> None:
        from cli_agent_orchestrator.ext_apps import sep2133

        mock_mcp = MagicMock()
        ctx = MagicMock()
        ctx.session.client_params.capabilities.experimental = {}
        mock_mcp.get_context.return_value = ctx

        with patch.object(sep2133, "CAO_MCP_APPS_ENABLED", True):
            assert sep2133.client_supports_mcp_apps(mock_mcp) is False


# ---------------------------------------------------------------------------
# Feature 4: Refinery Preflight
# ---------------------------------------------------------------------------


class TestRefineryPreflight:
    @pytest.mark.asyncio
    async def test_skipped_when_disabled(self) -> None:
        from cli_agent_orchestrator.refinery import preflight as pf

        with patch.object(pf, "REFINERY_CODE_REVIEW_ENABLED", False):
            result = await pf.run_review_loop("diff content", handoff_fn=AsyncMock())

        assert result.skipped is True
        assert result.findings == []

    def test_parses_structured_findings(self) -> None:
        from cli_agent_orchestrator.refinery.preflight import ReviewerFinding, _parse_findings

        raw = "FINDING: severe | logic | foo.py:42 | off-by-one in loop | use range(n-1)"
        findings = _parse_findings(raw)
        assert len(findings) == 1
        f = findings[0]
        assert isinstance(f, ReviewerFinding)
        assert f.severity == "severe"
        assert f.category == "logic"
        assert f.location == "foo.py:42"
        assert "off-by-one" in f.description
        assert f.suggested_fix == "use range(n-1)"

    def test_parse_falls_back_to_nit_on_no_findings(self) -> None:
        from cli_agent_orchestrator.refinery.preflight import _parse_findings

        findings = _parse_findings("This looks fine to me.")
        assert len(findings) == 1
        assert findings[0].severity == "nit"

    def test_parse_returns_empty_on_blank(self) -> None:
        from cli_agent_orchestrator.refinery.preflight import _parse_findings

        assert _parse_findings("") == []
        assert _parse_findings("   ") == []

    @pytest.mark.asyncio
    async def test_runs_handoff_when_enabled(self) -> None:
        from cli_agent_orchestrator.refinery import preflight as pf

        handoff = AsyncMock(
            return_value="FINDING: minor | style | a.py:1 | unused import | remove it"
        )
        with patch.object(pf, "REFINERY_CODE_REVIEW_ENABLED", True):
            result = await pf.run_review_loop("diff", handoff_fn=handoff, severe_threshold=0)

        assert result.skipped is False
        assert result.iterations_run >= 1
        assert len(result.findings) == 1
        assert result.findings[0].severity == "minor"


# ---------------------------------------------------------------------------
# Feature 5: Smart-Friend routing
# ---------------------------------------------------------------------------


class TestSmartFriendRouting:
    def test_classify_debug(self) -> None:
        from cli_agent_orchestrator.orchestration.topology_router import (
            SubTaskType,
            classify_subtask,
        )

        assert classify_subtask("debug the traceback in foo.py") == SubTaskType.DEBUG

    def test_classify_test_generation(self) -> None:
        from cli_agent_orchestrator.orchestration.topology_router import (
            SubTaskType,
            classify_subtask,
        )

        assert classify_subtask("write pytest tests for the handler") == SubTaskType.TEST_GENERATION

    def test_classify_review(self) -> None:
        from cli_agent_orchestrator.orchestration.topology_router import (
            SubTaskType,
            classify_subtask,
        )

        assert classify_subtask("review the PR for quality issues") == SubTaskType.REVIEW

    def test_classify_general_fallback(self) -> None:
        from cli_agent_orchestrator.orchestration.topology_router import (
            SubTaskType,
            classify_subtask,
        )

        assert classify_subtask("do something vague") == SubTaskType.GENERAL

    def test_recommend_provider_disabled_returns_coder(self) -> None:
        from cli_agent_orchestrator.orchestration import topology_router as tr

        with patch.object(tr, "SMART_FRIEND_ROUTING_ENABLED", False):
            result = tr.recommend_provider(tr.SubTaskType.DEBUG, coder_provider="kiro_cli")
        assert result == "kiro_cli"

    def test_recommend_reviewer_differs_from_coder(self) -> None:
        from cli_agent_orchestrator.orchestration import topology_router as tr

        with patch.object(tr, "SMART_FRIEND_ROUTING_ENABLED", True):
            provider = tr.recommend_provider(tr.SubTaskType.REVIEW, coder_provider="claude_code")
        assert provider != "claude_code"

    def test_recommend_non_review_returns_mapped_provider(self) -> None:
        from cli_agent_orchestrator.orchestration import topology_router as tr

        with patch.object(tr, "SMART_FRIEND_ROUTING_ENABLED", True):
            provider = tr.recommend_provider(tr.SubTaskType.DEBUG)
        assert provider == "claude_code"
