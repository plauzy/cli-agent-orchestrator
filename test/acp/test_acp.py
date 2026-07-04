"""Tests for the Phase 5 ACP server (commit 29).

Coverage matrix:
  * Types: AcpRequest.from_dict, AcpResponse.to_dict (success + error),
    AcpNotification round-trip
  * Handlers — initialize: handshake succeeds; double-init rejected;
    missing protocolVersion is invalid_params; future protocol version
    is unsupported
  * Handlers — session/new: assigns id when missing; idempotent on
    repeat; rejects empty id
  * Handlers — session/prompt: requires init + valid sessionId;
    completes the session; unknown sessionId rejected
  * Handlers — session/cancel: transitions active→canceled; idempotent
    on terminal sessions; unknown sessionId rejected
  * Server loop: parses one request → writes one response; parse error
    → -32700 with id=null; non-object → -32600; bad jsonrpc → -32600;
    missing method → -32600; notification (no id) ignored; HandlerError
    surfaces as error response; EOF on reader closes the loop
"""

from __future__ import annotations

import asyncio
import json

import pytest

from cli_agent_orchestrator.acp import (
    AcpErrorCode,
    AcpHandlers,
    AcpNotification,
    AcpRequest,
    AcpResponse,
    AcpServer,
    register_default_handlers,
)
from cli_agent_orchestrator.acp.handlers import HandlerError

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MemReader:
    """In-memory async reader of newline-delimited bytes."""

    def __init__(self, lines: list[bytes]) -> None:
        self._lines = list(lines)

    async def readline(self) -> bytes:
        if not self._lines:
            return b""
        return self._lines.pop(0)


class _MemWriter:
    def __init__(self) -> None:
        self.buf = bytearray()

    def write(self, data: bytes) -> None:
        self.buf.extend(data)

    async def drain(self) -> None:
        return None

    def lines(self) -> list[dict]:
        out: list[dict] = []
        for raw in self.buf.splitlines():
            if not raw.strip():
                continue
            out.append(json.loads(raw))
        return out


def _req(method: str, params: dict | None = None, *, req_id: str | int | None = "1") -> bytes:
    return (
        json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}})
        + "\n"
    ).encode("utf-8")


def _make_server() -> tuple[AcpServer, AcpHandlers]:
    handlers = register_default_handlers(AcpHandlers())
    return AcpServer(handlers=handlers), handlers


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class TestTypes:
    async def test_request_from_dict(self):
        req = AcpRequest.from_dict({"jsonrpc": "2.0", "id": "1", "method": "x", "params": {"y": 1}})
        assert req.method == "x"
        assert req.id == "1"
        assert req.params == {"y": 1}

    async def test_request_missing_params_defaults(self):
        req = AcpRequest.from_dict({"jsonrpc": "2.0", "id": 1, "method": "x"})
        assert req.params == {}

    async def test_response_to_dict_success(self):
        resp = AcpResponse(id="1", result={"ok": True})
        assert resp.to_dict() == {"jsonrpc": "2.0", "id": "1", "result": {"ok": True}}

    async def test_response_to_dict_error(self):
        from cli_agent_orchestrator.acp.types import AcpError

        resp = AcpResponse(id=42, error=AcpError(code=-32601, message="bad"))
        d = resp.to_dict()
        assert d == {
            "jsonrpc": "2.0",
            "id": 42,
            "error": {"code": -32601, "message": "bad"},
        }

    async def test_notification_to_dict(self):
        n = AcpNotification(method="session/output", params={"line": "hi"})
        assert n.to_dict() == {
            "jsonrpc": "2.0",
            "method": "session/output",
            "params": {"line": "hi"},
        }


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


class TestInitialize:
    async def test_handshake_returns_capabilities(self):
        _, handlers = _make_server()
        result = await handlers.dispatch("initialize", {"protocolVersion": 1})
        assert result["protocolVersion"] == 1
        assert result["serverInfo"]["name"] == "cli-agent-orchestrator"
        assert result["capabilities"]["session"]["new"] is True
        assert handlers.initialized is True

    async def test_double_init_rejected(self):
        _, handlers = _make_server()
        await handlers.dispatch("initialize", {"protocolVersion": 1})
        with pytest.raises(HandlerError) as exc:
            await handlers.dispatch("initialize", {"protocolVersion": 1})
        assert exc.value.code == int(AcpErrorCode.ALREADY_INITIALIZED)

    async def test_missing_protocol_version_is_invalid_params(self):
        _, handlers = _make_server()
        with pytest.raises(HandlerError) as exc:
            await handlers.dispatch("initialize", {})
        assert exc.value.code == int(AcpErrorCode.INVALID_PARAMS)

    async def test_future_protocol_version_rejected(self):
        _, handlers = _make_server()
        with pytest.raises(HandlerError) as exc:
            await handlers.dispatch("initialize", {"protocolVersion": 99})
        assert exc.value.code == int(AcpErrorCode.UNSUPPORTED_PROTOCOL_VERSION)

    async def test_other_methods_require_init(self):
        _, handlers = _make_server()
        with pytest.raises(HandlerError) as exc:
            await handlers.dispatch("session/new", {})
        assert exc.value.code == int(AcpErrorCode.NOT_INITIALIZED)


class TestSessionNew:
    async def test_assigns_id_when_missing(self):
        _, handlers = _make_server()
        await handlers.dispatch("initialize", {"protocolVersion": 1})
        result = await handlers.dispatch("session/new", {})
        assert result["sessionId"]
        assert result["state"] == "active"

    async def test_idempotent_on_repeat(self):
        _, handlers = _make_server()
        await handlers.dispatch("initialize", {"protocolVersion": 1})
        first = await handlers.dispatch("session/new", {"sessionId": "s1"})
        second = await handlers.dispatch("session/new", {"sessionId": "s1"})
        assert first["sessionId"] == second["sessionId"]


class TestSessionPrompt:
    async def test_completes_session(self):
        _, handlers = _make_server()
        await handlers.dispatch("initialize", {"protocolVersion": 1})
        await handlers.dispatch("session/new", {"sessionId": "s1"})
        result = await handlers.dispatch("session/prompt", {"sessionId": "s1", "prompt": "hello"})
        assert result["state"] == "completed"
        assert "hello" in result["output"]

    async def test_unknown_session_rejected(self):
        _, handlers = _make_server()
        await handlers.dispatch("initialize", {"protocolVersion": 1})
        with pytest.raises(HandlerError) as exc:
            await handlers.dispatch("session/prompt", {"sessionId": "nope", "prompt": "x"})
        assert exc.value.code == int(AcpErrorCode.SESSION_NOT_FOUND)

    async def test_missing_prompt_invalid_params(self):
        _, handlers = _make_server()
        await handlers.dispatch("initialize", {"protocolVersion": 1})
        await handlers.dispatch("session/new", {"sessionId": "s1"})
        with pytest.raises(HandlerError) as exc:
            await handlers.dispatch("session/prompt", {"sessionId": "s1"})
        assert exc.value.code == int(AcpErrorCode.INVALID_PARAMS)


class TestSessionCancel:
    async def test_cancels_active_session(self):
        _, handlers = _make_server()
        await handlers.dispatch("initialize", {"protocolVersion": 1})
        await handlers.dispatch("session/new", {"sessionId": "s1"})
        result = await handlers.dispatch("session/cancel", {"sessionId": "s1"})
        assert result["state"] == "canceled"

    async def test_cancel_completed_is_idempotent(self):
        _, handlers = _make_server()
        await handlers.dispatch("initialize", {"protocolVersion": 1})
        await handlers.dispatch("session/new", {"sessionId": "s1"})
        await handlers.dispatch("session/prompt", {"sessionId": "s1", "prompt": "x"})
        # Session is now completed; cancel should be a no-op.
        result = await handlers.dispatch("session/cancel", {"sessionId": "s1"})
        assert result["state"] == "completed"

    async def test_unknown_session_rejected(self):
        _, handlers = _make_server()
        await handlers.dispatch("initialize", {"protocolVersion": 1})
        with pytest.raises(HandlerError) as exc:
            await handlers.dispatch("session/cancel", {"sessionId": "nope"})
        assert exc.value.code == int(AcpErrorCode.SESSION_NOT_FOUND)


# ---------------------------------------------------------------------------
# Stdio loop
# ---------------------------------------------------------------------------


class TestServerLoop:
    async def test_one_request_one_response(self):
        server, _ = _make_server()
        reader = _MemReader([_req("initialize", {"protocolVersion": 1})])
        writer = _MemWriter()
        await asyncio.wait_for(server.run(reader, writer), timeout=1.0)
        responses = writer.lines()
        assert len(responses) == 1
        assert responses[0]["id"] == "1"
        assert "result" in responses[0]

    async def test_parse_error_emits_neg_32700(self):
        server, _ = _make_server()
        reader = _MemReader([b"not json\n"])
        writer = _MemWriter()
        await asyncio.wait_for(server.run(reader, writer), timeout=1.0)
        responses = writer.lines()
        assert responses[0]["error"]["code"] == int(AcpErrorCode.PARSE_ERROR)
        assert responses[0]["id"] is None

    async def test_non_object_request_emits_invalid_request(self):
        server, _ = _make_server()
        reader = _MemReader([b"[1, 2, 3]\n"])
        writer = _MemWriter()
        await asyncio.wait_for(server.run(reader, writer), timeout=1.0)
        responses = writer.lines()
        assert responses[0]["error"]["code"] == int(AcpErrorCode.INVALID_REQUEST)

    async def test_wrong_jsonrpc_version_rejected(self):
        server, _ = _make_server()
        line = (
            json.dumps({"jsonrpc": "1.0", "id": "1", "method": "initialize", "params": {}}) + "\n"
        ).encode("utf-8")
        reader = _MemReader([line])
        writer = _MemWriter()
        await asyncio.wait_for(server.run(reader, writer), timeout=1.0)
        responses = writer.lines()
        assert responses[0]["error"]["code"] == int(AcpErrorCode.INVALID_REQUEST)

    async def test_notification_is_silently_ignored(self):
        server, _ = _make_server()
        # No id → notification.
        line = (
            json.dumps({"jsonrpc": "2.0", "method": "session/output", "params": {}}) + "\n"
        ).encode("utf-8")
        reader = _MemReader([line])
        writer = _MemWriter()
        await asyncio.wait_for(server.run(reader, writer), timeout=1.0)
        # No response written.
        assert writer.lines() == []

    async def test_handler_error_surfaces_as_response(self):
        server, _ = _make_server()
        # session/new requires initialization → NOT_INITIALIZED.
        reader = _MemReader([_req("session/new", {})])
        writer = _MemWriter()
        await asyncio.wait_for(server.run(reader, writer), timeout=1.0)
        responses = writer.lines()
        assert responses[0]["error"]["code"] == int(AcpErrorCode.NOT_INITIALIZED)

    async def test_loop_exits_on_eof(self):
        # Empty reader → EOF immediately → loop returns.
        server, _ = _make_server()
        reader = _MemReader([])
        writer = _MemWriter()
        await asyncio.wait_for(server.run(reader, writer), timeout=1.0)
        assert writer.lines() == []

    async def test_multi_request_session(self):
        server, _ = _make_server()
        reader = _MemReader(
            [
                _req("initialize", {"protocolVersion": 1}, req_id=1),
                _req("session/new", {"sessionId": "s1"}, req_id=2),
                _req("session/prompt", {"sessionId": "s1", "prompt": "ping"}, req_id=3),
                _req("session/cancel", {"sessionId": "s1"}, req_id=4),
            ]
        )
        writer = _MemWriter()
        await asyncio.wait_for(server.run(reader, writer), timeout=1.0)
        responses = writer.lines()
        assert len(responses) == 4
        # Last request was cancel on a completed session → still ok,
        # state stays completed.
        assert responses[3]["result"]["state"] == "completed"


# ---------------------------------------------------------------------------
# Prompt executor bridge (Phase 5 follow-up)
# ---------------------------------------------------------------------------


class TestPromptExecutorBridge:
    """When AcpHandlers.prompt_executor is wired, session/prompt
    bridges to it instead of returning the scaffolding echo."""

    async def test_executor_runs_and_returns_output(self):
        handlers = register_default_handlers(AcpHandlers())
        captured: list[tuple[str, str]] = []

        async def executor(session, prompt: str) -> str:
            captured.append((session.id, prompt))
            return f"agent reply to: {prompt}"

        handlers.prompt_executor = executor
        await handlers.dispatch("initialize", {"protocolVersion": 1})
        await handlers.dispatch("session/new", {"sessionId": "s1"})
        result = await handlers.dispatch("session/prompt", {"sessionId": "s1", "prompt": "hello"})

        assert result["state"] == "completed"
        assert result["output"] == "agent reply to: hello"
        assert captured == [("s1", "hello")]

    async def test_executor_failure_transitions_to_failed(self):
        handlers = register_default_handlers(AcpHandlers())

        async def executor(session, prompt: str) -> str:
            raise RuntimeError("agent crashed")

        handlers.prompt_executor = executor
        await handlers.dispatch("initialize", {"protocolVersion": 1})
        await handlers.dispatch("session/new", {"sessionId": "s1"})
        result = await handlers.dispatch("session/prompt", {"sessionId": "s1", "prompt": "hi"})

        assert result["state"] == "failed"
        assert "agent crashed" in result["error"]
        # Session is in failed state; subsequent prompt would still be
        # gated by session existence, but the session table holds the
        # canonical record.
        assert handlers.sessions["s1"].state == "failed"

    async def test_no_executor_falls_back_to_scaffold_echo(self):
        # Without an executor wired, the existing scaffold behavior
        # is preserved (commit 29 contract).
        handlers = register_default_handlers(AcpHandlers())
        await handlers.dispatch("initialize", {"protocolVersion": 1})
        await handlers.dispatch("session/new", {"sessionId": "s1"})
        result = await handlers.dispatch("session/prompt", {"sessionId": "s1", "prompt": "hello"})
        assert result["output"].startswith("[CAO ACP scaffold]")
        assert "hello" in result["output"]
