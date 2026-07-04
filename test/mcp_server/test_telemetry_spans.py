"""Tests verifying that the MCP tool implementations emit GenAI execute_tool spans.

These tests assert that ``_send_message_impl``, ``_load_skill_impl``, and
``_assign_impl`` open an ``execute_tool {tool_name}`` span and record the
expected attributes (``gen_ai.operation.name``, ``cao.tool.outcome``, etc).
``_handoff_impl`` is exercised at unit level only — it spawns a real terminal
in production paths, so the deeper assertions live in E2E tests.

The shared in-memory exporter fixture is reused via ``conftest.py`` at
``test/telemetry/`` — to keep the fixture local without coupling the test
trees, we install our own here.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from cli_agent_orchestrator.telemetry import semconv
from cli_agent_orchestrator.telemetry import spans as spans_module


@pytest.fixture(scope="module")
def telemetry_exporter() -> InMemorySpanExporter:
    """Install (or attach to) a TracerProvider and surface an in-memory exporter."""
    exporter = InMemorySpanExporter()
    current = trace.get_tracer_provider()
    if isinstance(current, TracerProvider):
        current.add_span_processor(SimpleSpanProcessor(exporter))
    else:
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
    spans_module._TRACER = trace.get_tracer(spans_module._TRACER_NAME)
    return exporter


@pytest.fixture
def exporter(telemetry_exporter: InMemorySpanExporter) -> InMemorySpanExporter:
    telemetry_exporter.clear()
    return telemetry_exporter


def _execute_tool_span_for(exporter: InMemorySpanExporter, tool_name: str):
    target = f"execute_tool {tool_name}"
    matches = [s for s in exporter.get_finished_spans() if s.name == target]
    assert len(matches) == 1, (
        f"expected exactly 1 {target!r} span, got {len(matches)}"
        f" (all spans: {[s.name for s in exporter.get_finished_spans()]})"
    )
    return matches[0]


class TestSendMessageSpan:
    @patch("cli_agent_orchestrator.mcp_server.server._send_to_inbox")
    def test_send_message_emits_execute_tool_span(self, mock_inbox, exporter):
        from cli_agent_orchestrator.mcp_server.server import _send_message_impl

        mock_inbox.return_value = {"success": True, "message_id": 42}
        result = _send_message_impl("receiver-123", "ping")

        assert result == {"success": True, "message_id": 42}
        span = _execute_tool_span_for(exporter, "send_message")
        assert span.attributes[semconv.GEN_AI_OPERATION_NAME] == semconv.OPERATION_EXECUTE_TOOL
        assert span.attributes["cao.receiver_terminal_id"] == "receiver-123"
        assert span.attributes["cao.tool.outcome"] == "success"

    @patch("cli_agent_orchestrator.mcp_server.server._send_to_inbox")
    def test_send_message_records_failure_outcome(self, mock_inbox, exporter):
        from cli_agent_orchestrator.mcp_server.server import _send_message_impl

        mock_inbox.return_value = {"success": False, "error": "rate-limited"}
        _send_message_impl("receiver-9", "ping")

        span = _execute_tool_span_for(exporter, "send_message")
        assert span.attributes["cao.tool.outcome"] == "failure"

    @patch("cli_agent_orchestrator.mcp_server.server._send_to_inbox")
    def test_send_message_records_error_outcome_on_exception(self, mock_inbox, exporter):
        from cli_agent_orchestrator.mcp_server.server import _send_message_impl

        mock_inbox.side_effect = RuntimeError("boom")
        result = _send_message_impl("receiver-9", "ping")

        assert result["success"] is False
        span = _execute_tool_span_for(exporter, "send_message")
        assert span.attributes["cao.tool.outcome"] == "error"


class TestLoadSkillSpan:
    @patch("cli_agent_orchestrator.mcp_server.server.requests.get")
    def test_load_skill_emits_execute_tool_span_with_skill_name(self, mock_get, exporter):
        from cli_agent_orchestrator.mcp_server.server import _load_skill_impl

        mock_get.return_value.json.return_value = {"content": "# Skill body"}
        mock_get.return_value.raise_for_status.return_value = None

        result = _load_skill_impl("cao-supervisor-protocols")

        assert result == "# Skill body"
        span = _execute_tool_span_for(exporter, "load_skill")
        assert span.attributes[semconv.GEN_AI_OPERATION_NAME] == semconv.OPERATION_EXECUTE_TOOL
        assert span.attributes["cao.skill.name"] == "cao-supervisor-protocols"

    @patch("cli_agent_orchestrator.mcp_server.server.requests.get")
    def test_load_skill_records_connection_error(self, mock_get, exporter):
        import requests

        from cli_agent_orchestrator.mcp_server.server import _load_skill_impl

        mock_get.side_effect = requests.ConnectionError("nope")
        result = _load_skill_impl("missing")

        assert result["success"] is False
        span = _execute_tool_span_for(exporter, "load_skill")
        assert span.attributes["cao.tool.outcome"] == "connection_error"


class TestAssignSpan:
    @patch("cli_agent_orchestrator.mcp_server.server._send_direct_input_assign")
    @patch("cli_agent_orchestrator.mcp_server.server.wait_until_terminal_status")
    @patch("cli_agent_orchestrator.mcp_server.server._create_terminal")
    def test_assign_emits_execute_tool_span(self, mock_create, mock_wait, _mock_send, exporter):
        from cli_agent_orchestrator.mcp_server.server import _assign_impl

        mock_create.return_value = ("term-abc", "kiro_cli")
        mock_wait.return_value = True

        result = asyncio.run(_assign_impl("developer", "do the thing"))

        assert result["success"] is True
        span = _execute_tool_span_for(exporter, "assign")
        assert span.attributes["cao.target_agent_profile"] == "developer"
        assert span.attributes["cao.target_terminal_id"] == "term-abc"
        assert span.attributes["cao.tool.outcome"] == "success"

    @patch("cli_agent_orchestrator.mcp_server.server.wait_until_terminal_status")
    @patch("cli_agent_orchestrator.mcp_server.server._create_terminal")
    def test_assign_records_ready_timeout(self, mock_create, mock_wait, exporter):
        from cli_agent_orchestrator.mcp_server.server import _assign_impl

        mock_create.return_value = ("term-xyz", "kiro_cli")
        mock_wait.return_value = False

        result = asyncio.run(_assign_impl("developer", "do the thing"))

        assert result["success"] is False
        span = _execute_tool_span_for(exporter, "assign")
        assert span.attributes["cao.tool.outcome"] == "ready_timeout"
