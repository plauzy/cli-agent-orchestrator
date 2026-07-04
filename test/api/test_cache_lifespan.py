"""Tests for the Phase 5 three-layer cache lifespan integration.

Verifies that the FastAPI lifespan instantiates and exposes the
ThreeLayerCache at ``app.state.cache``, the L2 scheduler at
``app.state.cache_l2``, that ``CAO_CACHE_DISABLED=true`` opts out,
and that ``GET /cache/stats`` reports correctly in both modes.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cli_agent_orchestrator.api.main import app, lifespan
from cli_agent_orchestrator.cache import L2KeepAliveScheduler, ThreeLayerCache
from cli_agent_orchestrator.plugins import PluginRegistry


async def _fake_flow_daemon() -> None:
    return None


def _patch_lifespan_io():
    """Returns a list of context managers patching lifespan I/O so
    tests can run without touching the real DB. The event-driven
    background tasks (status_monitor/log_writer/inbox_service) start and
    are cancelled cleanly on lifespan exit, so they need no patching."""
    return [
        patch("cli_agent_orchestrator.api.main.setup_logging"),
        patch("cli_agent_orchestrator.api.main.init_db"),
        patch("cli_agent_orchestrator.api.main.cleanup_old_data"),
        patch("cli_agent_orchestrator.api.main.flow_daemon", _fake_flow_daemon),
    ]


class TestCacheLifespan:
    @pytest.mark.asyncio
    async def test_lifespan_initializes_cache_by_default(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ):
        monkeypatch.delenv("CAO_CACHE_DISABLED", raising=False)
        # Redirect cache file to tmp.
        monkeypatch.setattr("cli_agent_orchestrator.api.main.CACHE_DB_FILE", tmp_path / "cache.db")

        p = _patch_lifespan_io()
        with p[0], p[1], p[2], p[3]:
            async with lifespan(app):
                cache = getattr(app.state, "cache", None)
                l2 = getattr(app.state, "cache_l2", None)
                assert isinstance(cache, ThreeLayerCache)
                assert isinstance(l2, L2KeepAliveScheduler)

    @pytest.mark.asyncio
    async def test_lifespan_skips_cache_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ):
        monkeypatch.setenv("CAO_CACHE_DISABLED", "true")
        if hasattr(app.state, "cache"):
            delattr(app.state, "cache")
        if hasattr(app.state, "cache_l2"):
            delattr(app.state, "cache_l2")

        p = _patch_lifespan_io()
        with p[0], p[1], p[2], p[3]:
            async with lifespan(app):
                assert not hasattr(app.state, "cache")


class TestCacheStatsEndpoint:
    def test_returns_stats_when_cache_present(self, client, tmp_path):
        from cli_agent_orchestrator.cache import L1Cache, L3Cache

        cache = ThreeLayerCache(l1=L1Cache(max_size=10), l3=L3Cache(tmp_path / "c.db"))
        app.state.cache = cache
        try:
            resp = client.get("/cache/stats")
            assert resp.status_code == 200
            body = resp.json()
            assert body["available"] is True
            assert "cache" in body
            assert "l1_hits" in body["cache"]
        finally:
            del app.state.cache

    def test_returns_unavailable_when_no_cache(self, client):
        if hasattr(app.state, "cache"):
            del app.state.cache
        resp = client.get("/cache/stats")
        assert resp.status_code == 200
        assert resp.json() == {"available": False}

    def test_includes_l2_stats_when_present(self, client, tmp_path):
        from cli_agent_orchestrator.cache import L1Cache, L3Cache

        l2 = L2KeepAliveScheduler()
        l2.register("k1", "prefix")
        cache = ThreeLayerCache(l1=L1Cache(max_size=10), l3=L3Cache(tmp_path / "c.db"), l2=l2)
        app.state.cache = cache
        app.state.cache_l2 = l2
        try:
            resp = client.get("/cache/stats")
            body = resp.json()
            assert "l2" in body
            assert body["l2"]["tracked"] == 1
        finally:
            del app.state.cache
            del app.state.cache_l2
