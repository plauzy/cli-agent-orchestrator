"""Dedicated read-only listener for /.well-known/agent-card.json.

The Agent Card needs to be discoverable by external A2A peers, but the
main :9889 API is locked behind ``TrustedHostMiddleware`` to preserve
CAO's localhost-only security stance for arbitrary requests. The design
is a second uvicorn server bound to :9890 that hosts only the agent_card
router — no other routes, no Host restriction, read-only.

The listener is **default-off** (it only starts when ``CAO_AGENT_CARD_ENABLED``
is set) and binds **loopback (127.0.0.1) by default**, matching CAO's
localhost-only stance. Operators who explicitly want the Agent Card to be
discoverable by external A2A peers opt in with ``CAO_AGENT_CARD_HOST=0.0.0.0``
(and are responsible for the network exposure that implies).
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import uvicorn
from fastapi import FastAPI

from cli_agent_orchestrator.agent_card import router as card_router
from cli_agent_orchestrator.agent_card.signing import Signer

logger = logging.getLogger(__name__)


def build_listener_app(
    signer: Signer,
    metadata_provider: Callable[[], dict[str, Any]],
    *,
    a2a_router: Any = None,
    a2a_stream_router: Any = None,
) -> FastAPI:
    """Construct the dedicated FastAPI app served by the :9890 listener.

    Exposes ``/.well-known/agent-card.json`` and ``/.well-known/jwks.json``
    by default. When ``a2a_router`` and/or ``a2a_stream_router`` are
    supplied (Phase 5 commits 26 + 27), the A2A v1.0 JSON-RPC and
    streaming/REST endpoints are mounted alongside the discovery routes
    on the same external-facing boundary.
    """
    card_router.configure(signer, metadata_provider)
    app = FastAPI(
        title="CAO Agent Card",
        description="A2A v1.0 Agent Card + transport endpoints.",
        version="1.0.0",
        docs_url=None,  # No interactive docs on the public listener.
        redoc_url=None,
        openapi_url=None,
    )
    app.include_router(card_router.router)
    if a2a_router is not None:
        app.include_router(a2a_router)
    if a2a_stream_router is not None:
        app.include_router(a2a_stream_router)
    return app


@dataclass
class AgentCardListener:
    server: uvicorn.Server
    task: asyncio.Task[None]

    async def stop(self) -> None:
        self.server.should_exit = True
        try:
            await asyncio.wait_for(self.task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Agent Card listener did not stop within 5s")


async def start_agent_card_listener(
    signer_dir: Path,
    metadata_provider: Callable[[], dict[str, Any]],
    *,
    host: str | None = None,
    port: int = 9890,
    a2a_router: Any = None,
    a2a_stream_router: Any = None,
) -> AgentCardListener:
    """Start the :9890 uvicorn server in a background task.

    When ``a2a_router`` and/or ``a2a_stream_router`` are supplied
    (Phase 5 commits 26 + 27), the A2A v1.0 transport endpoints are
    mounted on the listener alongside the Agent Card discovery routes.

    Returns an ``AgentCardListener`` whose ``.stop()`` cleanly tears down
    the server. Failures during startup are logged and re-raised — the
    operator should know if the second listener can't bind.
    """
    bind_host = host or os.environ.get("CAO_AGENT_CARD_HOST", "127.0.0.1")
    signer = Signer(signer_dir)
    app = build_listener_app(
        signer,
        metadata_provider,
        a2a_router=a2a_router,
        a2a_stream_router=a2a_stream_router,
    )
    config = uvicorn.Config(
        app,
        host=bind_host,
        port=port,
        log_level="warning",
        # No access log — too noisy for a discovery endpoint that gets
        # polled. Errors still surface via the application logger.
        access_log=False,
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve(), name="agent-card-listener")
    logger.info("Agent Card listener starting on %s:%d", bind_host, port)
    return AgentCardListener(server=server, task=task)
