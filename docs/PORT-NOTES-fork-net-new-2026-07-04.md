# Port Notes — Net-New Subsystems from `plauzy/cao` → upstream

| Field | Value |
|---|---|
| **Created** | 2026-07-04 |
| **Source (fork)** | `plauzy/cao` @ `e84854f9207877c6b5622efbc5fbf5bccb38b607` (version `2.5.0` alpha line) |
| **Target (upstream)** | `cli-agent-orchestrator` @ `4dc8bf7` (version `2.2.0`, awslabs-tracking) |
| **Branch** | `feat/port-fork-net-new-subsystems` |
| **Method** | Content-manifest diff (shallow clones, no shared git history); clean-add subsystems + minimal additive reconciliation. `diff` unavailable in sandbox → MD5 manifests. |

This branch applies the **net-new work** the fork built independently, onto the up-to-date open-source line, **without clobbering** upstream's independently-evolved MCP Apps, `ConfigService`, workflow engine, or provider set.

---

## 1. What was applied (verified)

### 1.1 Net-new subsystems — landed as clean adds (257 files)

All import cleanly against upstream's core; **52/52 ported modules import**, and upstream core (`api.main`, `mcp_server.server`, `cli.main`, `plugins.builtin.mcp_apps`, `services.config_service`) **still imports** — confirming no clobber.

| Subsystem | Package | Notes |
|---|---|---|
| **A2A protocol** | `a2a/` (`rpc`, `stream`, `store`, `types`) | JSON-RPC + SSE agent-to-agent endpoint |
| **Agent Card** | `agent_card/` (`builder`, `listener`, `router`, `signing`) | Signed A2A Agent Card + OAuth PRM listener |
| **ACP** | `acp/` (`server`, `handlers`, `types`) | Zed/Cursor editor↔agent Agent Client Protocol (adds `cao-acp` script) |
| **AG-UI** | `services/agui_stream.py` | AG-UI event mapping (endpoint wiring deferred — see §3) |
| **Observability (Deacon ASI)** | `observability/` (`asi_evaluator`, `experiments`, `mitigations`, `phantom_state`, `span_consumer`) | ASI integrity evaluator + kill-switch |
| **Telemetry (OTel)** | `telemetry/` (`otel`, `semconv`, `spans`, `context`) | GenAI OTel scaffolding + W3C traceparent |
| **Orchestration** | `orchestration/` (`dag`, `dispatch`, `swarm`, `polecat`, `hybrid_cluster`, `topology_router`) | TaskDAG + AdaptOrch topology router + Polecat swarm |
| **Persistence** | `persistence/` (`wal_writer`, `replay`, `materialized_index`, `schema.sql`) | WAL (shadow mode) + replay |
| **Refinery (policy)** | `refinery/` (`cedar_policy`, `policy`, `rule_of_two`, `queue`, `preflight`) | Pure-Python Cedar policy + single-writer queue |
| **Cache** | `cache/` (`three_layer`, `orchestrator`, `metrics`) | L1/L2/L3 cache |
| **Providers** | `providers/` `gemini_cli`, `q_cli`, `mock_cli` | **Registered** (see §1.3). `mock_cli` = credential-free CI provider |
| **Plugins** | `plugins/builtin/{otel_sidecar, sse_event_publisher}`, `plugins/session_completion_plugin` | Registered via entry points |
| **Misc** | `clients/git_worktree.py`, `web/ai_manifest.py`, `models/q_agent.py`, `services/{budget_service, zellij_bridge}.py`, `zellij_assets/` | |
| **CLI cmds** | `cli/commands/{doctor, register, zellij}.py` | Copied; subcommand wiring into `cli/main.py` deferred — see §3 |
| **Frontends/assets** | `cao_pwa/` (React PWA), `zellij/` (Rust WASM) | AG-UI reference client + zellij backend |
| **Docs/examples/tests** | `docs/rfc/*`, `docs/*`, `examples/*`, `test/*`, `tests/validation/*` | Incl. the AG-UI + MCP-apps RFCs |

### 1.2 Reconciliations applied to shared files

- **`pyproject.toml`**: added deps `opentelemetry-api/sdk/exporter-otlp-proto-grpc>=1.27.0`, `authlib>=1.7.1`, `python-multipart>=0.0.27`; added `cao-acp` script; added plugin entry points `otel_sidecar`, `sse_event_publisher`, `session-completion`; added hatch artifacts (`persistence/*.sql`, zellij) + `orchestration` pytest marker. **Kept** upstream's `pyjwt[crypto]`, `jsonschema`, `fastmcp<4.0.0` cap, and the `mcp_apps` + `EventLogPublisher` entry points.
- **`plugins/events.py`**: added `traceparent` field to `CaoEvent` (OTel trace-context) and the `PostInterrupt/Pause/ResumeTerminalEvent` classes the ported plugins depend on. Additive; all defaulted.
- **`services/sse_bus.py`**: added `SSEBus = SseBus` back-compat alias (fork used `SSEBus`, upstream renamed to `SseBus`).
- **`constants.py`**: added `GEMINI_WORKSPACES_DIR`.
- **`models/provider.py`** + **`providers/manager.py`**: registered `Q_CLI`, `GEMINI_CLI`, `MOCK_CLI` (enum values + import + dispatch branches) — additive; upstream's Antigravity/Cursor/Hermes set untouched.

### 1.3 Verification performed

- `uv venv` (py3.11) + `uv pip install -e .` → OK.
- **All 52 net-new subsystem modules import**; upstream core modules still import (MCP Apps / config not clobbered).
- **Unit tests: 547 passing** across `a2a`, `acp`, `agent_card`, `cache`, `observability`, `orchestration` (206), `telemetry`, `refinery`, `services/agui_stream`, and the 3 new provider unit suites.
- OTel exporter warnings to `localhost:4317` during tests are environmental (no collector in sandbox), not failures.

---

## 2. Deliberately NOT applied (kept upstream's version)

| Item | Why |
|---|---|
| **MCP Apps** (`plugins/builtin/mcp_apps.py`, `mcp_server/app_tools.py`, `cao_mcp_apps/`, `ext_apps/apps_static/`) | Upstream's plugin-based implementation (PR #332) is more defensible (plugin isolation, HTTP-only AST boundary guard, full scope coverage, `ConfigService` gating) than the fork's inline `server.py` wiring. Fork's inline MCP Apps intentionally dropped. |
| **`ConfigService`** (`services/config_service.py`) | Kept upstream's unified config. Fork's scattered env reads should register into `ENV_REGISTRY` (follow-up). |
| **Workflow engine** (`workflow_service`, `cao schedule`/`workflow`) | Upstream-only; retained. Fork's superseded `cli/commands/flow.py` was **not** copied. |
| **`event_primitives.py`, `ui_state_service.py`** | Kept upstream's richer versions (6-kind normalization + RFC-6902 patch). |
| **`web/` React frontend** | Kept upstream's; fork's `cao_pwa/` added alongside as the AG-UI client. |

---

## 3. Remaining integration work (documented, not yet wired)

These require editing upstream's **diverged, hard-to-unit-verify** core files and are best reviewed as focused follow-ups. None blocks the subsystem code from importing/testing.

1. **AG-UI server endpoint (`GET /agui/v1/stream`).** The fork's handler maps the fork's *raw* event kinds. Upstream normalizes events to six `event_primitives` — so the correct move is to **re-base `agui_stream.to_agui_event()` onto `event_primitives`** (Phase 0/1 of the AG-UI roadmap), not a verbatim transplant. Wire into `api/main.py` alongside `/events`.
2. **A2A / Agent Card listener + telemetry lifespan.** The fork starts `start_agent_card_listener`, `init_telemetry`/`shutdown_telemetry`, the observability span consumer, and `BudgetService` in the app lifespan (`api/main.py` lines ~318–352 in the fork). Transplant into upstream's lifespan.
3. **ASI kill-switch + cache-stats endpoints** (`/asi/kill-switch`, `/asi/kill-switch/clear`, `/cache/stats`) and **terminal signal endpoints** (`/terminals/{id}/interrupt|pause|resume`, which emit the newly-added `PostInterrupt/Pause/Resume` events). Additive `@app` handlers.
4. **Persistence WAL + Refinery DB rewiring.** `test/persistence/*` and `test/refinery/test_sync_submit.py` expect `clients/database.py` mutations to route through the WAL queue. Upstream's `database.py` diverged (the `flow`→`schedule`/`workflow` rename, #378), so the method set differs (`create_flow` etc.). Rewire against upstream's current DB API. WAL runs in shadow mode, so this is non-blocking.
5. **CLI subcommand wiring.** Register `doctor`, `register`, `zellij` commands in `cli/main.py`.
6. **`ProviderType` README/docs.** Re-add Gemini/Q to provider docs if desired (upstream had retired Gemini → Antigravity).

---

## 4. Test-harness gaps (not code defects)

- `test/orchestration/test_handoff_mock.py` needs the `cao_server` e2e fixture (spawns a real `cao-server` + tmux). Register the fixture via `pytest_plugins` and run only in an e2e environment.
- `test/agent_card/test_oauth_prm.py` passes once §3.2 (listener/PRM wiring) lands.
