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
