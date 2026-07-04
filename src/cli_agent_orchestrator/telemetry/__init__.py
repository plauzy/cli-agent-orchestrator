"""OpenTelemetry GenAI v1.37+ instrumentation for CAO.

Telemetry is opt-in: set ``OTEL_SDK_DISABLED=false`` to enable. With telemetry
disabled the helpers fall back to OTel's no-op tracer and add no measurable
overhead.
"""

from cli_agent_orchestrator.telemetry.context import extract_traceparent, inject_traceparent
from cli_agent_orchestrator.telemetry.otel import init_telemetry, shutdown_telemetry
from cli_agent_orchestrator.telemetry.spans import (
    chat_span,
    execute_tool_span,
    invoke_agent_span,
)

__all__ = [
    "chat_span",
    "execute_tool_span",
    "extract_traceparent",
    "init_telemetry",
    "invoke_agent_span",
    "inject_traceparent",
    "shutdown_telemetry",
]
