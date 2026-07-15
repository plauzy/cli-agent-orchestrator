"""Async WebSocket helper for the WebSocket integration smoke tests.

Wraps :func:`websockets.asyncio.client.connect` to:

- Add the ``cao.bearer.<token>`` subprotocol when a token is supplied
  (browsers can't add custom headers to the WS handshake, so the JWT
  travels in the ``Sec-WebSocket-Protocol`` slot).
- Pin a sane default ``open_timeout`` so a stuck handshake fails fast
  rather than blocking the whole e2e run.
"""

from __future__ import annotations

from typing import Optional

from websockets.asyncio.client import ClientConnection, connect


def ws_connect(
    url: str,
    *,
    token: Optional[str] = None,
    open_timeout: float = 5.0,
) -> "connect":
    """Open a WebSocket against the cao server, optionally with a JWT.

    Returns the ``websockets`` connect context manager so callers use
    ``async with``::

        async with ws_connect(url, token=jwt) as ws:
            data = await ws.recv()
            await ws.send(json.dumps({"type": "input", "data": "ls\\n"}))

    The yielded object is a :class:`websockets.asyncio.client.ClientConnection`,
    so tests can inspect ``close_code`` / ``subprotocol`` and call
    ``recv()`` / ``send()`` directly.
    """
    # The server accepts with "cao.bearer" (JWT stripped for security); include
    # it so websockets' subprotocol negotiation accepts the echoed response.
    subprotocols = [f"cao.bearer.{token}", "cao.bearer"] if token else None
    return connect(
        url,
        subprotocols=subprotocols,  # type: ignore[arg-type]
        open_timeout=open_timeout,
    )


__all__ = ["ws_connect", "ClientConnection"]
