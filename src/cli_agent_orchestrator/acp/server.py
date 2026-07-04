"""ACP stdio server (Phase 5 / commit 29).

Async loop that reads newline-delimited JSON requests from a reader,
dispatches them to ``AcpHandlers``, and writes responses to a writer.
The default reader/writer pair is stdin/stdout (the production
deployment) but tests inject in-memory streams to exercise the loop
end to end.

The loop is intentionally minimal: one message in → one message out.
Notifications (server → client) are emitted via the writer directly
by handlers that need them (commit 30 wires session/output streaming
to dispatch_task).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Protocol

from cli_agent_orchestrator.acp.handlers import AcpHandlers, HandlerError
from cli_agent_orchestrator.acp.types import (
    AcpError,
    AcpErrorCode,
    AcpRequest,
    AcpResponse,
)

logger = logging.getLogger(__name__)


class AsyncByteReader(Protocol):
    """Minimal async reader contract — readline() returning bytes."""

    async def readline(self) -> bytes: ...


class AsyncByteWriter(Protocol):
    """Minimal async writer contract — write + drain."""

    def write(self, data: bytes) -> None: ...

    async def drain(self) -> None: ...


@dataclass
class AcpServer:
    """Runs the ACP message loop until EOF or stop().

    Usage:

        from cli_agent_orchestrator.acp import (
            AcpHandlers,
            AcpServer,
            register_default_handlers,
        )

        handlers = register_default_handlers(AcpHandlers())
        server = AcpServer(handlers=handlers)
        await server.run(reader, writer)
    """

    handlers: AcpHandlers
    _stop: asyncio.Event = field(default_factory=asyncio.Event)

    async def run(self, reader: AsyncByteReader, writer: AsyncByteWriter) -> None:
        """Drive the loop until reader hits EOF or stop() is called."""
        while not self._stop.is_set():
            line = await reader.readline()
            if not line:
                # EOF.
                return
            await self._handle_line(line, writer)

    def stop(self) -> None:
        self._stop.set()

    async def _handle_line(self, line: bytes, writer: AsyncByteWriter) -> None:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            await self._write(
                writer,
                AcpResponse(id=None, error=AcpError(int(AcpErrorCode.PARSE_ERROR), str(exc))),
            )
            return

        if not isinstance(payload, dict):
            await self._write(
                writer,
                AcpResponse(
                    id=None,
                    error=AcpError(
                        int(AcpErrorCode.INVALID_REQUEST),
                        "request must be a JSON object",
                    ),
                ),
            )
            return

        # Notifications have no id and we don't reply to them. ACP
        # accepts them but CAO doesn't have any client→server
        # notification methods yet, so they're a no-op log entry.
        if "id" not in payload:
            logger.debug("ACP notification ignored: method=%s", payload.get("method"))
            return

        request = AcpRequest.from_dict(payload)
        if request.jsonrpc != "2.0":
            await self._write(
                writer,
                AcpResponse(
                    id=request.id,
                    error=AcpError(int(AcpErrorCode.INVALID_REQUEST), "jsonrpc must be '2.0'"),
                ),
            )
            return
        if not request.method:
            await self._write(
                writer,
                AcpResponse(
                    id=request.id,
                    error=AcpError(int(AcpErrorCode.INVALID_REQUEST), "method is required"),
                ),
            )
            return

        try:
            result = await self.handlers.dispatch(request.method, request.params)
            await self._write(writer, AcpResponse(id=request.id, result=result))
        except HandlerError as exc:
            await self._write(writer, AcpResponse(id=request.id, error=exc.to_acp_error()))
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("ACP handler crashed: method=%s", request.method)
            await self._write(
                writer,
                AcpResponse(
                    id=request.id,
                    error=AcpError(int(AcpErrorCode.INTERNAL_ERROR), f"internal error: {exc}"),
                ),
            )

    @staticmethod
    async def _write(writer: AsyncByteWriter, response: AcpResponse) -> None:
        line = json.dumps(response.to_dict()).encode("utf-8") + b"\n"
        writer.write(line)
        await writer.drain()


# ---------------------------------------------------------------------------
# stdio entrypoint (production wiring)
# ---------------------------------------------------------------------------


async def _run_stdio_server() -> None:  # pragma: no cover - exercised manually
    """Bind the server to stdin/stdout and run until EOF.

    Used by the ``cao-acp`` CLI entry point that an ACP host (Cursor,
    Zed, Claude Code) launches as a subprocess.
    """
    import sys

    from cli_agent_orchestrator.acp.handlers import register_default_handlers

    handlers = register_default_handlers(AcpHandlers())
    server = AcpServer(handlers=handlers)

    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    transport, _ = await loop.connect_write_pipe(asyncio.streams.FlowControlMixin, sys.stdout)
    writer = asyncio.StreamWriter(transport, protocol, reader, loop)

    try:
        await server.run(reader, writer)
    finally:
        writer.close()


def main() -> None:  # pragma: no cover - CLI entry point
    """Synchronous wrapper for the ``cao-acp`` console script."""
    asyncio.run(_run_stdio_server())
