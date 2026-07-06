"""OpenTelemetry GenAI v1.37+ instrumentation for CAO.

Telemetry is opt-in twice over:

* the OTel packages ship as the ``[otel]`` optional extra
  (``pip install cli-agent-orchestrator[otel]``), keeping the base install
  lean, and
* even with the extra installed, the SDK activates only when
  ``OTEL_SDK_DISABLED=false``; otherwise the helpers fall back to OTel's
  no-op tracer and add no measurable overhead.

Without the extra, every helper below degrades to a no-op with the same
signature, so callers never need to guard their imports.
"""

from contextlib import contextmanager
from typing import Any, Iterator, Optional

try:
    from cli_agent_orchestrator.telemetry.context import extract_traceparent, inject_traceparent
    from cli_agent_orchestrator.telemetry.otel import init_telemetry, shutdown_telemetry
    from cli_agent_orchestrator.telemetry.spans import (
        chat_span,
        execute_tool_span,
        invoke_agent_span,
    )

    OTEL_AVAILABLE = True
except ImportError:  # opentelemetry not installed (base install, no [otel] extra)
    OTEL_AVAILABLE = False

    def init_telemetry(service_name: str) -> None:
        """No-op: the [otel] extra is not installed."""

    def shutdown_telemetry() -> None:
        """No-op: the [otel] extra is not installed."""

    def inject_traceparent() -> Optional[str]:
        """No-op: no recording span can exist without the [otel] extra."""
        return None

    def extract_traceparent(  # type: ignore[misc]  # real variant returns opentelemetry Context
        traceparent: Optional[str], tracestate: Optional[str] = None
    ) -> Any:
        """No-op: there is no OTel Context type without the [otel] extra."""
        return None

    @contextmanager
    def invoke_agent_span(
        agent_id: str,
        conversation_id: Optional[str] = None,
        tier: Optional[int] = None,
    ) -> Iterator[Any]:
        yield None

    @contextmanager
    def execute_tool_span(
        tool_name: str,
        conversation_id: Optional[str] = None,
    ) -> Iterator[Any]:
        yield None

    @contextmanager
    def chat_span(
        model: str,
        conversation_id: Optional[str] = None,
    ) -> Iterator[Any]:
        yield None


__all__ = [
    "OTEL_AVAILABLE",
    "chat_span",
    "execute_tool_span",
    "extract_traceparent",
    "init_telemetry",
    "invoke_agent_span",
    "inject_traceparent",
    "shutdown_telemetry",
]
