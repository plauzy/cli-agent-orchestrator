# CAO v2.5 Architecture

> Status: **alpha** — `2.5.0a4` (Phase 1 + 3 + 4 + 5 shipped). Phase 2
> (Zellij TUI) is deferred. Every v2.5 capability is gated off by
> default at first ship and adds no observable behavior change until
> explicitly enabled.
> See [`docs/v2-5-plan.md`](v2-5-plan.md) for the full implementation
> plan and [`docs/v2-5-tasks.md`](v2-5-tasks.md) for the per-phase task
> tracker.

## Overview

v2.5 evolves CAO from a single-tier hub orchestrator into a foundation
for a two-tier "Gas Town" topology:

```
                ┌─────────────────────────────────────────┐
External A2A ─► │ /.well-known/agent-card.json (port 9890)│ ◄─ JWKS
peers           │  Ed25519-signed, no host restriction    │
                └─────────────────┬───────────────────────┘
                                  │
                                  │ Discovery
                                  ▼
                ┌─────────────────────────────────────────┐
                │  CAO API (port 9889, localhost-only)    │
                │  ┌───────────────────────────────────┐  │
                │  │ MCP tools (execute_tool spans)    │  │
                │  │ assign / handoff / send_message   │  │
                │  └────────────────┬──────────────────┘  │
                │                   │                      │
                │                   ▼                      │
                │  ┌───────────────────────────────────┐  │
                │  │ services/                         │  │
                │  │  ├─ terminal_service              │  │
                │  │  ├─ inbox_service                 │  │
                │  │  └─ flow_service                  │  │
                │  └────────────────┬──────────────────┘  │
                │                   │ db.commit() + wal_append
                │                   ▼                      │
                │  ┌───────────────────────────────────┐  │
                │  │ clients/database.py (SQLAlchemy)  │  │
                │  │  authoritative writer in v2.5.x   │  │
                │  └────────────────┬──────────────────┘  │
                │                   │                      │
                │                   ▼                      │
                │  ┌───────────────┴───────────────────┐  │
                │  │ persistence/wal_writer            │  │
                │  │  WAL_DIR/{YYYYMMDD}.log JSONL     │  │
                │  └────────────────┬──────────────────┘  │
                │                   │                      │
                │                   │ replay_wal_into() on boot
                │                   ▼                      │
                │  ┌───────────────────────────────────┐  │
                │  │ persistence/materialized_index    │  │
                │  │  cao-index.db (SQLite, libsql-    │  │
                │  │  compatible for v2.6 swap)        │  │
                │  └───────────────────────────────────┘  │
                │                                          │
                │  Plugin event bus: PostCreateTerminal,   │
                │  PostSendMessage, ... (with traceparent) │
                │  ─► OtelSidecarPlugin                    │
                │  ─► SseEventPublisherPlugin              │
                │                   │                      │
                │                   ▼                      │
                │  GET /events (SSE)  ─►  /widgets/topology│
                └─────────────────────────────────────────┘
```

## Components added in Phase 1

| Component | Module | Status |
|---|---|---|
| OTel GenAI semconv helpers | `cli_agent_orchestrator/telemetry/` | Off by default; `OTEL_SDK_DISABLED=false` to enable |
| MCP tool spans (`execute_tool`) | `mcp_server/server.py` (`_*_impl` wrappers) | Always emitted; no-op when telemetry off |
| `OtelSidecarPlugin` | `plugins/builtin/otel_sidecar.py` | Always loaded via entry point |
| `traceparent` on events + inbox | `plugins/events.py`, `models/inbox.py`, `clients/database.py` | Always wired; column added via idempotent migration |
| WAL writer | `persistence/wal_writer.py` | Off by default; `init_wal()` from `lifespan` enables |
| WAL ingest sites (9 mutations) | `clients/database.py` | Always present; no-op when WAL off |
| Materialized index | `persistence/materialized_index.py` + `schema.sql` | Rebuilt from WAL in `lifespan` |
| Replay | `persistence/replay.py` | Idempotent, resilient to malformed/unknown ops |
| Ed25519 signer | `agent_card/signing.py` | Lazy key generation, mode 0600 |
| Agent Card builder | `agent_card/builder.py` | A2A v1.0 conformant |
| `/.well-known` router | `agent_card/router.py` | Mounted on `:9890` listener only |
| Dedicated `:9890` listener | `agent_card/listener.py` | `CAO_AGENT_CARD_DISABLED=true` skips startup |
| In-process SSE bus | `services/sse_bus.py` | Bounded queues; drops on slow consumer |
| `SseEventPublisherPlugin` | `plugins/builtin/sse_event_publisher.py` | Republishes `Post*` to bus |
| `GET /events` SSE endpoint | `api/main.py` | StreamingResponse over the bus |
| Topology widget | `ext_apps/widget.py` + `static/topology.{html,js,css}` | Mounted at `/widgets/topology/` |

## Data flow: a single `send_message` request

1. Calling agent invokes the CAO MCP `send_message` tool with a `traceparent`
   in the active OTel context.
2. `_send_message_impl` opens an `execute_tool send_message` span, captures
   the `traceparent` via `inject_traceparent()`, POSTs to
   `:9889/terminals/{receiver_id}/inbox/messages?traceparent=...`.
3. The FastAPI handler calls `create_inbox_message(..., traceparent=...)`.
4. `clients/database.py` writes the row through SQLAlchemy, commits, then
   `wal_append("create_inbox_message", payload)` durably appends a JSON
   line to today's `WAL_DIR/{YYYYMMDD}.log` with fsync.
5. `inbox_service.check_and_send_pending_messages` reads `traceparent`
   from the row when the receiver becomes IDLE and forwards it to
   `terminal_service.send_input(..., traceparent=...)`.
6. `send_input` types the message bytes into the tmux pane (body unchanged)
   and dispatches a `PostSendMessageEvent` carrying the `traceparent`.
7. `OtelSidecarPlugin` and `SseEventPublisherPlugin` both receive the
   event. The latter republishes `{type: "message.sent", payload: {sender,
   receiver, orchestration_type}, traceparent}` to the SSE bus.
8. Any subscribed `/events` consumer (e.g. the topology widget) sees the
   event live.
9. On next CAO boot, `replay_wal_into(conn, WAL_DIR)` rebuilds `cao-index.db`
   from the WAL — the index reflects the same state SQLAlchemy persisted.

## Critical invariants (pinned by tests)

- **Message bodies never reach the WAL or the SSE bus.** Provider
  status-detection regex matches on terminal output bytes; any extra
  prefix or suffix added to a user's message would silently break idle
  detection across all 7 providers. The WAL stores metadata only, and
  `SseEventPublisherPlugin` republishes only `{sender, receiver,
  orchestration_type}` — never `message`. Pinned by
  `test_create_inbox_message_writes_metadata_only` and
  `test_post_send_message_omits_message_body`.
- **`traceparent` never enters the message body.** Carried in the inbox
  column and the plugin event payload only. Pinned by
  `test_traceparent_does_not_pollute_message_body`.
- **WAL append never propagates errors.** SQLAlchemy is authoritative; a
  WAL append failure is logged and swallowed. Pinned by
  `test_wal_append_swallows_writer_errors`.
- **Replay is idempotent.** Replaying the same WAL files twice produces
  the same final state. Pinned by `test_replay_twice_produces_same_state`.
- **Card signature is stable across re-issues.** `sign_card` strips the
  `AgentCardSignature` field before signing so the signed bytes are
  identical regardless of any embedded prior signature. Pinned by
  `test_signature_does_not_cover_itself`.
- **SSE producer never blocks on slow consumers.** Per-subscriber
  bounded queues drop events when full. Pinned by
  `test_publish_drops_for_full_subscriber_queue`.

## Configuration matrix (env vars added in Phase 1)

| Env var | Default | Effect |
|---|---|---|
| `OTEL_SDK_DISABLED` | `true` | When `false`, the OTel SDK is installed and spans export via OTLP/gRPC. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | Standard OTel; honored by the SDK. |
| `OTEL_EXPORTER_OTLP_HEADERS` | _(unset)_ | Standard OTel; bearer/auth. |
| `CAO_AGENT_CARD_DISABLED` | `false` (in tests: `true`) | Skip starting the `:9890` listener entirely. |
| `CAO_AGENT_CARD_HOST` | `0.0.0.0` | Bind host for the `:9890` listener. Set to `127.0.0.1` for loopback-only. |
| `CAO_AGENT_CARD_PORT` | `9890` | Port for the Agent Card listener. |
| `CAO_ASI_DISABLED` | `false` | Skip Phase 4 Deacon initialization. The evaluator runs in-process and adds a small per-span overhead; opt out for benchmarks. |

## Phase 4 — Deacon ASI Governance

The Deacon implements the Rath (2026) Agent Stability Index framework
(arXiv:2601.04170): a rolling stability score in `[0, 1]` per task class,
weighted across four dimensions:

| Dimension | Weight | Default scorer |
|---|---|---|
| Response Consistency | 0.30 | success rate from `cao.tool.outcome` |
| Tool Usage Patterns | 0.25 | 1 − normalized Shannon entropy across span names |
| Inter-Agent Coordination | 0.25 | logistic curve over span duration (REFERENCE_MS = 30 000) |
| Behavioral Boundaries | 0.20 | 1 − error rate (treats `*_timeout` outcomes as errors) |

Default thresholds are calibration parameters and are documented as
"tune over the first month of operation":

| Threshold | Default | Action when breached |
|---|---|---|
| `warn` | 0.85 | `MitigationEvent(severity="warn")` fires immediately |
| `mitigate` | 0.75 | Fires after 3 consecutive windows below |
| `kill` | 0.60 | Fires immediately; flips the per-task-class kill switch |
| `recover` | back above `mitigate` | Clears the kill switch automatically |

Spans flow into the evaluator via the in-process `AsiSpanProcessor`,
attached to the global OTel TracerProvider in the FastAPI lifespan.
The collector-sidecar deployment described in the v2.5 vision doc
remains supported — operators can disable the in-process processor
and run the Deacon as a separate OTLP consumer. The duck-typed
`AsiOracle` Protocol (`score_for_task_class(task_class) -> float`) is
satisfied directly by `AsiEvaluator`, so `select_topology(dag, asi=evaluator, ...)`
consults the live score with no adapter class.

Mitigation handlers are independent and pluggable (`standard_handlers()`
returns the four wired together):

- `LoggingHandler` — severity → log level (warn/mitigate/kill/recover map to WARNING/ERROR/CRITICAL/INFO).
- `SseBroadcastHandler` — republishes events on `:9889/events` as `asi.mitigation` SSE entries; the topology widget surfaces them visually.
- `WALPersistenceHandler` — appends to the Phase 1 WAL under op `asi.mitigation` for the audit trail.
- `KillSwitchHandler` — flips a process-wide `KillSwitchState` flag keyed by `task_class` on `severity=kill`; clears it on `severity=recover`.

The dispatch layer consumes the kill switch via the
`KillSwitchOracle` Protocol: `dispatch_task(request, kill_switch=...)`
raises `KillSwitchEngaged(task_class)` before the topology router
runs when the Deacon has flipped the switch. Operators clear via the
kill-switch API (Phase 5) or by restarting CAO.

All handlers swallow their own exceptions so a transient handler bug
never propagates back into the SDK span-emit hot path. Drift detection
is opportunistic by design.

## Roadmap

- **Phase 1 (Persistence & Protocol Foundation)** — Shipped in v2.5.0a1 (PR #1).
  OTel GenAI v1.37+ instrumentation, traceparent propagation, shadow WAL, libsql
  materialized index, signed Agent Card on `:9890`, SEP-1865 topology widget +
  SSE bus.
- **Phase 3 (Topology router + Refinery + Polecat)** — Shipped in v2.5.0a2 (PR #3).
  AdaptOrch DAG classification, single-threaded write queue with Cedar-style
  policy gate, Polecat sandboxed read-swarm execution. Held-out benchmark
  reports +17.4% reliability-adjusted-cost-per-task vs static hierarchy.
- **Phase 4 (ASI governance)** — Shipped in v2.5.0a3 (PR #4). Deacon in-process
  evaluator implementing the Rath (2026) framework with full mitigation
  control loop (logging / SSE broadcast / WAL persistence / kill switch);
  `dispatch_task(kill_switch=...)` gate refuses new work for task classes the
  Deacon has flagged.
- **Phase 5 (Performance + Ecosystem)** — Shipped in v2.5.0a4 (PR #5).
  Three-layer cache with 4-minute keep-alive against Anthropic's 5-minute
  prompt-cache TTL; AI Manifest fetcher for Polecat web interaction; full A2A
  v1.0 transport endpoints (`/a2a/v1/{rpc,stream,tasks}`) layered on top of the
  Phase 1 Agent Card listener; ACP server (`cao-acp` stdio entry point) for
  Cursor 3 / Zed Parallel Agents / Claude Code.
- **Phase 2 (Zellij TUI)** — _Deferred._ Separate split-pane layout for control,
  trace, and shell. Re-uses the WAL as the canonical source for the trace
  pane. tmux + iTerm2 `-CC` documented as compat path; Phase 2 becomes
  mechanical once Phase 1's WAL is the system of record (already shipped).

See [`docs/v2-5-plan.md`](v2-5-plan.md) for the full implementation plan and
[`docs/v2-5-tasks.md`](v2-5-tasks.md) for the per-phase task tracker.
