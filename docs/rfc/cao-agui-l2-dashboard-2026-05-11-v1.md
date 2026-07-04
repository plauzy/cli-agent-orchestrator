# cao-agui-l2-dashboard-2026-05-11-v1

| Field | Value |
|---|---|
| **Created** | 2026-05-11 |
| **Version** | v1 |
| **Status** | Draft — L2 sibling RFC to `cao-mcp-apps-implementation-plan-2026-05-10-v2.md` |
| **Author** | Patrick Lauer |
| **Target repo** | https://github.com/awslabs/cli-agent-orchestrator |

## Table of contents

1. [Context](#1-context)
2. [Design goals](#2-design-goals)
3. [Construct level](#3-construct-level)
4. [Threat model](#4-threat-model)
5. [AG-UI event mapping](#5-ag-ui-event-mapping)
6. [Wire protocol](#6-wire-protocol)
7. [Multi-instance config](#7-multi-instance-config)
8. [CORS posture](#8-cors-posture)
9. [What ships in v1 vs deferred](#9-what-ships-in-v1-vs-deferred)
10. [Risks](#10-risks)
11. [Verification](#11-verification)

## 1. Context

PRs #16-19 shipped the cao-mcp-apps **L1** surface (iframe-based,
single-instance, in-host). PR #20 added the L3 Auth0 layer. What's
still missing is the L2 construct the v2 plan §18 flagged: a
standalone PWA that consumes `ui://cao/*` resources from one or more
reachable CAO instances over AG-UI streams.

L1 closes the AI-host context loop (Claude Desktop, Cursor, etc.). L2
closes three gaps the L1 surface architecturally cannot:

1. **Operators outside an MCP host.** Team leads using just a browser
   need a dashboard without installing Claude / Cursor / VS Code.
2. **Multi-instance fleets.** L1 sees one CAO daemon. Team setups
   want one dashboard, many daemons.
3. **Cross-origin freedom.** Iframes are sandboxed; PWAs at their own
   origin use real WebSocket, full IndexedDB, normal CORS.

## 2. Design goals

- **Backwards-compatible default.** The L1 iframe and the existing
  `/events` SSE stream keep working byte-identically. The L2 surface
  is additive.
- **AG-UI as the wire protocol.** Industry-standard typed-event SSE
  (16 events, Apache-2.0, CopilotKit-stewarded). Future AG-UI clients
  (CopilotKit, custom dashboards) can consume CAO's stream without
  custom adapter code.
- **Single source of truth for event semantics.** CAO's existing
  `sse_bus` and `event_log_service` are the sources; an adapter maps
  to AG-UI's typed-event names on the wire.
- **Default-off CORS.** Localhost-only origins by default; PWA origins
  opt in via `CAO_PWA_ORIGIN`.
- **Read-only in v1.** The PWA shows fleet state; mutations require
  Auth0 Bearer flow + the same `submit_command` choke point from L1.
  v1 doesn't ship the Bearer-input UX or the WS terminal stream.

## 3. Construct level

Per the construct vocabulary in v2 plan §5:

| Layer | Surface | Status |
|---|---|---|
| L1 — Raw construct | iframe-based `ui://cao/*` resources | shipped (PRs #16-19) |
| L2 — Opinionated construct | standalone dashboard PWA | **this RFC** |
| L3 — Composed system | Auth0 + multi-tenant | shipped (PR #20), v2 deferred |

This RFC is L2: an opinionated dashboard surface composed from L1 raw
primitives (the AG-UI stream + REST surface). It does NOT replace L1
— both surfaces coexist for different operator personas (in-host vs
standalone-browser).

## 4. Threat model

| Threat | Mitigation |
|---|---|
| **PWA exfiltrates secrets from CAO** | Privacy boundary preserved: `message.sent` carries empty `delta` on the wire (same contract as WAL / SSE bus). PWA never sees message bodies. |
| **CORS widening allows arbitrary origins** | `CAO_PWA_ORIGIN` is an explicit allow-list; empty default; comma-separated. |
| **EventSource can't set Authorization headers** | Token via `?access_token=` query parameter. Validated server-side same as headers. Documented as the standard workaround. |
| **Cross-instance attack via tab-shared cookies** | PWA stores instances in IndexedDB (per-origin), not localStorage. No cross-instance cookie sharing because each CAO has its own origin. |
| **Stale event-log replay reveals deleted-session metadata** | The buffer's 24 h TTL bounds replay. Operators wanting hard delete should restart CAO. Documented. |
| **AG-UI adapter mistranslates event semantics** | Table-driven mapping in `services/agui_stream.py`, version-pinned; tests assert each mapping; privacy redaction asserted. |

## 5. AG-UI event mapping

v1 ships 6 of the 16 AG-UI typed events. The mapping is a pure
function in `src/cli_agent_orchestrator/services/agui_stream.py`.

| CAO event             | AG-UI type             | Notes |
|-----------------------|------------------------|-------|
| `session.created`     | `RUN_STARTED`          | `thread_id` = `run_id` = session_name |
| `session.killed`      | `RUN_FINISHED`         | status: "terminated" |
| `terminal.created`    | `STEP_STARTED`         | `step_id` = terminal_id; `step_name` = agent_name |
| `terminal.killed`     | `STEP_FINISHED`        | |
| `message.sent`        | `TEXT_MESSAGE_CONTENT` | `delta` is empty (privacy); metadata only |
| (every other)         | `RAW`                  | `cao_type` field preserves original semantics |

Future commits add `STATE_SNAPSHOT` / `STATE_DELTA` for dashboard
snapshots and `TOOL_CALL_*` once CAO surfaces individual tool-call
events.

## 6. Wire protocol

```
GET /agui/v1/stream?since=<iso8601>&access_token=<JWT>
```

Response is `text/event-stream`:

```
event: RUN_STARTED
data: {"thread_id":"cao-x","run_id":"cao-x","traceparent":null}

event: STEP_STARTED
data: {"step_id":"abc12345","step_name":"developer","provider":"claude_code"}

event: RAW
data: {"cao_type":"terminal.interrupt","payload":{"terminal_id":"abc12345"}}
```

Behavior:
1. Connect: replay buffered events from `event_log.history(since=...)`,
   each transformed via `to_agui_event(...)`.
2. Continue: subscribe to the in-process SSE bus; every published event
   re-transforms and streams.
3. Disconnect: clean up the per-subscriber queue.

Auth: when `AUTH0_DOMAIN` is set, `access_token` query parameter is
required (native EventSource can't send `Authorization:` headers).
`cao:read` scope required.

## 7. Multi-instance config

PWA stores instance URLs in IndexedDB:

```ts
interface CaoInstance {
  id: string;          // uuid
  url: string;         // e.g. "http://localhost:9889"
  label: string;       // user-friendly name
  added_at: string;    // ISO-8601
}
```

Each instance is one tab/panel; the user adds via an `<dialog>`-based
form that validates with `HEAD /health` before persisting.

mDNS / Bonjour discovery is v2 (documented under §9).

## 8. CORS posture

| Env var | Required? | Default | Notes |
|---|---|---|---|
| `CAO_PWA_ORIGIN` | No | (empty) | Comma-separated allow-list. Appended to `CORS_ORIGINS`. Empty = localhost-only. |

`TrustedHostMiddleware` is unaffected — it gates `Host` header (DNS
rebinding), not Origin (CORS).

## 9. What ships in v1 vs deferred

**v1 (this PR):**
- AG-UI HTTP+SSE endpoint at `/agui/v1/stream`
- CAO→AG-UI adapter with 6 mapped + RAW fallback
- `CAO_PWA_ORIGIN` env-driven CORS widening
- `cao_pwa/` Vite + React scaffold
- Multi-instance picker (IndexedDB-backed)
- Read-only `DashboardView` consuming the AG-UI stream
- Tests + docs

**Deferred to follow-up:**

| Item | Why | Tracking |
|---|---|---|
| **Bidirectional commands** (PWA sends `submit_command`) | Requires Auth0 Bearer-input UX. v2 PR. | `cao-agui-mutations-2026-NN-NN-v1.md` |
| **WebSocket terminal stream** | Same auth pattern needed; also flagged in Auth0 RFC §9 | Shared follow-up |
| **mDNS / Bonjour discovery** | Browser support inconsistent; manual entry covers v1 | v2 |
| **Cross-instance aggregated view** | One-tab-per-instance is v1; cross-instance is v3 | v3 |
| **AG-UI TOOL_CALL_* events** | CAO doesn't yet surface per-tool-call events | When the event stream emits them |
| **Shared-component npm workspace** | `cao_pwa` duplicates types from `cao_mcp_apps` | v2 chore |
| **Mobile responsive layout** | Hard with current xterm.js / container queries | v3 |

## 10. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| AG-UI spec evolves; the 16-event names change | Med | Med | Adapter is a single file; mapping is version-pinned. |
| EventSource auth via query param leaks token to access logs | Med | Med | Document operator should configure log redaction. Bearer-via-headers is impossible with native EventSource. |
| PWA bundle bloat | Low | Low | No xterm.js in v1; single-file Vite + React = ~140 KB gz. |
| IndexedDB compat across Safari versions | Low | Low | `fake-indexeddb` in tests; documented baseline. |
| CORS widening misconfigured → wildcard | Low | High | Comma-split + filter empty; explicit `CAO_PWA_ORIGIN` (no wildcards); tested. |
| Replay buffer + live stream race emits duplicate events | Low | Low | Each event has a unique `id` from `event_log.append`; PWA dedups in its reducer. |

## 11. Verification

```sh
# Python unit tests
uv run pytest test/services/test_agui_stream_mapping.py \
              test/api/test_agui_stream.py -v
uv run pytest test/ --ignore=test/providers/test_q_cli_integration.py \
                    --ignore=test/providers/test_kiro_cli_integration.py \
                    --ignore=test/e2e -m "not e2e" --no-cov -q

# PWA tests
cd cao_pwa
npm ci && npx tsc --noEmit && npm test && npm run build
cd -

# End-to-end smoke (default-off CORS)
uv run cao-server &
SERVER_PID=$!
curl -s "http://localhost:9889/agui/v1/stream?since=2020-01-01T00:00:00Z" \
     --max-time 3 -H "Accept: text/event-stream" | head -20
# Expect: SSE replay of any buffered events as AG-UI typed events
kill $SERVER_PID

# CORS smoke
unset CAO_PWA_ORIGIN
uv run cao-server &
SERVER_PID=$!
curl -s -H "Origin: https://cao.example.com" -X OPTIONS \
     http://localhost:9889/agui/v1/stream -i | head -3
# Expect: NO Access-Control-Allow-Origin header
kill $SERVER_PID

export CAO_PWA_ORIGIN="https://cao.example.com"
uv run cao-server &
SERVER_PID=$!
curl -s -H "Origin: https://cao.example.com" -X OPTIONS \
     http://localhost:9889/agui/v1/stream -i | grep -i access-control
# Expect: Access-Control-Allow-Origin: https://cao.example.com
kill $SERVER_PID
```

---

## Version history

| Version | Date | Author | Changes |
|---|---|---|---|
| v1 | 2026-05-11 | Patrick Lauer | Initial L2 RFC. Ships AG-UI HTTP+SSE adapter, /agui/v1/stream endpoint, CAO_PWA_ORIGIN CORS widening, cao_pwa/ scaffold with multi-instance IndexedDB picker. Defers bidirectional commands, WS terminal stream, mDNS, cross-instance aggregation. |
