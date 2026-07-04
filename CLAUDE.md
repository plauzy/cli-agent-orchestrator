# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

CLI Agent Orchestrator (CAO) — Python orchestrator that runs multiple AI coding-CLI agents (Kiro, Claude Code, Codex, Gemini, Kimi, Copilot, Q, OpenCode) inside isolated tmux sessions, with a FastAPI server, MCP server, scheduled flows, and a React/Vite web UI. Package: `cli_agent_orchestrator` (src layout). Python ≥3.10. Dependency manager: `uv`.

## Common commands

```bash
# Install / sync deps (creates .venv)
uv sync

# Run the CLI / servers locally
uv run cao --help
uv run cao-server          # FastAPI on :9889 (also serves bundled web UI)
uv run cao-mcp-server      # MCP entry point
uv run cao-acp             # ACP entry point

# Tests — pyproject sets `addopts = -m 'not e2e'`, so plain pytest skips e2e
uv run pytest                                  # unit + integration, no e2e
uv run pytest test/path/to/test_x.py -v        # single file
uv run pytest test/x.py::TestClass::test_y -v  # single test
uv run pytest -m e2e test/e2e/ -v              # e2e (needs cao-server, tmux, auth'd CLIs)
uv run pytest -m integration -v                # integration only
uv run pytest -n auto                          # parallel (pytest-xdist)
uv run pytest --cov=src --cov-report=term-missing

# Quality (CI runs all three)
uv run black src/ test/
uv run isort src/ test/
uv run mypy src/                              # strict mode per pyproject

# Web UI (React + Vite + Tailwind, in web/)
cd web && npm install && npm run dev          # dev server :5173, proxies to :9889
cd web && npm run build                       # outputs to src/cli_agent_orchestrator/web_ui/ (bundled into wheel)
cd web && npm run test                        # vitest
```

`pytest.ini_options.addopts` includes `--cov=src` — every pytest run produces a coverage report; pass `--no-cov` to suppress.

## Architecture

The system is layered: **Entry points → FastAPI HTTP API → Services → Clients/Providers → tmux + SQLite + external CLIs**. There is no in-process agent loop — agents are real CLI processes running inside tmux panes that CAO drives via `send-keys` / paste-buffer and reads back from the pane's log file.

### Entry points (all converge on the HTTP API)
- `cli/` — `cao` Click CLI (`launch`, `session`, `flow`, `install`, `skills`, `shutdown`, ...).
- `mcp_server/server.py` — exposes `handoff`, `assign`, `send_message` MCP tools that agents call from inside their own terminals.
- `api/main.py` — `cao-server`, the FastAPI app on :9889. The CLI and MCP server both speak to it; nothing bypasses it.
- `acp/server.py` — separate ACP entry point.

### Services layer (`services/`)
Business logic, callable from any entry point:
- `terminal_service` — create/get/send-input/get-output/delete; the contract for talking to a tmux pane.
- `session_service` — list/get/delete groups of terminals.
- `inbox_service` — terminal-to-terminal messaging with a watchdog that observes provider log files. Messages to a busy receiver stay PENDING until the watchdog detects an IDLE pattern, then flush.
- `flow_service` — APScheduler-driven cron flows (markdown frontmatter + optional shell script for conditional execution / template vars).
- `sse_bus`, `plugin_dispatch`, `cleanup_service`, `budget_service`, `settings_service`, `zellij_bridge`.

### Clients (`clients/`)
- `tmux.py` — wraps libtmux; sets `CAO_TERMINAL_ID` env on session create; uses bracketed paste (`send_keys_via_paste`) for multi-line input.
- `database.py` — SQLAlchemy/SQLite. Two main tables: `terminals` and `inbox_messages`.

### Providers (`providers/`)
One module per CLI tool — `kiro_cli` (default), `claude_code`, `codex`, `q_cli`, `gemini_cli`, `kimi_cli`, `copilot_cli`, `opencode_cli`. Each subclasses `base.Provider` and implements:
- `initialize()` — wait for shell, launch the CLI, wait for IDLE.
- Regex-based status detection (IDLE / PROCESSING / COMPLETED / ERROR) by tailing the pane's log file — these patterns are fragile when CLI versions update; treat them as the integration surface.
- Trust/confirmation-prompt handling and the prompt characters that mark "ready for input" (e.g. `❯` for Claude Code, `›` + `•` for Codex).
- Tool-restriction translation: `role` / `allowedTools` from the agent profile → that provider's native enforcement flags. 5 of 8 providers support hard enforcement; the others are best-effort.

`providers/manager.py` maps `terminal_id → provider` and resolves the cross-provider rule: a worker uses its agent profile's `provider:` frontmatter if set, else inherits the parent terminal's provider; `cao launch --provider` is an explicit override.

### Models / Agent profiles
- `models/` — Pydantic data classes: `Terminal`, `TerminalStatus`, `Session`, `InboxMessage`, `Flow`, `AgentProfile`.
- `agent_store/` — built-in agent profiles (`code_supervisor.md`, `developer.md`, `reviewer.md`) installed via `cao install <name>`; these are markdown with YAML frontmatter (`name`, `role`, `description`, optional `provider`, `allowedTools`).

### Three orchestration patterns (the user-facing concept)
- **Handoff** — synchronous: spawn terminal, send message, wait for COMPLETED, return last output, exit the worker.
- **Assign** — async: spawn terminal, send message with callback instructions, return terminal id immediately; worker reports back via `send_message` when done.
- **Send Message** — deliver a message to an existing terminal's inbox; queued and flushed when receiver is IDLE.

All three accept an optional `working_directory` (gated by `CAO_ENABLE_WORKING_DIRECTORY=true`); paths go through `realpath` and a deny-list of system dirs.

Smallest invocation per pattern (full worked examples in `examples/`):

```bash
# Handoff — sync, blocks until COMPLETED, returns output
cao launch --agents code_supervisor --headless --yolo \
  --session-name handoff-demo "Review src/foo.py and report issues."
```

```bash
# Assign — async, returns immediately; worker calls send_message when done
cao launch --agents code_supervisor --headless --async --yolo \
  --session-name assign-demo "Audit each file in src/ in parallel."
```

```bash
# Send Message — message an existing terminal's inbox via the HTTP API
curl -X POST "http://localhost:9889/terminals/<id>/inbox/messages" \
  --data-urlencode "sender_id=<other-id>" \
  --data-urlencode "message=please re-run with verbose=true"
```

### v2.5 alpha subsystems (additive, opt-in or shadow-mode)
- `telemetry/` — OpenTelemetry GenAI v1.37+ semantic conventions; gated on `OTEL_SDK_DISABLED=false`.
- `persistence/` — append-only WAL (daily-rotated JSONL + fsync) plus a SQLite materialized index rebuilt idempotently on boot via `replay.py`.
- `agent_card/` — A2A v1.0 Agent Card with Ed25519/JWS signing; served on a separate :9890 uvicorn at `/.well-known/{agent-card,jwks}.json`.
- `ext_apps/` — SEP-1865 MCP Apps widget (topology view).
- `plugins/builtin/` — `otel_sidecar` and `sse_event_publisher`; plugins are observer-only and discovered via the `cao.plugins` entry-point group at server startup.

### Build artifacts shipped in the wheel
`pyproject.toml` `[tool.hatch.build]` force-includes `src/cli_agent_orchestrator/web_ui/**` (built frontend), `persistence/*.sql`, `ext_apps/static/**`, and zellij assets — the wheel is self-contained, so `uv tool install .` ships the UI and SQL DDL.

## Conventions / gotchas

- Session names are auto-prefixed with `cao-`. Reference the prefixed form (`cao-foo`) in `cao session send` and `cao shutdown`, but not in `--session-name foo` on `cao launch`.
- The HTTP server is **localhost-only** by design — Host header is validated against `localhost`/`127.0.0.1` to block DNS rebinding; the WebSocket terminal endpoint refuses non-loopback peers. Don't add network-exposed routes without auth.
- Provider status detection is regex on log files. When tests fail after a provider CLI upgrade, regenerate fixtures: `uv run python test/providers/fixtures/generate_fixtures.py` (Q CLI; pattern is similar for others).
- `mypy` is in `strict` mode for `src/` — new code must be fully typed.
- Black/isort line length is 100 (not 88).
- `addopts` excludes e2e by default; CI matrices run unit tests on Python 3.10/3.11/3.12. Provider-specific workflows are path-triggered (see `.github/workflows/test-*-provider.yml`).
- The `.claude/hooks/session-start.sh` hook only runs on Claude Code on the web (`CLAUDE_CODE_REMOTE=true`); locally you manage your own env.

## Reference docs

- `CODEBASE.md` — directory map and data-flow diagrams (terminal create, inbox, handoff).
- `DEVELOPMENT.md` — full workflow, CI matrix, troubleshooting.
- `docs/api.md`, `docs/v2-5-architecture.md`, `docs/tool-restrictions.md`, `docs/agent-profile.md`, `docs/working-directory.md`, `docs/skills.md`, `docs/plugins.md`.
- `skills/cao-provider/SKILL.md` — playbook for adding a new provider (20 lessons learnt).
- `test/README.md` — test-suite layout.
