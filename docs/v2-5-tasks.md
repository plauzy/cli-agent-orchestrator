# CAO v2.5 — Task Tracker

Phase-by-phase checklist. See [`docs/v2-5-plan.md`](v2-5-plan.md) for the full plan and [`docs/v2-5-architecture.md`](v2-5-architecture.md) for the architecture reference.

**Legend:** ✅ done · 🚧 in progress · ⏳ pending · 🗓 deferred

---

## Phase 1 — Persistence & Protocol Foundation ✅ Shipped (PR #1)

- [x] **C1** OTel scaffolding (no-op by default)
- [x] **C2** `OtelSidecarPlugin` + spans on MCP tool dispatch
- [x] **C3** Thread `traceparent` through `CaoEvent` + `InboxMessage`
- [x] **C4** WAL writer in shadow mode
- [x] **C5** LibSQL materialized index + replay-on-boot
- [x] **C6** Signed Agent Card on `:9890` listener
- [x] **C7** MCP Apps widget + SSE bus
- [x] **C8** Documentation + flag flip

**Acceptance:** ✅ All checks green at PR #1 merge.

---

## Phase 3 — Topology Router & Two-Tier Execution ✅ Shipped (PR #3)

- [x] **C9** `TaskDAG` + AdaptOrch features extractor
- [x] **C10** Topology router with stubbed ASI oracle
- [x] **C11** Refinery queue + Rule-of-Two + policy interface
- [x] **C12** `read_only=True` provider tool stripping
- [x] **C13** Git worktree manager + Polecat spawn/teardown
- [x] **C14** Polecat swarm dispatch (1000-task burn-in)
- [x] **C15** Hybrid hierarchical-cluster topology
- [x] **C16** Held-out improvement benchmark — +17.4% measured
- [x] **C17** `dispatch_task` entrypoint
- [x] **C18** Migrate `_handoff_impl` through `dispatch_task`

**Acceptance:** ✅ All checks green at PR #3 merge. Benchmark exceeds 12% target.

### Deferred follow-ups (closed in cleanup PR)

- [x] Migrate `_assign_impl` through `dispatch_task` — already shipped via PR #4 (`mcp_server/server.py:656`); regression test in `test/mcp_server/test_assign.py`
- [x] Real `dispatch_swarm` collector — `orchestration/swarm.py::_aggregate` + `AggregatedFindings`; correctness benchmark in `test/benchmarks/test_swarm_correctness.py`
- [x] Refinery rewiring of remaining inline `db.commit()` sites in `clients/database.py` — 10 sites routed through `submit_sync_or_run`; regression in `test/refinery/test_sync_submit.py`

---

## Phase 4 — Deacon ASI Governance ✅ Shipped (PR #4)

- [x] **C19** `AsiEvaluator` core — rolling-window per-task-class scoring
- [x] **C20** Wire Deacon as topology router `AsiOracle` (duck-typed)
- [x] **C21** Mitigation handlers (`Logging` / `SseBroadcast` / `WALPersistence` / `KillSwitch`)
- [x] **C22** `AsiSpanProcessor` — in-process OTel span consumer
- [x] **C23** FastAPI lifespan wiring + `dispatch_task(kill_switch=...)` gate + docs

**Acceptance:** ✅ +72 tests, 1841/1841 passing at PR #4 merge.

### Deferred follow-ups (closed in cleanup PR)

- [x] Plumb `app.state.kill_switch` into MCP `_handoff_impl` / `_assign_impl` — already shipped via PR #4 (`mcp_server/server.py:472, 658`); both impls call `dispatch_task(kill_switch=get_kill_switch())`
- [x] Operator API endpoint to clear kill switch without restart — already shipped via PR #4 (`api/main.py:387, 419`)
- [x] Memory consolidation handler — `observability/mitigations.py::MemoryConsolidationHandler`; consumed by `topology_router.py::select_topology` via `consolidation` kwarg
- [x] Behavioral anchoring handler — `observability/mitigations.py::BehavioralAnchoringHandler`; threaded through `dispatch_task(anchors=...)`; recovery benchmark in `test/benchmarks/test_anchoring_recovery.py`

---

## Phase 5 — Performance & Ecosystem ✅ Shipped (PR #5)

- [x] **C24** L1 (in-process LRU + TTL) + L3 (SQLite cross-session) cache primitives
- [x] **C25** L2 Anthropic prompt-cache keep-alive scheduler + `ThreeLayerCache` orchestrator
- [x] **C26** A2A v1.0 RPC endpoint (`task.send` / `task.get` / `task.cancel`) on `:9890`
- [x] **C27** A2A v1.0 stream (SSE) + tasks (REST polling) endpoints
- [x] **C28** AI Manifest support in Polecat web-interaction harness
- [x] **C29** ACP exposure for Cursor 3 / Zed Parallel Agents / Claude Code
- [x] **C30** Lifespan wires A2A endpoints onto :9890; Phase 5 docs + finalize PR #5

### Acceptance criteria (per Phase 5) — closed in cleanup PR

- [x] L1 + L3 cache hit rates exposed via observability surface — OTel counters `cao.cache.l1.hits_total` / `.l3.hits_total` / `.misses_total` + observable gauge `cao.cache.hit_rate_5m`; also surfaced on `/cache/stats` as `hit_rate_5m_percent`
- [x] L2 keep-alive is best-effort; failures never block request path — pinned by `test/cache/test_orchestrator.py::TestL2FailureIsolation`
- [x] A2A v1.0 endpoints round-trip a task against a real peer — `test/e2e/test_a2a_roundtrip.py` (two ASGI peers, executor on B, A polls + streams)
- [x] Cache-aware budget oracle reflects post-cache cost in router decisions — `services/budget_service.py::BudgetService`; benchmark in `test/benchmarks/test_cache_aware_router.py`

---

## Phase 2 — Zellij TUI ✅ Shipped

- [x] **C31** Zellij KDL layout (Control / Trace / Shell) — `zellij/layouts/cao.kdl`
- [x] **C32** `zellaude.wasm` status-bar plugin — `zellij/src/lib.rs` (vendored at `zellij/zellaude.wasm`)
- [x] **C33** Hook bridge — SSE bus → `zellij pipe` → plugin — `services/zellij_bridge.py`, lifespan-gated on `CAO_ZELLIJ_ENABLED=true`
- [x] **C34** Zellij installation + bootstrap docs — `cao zellij {install,start,tail}` + [`docs/zellij.md`](zellij.md)

**Acceptance:** ✅ +20 tests (12 bridge, 8 CLI), suite green on Python 3.11 + 3.12. tmux + iTerm2 `-CC` remain the documented compatibility path. End users do not need a Rust toolchain — the `.wasm` is vendored and shipped via Hatch `force-include`.

---

## Cross-cutting follow-ups

These are not tied to a single phase and could be picked up at any time:

- [x] Provider regex fragility tests — assert `traceparent` never enters the message body for all 7 providers (covered at the shared chokepoint in `test/services/test_terminal_service_full.py::TestSendInputTraceparentInvariant` + `test/services/test_inbox_service.py::TestInboxTraceparentInvariant`)
- [x] OTel collector deployment matrix doc (gRPC vs HTTP, auth modes) — see [`docs/otel-deployment.md`](otel-deployment.md)
- [x] Operator key rotation runbook for the Agent Card signing key — see [`docs/runbooks.md`](runbooks.md) §"Phase 1 — Agent Card signing key rotation"
- [x] Cedar policy migration path (YAML → Cedar) for the Refinery — see [`docs/cedar-migration.md`](cedar-migration.md); adapter at `refinery/cedar_policy.py`; runtime flip via `CAO_REFINERY_ENGINE`
- [x] Periodic `git worktree prune` runbook for stranded Polecat worktrees — see [`docs/runbooks.md`](runbooks.md) §"Phase 1 — Polecat git-worktree GC"
- [x] ASI threshold recalibration runbook ("first month of operation") — see [`docs/runbooks.md`](runbooks.md) §"Phase 4 — ASI threshold recalibration"

---

## How to update this tracker

When you ship a commit:

1. Tick the box on the corresponding line.
2. Update the phase header status emoji if the whole phase is done.
3. Update the "Status as of" date in [`docs/v2-5-plan.md`](v2-5-plan.md).
4. Run `pytest -m 'not e2e' --no-cov` and add the test count to the Acceptance line if changed.
5. If the work splits or merges with adjacent commits, edit this file in the same commit so the tracker stays accurate at every point in history.
