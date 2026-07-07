"""The [otel] extra is optional: the telemetry package must degrade to no-ops.

Review remediation (awslabs/cli-agent-orchestrator#387): the OTel packages
moved from unconditional runtime deps to the ``[otel]`` optional extra, so a
base install imports ``cli_agent_orchestrator.telemetry`` (and everything that
imports it, e.g. ``api.main``) without the SDK present.

The missing-SDK condition is simulated in a subprocess with a meta-path hook
that blocks ``opentelemetry`` imports — the SDK *is* installed in the dev
environment, so an in-process test could not exercise the fallback branch.
"""

from __future__ import annotations

import subprocess
import sys

_BLOCK_OTEL_AND_PROBE = """
import sys
from importlib.abc import MetaPathFinder

class _BlockOtel(MetaPathFinder):
    # find_spec, not the legacy find_module/load_module pair: the legacy
    # finder protocol was removed in Python 3.12, where a legacy blocker
    # silently stops blocking and this probe fails.
    def find_spec(self, name, path=None, target=None):
        if name == "opentelemetry" or name.startswith("opentelemetry."):
            raise ImportError(f"blocked for test: {name}")
        return None

sys.meta_path.insert(0, _BlockOtel())

import cli_agent_orchestrator.telemetry as t

assert t.OTEL_AVAILABLE is False, "fallback branch not taken"

# Every public helper must be callable and inert.
t.init_telemetry("cao")
t.shutdown_telemetry()
assert t.inject_traceparent() is None
assert t.extract_traceparent(None) is None
with t.invoke_agent_span("agent-1", conversation_id="c1", tier=2) as span:
    assert span is None
with t.execute_tool_span("tool-1") as span:
    assert span is None
with t.chat_span("model-1") as span:
    assert span is None

print("OK")
"""

# Same blocked-import environment, but telemetry is explicitly requested:
# the operator must get an actionable warning, not a silent no-op.
_WARN_WHEN_REQUESTED_PROBE = """
import logging
import os
import sys
from importlib.abc import MetaPathFinder

class _BlockOtel(MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == "opentelemetry" or name.startswith("opentelemetry."):
            raise ImportError(f"blocked for test: {name}")
        return None

sys.meta_path.insert(0, _BlockOtel())
os.environ["OTEL_SDK_DISABLED"] = "false"
logging.basicConfig(level=logging.WARNING)

import cli_agent_orchestrator.telemetry as t

assert t.OTEL_AVAILABLE is False
t.init_telemetry("cao")
print("OK")
"""


def test_telemetry_package_noops_without_otel_sdk() -> None:
    proc = subprocess.run(
        [sys.executable, "-c", _BLOCK_OTEL_AND_PROBE],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, f"stderr:\n{proc.stderr}\nstdout:\n{proc.stdout}"
    assert "OK" in proc.stdout


def test_api_main_imports_without_otel_sdk() -> None:
    """cao-server's module import path survives a base (no-extra) install."""
    probe = _BLOCK_OTEL_AND_PROBE.replace(
        "import cli_agent_orchestrator.telemetry as t",
        "import cli_agent_orchestrator.api.main  # noqa: F401\n"
        "import cli_agent_orchestrator.telemetry as t",
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"stderr:\n{proc.stderr}\nstdout:\n{proc.stdout}"
    assert "OK" in proc.stdout


def test_requested_telemetry_without_extra_warns() -> None:
    """OTEL_SDK_DISABLED=false + no [otel] extra → actionable warning, not silence."""
    proc = subprocess.run(
        [sys.executable, "-c", _WARN_WHEN_REQUESTED_PROBE],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, f"stderr:\n{proc.stderr}\nstdout:\n{proc.stdout}"
    assert "OK" in proc.stdout
    assert "cli-agent-orchestrator[otel]" in proc.stderr, (
        f"expected the install hint on stderr; got:\n{proc.stderr}"
    )
