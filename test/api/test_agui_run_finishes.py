"""POST /agui/v1/run must end its body (ag-ui-protocol/ag-ui#2216).

A stock AG-UI client completes a run only when the response body ends. These
tests drive the real route with the real SseBus, which never ends on its own,
and bound each request so a regression fails fast instead of hanging.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

import httpx
import pytest

import cli_agent_orchestrator.api.main as main
from cli_agent_orchestrator.api.main import app
from cli_agent_orchestrator.services import sse_bus
from cli_agent_orchestrator.services.agui.base import RecordingUiEmitter
from cli_agent_orchestrator.services.agui.handoff_approval import AgentHandoffWithApproval

# Without the [agui] extra the route returns 501; skip rather than fail for the wrong reason.
pytest.importorskip("ag_ui")

RUN_DEADLINE_SECONDS = 5.0
_WAITING_PROMPT = "↑/↓ to navigate"


class _FakeBridge:
    def __init__(self, construct: AgentHandoffWithApproval):
        self.construct = construct


@pytest.fixture(autouse=True)
def _route_env(monkeypatch):
    monkeypatch.setenv("CAO_AGUI_ENABLED", "true")
    monkeypatch.setattr(main, "is_auth_enabled", lambda: False)
    monkeypatch.setattr("cli_agent_orchestrator.security.auth.is_auth_enabled", lambda: False)
    monkeypatch.setattr("cli_agent_orchestrator.services.session_service.list_sessions", lambda: [])
    sse_bus.reset_bus()
    yield
    sse_bus.reset_bus()


@pytest.fixture
def construct():
    c = AgentHandoffWithApproval(emitter=RecordingUiEmitter(), answer_delivery=None)
    app.state.approval_bridge = _FakeBridge(c)
    yield c
    del app.state.approval_bridge


def _body(resume: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "threadId": "thread-finish",
        "runId": "run-finish",
        "state": {},
        "messages": [],
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }
    if resume is not None:
        body["resume"] = resume
    return body


def _approve(interrupt_id: str) -> Dict[str, Any]:
    return {"interruptId": interrupt_id, "status": "resolved", "payload": {"approved": True}}


async def _post_run(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as http:
        try:
            resp = await asyncio.wait_for(
                http.post("/agui/v1/run", json=body), timeout=RUN_DEADLINE_SECONDS
            )
        except asyncio.TimeoutError:
            pytest.fail(f"/agui/v1/run body did not end within {RUN_DEADLINE_SECONDS}s")
    assert resp.status_code == 200
    return [
        json.loads(line[len("data: ") :])
        for line in resp.text.split("\n")
        if line.startswith("data: ")
    ]


@pytest.mark.asyncio
async def test_run_ends_when_nothing_is_pending(construct):
    frames = await _post_run(_body())

    assert [f["type"] for f in frames] == ["RUN_STARTED", "STATE_SNAPSHOT", "RUN_FINISHED"]
    assert frames[-1]["outcome"]["type"] == "success"


@pytest.mark.asyncio
async def test_run_ends_after_resume_resolves_the_only_interrupt(construct):
    interrupt = construct.on_provider_waiting("t-1", "claude_code", _WAITING_PROMPT)

    frames = await _post_run(_body(resume=[_approve(interrupt.id)]))

    assert construct.get_interrupt(interrupt.id).resolved
    assert frames[0]["type"] == "RUN_STARTED"
    assert frames[-1]["type"] == "RUN_FINISHED"
    assert frames[-1]["outcome"]["type"] == "success"


@pytest.mark.asyncio
async def test_run_ends_with_remaining_interrupt_after_partial_resume(construct):
    first = construct.on_provider_waiting("t-1", "claude_code", _WAITING_PROMPT)
    second = construct.on_provider_waiting("t-2", "claude_code", _WAITING_PROMPT)

    frames = await _post_run(_body(resume=[_approve(first.id)]))

    assert construct.get_interrupt(first.id).resolved
    assert frames[-1]["type"] == "RUN_FINISHED"
    assert frames[-1]["outcome"]["type"] == "interrupt"
    assert [i["id"] for i in frames[-1]["outcome"]["interrupts"]] == [second.id]
