"""ACP method handlers (Phase 5 / commit 29).

The four core ACP methods CAO implements:

  * ``initialize`` — handshake. Client sends its protocol version +
    capabilities; server replies with its own. Must be the first
    message; subsequent calls fail with ``ALREADY_INITIALIZED``.

  * ``session/new`` — client requests a new session. Server allocates
    a session id and returns it. Sessions are independent agent
    contexts — analogous to A2A's task envelope.

  * ``session/prompt`` — client sends a user prompt for a given
    session id. Server processes the prompt and replies with the
    agent's response. Streaming output is delivered via
    ``session/output`` notifications between the request + the
    final response (handled at the server layer; this handler
    returns the synchronous result envelope).

  * ``session/cancel`` — client requests cancellation of an in-flight
    prompt. Server transitions the session and sends a
    ``session/state-change`` notification.

Handlers are pluggable via the ``AcpHandlers`` registry — the production
wiring will register handlers that bridge to CAO's dispatch_task.
This commit ships scaffolding handlers that round-trip the protocol
correctly so the stdio loop is testable end-to-end.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from cli_agent_orchestrator.acp.types import AcpError, AcpErrorCode

logger = logging.getLogger(__name__)


# Protocol version we implement. Increment when wire-format changes
# require coordination with clients.
SUPPORTED_PROTOCOL_VERSION = 1


HandlerFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


# Async callable that runs a prompt and returns the agent's output.
# CAO's production wiring passes a callable that bridges to
# ``dispatch_task``; tests inject a stub. When ``None``, the default
# scaffolding behavior (echo) is used.
PromptExecutor = Callable[["AcpSession", str], Awaitable[str]]


@dataclass
class AcpSession:
    """Server-side session state."""

    id: str
    state: str = "active"  # active | running | canceled | completed | failed
    created_at: float = field(default_factory=time.time)
    last_prompt: Optional[str] = None
    last_output: Optional[str] = None


@dataclass
class AcpHandlers:
    """Registry of method handlers + shared state.

    Lifetime spans one stdio connection. Holds the initialization
    handshake state and the active session table.
    """

    initialized: bool = False
    sessions: dict[str, AcpSession] = field(default_factory=dict)
    handlers: dict[str, HandlerFn] = field(default_factory=dict)
    prompt_executor: Optional[PromptExecutor] = None

    def register(self, method: str, handler: HandlerFn) -> None:
        self.handlers[method] = handler

    async def dispatch(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Look up the handler and invoke it. Raises HandlerError on failure."""
        # initialize must run first (special-cased here so handler
        # implementations don't all need to check).
        if method != "initialize" and not self.initialized:
            raise HandlerError(AcpErrorCode.NOT_INITIALIZED, "server has not been initialized")
        fn = self.handlers.get(method)
        if fn is None:
            raise HandlerError(AcpErrorCode.METHOD_NOT_FOUND, f"unknown method {method!r}")
        return await fn(params)


class HandlerError(Exception):
    """Raised by handlers to signal an ACP error response."""

    def __init__(self, code: AcpErrorCode | int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = int(code)
        self.message = message
        self.data = data

    def to_acp_error(self) -> AcpError:
        return AcpError(code=self.code, message=self.message, data=self.data)


# ---------------------------------------------------------------------------
# Default handler implementations
# ---------------------------------------------------------------------------


def _make_initialize(handlers: AcpHandlers) -> HandlerFn:
    async def initialize(params: dict[str, Any]) -> dict[str, Any]:
        if handlers.initialized:
            raise HandlerError(
                AcpErrorCode.ALREADY_INITIALIZED, "initialize may only be called once"
            )
        client_version = params.get("protocolVersion")
        if not isinstance(client_version, int):
            raise HandlerError(AcpErrorCode.INVALID_PARAMS, "protocolVersion (int) is required")
        if client_version > SUPPORTED_PROTOCOL_VERSION:
            raise HandlerError(
                AcpErrorCode.UNSUPPORTED_PROTOCOL_VERSION,
                f"server supports protocolVersion {SUPPORTED_PROTOCOL_VERSION}, "
                f"client requested {client_version}",
            )
        handlers.initialized = True
        return {
            "protocolVersion": SUPPORTED_PROTOCOL_VERSION,
            "serverInfo": {
                "name": "cli-agent-orchestrator",
                "version": "2.5.0a4",
            },
            "capabilities": {
                "session": {
                    "new": True,
                    "prompt": True,
                    "cancel": True,
                },
            },
        }

    return initialize


def _make_session_new(handlers: AcpHandlers) -> HandlerFn:
    async def session_new(params: dict[str, Any]) -> dict[str, Any]:
        session_id = params.get("sessionId") or str(uuid.uuid4())
        if not isinstance(session_id, str) or not session_id:
            raise HandlerError(AcpErrorCode.INVALID_PARAMS, "sessionId must be a non-empty string")
        if session_id in handlers.sessions:
            # Idempotent: re-issuing returns the existing session.
            return {"sessionId": session_id, "state": handlers.sessions[session_id].state}
        handlers.sessions[session_id] = AcpSession(id=session_id)
        return {"sessionId": session_id, "state": "active"}

    return session_new


def _make_session_prompt(handlers: AcpHandlers) -> HandlerFn:
    async def session_prompt(params: dict[str, Any]) -> dict[str, Any]:
        session_id = params.get("sessionId")
        if not isinstance(session_id, str) or not session_id:
            raise HandlerError(AcpErrorCode.INVALID_PARAMS, "sessionId is required")
        session = handlers.sessions.get(session_id)
        if session is None:
            raise HandlerError(AcpErrorCode.SESSION_NOT_FOUND, f"session {session_id!r} not found")
        prompt = params.get("prompt")
        if not isinstance(prompt, str):
            raise HandlerError(AcpErrorCode.INVALID_PARAMS, "prompt (string) is required")

        session.state = "running"
        session.last_prompt = prompt

        if handlers.prompt_executor is not None:
            # Bridge to a real executor (dispatch_task in production).
            try:
                output = await handlers.prompt_executor(session, prompt)
                session.last_output = output
                session.state = "completed"
                return {
                    "sessionId": session_id,
                    "state": "completed",
                    "output": output,
                }
            except Exception as exc:
                logger.warning(
                    "ACP prompt executor failed for session=%s", session_id, exc_info=True
                )
                session.state = "failed"
                return {
                    "sessionId": session_id,
                    "state": "failed",
                    "error": str(exc),
                }

        # Scaffolding: echo a placeholder when no executor is wired.
        # Useful for round-tripping the protocol against an ACP host
        # without spinning up the full CAO dispatch stack.
        session.state = "completed"
        session.last_output = f"[CAO ACP scaffold] received: {prompt}"
        return {
            "sessionId": session_id,
            "state": "completed",
            "output": session.last_output,
        }

    return session_prompt


def _make_session_cancel(handlers: AcpHandlers) -> HandlerFn:
    async def session_cancel(params: dict[str, Any]) -> dict[str, Any]:
        session_id = params.get("sessionId")
        if not isinstance(session_id, str) or not session_id:
            raise HandlerError(AcpErrorCode.INVALID_PARAMS, "sessionId is required")
        session = handlers.sessions.get(session_id)
        if session is None:
            raise HandlerError(AcpErrorCode.SESSION_NOT_FOUND, f"session {session_id!r} not found")
        if session.state in ("completed", "canceled", "failed"):
            return {"sessionId": session_id, "state": session.state}
        session.state = "canceled"
        return {"sessionId": session_id, "state": "canceled"}

    return session_cancel


def register_default_handlers(handlers: AcpHandlers) -> AcpHandlers:
    """Wire the four core method handlers onto the registry."""
    handlers.register("initialize", _make_initialize(handlers))
    handlers.register("session/new", _make_session_new(handlers))
    handlers.register("session/prompt", _make_session_prompt(handlers))
    handlers.register("session/cancel", _make_session_cancel(handlers))
    return handlers
