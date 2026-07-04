"""Managed-subprocess pytest fixtures (W1 from PR #23 follow-up roadmap).

The fixtures here spin up real ``cao-server`` subprocesses (with optional
Auth0 enforcement via an in-process JWKS HTTP server) and tear them down on
session exit. Downstream workstreams (W2 WebSocket integration smoke, W3
Playwright browser e2e, W4 MCP Apps iframe smoke) consume the same harness.

Exports live in ``cao_server.py`` and are auto-discovered via the
``pytest_plugins`` entry in ``test/conftest.py``.
"""
