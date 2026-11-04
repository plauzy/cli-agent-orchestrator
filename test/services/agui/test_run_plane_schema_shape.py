"""Every run-plane event carries only the fields the AG-UI 1.0 schema defines (A-M13).

AG-UI 1.0 ``architecture.mdx`` (Design Principles, "Tolerant reader, strict
writer"): "A producer MUST emit only what the schema defines". The schema closes
every event (``unevaluatedProperties: false``), while the SDK models are
``extra="allow"``, so a ``thread_id=`` or ``run_id=`` passed to an event that
does not define them reaches the wire as an undescribed key. Only
``RUN_STARTED`` and ``RUN_FINISHED`` carry ``threadId``/``runId``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pytest

pytest.importorskip("ag_ui")

from ag_ui.core import events as agui_events  # noqa: E402
from ag_ui.encoder import EventEncoder  # noqa: E402

from cli_agent_orchestrator.services.agui.base import RecordingUiEmitter  # noqa: E402
from cli_agent_orchestrator.services.agui.handoff_approval import (  # noqa: E402
    AgentHandoffWithApproval,
)
from cli_agent_orchestrator.services.agui.run_plane import (  # noqa: E402
    _translate_live_frame,
    run_plane_stream,
)

_KIRO_PROMPT = ("kiro_cli", "Allow this action? [y/n/t]:")
_SELECTOR_PROMPT = ("claude_code", "\u2191/\u2193 to navigate")

# AG-UI event type -> SDK model, for every type the run plane can emit.
_MODELS = {
    "RUN_STARTED": agui_events.RunStartedEvent,
    "RUN_FINISHED": agui_events.RunFinishedEvent,
    "RUN_ERROR": agui_events.RunErrorEvent,
    "STATE_SNAPSHOT": agui_events.StateSnapshotEvent,
    "STATE_DELTA": agui_events.StateDeltaEvent,
    "STEP_STARTED": agui_events.StepStartedEvent,
    "STEP_FINISHED": agui_events.StepFinishedEvent,
    "TOOL_CALL_START": agui_events.ToolCallStartEvent,
    "TOOL_CALL_END": agui_events.ToolCallEndEvent,
    "CUSTOM": agui_events.CustomEvent,
}


def _undescribed_keys(event: Dict[str, Any]) -> List[str]:
    model = _MODELS[event["type"]]
    allowed = {f.alias or name for name, f in model.model_fields.items()} | set(model.model_fields)
    return sorted(set(event) - allowed)


def _data(frames: List[str]) -> List[Dict[str, Any]]:
    return [
        json.loads(line[len("data: ") :])
        for frame in frames
        for line in frame.strip().split("\n")
        if line.startswith("data: ")
    ]


def _input(resume: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "threadId": "thread-m13",
        "runId": "run-m13",
        "state": {},
        "messages": [],
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }
    if resume is not None:
        body["resume"] = resume
    return body


async def _stream(construct: Any, snapshot: bool = True, **kw: Any) -> List[Dict[str, Any]]:
    frames = [
        f
        async for f in run_plane_stream(
            input_data=_input(**kw),
            approval_construct=construct,
            snapshot_fn=(lambda: {"sessions": [], "terminals": []}) if snapshot else None,
        )
    ]
    return _data(frames)


class _RecordingDelivery:
    def send_input(self, terminal_id: str, text: str, **kwargs: Any) -> None:
        pass

    def send_special_key(self, terminal_id: str, key: str) -> bool:
        return True


class _FailingDelivery:
    def send_input(self, terminal_id: str, text: str, **kwargs: Any) -> None:
        raise RuntimeError("backend down")

    def send_special_key(self, terminal_id: str, key: str) -> bool:
        raise RuntimeError("backend down")


def _construct(delivery: Any = None) -> AgentHandoffWithApproval:
    return AgentHandoffWithApproval(emitter=RecordingUiEmitter(), answer_delivery=delivery)


def _raise(construct: AgentHandoffWithApproval, prompt: tuple = _KIRO_PROMPT) -> Any:
    provider, raw = prompt
    return construct.on_provider_waiting(
        terminal_id="t-m13", provider=provider, raw_prompt=raw, session_name="s-m13"
    )


@pytest.mark.asyncio
async def test_interrupt_run_emits_only_described_fields():
    construct = _construct()
    _raise(construct)
    events = await _stream(construct)
    assert [e["type"] for e in events] == ["RUN_STARTED", "STATE_SNAPSHOT", "RUN_FINISHED"]
    for event in events:
        assert _undescribed_keys(event) == [], event


@pytest.mark.asyncio
async def test_success_run_emits_only_described_fields():
    events = await _stream(_construct())
    assert [e["type"] for e in events] == ["RUN_STARTED", "STATE_SNAPSHOT", "RUN_FINISHED"]
    for event in events:
        assert _undescribed_keys(event) == [], event


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prompt, delivery, payload",
    [
        pytest.param(_KIRO_PROMPT, _RecordingDelivery, {}, id="ambiguous"),
        pytest.param(_SELECTOR_PROMPT, _RecordingDelivery, {"editedArgs": "x"}, id="invalid"),
        pytest.param(_KIRO_PROMPT, _FailingDelivery, {"approved": True}, id="delivery"),
    ],
)
async def test_run_error_exits_emit_only_described_fields(prompt, delivery, payload):
    construct = _construct(delivery())
    pending = _raise(construct, prompt)
    events = await _stream(
        construct,
        resume=[{"interruptId": pending.id, "status": "resolved", "payload": payload}],
    )
    assert events[-1]["type"] == "RUN_ERROR", events
    for event in events:
        assert _undescribed_keys(event) == [], event


@pytest.mark.parametrize(
    "agui_type, data",
    [
        ("STATE_SNAPSHOT", {"snapshot": {"sessions": []}}),
        ("STATE_DELTA", {"delta": [{"op": "add", "path": "/x", "value": 1}]}),
        ("STEP_STARTED", {"step_id": "t1", "step_name": "worker"}),
        ("STEP_FINISHED", {"step_id": "t1", "step_name": "worker"}),
        ("TOOL_CALL_START", {"tool_call_id": "c1", "tool_call_name": "handoff"}),
        ("TOOL_CALL_END", {"tool_call_id": "c1"}),
        ("CUSTOM", {"name": "cao.generative_ui", "value": {"component": "metric"}}),
        ("TEXT_MESSAGE_CONTENT", {"message_id": "m1", "delta": ""}),
        ("RAW", {"event": {"kind": "other"}}),
        ("RUN_ERROR", {"message": "boom"}),
        ("SOMETHING_ELSE", {"x": 1}),
    ],
)
def test_live_frames_emit_only_described_fields(agui_type, data):
    encoded = _translate_live_frame(agui_type, data, "thread-m13", "run-m13", EventEncoder())
    assert encoded is not None
    (event,) = _data([encoded])
    assert _undescribed_keys(event) == [], event


@pytest.mark.parametrize("agui_type", ["STEP_STARTED", "STEP_FINISHED"])
def test_step_frames_carry_the_terminal_in_metadata(agui_type):
    """The terminal id moves from an undescribed ``stepId`` to ``metadata``."""
    encoded = _translate_live_frame(
        agui_type, {"step_id": "t1", "step_name": "worker"}, "th", "r", EventEncoder()
    )
    (event,) = _data([encoded])
    assert event["metadata"] == {"cao.terminalId": "t1"}
    assert "stepId" not in event


def test_step_frame_without_a_terminal_has_no_metadata():
    encoded = _translate_live_frame(
        "STEP_STARTED", {"step_name": "worker"}, "th", "r", EventEncoder()
    )
    (event,) = _data([encoded])
    assert "metadata" not in event
