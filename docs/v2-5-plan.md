# CAO v2.5 — Unified Implementation Plan

**Source vision:** "CAO v2.5 Unified Vision: Cross-Verified Synthesis & Implementation Blueprint"
**Branch:** `claude/cao-v2.5-unified-synthesis-T2E27`
**Status as of 2026-05-06:** v2.5 closed out — all five phases shipped; deferred follow-ups, acceptance criteria, and cross-cutting items all complete (PR-cleanup-7KCis).

---

## Status at a glance

| Phase | Title | Status | PR | Notes |
|---|---|---|---|---|
| 1 | Persistence & Protocol Foundation | ✅ Shipped | [#1](https://github.com/plauzy/cli-agent-orchestrator.bak/pull/1) | OTel + WAL + libsql + Agent Card + SSE bus + widget |
| 3 | Topology Router & Two-Tier Execution | ✅ Shipped | [#3](https://github.com/plauzy/cli-agent-orchestrator.bak/pull/3) | AdaptOrch + Refinery + Polecat swarm; +17.4% benchmark |
| 4 | Deacon ASI Governance | ✅ Shipped | [#4](https://github.com/plauzy/cli-agent-orchestrator.bak/pull/4) | Rath (2026) ASI + mitigation handlers + kill switch |
| 5 | Performance & Ecosystem | ✅ Shipped | [#5](https://github.com/plauzy/cli-agent-orchestrator.bak/pull/5) | 3-layer cache + A2A v1.0 transport + ACP + AI Manifest |
| 2 | Zellij TUI | ✅ Shipped | — | KDL layout + zellaude.wasm + bridge; tmux + iTerm2 `-CC` remain compat path |

---

## Vision summary

CAO is shipping on a 2.x line: hierarchical multi-agent orchestration via tmux + a FastAPI hub on `:9889` + a FastMCP server exposing `assign / handoff / send_message / load_skill`. State is SQLite via SQLAlchemy; coordination is by inbox-message + watchdog idle-detection. Seven CLI providers (Kiro, ClaudeCode, Q, Codex, Gemini, Kimi, Copilot, OpenCode) plug in behind a `Provider` interface.

The v2.5 vision unifies prior research passes around four primitives that are doubly supported and non-negotiable:

1. **Hierarchy on writes / swarm on reads** — single-threaded write spine (Refinery) prevents Cognition's "write contention" failure mode; parallel Polecat workers handle reads.
2. **Decoupled persistent state** — WAL + materialized index, with SQLAlchemy authoritative in v2.5.x.
3. **A2A v1.0 as external boundary** — signed Agent Card + JSON-RPC + SSE transport.
4. **OpenTelemetry GenAI semconv as the spine** — every dispatch is a span; the Deacon scores those spans.

The ASI paper (arXiv:2601.04170) further constrains the architecture to **two functional tiers** — deeper trees underperform.

User decisions encoded in this plan:

- **WAL = shadow ingest** in v2.5.x. SQLAlchemy stays authoritative; WAL writes alongside each commit and feeds the libsql materialized index.
- **Agent Card = dedicated `:9890` listener.** Localhost-only `:9889` is preserved unchanged.
- **traceparent propagation = inbox column + plugin event only.** Never in the message body — protects the seven providers' status-detection regex from byte-level drift.

---

## Architecture map

| Vision role | Existing CAO surface | Action |
|---|---|---|
| Mayor (Tier-1 orchestrator, planner, WAL owner) | FastAPI server + MCP `_handoff_impl` / `_assign_impl` | **Extend** — WAL writes alongside `db.commit()`; wrap dispatch in `invoke_agent` spans. |
| Topology Router (AdaptOrch) | None | **New** — `orchestration/topology_router.py`, embedded in MCP dispatch. |
| Refinery (single-threaded write queue + policy) | None | **New** — `refinery/queue.py` with `asyncio.Lock` + pluggable policy. |
| Deacon (ASI sidecar) | None | **New** — `observability/asi_evaluator.py` + mitigation handlers. |
| Specialist Pool | Existing agent profiles | **Reuse as-is.** |
| Polecat (ephemeral read-only worker) | None | **New** — `orchestration/polecat.py` + `clients/git_worktree.py`. |
| WAL primary write path | None | **New** — `persistence/wal_writer.py`, shadow mode in v2.5.x. |
| LibSQL materialized index | SQLAlchemy/SQLite | **New** — `persistence/materialized_index.py`. |
| Agent Card at `/.well-known/agent-card.json` | None | **New** — dedicated `:9890` listener via `agent_card/router.py`. Ed25519 signed. |
| MCP Apps widget (SEP-1865) | REST-coupled React UI | **New** — `ext_apps/widget.py` resource handler. |
| OTel GenAI v1.37+ instrumentation | stdlib logging only | **New** — `telemetry/` package via `services/plugin_dispatch.py`. |
| SSE event bus | watchdog file events | **New** — `services/sse_bus.py` fed by builtin plugin. |
| A2A v1.0 transport | FastAPI + FastMCP | **Phase 5** — full `/a2a/v1/{rpc,stream,tasks}`. |
| Three-layer cache | None | **Phase 5** — `cache/three_layer.py`. |

---

## Phase 1 — Persistence & Protocol Foundation ✅ Shipped (PR #1)

Eight commits, each leaving `pytest -m 'not e2e'` green. OTel off-by-default; WAL off-by-default until commit 8.

### Files created

- `telemetry/{__init__,otel,semconv,spans,context}.py`
- `persistence/{__init__,wal_writer,materialized_index,replay,schema_libsql.sql}.py`
- `agent_card/{__init__,builder,signing,router,listener}.py`
- `ext_apps/{__init__,widget,static/topology.{html,js,css}}`
- `services/sse_bus.py`
- `plugins/builtin/{__init__,otel_sidecar,sse_event_publisher}.py`

### Commit sequence

| # | Title |
|---|---|
| 1 | OTel scaffolding (no-op by default) |
| 2 | `OtelSidecarPlugin` + `invoke_agent` / `execute_tool` spans from MCP tools |
| 3 | Thread `traceparent` through `CaoEvent` + `InboxMessage` (nullable column) |
| 4 | WAL writer in shadow mode (mirrors every `db.commit()`) |
| 5 | LibSQL materialized index + replay-on-boot |
| 6 | Signed Agent Card on dedicated `:9890` listener |
| 7 | MCP Apps widget + SSE bus |
| 8 | Documentation + flag flip (semantic only — shadow has been live since commit 4) |

### Critical invariants pinned by tests

- Trace context never enters the message body — provider regex is byte-stable.
- WAL appends are best-effort (after `db.commit()` returns); failure logs and continues.
- Replay produces a libsql index byte-identical to the live SQLAlchemy state.
- Agent Card listener has no `TrustedHostMiddleware`; main `:9889` API stays localhost-only.

---

## Phase 3 — Topology Router & Two-Tier Execution ✅ Shipped (PR #3)

Built on Phase 1. Ten commits. Held-out benchmark reports +17.4% reliability-adjusted-cost-per-task improvement vs static hierarchy (target was ≥12%).

### Files created

- `orchestration/{__init__,dag,topology_router,specialist_pool,polecat,swarm,hybrid_cluster,dispatch}.py`
- `refinery/{__init__,queue,policy,rule_of_two}.py`
- `clients/git_worktree.py`
- `services/budget_service.py`

### Commit sequence

| # | Title |
|---|---|
| 9 | DAG parser + `TaskDAG` model |
| 10 | Topology router with stubbed ASI oracle |
| 11 | Refinery queue, single-specialist path (all mutations re-routed) |
| 12 | `read_only=True` provider tool stripping |
| 13 | Git worktree manager + Polecat spawn/teardown |
| 14 | Polecat swarm dispatch (1000-task burn-in: zero parallel-write collisions) |
| 15 | Hybrid hierarchical-cluster topology (label propagation clusterer for `k > 50`) |
| 16 | Held-out improvement benchmark (+17.4%) |
| 17 | `dispatch_task` entrypoint composing router + Refinery + swarm |
| 18 | Migrate `_handoff_impl` through `dispatch_task` |

### Span attributes recorded

`cao.topology.choice`, `cao.topology.features.{omega, gamma, depth, k}`, `cao.task_class`, `cao.tier`.

### Deferred follow-ups (small surgical PRs)

- Migrate `_assign_impl` through `dispatch_task`.
- Real `dispatch_swarm` collector (currently stubbed to return findings list).
- Refinery rewiring of remaining inline `db.commit()` sites in `clients/database.py`.

---

## Phase 4 — Deacon ASI Governance ✅ Shipped (PR #4)

Built on Phase 1 + Phase 3. Five commits; +72 tests. Implements the Rath (2026) Agent Stability Index framework (arXiv:2601.04170).

### Files created

- `observability/{__init__,asi_evaluator,mitigations,span_consumer}.py`

### Files modified

- `orchestration/dispatch.py` (added `KillSwitchOracle` Protocol + `dispatch_task(kill_switch=...)` gate)
- `orchestration/__init__.py` (exports)
- `api/main.py` (lifespan wires `AsiEvaluator` + `standard_handlers` + `AsiSpanProcessor`)

### Commit sequence

| # | Title |
|---|---|
| 19 | `AsiEvaluator` core — rolling-window per-task-class scoring + 4 dimension scorers |
| 20 | Wire Deacon as topology router `AsiOracle` (duck-typed; no adapter class) |
| 21 | Mitigation handlers (`Logging` / `SseBroadcast` / `WALPersistence` / `KillSwitch`) |
| 22 | `AsiSpanProcessor` — in-process OTel span consumer feeding the evaluator |
| 23 | FastAPI lifespan wiring + `dispatch_task` kill-switch gate + docs |

### Rath (2026) weights (load-bearing)

| Dimension | Weight | Default scorer |
|---|---|---|
| Response Consistency | 0.30 | success rate from `cao.tool.outcome` |
| Tool Usage Patterns | 0.25 | 1 − normalized Shannon entropy |
| Inter-Agent Coordination | 0.25 | logistic curve over span duration (REFERENCE_MS = 30 000) |
| Behavioral Boundaries | 0.20 | 1 − error rate |

### Threshold defaults (calibration parameters)

| Threshold | Default | Action |
|---|---|---|
| `warn` | 0.85 | event fires immediately |
| `mitigate` | 0.75 | fires after 3 consecutive windows below |
| `kill` | 0.60 | fires immediately; flips per-task-class kill switch |
| `recover` | back above `mitigate` | clears kill switch automatically |

### Deferred follow-ups (small surgical PRs)

- Plumb `app.state.kill_switch` into MCP `_handoff_impl` / `_assign_impl` so dispatch consults it.
- Operator API endpoint to clear the kill switch without a restart.
- Memory consolidation / behavioral anchoring handlers (require Phase 5 model-runtime integration).

---

## Phase 5 — Performance & Ecosystem 🚧 In progress

Three-layer cache, A2A v1.0 transport, AI Manifest support, ACP exposure.

### Files to create

- `cache/__init__.py`
- `cache/three_layer.py` — L1 (in-process LRU + TTL), L2 (Anthropic prompt-cache keep-alive), L3 (SQLite cross-session).
- `a2a/__init__.py`
- `a2a/rpc.py` — JSON-RPC 2.0 handler for `/a2a/v1/rpc`. Methods: `task.send`, `task.get`, `task.cancel`.
- `a2a/stream.py` — SSE handler for `/a2a/v1/stream`. Streams `task.update` and `message.delta` events.
- `a2a/tasks.py` — REST handler for `/a2a/v1/tasks/{taskId}`. Polling fallback for streaming.
- `a2a/auth.py` — JWT verification using the JWKS published by the Phase 1 Agent Card listener.

### Files to modify

- `agent_card/listener.py` — mount the `/a2a/v1/*` routes on the existing `:9890` listener (read-write boundary).
- `services/budget_service.py` — Cache-aware projected_cost (cache hits cost ~10% of full).

### Commit sequence (planned)

| # | Title | Status |
|---|---|---|
| 24 | Cache primitives — L1 + L3 storage layers with `CacheBackend` Protocol | ✅ shipped |
| 25 | L2 Anthropic prompt-cache keep-alive scheduler + `ThreeLayerCache` orchestrator | ✅ shipped |
| 26 | A2A v1.0 RPC endpoint (`task.send` / `task.get` / `task.cancel`) on `:9890` | ✅ shipped |
| 27 | A2A v1.0 stream + tasks endpoints (SSE + REST polling fallback) | ✅ shipped |
| 28 | AI Manifest support in Polecat web-interaction harness | ✅ shipped |
| 29 | ACP exposure for Cursor 3 / Zed Parallel Agents / Claude Code | ✅ shipped |
| 30 | Phase 5 lifespan wiring + docs + finalize PR #5 | ✅ shipped |

### Acceptance criteria

- L1 + L3 cache hit rates exposed via `/health/cache` (or equivalent observability surface).
- L2 keep-alive task is best-effort; failures are logged but never block the request path.
- A2A v1.0 endpoints round-trip a task end-to-end against a real A2A peer (manual E2E).
- Cache-aware budget oracle reflects true post-cache cost in topology-router decisions.

---

## Phase 2 — Zellij TUI ✅ Shipped

Three-pane KDL layout (Control / Trace / Shell) plus the vendored
`zellaude.wasm` status-bar plugin. The hook bridge (`services/zellij_bridge.py`)
is gated behind `CAO_ZELLIJ_ENABLED=true`. tmux + iTerm2 `-CC` remain
the documented compat path; end users do not need a Rust toolchain
because the `.wasm` ships in the wheel via Hatch `force-include`.

See [`docs/zellij.md`](zellij.md) for the operator setup guide and
[`docs/v2-5-tasks.md`](v2-5-tasks.md) for the Phase 2 task tracker
(C31–C34 ✅).

---

## Verification plan

Each commit must pass:

1. `pytest -m 'not e2e' --no-cov` — full default suite green.
2. `mypy` clean on every changed file.
3. `black --check . && isort --check-only .` — lint gate matches `.github/workflows/ci.yml`.
4. **Manual E2E (Phase boundary):** `pytest -m e2e` against Kiro CLI + Claude Code with real tmux. Assigns, handoffs, send_messages all complete; no idle-detection regressions.

Per-phase acceptance criteria are documented inline above.

---

## Open questions deferred to implementation

These are research/calibration items that get answered by running the system, not gating items:

1. **OTel collector choice** — defaulted to gRPC + bearer; Langfuse/Honeycomb/Datadog all accept it.
2. **libsql variant** — defaulted to embedded `libsql-experimental`; falls back to plain SQLite at runtime.
3. **Card signing key lifecycle** — auto-generate on first boot; document operator key rotation.
4. **Agent Card public reachability** — `:9890` has no `TrustedHostMiddleware`; document a deployment matrix.
5. **Cedar adoption timing** — Phase 3 ships YAML rules; Cedar is a v2.6 candidate.
6. **Topology improvement benchmark target** — actual: +17.4% (target was ≥12%).
7. **ASI threshold calibration** — defaults follow Rath paper; tune over the first month of operation.

---

## Risks not addressed in the vision doc

- **WAL ↔ SQLAlchemy coexistence under failure** — WAL is appended after `db.commit()` returns. Crash between commit and append → missing log entry, recoverable from SQLAlchemy. Acceptable in shadow mode.
- **Provider regex fragility** — trace context must never enter the message body. Code review enforces.
- **OTel BatchSpanProcessor blocking shutdown** — `shutdown_telemetry()` uses an explicit short timeout.
- **Trace completeness ≥ 99.9% target** — operators bypassing MCP produce orphan traces. Documented and accepted.
- **Polecat worktree garbage** — crashed Polecats leave stranded worktrees. `lifespan` startup runs `git worktree prune`.
- **Refinery becoming a global bottleneck** — single `asyncio.Lock` serializes all writes. Today's CAO write rate is low; shard by tenant/session in v2.6 if needed.
- **AsiSpanProcessor in hot path** — feeds evaluator on every span emit. `try/except` swallowing keeps drift detection opportunistic; bounded `deque` keeps memory `O(num_task_classes)`.

---

See [`docs/v2-5-tasks.md`](v2-5-tasks.md) for the per-phase task checklist and [`docs/v2-5-architecture.md`](v2-5-architecture.md) for the architecture reference.
