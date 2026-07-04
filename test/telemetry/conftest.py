"""Shared pytest fixtures for the telemetry tests.

OTel only allows the global ``TracerProvider`` to be installed once per
process, so the provider and its in-memory exporter are created once at
session scope and shared across all telemetry test modules.
"""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from cli_agent_orchestrator.telemetry import spans as spans_module


@pytest.fixture(scope="session")
def telemetry_exporter() -> InMemorySpanExporter:
    """Install a real ``TracerProvider`` once for the test session.

    Idempotent: if another test installed a provider first, we attach our
    span processor to that provider rather than trying to replace it.
    """
    exporter = InMemorySpanExporter()
    current = trace.get_tracer_provider()
    if isinstance(current, TracerProvider):
        # Provider already installed — just add our processor.
        current.add_span_processor(SimpleSpanProcessor(exporter))
    else:
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
    # Refresh the spans module's cached tracer to point at the active provider.
    spans_module._TRACER = trace.get_tracer(spans_module._TRACER_NAME)
    return exporter


@pytest.fixture
def exporter(telemetry_exporter: InMemorySpanExporter) -> InMemorySpanExporter:
    """Per-test exporter handle — clears finished spans on entry."""
    telemetry_exporter.clear()
    return telemetry_exporter
