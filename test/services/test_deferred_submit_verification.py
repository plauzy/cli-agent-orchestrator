"""Tests for the deferred-init submit-verification guard.

The deferred-init delivery (send_input: paste -> fixed sleep -> Enter) can drop
the Enter (message left in the box) or the whole paste (TUI not input-ready).
Nothing blocks on completion in that path, so a dropped submit would leave the
worker idle forever. These cover the confirm + re-submit logic that closes it.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cli_agent_orchestrator.models.terminal import TerminalStatus
from cli_agent_orchestrator.services import terminal_service as ts
from cli_agent_orchestrator.services.status_monitor import StatusMonitor


def _backend(event_inbox):
    backend = MagicMock()
    backend.supports_event_inbox.return_value = event_inbox
    return backend


class TestMessageVisibleInBox:
    def test_true_when_probe_present(self):
        with patch.object(ts, "get_output", return_value="❯ Analyze the logs now"):
            assert ts._message_visible_in_box("t1", "Analyze the logs") is True

    def test_false_when_absent(self):
        with patch.object(ts, "get_output", return_value="❯ (empty prompt)"):
            assert ts._message_visible_in_box("t1", "Analyze the logs") is False

    def test_false_when_message_too_short(self):
        # < 8 alnum chars → don't risk a blank submit; report not-shown.
        with patch.object(ts, "get_output", return_value="go go go") as mock_out:
            assert ts._message_visible_in_box("t1", "go") is False
            mock_out.assert_not_called()

    def test_false_when_output_fetch_raises(self):
        with patch.object(ts, "get_output", side_effect=Exception("boom")):
            assert ts._message_visible_in_box("t1", "Analyze the logs") is False

    def test_match_survives_wrapping_and_whitespace(self):
        # Rendered box wraps the text across lines / pads with spaces.
        with patch.object(ts, "get_output", return_value="❯ Analyze the\n  logs carefully"):
            assert ts._message_visible_in_box("t1", "Analyze the logs") is True


@pytest.mark.asyncio
class TestConfirmWorkerStartedOrResubmit:
    async def test_started_on_first_confirm_no_resubmit(self):
        with (
            patch.object(ts, "_wait_for_started_edge", new=AsyncMock(return_value=True)),
            patch.object(ts, "send_special_key") as key,
            patch.object(ts, "send_input") as send,
        ):
            ok = await ts._confirm_worker_started_or_resubmit(
                "t1", "Analyze the logs", None, "sup", None
            )
        assert ok is True
        key.assert_not_called()
        send.assert_not_called()

    async def test_enter_resubmit_when_message_in_box(self):
        # First confirm fails, box shows our text (Enter swallowed) → bare Enter,
        # second confirm succeeds.
        with (
            patch.object(ts, "_wait_for_started_edge", new=AsyncMock(side_effect=[False, True])),
            patch.object(ts, "_message_visible_in_box", return_value=True),
            patch.object(ts, "send_special_key") as key,
            patch.object(ts, "send_input") as send,
        ):
            ok = await ts._confirm_worker_started_or_resubmit(
                "t1", "Analyze the logs", None, "sup", None
            )
        assert ok is True
        key.assert_called_once_with("t1", "Enter")
        send.assert_not_called()

    async def test_full_redeliver_when_box_empty(self):
        # First confirm fails, box empty (paste dropped) → re-deliver full msg.
        with (
            patch.object(ts, "_wait_for_started_edge", new=AsyncMock(side_effect=[False, True])),
            patch.object(ts, "_message_visible_in_box", return_value=False),
            patch.object(ts, "send_special_key") as key,
            patch.object(ts, "send_input") as send,
        ):
            ok = await ts._confirm_worker_started_or_resubmit(
                "t1", "Analyze the logs", "reg", "sup", None
            )
        assert ok is True
        key.assert_not_called()
        send.assert_called_once()
        assert send.call_args.args[0] == "t1"
        assert send.call_args.args[1] == "Analyze the logs"

    async def test_returns_false_when_worker_never_starts(self):
        # Every confirm fails through all resubmit attempts.
        with (
            patch.object(ts, "_wait_for_started_edge", new=AsyncMock(return_value=False)),
            patch.object(ts, "_message_visible_in_box", return_value=True),
            patch.object(ts, "send_special_key"),
            patch.object(ts, "send_input"),
        ):
            ok = await ts._confirm_worker_started_or_resubmit(
                "t1", "Analyze the logs", None, "sup", None
            )
        assert ok is False

    async def test_direct_probe_short_circuits_when_worker_started(self):
        # Provider with supports_direct_status_probe=True + direct probe True →
        # returns True without calling send_input or send_special_key.
        provider = MagicMock(supports_direct_status_probe=True)
        with (
            patch.object(ts, "_wait_for_started_edge", new=AsyncMock(return_value=False)),
            patch.object(ts, "_worker_is_started_direct", return_value=True),
            patch.object(ts, "send_special_key") as key,
            patch.object(ts, "send_input") as send,
        ):
            ok = await ts._confirm_worker_started_or_resubmit(
                "t1",
                "Analyze the logs",
                None,
                "sup",
                None,
                provider=provider,
            )
        assert ok is True
        key.assert_not_called()
        send.assert_not_called()

    async def test_direct_probe_falls_through_when_worker_not_started(self):
        # Direct probe returns False → continues to existing resubmit logic.
        provider = MagicMock(supports_direct_status_probe=True)
        with (
            patch.object(ts, "_wait_for_started_edge", new=AsyncMock(side_effect=[False, True])),
            patch.object(ts, "_worker_is_started_direct", return_value=False),
            patch.object(ts, "_message_visible_in_box", return_value=True),
            patch.object(ts, "send_special_key") as key,
            patch.object(ts, "send_input") as send,
        ):
            ok = await ts._confirm_worker_started_or_resubmit(
                "t1",
                "Analyze the logs",
                None,
                "sup",
                None,
                provider=provider,
            )
        assert ok is True
        key.assert_called_once()
        send.assert_not_called()

    async def test_direct_probe_skipped_when_provider_not_opted_in(self):
        # Provider without supports_direct_status_probe → direct probe never
        # invoked; falls through to existing resubmit logic.
        provider = MagicMock(supports_direct_status_probe=False)
        with (
            patch.object(ts, "_wait_for_started_edge", new=AsyncMock(side_effect=[False, True])),
            patch.object(ts, "_worker_is_started_direct") as probe,
            patch.object(ts, "_message_visible_in_box", return_value=True),
            patch.object(ts, "send_special_key"),
            patch.object(ts, "send_input"),
        ):
            ok = await ts._confirm_worker_started_or_resubmit(
                "t1",
                "Analyze the logs",
                None,
                "sup",
                None,
                provider=provider,
            )
        assert ok is True
        probe.assert_not_called()

    async def test_provider_none_skips_direct_probe(self):
        # The existing None-provider path still works unchanged.
        with (
            patch.object(ts, "_wait_for_started_edge", new=AsyncMock(side_effect=[False, True])),
            patch.object(ts, "_worker_is_started_direct") as probe,
            patch.object(ts, "_message_visible_in_box", return_value=True),
            patch.object(ts, "send_special_key"),
            patch.object(ts, "send_input"),
        ):
            ok = await ts._confirm_worker_started_or_resubmit(
                "t1",
                "Analyze the logs",
                None,
                "sup",
                None,
                provider=None,
            )
        assert ok is True
        probe.assert_not_called()


class TestStartedEdgeGate:
    """BUG #5: the confirm gate must test an EDGE, not a status LEVEL.

    ``_DEFERRED_STARTED_STATUSES`` includes COMPLETED, and a freshly
    initialized worker that received nothing commonly RESTS at COMPLETED
    (kiro-cli's startup banner parses as a completed response — see
    ``KiroCliProvider.initialize``, which accepts IDLE *or* COMPLETED as ready —
    and COMPLETED is sticky, so it never decays to IDLE). Asking "is the current
    status in that set?" therefore answered *yes* before any input landed, the
    whole resubmit ladder became unreachable, and a swallowed Enter was reported
    as a started worker.
    """

    def test_level_is_vacuous_where_edge_is_not(self):
        """Pins the defect itself, on a real StatusMonitor: post-init resting
        level satisfies the old predicate while nothing has been accepted."""
        sm = StatusMonitor()
        sm._last_status["t1"] = TerminalStatus.COMPLETED  # startup banner
        sm.notify_input_sent("t1")  # send_input's dispatch boundary
        # Old gate's question — vacuously satisfied, which is the bug.
        assert sm._last_status["t1"] in ts._DEFERRED_STARTED_STATUSES
        # New gate's question — correctly unsatisfied.
        assert sm.saw_new_turn_since_input("t1") is False

    @pytest.mark.asyncio
    async def test_returns_true_when_edge_latched(self):
        sm = MagicMock()
        sm.saw_new_turn_since_input.return_value = True
        with (
            patch.object(ts, "get_backend", return_value=_backend(event_inbox=False)),
            patch.object(ts, "status_monitor", sm),
        ):
            assert await ts._wait_for_started_edge("t1", 0.05) is True

    @pytest.mark.asyncio
    async def test_returns_false_when_status_never_moves(self):
        """The BUG #5 scenario end to end through the gate: status parked at a
        'started' LEVEL the whole time, no edge → not confirmed."""
        sm = MagicMock()
        sm.saw_new_turn_since_input.return_value = False
        sm.get_status.return_value = TerminalStatus.COMPLETED
        with (
            patch.object(ts, "get_backend", return_value=_backend(event_inbox=False)),
            patch.object(ts, "status_monitor", sm),
        ):
            assert await ts._wait_for_started_edge("t1", 0.05) is False

    @pytest.mark.asyncio
    async def test_event_inbox_backend_falls_back_to_level_poll(self):
        """herdr never feeds the detection pipeline, so no transition is ever
        committed and the latch would stay False forever — a missing signal must
        not become a spurious teardown."""
        sm = MagicMock()
        sm.saw_new_turn_since_input.return_value = False
        with (
            patch.object(ts, "get_backend", return_value=_backend(event_inbox=True)),
            patch.object(ts, "status_monitor", sm),
            patch.object(ts, "wait_until_status", new=AsyncMock(return_value=True)) as level,
        ):
            assert await ts._wait_for_started_edge("t1", 0.05) is True
        level.assert_awaited_once()
        assert level.await_args.args[1] == ts._DEFERRED_STARTED_STATUSES
        sm.saw_new_turn_since_input.assert_not_called()


class TestWorkerIsStartedDirect:
    """Unit tests for the capture-pane direct status probe."""

    def test_returns_false_when_metadata_is_none(self):
        with patch.object(ts, "get_terminal_metadata", return_value=None):
            assert ts._worker_is_started_direct("t1", MagicMock()) is False

    def test_returns_false_when_session_key_missing(self):
        with patch.object(ts, "get_terminal_metadata", return_value={"tmux_window": "w1"}):
            assert ts._worker_is_started_direct("t1", MagicMock()) is False

    def test_returns_false_when_window_key_missing(self):
        with patch.object(ts, "get_terminal_metadata", return_value={"tmux_session": "s1"}):
            assert ts._worker_is_started_direct("t1", MagicMock()) is False

    def test_returns_false_when_get_history_raises(self):
        with (
            patch.object(
                ts,
                "get_terminal_metadata",
                return_value={
                    "tmux_session": "s1",
                    "tmux_window": "w1",
                },
            ),
            patch.object(ts, "get_backend") as mock_be,
        ):
            mock_be.return_value.get_history.side_effect = Exception("capture failed")
            assert ts._worker_is_started_direct("t1", MagicMock()) is False

    def test_returns_false_when_get_status_raises(self):
        provider = MagicMock()
        provider.get_status.side_effect = Exception("parse failure")
        with (
            patch.object(
                ts,
                "get_terminal_metadata",
                return_value={
                    "tmux_session": "s1",
                    "tmux_window": "w1",
                },
            ),
            patch.object(ts, "get_backend") as mock_be,
        ):
            assert ts._worker_is_started_direct("t1", provider) is False

    def test_returns_true_when_status_is_processing(self):
        from cli_agent_orchestrator.models.terminal import TerminalStatus

        provider = MagicMock()
        provider.get_status.return_value = TerminalStatus.PROCESSING
        with (
            patch.object(
                ts,
                "get_terminal_metadata",
                return_value={
                    "tmux_session": "s1",
                    "tmux_window": "w1",
                },
            ),
            patch.object(ts, "get_backend") as mock_be,
        ):
            assert ts._worker_is_started_direct("t1", provider) is True

    def test_returns_false_when_status_is_idle(self):
        from cli_agent_orchestrator.models.terminal import TerminalStatus

        provider = MagicMock()
        provider.get_status.return_value = TerminalStatus.IDLE
        with (
            patch.object(
                ts,
                "get_terminal_metadata",
                return_value={
                    "tmux_session": "s1",
                    "tmux_window": "w1",
                },
            ),
            patch.object(ts, "get_backend") as mock_be,
        ):
            assert ts._worker_is_started_direct("t1", provider) is False
