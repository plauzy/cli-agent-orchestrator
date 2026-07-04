"""ACP (Agent Communication Protocol) server scaffolding (Phase 5 / commit 29).

ACP is the protocol Cursor 3, Zed Parallel Agents, and Claude Code use
to talk to external agent backends over stdio. Wire format is JSON-RPC
2.0 with newline-delimited JSON messages on stdin/stdout (similar to
the Language Server Protocol). This commit ships the protocol surface
+ a stdio dispatcher; full plumbing into CAO's dispatch_task lands as
a follow-up.

Exports:
  * ``AcpServer`` — async stdio server with pluggable method handlers
  * ``AcpMessage`` / ``AcpResponse`` / ``AcpNotification`` — wire types
  * ``register_default_handlers`` — wires the four core methods
    (initialize, session/new, session/prompt, session/cancel)
"""

from cli_agent_orchestrator.acp.handlers import (
    AcpHandlers,
    AcpSession,
    PromptExecutor,
    register_default_handlers,
)
from cli_agent_orchestrator.acp.server import AcpServer
from cli_agent_orchestrator.acp.types import (
    AcpError,
    AcpErrorCode,
    AcpMessage,
    AcpNotification,
    AcpRequest,
    AcpResponse,
)

__all__ = [
    "AcpError",
    "AcpErrorCode",
    "AcpHandlers",
    "AcpMessage",
    "AcpNotification",
    "AcpRequest",
    "AcpResponse",
    "AcpServer",
    "AcpSession",
    "PromptExecutor",
    "register_default_handlers",
]
