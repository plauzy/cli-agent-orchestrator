# cao-auth0-websocket-2026-05-11-v1

| Field | Value |
|---|---|
| **Created** | 2026-05-11 |
| **Version** | v1 |
| **Status** | Draft — sibling RFC to `cao-auth0-mcp-integration-2026-05-11-v1.md` (closes its §9 row 1) |
| **Author** | Patrick Lauer |
| **Target repo** | https://github.com/awslabs/cli-agent-orchestrator |
| **Target branch** | `main` (commit baseline as of 2.5.0a3) |

---

## Table of contents

1. [Context](#1-context)
2. [Design goals](#2-design-goals)
3. [Threat model](#3-threat-model)
4. [Handshake and close codes](#4-handshake-and-close-codes)
5. [Scope policy](#5-scope-policy)
6. [Client transport conventions](#6-client-transport-conventions)
7. [Configuration](#7-configuration)
8. [Backwards compatibility](#8-backwards-compatibility)
9. [What ships in v1 vs deferred](#9-what-ships-in-v1-vs-deferred)
10. [Operational concerns](#10-operational-concerns)
11. [Risks](#11-risks)
12. [Verification](#12-verification)

---

## 1. Context

The parent `cao-mcp-apps-implementation-plan-2026-05-10-v2.md` §11 noted
that `<AgentDetail>` renders arbitrary terminal output via xterm.js and
gated the trust boundary on loopback only. The Auth0 sibling
(`cao-auth0-mcp-integration-2026-05-11-v1.md`) then closed the auth gap
on the FastAPI mutation endpoints — but §9 row 1 and §11 row 5 explicitly
deferred the matching work for the WebSocket terminal endpoint
`/terminals/{id}/ws`, citing the small WS-handshake delta and the desire
to keep the L3 v1 surface small.

This RFC closes that gap. In auth-enabled deployments the WebSocket
endpoint becomes a scoped resource: `cao:read` to connect (streaming
output), `cao:write` to send `input` / `resize` frames. In default-off
deployments behavior is byte-identical to 2.5.0a3 — the existing
loopback peer check at `api/main.py:1232-1235` remains the only gate.

The implementation reuses `cli_agent_orchestrator/security/auth.py`
(`auth_enabled`, `extract_scopes_from_token`, the scope constants). No
new public surface in `security/`; the WS-specific glue lives next to
the existing `_require_read` / `_require_write` helpers in
`api/main.py`.

## 2. Design goals

| Goal | Mechanism |
|---|---|
| **Backwards-compatible default** | `auth_enabled() == False` → no token required, loopback check is the boundary (current 2.5.0a3 contract). The 2144-test suite passes unchanged. |
| **Browser-native transport** | JWT travels as `Sec-WebSocket-Protocol: cao.bearer.<jwt>`. Browsers cannot set custom headers on the WS handshake; the subprotocol array argument to `new WebSocket(url, subprotocols)` is the canonical workaround. |
| **No URL leakage** | Tokens never appear in query strings (server-side access logs, browser history, referer chains). |
| **Read-only viewer mode** | `cao:read` scope alone permits streaming output, but input/resize frames are dropped server-side. Falls out of the existing scope taxonomy without a new role. |
| **Single source of truth** | Reuses `extract_scopes_from_token` directly; no duplicate JWT-validation path. Same JWKS cache, same audience check, same leeway. |

## 3. Threat model

| Threat | Mitigation |
|---|---|
| **Unauthenticated PTY access on auth-enabled host** | Subprotocol-bearer check before `accept()`; missing/invalid token closes 4401 before any PTY is allocated. |
| **Read-scoped operator typing keystrokes** | Per-frame `cao:write` check inside `_forward_input`. Frames without the scope are dropped + logged once per connection. |
| **Subprotocol echo trick** | Server only `accept()`s subprotocol `"cao.bearer"` (without the JWT suffix); the JWT is consumed and validated, not echoed back to the client. |
| **Token-in-URL leakage** | Not applicable — token rides in the WebSocket subprotocol header, not the query string. |
| **Defense-in-depth vs the loopback gate** | The existing 1232-1235 loopback check stays. Even in auth-enabled mode, non-loopback peers are rejected before token parsing. Two independent gates. |
| **Token replay across CAO instances** | Inherited from the Auth0 sibling: `aud` is bound to `AUTH0_AUDIENCE` (RFC 8707). A token issued for a different CAO host fails audience validation. |
| **JWT material in browser memory** | Same exposure as the FastAPI Bearer path. Operators rotate via the IdP; the v2 plan §11.1 documents refresh-token rotation as a client-side concern. |

## 4. Handshake and close codes

The WebSocket handshake is amended to:

1. Loopback peer check (unchanged, line 1232-1235).
2. Subprotocol scan: locate the first protocol with prefix `cao.bearer.`; strip the prefix; pass the remainder to `extract_scopes_from_token`.
3. Default-off short-circuit: if `auth_enabled() == False`, treat as `ALL_SCOPES` and skip the JWT path entirely.
4. Scope check: `cao:read` required to proceed.
5. `accept(subprotocol="cao.bearer")` on success (echoes only the bare protocol name, never the JWT).

Close codes:

| Code | Reason | Meaning |
|---|---|---|
| 4003 | `WebSocket access is restricted to localhost` | Existing loopback gate (unchanged). |
| 4401 | `Unauthorized` | Auth-enabled and no `cao.bearer.*` subprotocol present, or token failed JWT validation. Mirrors HTTP 401 semantics. |
| 4403 | `Insufficient scope` | Auth-enabled, valid token, but `cao:read` not in granted scopes. Mirrors HTTP 403 semantics. |
| 4004 | `Terminal not found` | Existing (unchanged). |

The 4401/4403 codes follow the WebSocket close-code convention of `4xxx`
for application-defined errors that mirror HTTP semantics. They are
distinct from the 1008 (policy violation) the loopback path uses,
because callers may want to distinguish "no token" from "wrong origin".

## 5. Scope policy

| Action | Scope required |
|---|---|
| Open the connection (stream output) | `cao:read` |
| `type: "input"` frame (PTY keystrokes) | `cao:write` |
| `type: "resize"` frame (PTY size change) | `cao:write` |

`cao:write` is checked **per frame** inside `_forward_input`. A
read-only viewer sees output but its keystrokes silently drop. The
read-only path logs a single warning per connection ("write frame
dropped — caller lacks cao:write") to keep the log volume bounded.

The choice to drop silently instead of closing the connection is
deliberate: a misconfigured client (e.g. a screen-share viewer that
accidentally proxies keystrokes) is far more common than an attacker,
and dropping the frame preserves the legitimate output stream the user
came for.

## 6. Client transport conventions

| Client | Token source | Subprotocol construction |
|---|---|---|
| `web/src/components/TerminalView.tsx` (bundled web UI) | `URLSearchParams(location.search).get("access_token")` first, else `localStorage.getItem("cao.auth.token")` | `new WebSocket(url, ["cao.bearer." + token])` when present; bare `new WebSocket(url)` when absent (default-off path). |
| `cao_mcp_apps/src/agent/AgentTerminal.tsx` (MCP App iframe) | Same `?access_token=` URL param; the MCP host carries the param through when navigating the iframe. | Same. |
| `cao_pwa/` | Not affected — PWA only uses `EventSource` against `/agui/v1/stream` today. WebSocket consumer would be a follow-up chunk. |
| Direct clients (curl, scripts) | `--header 'Sec-WebSocket-Protocol: cao.bearer.<jwt>'` via `wscat -H` or equivalent. | Documented in `docs/auth.md`. |

The `?access_token=` query convention aligns with the existing PWA
pattern at `cao_pwa/src/api.ts:25` for the AG-UI SSE stream. Browsers
strip query strings from `Referer` for the WebSocket-upgrade request,
so the token is not leaked across origins — but operators should still
avoid pasting URLs containing tokens.

## 7. Configuration

No new environment variables. The WebSocket auth path consumes the same
config as the Auth0 sibling:

- `AUTH0_DOMAIN` — unset disables auth (loopback-only contract).
- `AUTH0_AUDIENCE` — required when `AUTH0_DOMAIN` is set.
- `CAO_AUTH_JWKS_URI`, `CAO_AUTH_JWKS_CACHE_TTL`, `CAO_AUTH_CLOCK_LEEWAY` — inherited.

## 8. Backwards compatibility

A 2.5.0a3 → 2.5.0a4 upgrade with `AUTH0_DOMAIN` unset is byte-identical
on the WS path. The TestClient suite asserts this directly
(`test_terminals.py::TestWebSocketAuth::test_default_off_connects_without_subprotocol`).
Operators running with auth enabled who had been tolerating the WS gap
must update their web UI access pattern to include `?access_token=` or
populate `localStorage["cao.auth.token"]`; the upgrade note in
`docs/auth.md` calls this out.

## 9. What ships in v1 vs deferred

**v1 (this PR):**

- Subprotocol-bearer JWT extraction in `terminal_ws`.
- 4401 / 4403 close codes.
- `cao:read` on connect, `cao:write` per input/resize frame.
- Client patches for the bundled web UI and the MCP Apps agent iframe.
- 6 new test cases (`TestWebSocketAuth`).
- `docs/auth.md` WebSocket terminals section.

**Deferred to follow-up sibling-PRs:**

| Item | Why deferred | Tracking |
|---|---|---|
| **PWA bidirectional WebSocket** | The PWA only uses SSE today. A WS-based command channel from the PWA back to CAO is item #2 on the original 2.5.0a3 deferred menu. | Separate RFC. |
| **Per-connection rate limiting** | WS sessions are long-lived and a single connection can in theory flood the server with input frames. v1 relies on the existing tmux paste-buffer chunking; rate-limit middleware is a v2 concern. | Future. |
| **WebSocket-level RBAC beyond read/write** | Some operators want admin-only on `resize` (rare). Not in this PR. | Future RFC. |
| **Ticket exchange (HTTP → WS)** | Considered (RFC §2 alternatives). Subprotocol path chosen for simplicity; ticket exchange is a future-tractable hardening if browser sandbox attacks against `Sec-WebSocket-Protocol` headers materialize. | Future RFC. |

## 10. Operational concerns

**Web UI access pattern in auth-enabled mode.** Operators must now
either (a) bookmark `http://localhost:9889/?access_token=<jwt>` or
(b) set `localStorage["cao.auth.token"] = "<jwt>"` once per browser.
The web UI does not implement a login flow; the JWT is provisioned
out-of-band per the parent §11.1 contract.

**Close-code visibility in the browser.** Chrome's DevTools surface
4401/4403 in the Network → WS panel with the reason text. Firefox
surfaces the close code only. The 4401 reason `"Unauthorized"` and
4403 reason `"Insufficient scope"` are stable strings the operator
runbook can grep for.

**JWKS cache on the WS path.** The same per-process JWKS cache the
HTTP path uses is shared with the WS path (in-process, lock-protected
dict in `auth.py`). A long-lived WS connection holds no JWKS state;
new connections re-read the cache. Operators rotating IdP signing keys
should plan for one full `CAO_AUTH_JWKS_CACHE_TTL` of drift, identical
to the HTTP path.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Client misses the subprotocol upgrade and connections silently fail in auth-enabled mode** | Med | Med | Close-code 4401 with stable reason text. `docs/auth.md` upgrade note. Bundled web UI patched in this PR. |
| **Sec-WebSocket-Protocol header logged at intermediary proxies** | Low | Low | CAO is localhost-only; no intermediary proxies in the recommended posture. Documented for operators fronting CAO with a reverse proxy. |
| **Per-frame `cao:write` check adds latency to input** | Low | Low | Pure in-memory list check; benchmarked to be ~10ns. The PTY chunking loop at line 1316-1319 dominates. |
| **Read-only viewer mode confuses operators when keystrokes don't appear** | Med | Low | Single per-connection warning log. `docs/auth.md` documents the viewer-mode UX. Frontend could surface a banner — out of scope for v1. |
| **Subprotocol token leak via browser extension** | Low | Med | Equivalent exposure to existing `Authorization: Bearer` headers. The browser is the trust boundary. |

## 12. Verification

End-to-end smoke (default-off — must remain byte-identical):

```sh
unset AUTH0_DOMAIN AUTH0_AUDIENCE
uv run cao-server &
# Open http://localhost:9889; terminal stream connects without token.
```

End-to-end smoke (auth-enabled, three scope postures):

```sh
export AUTH0_DOMAIN=tenant.auth0.com
export AUTH0_AUDIENCE=cao://localhost
uv run cao-server &

# 1. No token → 4401
wscat -c ws://localhost:9889/terminals/t1/ws  # closes 4401

# 2. cao:read only → connects, output streams, input dropped
wscat -c ws://localhost:9889/terminals/t1/ws \
      -s "cao.bearer.<READ_ONLY_JWT>"
# Type a keystroke; server logs "write frame dropped".

# 3. cao:read + cao:write → full operator
wscat -c ws://localhost:9889/terminals/t1/ws \
      -s "cao.bearer.<READ_WRITE_JWT>"
# Keystrokes are processed.
```

Unit tests (`test/api/test_terminals.py::TestWebSocketAuth`):

| Case | Expected |
|---|---|
| Default-off, no subprotocol | Connects (default-off contract). |
| Auth-enabled, no subprotocol | Closes 4401. |
| Auth-enabled, malformed `cao.bearer.` value | Closes 4401. |
| Auth-enabled, valid JWT without `cao:read` | Closes 4403. |
| Auth-enabled, `cao:read` only, input frame sent | Connects; `os.write` not called. |
| Auth-enabled, `cao:read` + `cao:write`, input frame sent | Connects; `os.write` called. |
