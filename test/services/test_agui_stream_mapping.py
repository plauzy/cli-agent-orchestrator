"""Tests for the CAO→AG-UI event mapping.

Sibling RFC: docs/rfc/cao-agui-l2-dashboard-2026-05-11-v1.md.

Privacy boundary asserted: message bodies are never carried on the
wire, even when the CAO event's payload includes them.
"""

from __future__ import annotations

import pytest

from cli_agent_orchestrator.services.agui_stream import (
    AGUI_RAW,
    AGUI_RUN_FINISHED,
    AGUI_RUN_STARTED,
    AGUI_STEP_FINISHED,
    AGUI_STEP_STARTED,
    AGUI_TEXT_MESSAGE_CONTENT,
    to_agui_event,
)


class TestRunStartedFinished:
    def test_session_created_maps_to_run_started(self) -> None:
        agui_type, data = to_agui_event(
            {
                "type": "session.created",
                "payload": {"session_name": "cao-foo"},
                "traceparent": "tp",
            }
        )
        assert agui_type == AGUI_RUN_STARTED
        assert data["thread_id"] == "cao-foo"
        assert data["run_id"] == "cao-foo"
        assert data["traceparent"] == "tp"

    def test_session_killed_maps_to_run_finished(self) -> None:
        agui_type, data = to_agui_event(
            {"type": "session.killed", "payload": {"session_name": "cao-foo"}}
        )
        assert agui_type == AGUI_RUN_FINISHED
        assert data["status"] == "terminated"


class TestStepStartedFinished:
    def test_terminal_created_maps_to_step_started(self) -> None:
        agui_type, data = to_agui_event(
            {
                "type": "terminal.created",
                "payload": {
                    "terminal_id": "abc12345",
                    "agent_name": "developer",
                    "provider": "claude_code",
                },
            }
        )
        assert agui_type == AGUI_STEP_STARTED
        assert data["step_id"] == "abc12345"
        assert data["step_name"] == "developer"
        assert data["provider"] == "claude_code"

    def test_terminal_killed_maps_to_step_finished(self) -> None:
        agui_type, data = to_agui_event(
            {
                "type": "terminal.killed",
                "payload": {"terminal_id": "abc12345", "agent_name": "developer"},
            }
        )
        assert agui_type == AGUI_STEP_FINISHED
        assert data["step_id"] == "abc12345"


class TestTextMessage:
    def test_message_sent_maps_to_text_message_content(self) -> None:
        agui_type, data = to_agui_event(
            {
                "type": "message.sent",
                "payload": {
                    "sender": "s",
                    "receiver": "r",
                    "orchestration_type": "handoff",
                },
            }
        )
        assert agui_type == AGUI_TEXT_MESSAGE_CONTENT
        assert data["role"] == "assistant"
        assert data["message_id"] == "r"
        # Privacy: never include the body.
        assert data["delta"] == ""

    def test_message_body_redacted_even_when_payload_includes_it(self) -> None:
        agui_type, data = to_agui_event(
            {
                "type": "message.sent",
                "payload": {
                    "sender": "s",
                    "receiver": "r",
                    "orchestration_type": "handoff",
                    "message": "SECRET — must not appear on the wire",
                },
            }
        )
        assert agui_type == AGUI_TEXT_MESSAGE_CONTENT
        # The body never appears in any field, not in delta and not in
        # metadata. Stringify the whole payload to be thorough.
        as_str = str(data)
        assert "SECRET" not in as_str
        assert "must not appear" not in as_str


class TestRaw:
    @pytest.mark.parametrize(
        "kind",
        [
            "terminal.interrupted",
            "terminal.paused",
            "terminal.resumed",
            "asi.mitigation",
            "anything.else.we.havent.mapped",
        ],
    )
    def test_unmapped_falls_back_to_raw(self, kind: str) -> None:
        agui_type, data = to_agui_event({"type": kind, "payload": {"terminal_id": "abc12345"}})
        assert agui_type == AGUI_RAW
        # RAW preserves the original semantics so the PWA's reducer
        # can dispatch on the cao_type field.
        assert data["cao_type"] == kind
        assert data["payload"]["terminal_id"] == "abc12345"


class TestNullSafety:
    def test_empty_event(self) -> None:
        agui_type, data = to_agui_event({})
        assert agui_type == AGUI_RAW
        assert data["cao_type"] == ""


# ---------------------------------------------------------------------------
# Re-based primitive path: map upstream's normalized six-primitive event
# records (the SseBus / EventLog shape) onto AG-UI typed events.
# ---------------------------------------------------------------------------

from cli_agent_orchestrator.services.agui_stream import (  # noqa: E402
    AGUI_RUN_ERROR,
    AGUI_STATE_DELTA,
    AGUI_TOOL_CALL_START,
)


def _record(kind: str, *, terminal_id=None, session_name=None, detail=None) -> dict:
    """Build an upstream-shaped normalized event record."""
    return {
        "id": "evt-1",
        "kind": kind,
        "terminal_id": terminal_id,
        "session_name": session_name,
        "timestamp": "2026-07-04T00:00:00+00:00",
        "detail": detail or {},
    }


class TestPrimitivePath:
    def test_launch_session_maps_to_run_started(self) -> None:
        agui_type, data = to_agui_event(
            _record("launch", session_name="cao-foo", detail={"event_type": "post_create_session"})
        )
        assert agui_type == AGUI_RUN_STARTED
        assert data["thread_id"] == "cao-foo"
        assert data["run_id"] == "cao-foo"
        assert data["event_id"] == "evt-1"

    def test_launch_terminal_maps_to_step_started(self) -> None:
        agui_type, data = to_agui_event(
            _record(
                "launch",
                terminal_id="abc12345",
                session_name="cao-foo",
                detail={"event_type": "post_create_terminal", "agent_name": "developer", "provider": "claude_code"},
            )
        )
        assert agui_type == AGUI_STEP_STARTED
        assert data["step_id"] == "abc12345"
        assert data["step_name"] == "developer"
        assert data["provider"] == "claude_code"

    def test_completion_session_maps_to_run_finished(self) -> None:
        agui_type, data = to_agui_event(
            _record("completion", session_name="cao-foo", detail={"event_type": "post_kill_session"})
        )
        assert agui_type == AGUI_RUN_FINISHED
        assert data["status"] == "terminated"

    def test_completion_terminal_maps_to_step_finished(self) -> None:
        agui_type, data = to_agui_event(
            _record("completion", terminal_id="abc12345", detail={"event_type": "post_kill_terminal", "agent_name": "developer"})
        )
        assert agui_type == AGUI_STEP_FINISHED
        assert data["step_id"] == "abc12345"

    def test_handoff_maps_to_text_message_content_and_redacts_body(self) -> None:
        agui_type, data = to_agui_event(
            _record(
                "handoff",
                terminal_id="r",
                detail={"sender": "s", "receiver": "r", "orchestration_type": "handoff"},
            )
        )
        assert agui_type == AGUI_TEXT_MESSAGE_CONTENT
        assert data["role"] == "assistant"
        assert data["message_id"] == "r"
        assert data["delta"] == ""

    def test_a2a_delegation_maps_to_tool_call_start(self) -> None:
        agui_type, data = to_agui_event(
            _record("a2a_delegation", detail={"sender": "s", "receiver": "r", "orchestration_type": "a2a_send"})
        )
        assert agui_type == AGUI_TOOL_CALL_START
        assert data["tool_call_name"] == "a2a_delegation"

    def test_file_mod_maps_to_state_delta(self) -> None:
        agui_type, data = to_agui_event(_record("file_mod", terminal_id="t", detail={"path": "x.py"}))
        assert agui_type == AGUI_STATE_DELTA
        assert data["delta"] == []

    def test_error_maps_to_run_error(self) -> None:
        agui_type, data = to_agui_event(_record("error", detail={"event_type": "boom"}))
        assert agui_type == AGUI_RUN_ERROR

    def test_other_falls_back_to_raw(self) -> None:
        agui_type, data = to_agui_event(_record("other", detail={"event_type": "post_pause_terminal"}))
        assert agui_type == AGUI_RAW
        assert data["cao_kind"] == "other"
        assert data["cao_type"] == "post_pause_terminal"

    def test_handoff_never_leaks_body_even_if_detail_has_one(self) -> None:
        # The publisher never puts bodies in detail, but assert defensively.
        agui_type, data = to_agui_event(
            _record("handoff", terminal_id="r", detail={"receiver": "r", "message": "SECRET-BODY"})
        )
        assert agui_type == AGUI_TEXT_MESSAGE_CONTENT
        assert "SECRET-BODY" not in str(data)
