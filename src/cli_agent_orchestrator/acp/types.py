"""ACP wire types — JSON-RPC 2.0 over stdio (Phase 5 / commit 29).

The Agent Communication Protocol is JSON-RPC 2.0 with newline-delimited
JSON messages on stdin/stdout. Cursor 3, Zed Parallel Agents, and
Claude Code all speak this protocol — adopting it makes CAO a
first-class peer in those ecosystems.

Three message kinds:

  * ``AcpRequest`` — id present, method present, expects an
    ``AcpResponse`` back.
  * ``AcpResponse`` — id present, either ``result`` or ``error`` set.
  * ``AcpNotification`` — id absent. The server can push these to the
    client (session/output, session/state-change) without expecting a
    reply.

Method names use slash notation per the ACP convention (``session/new``,
``session/prompt``, etc.) rather than the dot notation A2A uses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional, Union

# JSON-RPC ids per the spec — string, integer, or null.
AcpId = Union[str, int, None]


class AcpErrorCode(IntEnum):
    """Error codes. JSON-RPC reserved range + ACP-specific application codes."""

    # JSON-RPC 2.0 reserved.
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # ACP-specific (positive codes per the spec convention).
    NOT_INITIALIZED = 100
    ALREADY_INITIALIZED = 101
    SESSION_NOT_FOUND = 102
    UNSUPPORTED_PROTOCOL_VERSION = 103


@dataclass
class AcpError:
    code: int
    message: str
    data: Optional[Any] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"code": int(self.code), "message": self.message}
        if self.data is not None:
            d["data"] = self.data
        return d


@dataclass
class AcpRequest:
    """JSON-RPC request: ``{jsonrpc, id, method, params}``.

    Differs from ``AcpNotification`` only in the presence of ``id``.
    """

    method: str
    id: AcpId
    params: dict[str, Any] = field(default_factory=dict)
    jsonrpc: str = "2.0"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AcpRequest":
        return cls(
            method=data.get("method", ""),
            id=data.get("id"),
            params=data.get("params") or {},
            jsonrpc=data.get("jsonrpc", "2.0"),
        )


@dataclass
class AcpNotification:
    """JSON-RPC notification: like ``AcpRequest`` but with no ``id``."""

    method: str
    params: dict[str, Any] = field(default_factory=dict)
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict[str, Any]:
        return {"jsonrpc": self.jsonrpc, "method": self.method, "params": self.params}


@dataclass
class AcpResponse:
    """JSON-RPC response: ``{jsonrpc, id, result}`` or ``{jsonrpc, id, error}``."""

    id: AcpId
    result: Optional[Any] = None
    error: Optional[AcpError] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jsonrpc": "2.0", "id": self.id}
        if self.error is not None:
            d["error"] = self.error.to_dict()
        else:
            d["result"] = self.result
        return d


# Type alias for any wire message (request or notification — both flow
# from client to server).
AcpMessage = Union[AcpRequest, AcpNotification]
