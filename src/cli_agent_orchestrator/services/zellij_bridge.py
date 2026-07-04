"""CAO v2.5 Phase 2 — Zellij hook bridge.

Subscribes to the in-process SSE bus (``services.sse_bus.get_bus()``)
and pushes a small aggregated snapshot to the ``zellaude`` Zellij
status-bar plugin via ``zellij pipe --name zellaude``.

The plugin is intentionally dumb (see ``zellij/src/lib.rs``); this
module owns all rolling state:

  * active session count (from ``session.created`` / ``session.killed``)
  * kill-switched task classes (from ``asi.mitigation`` events with
    ``severity == "kill"``)
  * latest ASI score per task class with a green / yellow / red band
  * 60s rolling cache hit-rate, polled from ``/cache/stats`` every 5s

Failures are best-effort: if the ``zellij`` binary is missing or no
zellij session is running we log once at WARNING and keep consuming
the bus, so production traffic is never blocked by a missing TUI.

Started in the FastAPI lifespan when ``CAO_ZELLIJ_ENABLED=true``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Optional

import requests  # type: ignore[import-untyped]

from cli_agent_orchestrator.services.sse_bus import SSEBus

logger = logging.getLogger(__name__)


# How often we may push a snapshot to the plugin. The plugin re-renders
# on every pipe message, so we throttle to keep the status bar from
# flickering under bursty event traffic.
_PIPE_MIN_INTERVAL_SECONDS = 1.0

# Cache-stats poll interval and rolling-window size.
_CACHE_POLL_INTERVAL_SECONDS = 5.0
_CACHE_WINDOW_SECONDS = 60.0

# ASI banding thresholds (mirrors the plugin's render() colors).
_ASI_BAND_GREEN_MIN = 0.7
_ASI_BAND_YELLOW_MIN = 0.4

_DEFAULT_PLUGIN_URL = "file:~/.config/zellij/plugins/zellaude.wasm"
_DEFAULT_API_BASE = "http://127.0.0.1:9889"


def _band(score: float) -> str:
    if score >= _ASI_BAND_GREEN_MIN:
        return "green"
    if score >= _ASI_BAND_YELLOW_MIN:
        return "yellow"
    return "red"


@dataclass
class _AsiSnapshot:
    task_class: str
    score: float
    band: str

    def as_dict(self) -> dict[str, Any]:
        return {"task_class": self.task_class, "score": self.score, "band": self.band}


@dataclass
class _State:
    sessions: set[str] = field(default_factory=set)
    kill_switched: set[str] = field(default_factory=set)
    asi: Optional[_AsiSnapshot] = None
    cache_window: Deque[tuple[float, int, int]] = field(default_factory=deque)
    cache_hit_rate_60s: Optional[float] = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "sessions": len(self.sessions),
            "kill_switched": sorted(self.kill_switched),
            "cache_hit_rate_60s": self.cache_hit_rate_60s,
            "asi": self.asi.as_dict() if self.asi is not None else None,
        }


class ZellijBridge:
    """SSE-bus → ``zellij pipe`` aggregator for the ``zellaude`` plugin."""

    def __init__(
        self,
        bus: SSEBus,
        *,
        plugin_url: str = _DEFAULT_PLUGIN_URL,
        api_base: Optional[str] = None,
        pipe_name: str = "zellaude",
    ) -> None:
        self._bus = bus
        self._plugin_url = os.path.expandvars(os.path.expanduser(plugin_url))
        self._api_base = api_base or os.environ.get("CAO_API_URL", _DEFAULT_API_BASE)
        self._pipe_name = pipe_name
        self._state = _State()
        self._task: Optional[asyncio.Task[None]] = None
        self._cache_task: Optional[asyncio.Task[None]] = None
        self._last_pipe_at = 0.0
        self._zellij_disabled = False

    async def start(self) -> None:
        """Spawn the subscribe + cache-poll background tasks."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run_subscribe(), name="zellij-bridge-subscribe")
        self._cache_task = asyncio.create_task(self._run_cache_poll(), name="zellij-bridge-cache")
        logger.info("Zellij bridge started (plugin=%s)", self._plugin_url)

    async def stop(self) -> None:
        """Cancel and await both background tasks."""
        for task in (self._task, self._cache_task):
            if task is not None and not task.done():
                task.cancel()
        for task in (self._task, self._cache_task):
            if task is not None:
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass
        self._task = None
        self._cache_task = None
        logger.info("Zellij bridge stopped")

    # ------------------------------------------------------------------
    # State derivation

    def _apply(self, event: dict[str, Any]) -> None:
        kind = event.get("type")
        if kind == "session.created":
            name = event.get("session_name")
            if isinstance(name, str):
                self._state.sessions.add(name)
        elif kind == "session.killed":
            name = event.get("session_name")
            if isinstance(name, str):
                self._state.sessions.discard(name)
        elif kind == "asi.mitigation":
            task_class = event.get("task_class")
            score = event.get("overall")
            severity = event.get("severity")
            if isinstance(task_class, str) and isinstance(score, (int, float)):
                self._state.asi = _AsiSnapshot(
                    task_class=task_class,
                    score=float(score),
                    band=_band(float(score)),
                )
            if severity == "kill" and isinstance(task_class, str):
                self._state.kill_switched.add(task_class)
            elif severity == "recover" and isinstance(task_class, str):
                self._state.kill_switched.discard(task_class)

    # ------------------------------------------------------------------
    # Background loops

    async def _run_subscribe(self) -> None:
        try:
            async for event in self._bus.subscribe():
                self._apply(event)
                now = time.monotonic()
                if now - self._last_pipe_at >= _PIPE_MIN_INTERVAL_SECONDS:
                    self._last_pipe_at = now
                    await self._pipe_snapshot()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — bridge must never crash the lifespan
            logger.exception("Zellij bridge subscribe loop terminated unexpectedly")

    async def _run_cache_poll(self) -> None:
        while True:
            try:
                await self._poll_cache_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.debug("cache poll iteration failed", exc_info=True)
            try:
                await asyncio.sleep(_CACHE_POLL_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                raise

    async def _poll_cache_once(self) -> None:
        url = f"{self._api_base.rstrip('/')}/cache/stats"
        try:
            payload = await asyncio.to_thread(self._fetch_cache_stats, url)
        except Exception:  # noqa: BLE001
            return
        if not payload:
            return
        cache = payload.get("cache") or {}
        hits = int(cache.get("l1_hits", 0)) + int(cache.get("l3_hits", 0))
        misses = int(cache.get("misses", 0))
        now = time.monotonic()
        window = self._state.cache_window
        window.append((now, hits, misses))
        cutoff = now - _CACHE_WINDOW_SECONDS
        while window and window[0][0] < cutoff:
            window.popleft()
        if len(window) >= 2:
            first_ts, first_hits, first_misses = window[0]
            _, last_hits, last_misses = window[-1]
            d_hits = max(0, last_hits - first_hits)
            d_misses = max(0, last_misses - first_misses)
            total = d_hits + d_misses
            self._state.cache_hit_rate_60s = (d_hits / total) if total > 0 else None

    @staticmethod
    def _fetch_cache_stats(url: str) -> Optional[dict[str, Any]]:
        try:
            response = requests.get(url, timeout=2.0)
        except requests.RequestException:
            return None
        if response.status_code != 200:
            return None
        try:
            data = response.json()
            assert isinstance(data, dict)
            return data
        except (ValueError, AssertionError):
            return None

    # ------------------------------------------------------------------
    # Plugin pipe

    async def _pipe_snapshot(self) -> None:
        if self._zellij_disabled:
            return
        payload = json.dumps(self._state.snapshot()).encode("utf-8")
        try:
            proc = await asyncio.create_subprocess_exec(
                "zellij",
                "pipe",
                "--name",
                self._pipe_name,
                "--plugin",
                self._plugin_url,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except FileNotFoundError:
            logger.warning(
                "Zellij binary not found; disabling pipe (set CAO_ZELLIJ_ENABLED=false to silence)"
            )
            self._zellij_disabled = True
            return
        except Exception:  # noqa: BLE001
            logger.warning("Zellij bridge could not spawn `zellij pipe`", exc_info=True)
            self._zellij_disabled = True
            return
        assert proc.stdin is not None
        try:
            proc.stdin.write(payload)
            await proc.stdin.drain()
            proc.stdin.close()
        except (BrokenPipeError, ConnectionResetError):
            pass
        rc = await proc.wait()
        if rc != 0:
            # Most likely "no zellij session running". Soft-disable so
            # we don't spin the subprocess on every event.
            logger.warning("Zellij pipe returned exit %d; suspending bridge until restart", rc)
            self._zellij_disabled = True
