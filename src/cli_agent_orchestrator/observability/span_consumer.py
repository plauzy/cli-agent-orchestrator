"""OTel span → AsiEvaluator bridge (Phase 4 / commit 22).

The Deacon needs a stream of ``SpanRecord`` instances to score. Phase 1
(commit 1) installed an OTel SDK with a ``BatchSpanProcessor`` exporting
to a collector. The vision doc described the Deacon as "out-of-band
sidecar consuming OTel spans over the collector OTLP endpoint" — a
faithful reading, but operationally heavy: it requires running a
collector + a separate Deacon process just to evaluate ASI.

This module ships a lighter-weight equivalent: an in-process
``SpanProcessor`` that taps the same span stream the exporter sees,
extracts the CAO attributes, and feeds an ``AsiEvaluator``. The
collector path remains available for operators who prefer the
sidecar deployment — they can disable this processor and run the
Deacon as a separate OTLP consumer instead.

Wiring (lifespan-level, commit 23):

    from cli_agent_orchestrator.observability import (
        AsiEvaluator,
        AsiSpanProcessor,
        standard_handlers,
    )

    evaluator = AsiEvaluator()
    for h in standard_handlers(...):
        evaluator.add_handler(h)
    AsiSpanProcessor(evaluator).attach()  # installs on global provider

The processor is a no-op when telemetry is disabled (no global
TracerProvider with span processors) — same opt-in semantics as the
rest of the OTel stack.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from cli_agent_orchestrator.observability.asi_evaluator import (
    AsiEvaluator,
    SpanRecord,
)
from cli_agent_orchestrator.telemetry import semconv

logger = logging.getLogger(__name__)


def span_to_record(span: Any) -> Optional[SpanRecord]:
    """Convert an OTel ``ReadableSpan`` to a ``SpanRecord``.

    Returns ``None`` when the span is missing required CAO context
    (``cao.task_class`` is the discriminator — without it the Deacon
    can't bucket the span). This filters non-CAO spans on hosts where
    multiple SDK-instrumented libraries share the same TracerProvider.
    """
    attrs = dict(getattr(span, "attributes", {}) or {})
    task_class = attrs.get(semconv.CAO_TASK_CLASS)
    if not task_class:
        return None

    operation = attrs.get(semconv.GEN_AI_OPERATION_NAME)
    if not operation:
        # Best-effort fallback: pick up well-known span names. CAO
        # emits "invoke_agent" / "execute_tool" / "chat" via
        # telemetry.spans, but the attribute is the source of truth.
        operation = getattr(span, "name", "unknown") or "unknown"

    agent_id = attrs.get(semconv.GEN_AI_AGENT_ID, "")
    conversation_id = attrs.get(semconv.GEN_AI_CONVERSATION_ID, "")

    # OTel ReadableSpan exposes start_time / end_time as ints in
    # nanoseconds since epoch. Defensive: fall back to 0 if either is
    # missing so a malformed span doesn't crash the processor.
    start = getattr(span, "start_time", None) or 0
    end = getattr(span, "end_time", None) or start
    duration_ms = max((end - start) / 1_000_000.0, 0.0)

    return SpanRecord(
        name=getattr(span, "name", "") or "",
        operation=str(operation),
        agent_id=str(agent_id),
        conversation_id=str(conversation_id),
        task_class=str(task_class),
        duration_ms=duration_ms,
        attributes=attrs,
    )


class AsiSpanProcessor:
    """OTel ``SpanProcessor`` that feeds the Deacon.

    Implements the duck-typed ``SpanProcessor`` interface
    (``on_start`` / ``on_end`` / ``shutdown`` / ``force_flush``) so it
    can be attached to ``opentelemetry.sdk.trace.TracerProvider`` via
    ``add_span_processor``. We don't subclass the SDK's ``SpanProcessor``
    base because the SDK is an optional dependency — the type hints
    would force it eagerly, which breaks the OTel-disabled fast path.

    All exceptions are swallowed: the processor must never propagate
    errors back into the SDK's span-emit hot path. Drift detection is
    opportunistic — a transient handler bug must not break the
    application.
    """

    def __init__(self, evaluator: AsiEvaluator) -> None:
        self._evaluator = evaluator

    # SpanProcessor protocol ------------------------------------------------

    def on_start(self, span: Any, parent_context: Any = None) -> None:  # noqa: D401
        """No-op: the Deacon scores completed spans."""

    def _on_ending(self, span: Any) -> None:
        # Newer OTel SDK versions call this private hook before ``on_end``
        # to give processors a chance to mutate the span. The Deacon is
        # purely observational, so this is a no-op.
        pass

    def on_end(self, span: Any) -> None:
        try:
            record = span_to_record(span)
            if record is None:
                return
            self._evaluator.observe(record)
        except Exception:
            logger.warning("AsiSpanProcessor.on_end failed", exc_info=True)

    def shutdown(self) -> None:
        # Nothing to flush — the evaluator is fully synchronous.
        pass

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True

    # Convenience wiring ----------------------------------------------------

    def attach(self, provider: Any = None) -> bool:
        """Install on the given (or global) TracerProvider.

        Returns True if attached, False if the provider doesn't accept
        processors (e.g. the default no-op provider when telemetry is
        disabled). Callers should treat False as "OTel is off; the
        Deacon will see no spans" — not as an error.
        """
        if provider is None:
            try:
                from opentelemetry import trace

                provider = trace.get_tracer_provider()
            except Exception:
                logger.debug("opentelemetry not importable; AsiSpanProcessor not attached")
                return False

        add = getattr(provider, "add_span_processor", None)
        if not callable(add):
            # ProxyTracerProvider (default no-op) doesn't expose this.
            logger.debug(
                "TracerProvider %r has no add_span_processor; " "AsiSpanProcessor not attached",
                type(provider).__name__,
            )
            return False
        add(self)
        logger.info("AsiSpanProcessor attached to %s", type(provider).__name__)
        return True
