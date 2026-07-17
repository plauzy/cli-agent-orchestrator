"""AG-UI L2 construct library.

Re-exports the foundation layer: the base construct ABC, the emitter family,
the stream reader, the apply_json_patch_strict helper, and the lifecycle tracker.
"""

from __future__ import annotations

from cli_agent_orchestrator.services.agui.base import (
    AguiConstruct,
    HttpUiEmitter,
    InProcessUiEmitter,
    RecordingUiEmitter,
    UiEmitter,
    apply_json_patch_strict,
)
from cli_agent_orchestrator.services.agui.lifecycle_tracker import ToolCallLifecycleTracker
from cli_agent_orchestrator.services.agui.stream_reader import AguiStreamReader

__all__ = [
    "AguiConstruct",
    "AguiStreamReader",
    "HttpUiEmitter",
    "InProcessUiEmitter",
    "RecordingUiEmitter",
    "ToolCallLifecycleTracker",
    "UiEmitter",
    "apply_json_patch_strict",
]
