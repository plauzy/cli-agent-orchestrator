"""A2A v1.0 wire types + JSON-RPC envelope.

Phase 5 / commit 26. The A2A spec is JSON-RPC 2.0 over HTTP with task
state machine semantics. We model only what CAO needs to round-trip a
task end-to-end:

  * ``Task`` — opaque wrapper around the message thread. The state
    machine has five terminal/non-terminal states (per the A2A spec):
    ``submitted``, ``working``, ``input-required``, ``completed``,
    ``canceled``, ``failed``.
  * ``JsonRpcRequest`` / ``JsonRpcResponse`` — the canonical JSON-RPC
    2.0 envelope. We accept both string and integer ids per the spec.
  * ``A2AErrorCode`` — error codes. Negative numbers in the JSON-RPC
    reserved range (-32xxx) for protocol errors; positive task-state
    errors layered on top.

The fields here are deliberately permissive (`extra: dict[str, Any]`
on Task) so we can round-trip novel A2A extensions a peer might send
without losing them. CAO doesn't interpret extension fields itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional, Union

# JSON-RPC ids are str | int | None per the spec.
JsonRpcId = Union[str, int, None]


class TaskState(str):
    """A2A task state machine values. Strings, not an Enum, so they
    serialize directly to JSON without a converter step."""

    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"

    @classmethod
    def all(cls) -> tuple[str, ...]:
        return (
            cls.SUBMITTED,
            cls.WORKING,
            cls.INPUT_REQUIRED,
            cls.COMPLETED,
            cls.CANCELED,
            cls.FAILED,
        )

    @classmethod
    def is_terminal(cls, state: str) -> bool:
        return state in (cls.COMPLETED, cls.CANCELED, cls.FAILED)


class A2AErrorCode(IntEnum):
    """Error codes for JSON-RPC responses + A2A task semantics."""

    # JSON-RPC 2.0 reserved range.
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # A2A-specific. Per the v1.0 spec these are application-defined
    # codes outside the reserved range.
    TASK_NOT_FOUND = 1
    TASK_ALREADY_TERMINAL = 2
    UNAUTHENTICATED = 3
    UNSUPPORTED_OPERATION = 4


@dataclass
class Task:
    """A2A task. Mostly opaque to CAO — the state machine + id are
    load-bearing, the rest is round-tripped to the peer."""

    id: str
    state: str = TaskState.SUBMITTED
    messages: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    created_at: Optional[float] = None
    updated_at: Optional[float] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "state": self.state,
            "messages": self.messages,
            "metadata": self.metadata,
            "artifacts": self.artifacts,
        }
        if self.created_at is not None:
            d["created_at"] = self.created_at
        if self.updated_at is not None:
            d["updated_at"] = self.updated_at
        # Round-trip unknown fields verbatim.
        d.update(self.extra)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        known = {"id", "state", "messages", "metadata", "artifacts", "created_at", "updated_at"}
        extra = {k: v for k, v in data.items() if k not in known}
        return cls(
            id=str(data["id"]),
            state=data.get("state", TaskState.SUBMITTED),
            messages=list(data.get("messages", [])),
            metadata=dict(data.get("metadata", {})),
            artifacts=list(data.get("artifacts", [])),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            extra=extra,
        )


@dataclass
class JsonRpcRequest:
    """JSON-RPC 2.0 request envelope.

    The ``id`` field distinguishes requests (id present) from
    notifications (id missing). CAO's A2A implementation does not
    yet support notifications; missing-id requests get a
    ``INVALID_REQUEST`` response.
    """

    jsonrpc: str
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    id: JsonRpcId = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JsonRpcRequest":
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            method=data.get("method", ""),
            params=data.get("params") or {},
            id=data.get("id"),
        )


@dataclass
class JsonRpcError:
    code: int
    message: str
    data: Optional[Any] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"code": int(self.code), "message": self.message}
        if self.data is not None:
            d["data"] = self.data
        return d


@dataclass
class JsonRpcResponse:
    id: JsonRpcId
    result: Optional[Any] = None
    error: Optional[JsonRpcError] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jsonrpc": "2.0", "id": self.id}
        if self.error is not None:
            d["error"] = self.error.to_dict()
        else:
            d["result"] = self.result
        return d
