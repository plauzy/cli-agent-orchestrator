"""Coverage for the A2A background executor + type helpers.

Targets the branches in ``a2a/rpc.py`` and ``a2a/types.py`` not hit by
the HTTP-level tests: ``_run_task_in_background`` (executor sets terminal
state, executor omits terminal state → COMPLETED, executor raises →
FAILED with error metadata), and the ``TaskState.all`` /
``JsonRpcError.to_dict`` helpers.
"""

from __future__ import annotations

import pytest

from cli_agent_orchestrator.a2a.rpc import _run_task_in_background
from cli_agent_orchestrator.a2a.store import InMemoryTaskStore
from cli_agent_orchestrator.a2a.stream import InMemoryTaskEventBus
from cli_agent_orchestrator.a2a.types import (
    A2AErrorCode,
    JsonRpcError,
    Task,
    TaskState,
)


@pytest.mark.asyncio
async def test_background_defaults_to_completed_when_executor_omits_terminal() -> None:
    store = InMemoryTaskStore()
    bus = InMemoryTaskEventBus()
    task = Task(id="t1", state=TaskState.SUBMITTED)
    await store.upsert(task)

    async def executor(t: Task) -> Task:
        # Returns without setting a terminal state.
        return t

    await _run_task_in_background(task, executor, store, bus)
    result = await store.get("t1")
    assert result is not None
    assert result.state == TaskState.COMPLETED


@pytest.mark.asyncio
async def test_background_honors_executor_terminal_state() -> None:
    store = InMemoryTaskStore()
    bus = InMemoryTaskEventBus()
    task = Task(id="t2", state=TaskState.SUBMITTED)
    await store.upsert(task)

    async def executor(t: Task) -> Task:
        t.state = TaskState.CANCELED
        return t

    await _run_task_in_background(task, executor, store, bus)
    result = await store.get("t2")
    assert result is not None
    assert result.state == TaskState.CANCELED


@pytest.mark.asyncio
async def test_background_marks_failed_on_executor_exception() -> None:
    store = InMemoryTaskStore()
    bus = InMemoryTaskEventBus()
    task = Task(id="t3", state=TaskState.SUBMITTED)
    await store.upsert(task)

    async def executor(t: Task) -> Task:
        raise RuntimeError("boom")

    await _run_task_in_background(task, executor, store, bus)
    result = await store.get("t3")
    assert result is not None
    assert result.state == TaskState.FAILED
    assert result.metadata.get("error") == "boom"


def test_task_state_all_lists_every_state() -> None:
    states = TaskState.all()
    assert set(states) == {
        TaskState.SUBMITTED,
        TaskState.WORKING,
        TaskState.INPUT_REQUIRED,
        TaskState.COMPLETED,
        TaskState.CANCELED,
        TaskState.FAILED,
    }


def test_jsonrpc_error_to_dict_includes_data_when_present() -> None:
    err = JsonRpcError(code=A2AErrorCode.TASK_NOT_FOUND, message="missing", data={"id": "x"})
    d = err.to_dict()
    assert d == {"code": 1, "message": "missing", "data": {"id": "x"}}

    # Omits data when None.
    err2 = JsonRpcError(code=A2AErrorCode.INVALID_PARAMS, message="bad")
    assert "data" not in err2.to_dict()
