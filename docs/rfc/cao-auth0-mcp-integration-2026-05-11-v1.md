# cao-auth0-mcp-integration-2026-05-11-v1

| Field | Value |
|---|---|
| **Created** | 2026-05-11 |
| **Version** | v1 |
| **Status** | Draft — sibling RFC to `cao-mcp-apps-implementation-plan-2026-05-10-v2.md` |
| **Author** | Patrick Lauer |
| **Target repo** | https://github.com/awslabs/cli-agent-orchestrator |
| **Target branch** | `main` (commit baseline as of PR #19 merge) |

---

## Table of contents

1. [Context](#1-context)
2. [Design goals](#2-design-goals)
3. [Threat model](#3-threat-model)
4. [Protected Resource Metadata](#4-protected-resource-metadata)
5. [FastAPI scope enforcement](#5-fastapi-scope-enforcement)
6. [MCP-tool-layer pre-check](#6-mcp-tool-layer-pre-check)
7. [Snapshot scope propagation](#7-snapshot-scope-propagation)
8. [Configuration](#8-configuration)
9. [What ships in v1 vs deferred](#9-what-ships-in-v1-vs-deferred)
10. [Operational concerns](#10-operational-concerns)
11. [Risks](#11-risks)
12. [Verification](#12-verification)

---

## 1. Context

CAO 2.5.0a2 ships the cao-mcp-apps v2 L1 surface (PRs #16-19): the
operator dashboard renders inline inside any SEP-1865 MCP host, the
seven `submit_command` kinds do real work, and the FastAPI server's
localhost-only Host-header check is the entire security boundary. That
posture is correct for a single-developer install — every CAO release
since v1 has assumed the loopback is trusted.

It is **not** correct for the deployments the v2 plan §16 explicitly
flagged: team-shared CAO instances where a team lead holds a read-only
token, ChatGPT/Claude.ai users whose iframe sandboxes need a
discoverable authorization server, multi-tenant Auth0 + CAO setups
where different teams' tokens point at the same CAO host.

This RFC adds **OAuth 2.1 + RFC 9728 Protected Resource Metadata**
support to CAO without disturbing the localhost path. Default-off:
unset `AUTH0_DOMAIN` and v2.5.0a2 behavior is byte-identical. Opt-in:
set `AUTH0_DOMAIN` + `AUTH0_AUDIENCE` and every mutation endpoint
requires a Bearer token with the right scope.

The v2 plan §11.1 framed this as a sibling RFC because (a) Auth0 for
MCP went GA in May 2026 with a clean OAuth 2.1 + DCR + OBO surface
specifically tuned to MCP servers, and (b) the L1 work needed to ship
on the localhost contract without waiting for auth design. With L1
merged, this RFC closes the L3 gap.

## 2. Design goals

| Goal | Mechanism |
|---|---|
| **Backwards-compatible default** | `auth_enabled()` returns False when `AUTH0_DOMAIN` is unset; every dependency returns the full scope set. |
| **Single source of truth for scope decisions** | `_REQUIRED_SCOPE_BY_KIND` table consulted from both the MCP tool layer (UX-friendly precheck) and the FastAPI endpoint layer (defense-in-depth backstop). |
| **Discoverable** | `/.well-known/oauth-protected-resource` (RFC 9728) on the existing :9890 agent-card listener tells MCP clients where to get tokens. |
| **No new key material** | JWKS validation only. CAO doesn't issue tokens; it's a resource server, not an authorization server. |
| **Friendly errors** | Insufficient scope returns 403 with the required scope in the body. The MCP tool layer mirrors this so the iframe surfaces a clear "you can't do that" message before the REST round-trip. |
| **Forward-compatible with OBO / DCR / multi-tenant** | All deferred surfaces (§9) are documented and explicitly out-of-scope; the single-mutation-choke-point and the PRM endpoint are the foundations they build on. |

## 3. Threat model

| Threat | Mitigation |
|---|---|
| **Read-only user issuing destructive commands** | Per-scope authorization at `submit_command` + every mutation endpoint. The frontend disables the buttons; the server enforces independently. |
| **Iframe bypass — attacker hits REST surface directly** | FastAPI endpoint dependency enforces same scope check unconditionally. The MCP tool layer is convenience; the REST layer is the security boundary. |
| **Cross-server token replay** | RFC 8707 resource indicator: tokens carry `aud=cao://<host>`; CAO validates audience against `AUTH0_AUDIENCE`. |
| **JWKS endpoint MITM** | TLS to the IdP. JWKS URI defaults to `https://<AUTH0_DOMAIN>/.well-known/jwks.json`; the configured domain is the trust anchor. |
| **JWKS cache poisoning** | Per-process in-memory cache only; no shared state across CAO instances. |
| **Stale token after rotation** | Token `exp` is validated with 60 s leeway. Operators rotate by issuing a new token; revocation is the IdP's responsibility. |
| **Defense-in-depth for the dashboard `<TaskControl>`** | The frontend reads `scopes` from the initial tool result and disables controls. Spoofing the array doesn't bypass server-side enforcement. |

~~Explicitly out of scope: **WebSocket terminal stream auth** at
`/terminals/{id}/ws`. The existing localhost-only middleware still
gates this; a follow-up sibling-PR will plumb the same Bearer check.~~

**Update (2.5.0a4):** WebSocket auth shipped — see sibling RFC
[`cao-auth0-websocket-2026-05-11-v1.md`](cao-auth0-websocket-2026-05-11-v1.md).
The same Bearer scopes are now enforced via the `cao.bearer.<jwt>`
subprotocol on `/terminals/{id}/ws`.

## 4. Protected Resource Metadata

CAO publishes RFC 9728 PRM at:

```
GET /.well-known/oauth-protected-resource
```

on the **:9890 agent-card listener** (not the main FastAPI server) so
external MCP clients can discover the resource without hitting
`TrustedHostMiddleware`. Returns:

```json
{
  "resource": "cao://my-host",
  "authorization_servers": ["https://tenant.auth0.com/"],
  "bearer_methods_supported": ["header"],
  "scopes_supported": ["cao:read", "cao:write", "cao:admin"],
  "resource_documentation": "https://github.com/awslabs/cli-agent-orchestrator/blob/main/docs/auth.md"
}
```

When `AUTH0_DOMAIN` is unset the route returns 404 — discovery
correctly signals "no auth required, treat as localhost-only".

## 5. FastAPI scope enforcement

Every mutation endpoint adds `_scopes: List[str] = Depends(_require_X)`
to its signature, where `_require_X` is one of three helpers
(`_require_read`, `_require_write`, `_require_admin`) that delegate to
`get_current_scopes` and raise 403 on missing scope.

Scope map (v1):

| Endpoint pattern | Scope |
|---|---|
| `POST /sessions` | `cao:write` |
| `POST /sessions/{name}/assign` | `cao:write` |
| `POST /sessions/{name}/terminals` | `cao:write` |
| `POST /terminals/{id}/input` | `cao:write` |
| `POST /terminals/{id}/exit` | `cao:write` |
| `POST /terminals/{id}/{interrupt,pause,resume}` | `cao:write` |
| `POST /terminals/{id}/inbox/messages` | `cao:write` |
| `DELETE /sessions/{name}` | `cao:admin` |
| `DELETE /terminals/{id}` | `cao:admin` |
| `POST /flows{,/{name}/enable,/disable,/run}` | `cao:admin` |
| `DELETE /flows/{name}` | `cao:admin` |
| `POST /settings/agent-dirs` | `cao:admin` |

Read endpoints don't currently enforce scopes; the default-off mode
treats every caller as trusted on read, and enabling auth means tokens
still get the full read view. A future tightening would add
`Depends(_require_read)` to GETs.

## 6. MCP-tool-layer pre-check

`_submit_command_impl` consults a static dict:

```python
_REQUIRED_SCOPE_BY_KIND = {
    "send_message": "cao:write",
    "assign": "cao:write",
    "create_session": "cao:write",
    "interrupt": "cao:write",
    "pause": "cao:write",
    "resume": "cao:write",
    "shutdown_session": "cao:admin",
}
```

On insufficient scope, returns:

```json
{
  "success": false,
  "error": "insufficient scope",
  "required": "cao:admin",
  "granted": ["cao:read"]
}
```

This is **not the security boundary** — the FastAPI endpoint enforces
identically — but it gives the iframe a fast, friendly error that
includes the required scope so the operator knows what token they
need.

## 7. Snapshot scope propagation

`mcp_server/server.py::_build_dashboard_payload` reads scopes from
`CAO_AUTH_TOKEN` (env var the MCP host sets when launching
`cao-mcp-server`) via `security.get_scopes_for_local_token`. The
scopes thread through `build_dashboard_snapshot(...)` into the iframe
payload. `<TaskControl>` already (Phase 1) disables destructive
controls when `scopes` lacks `cao:admin` — no React changes needed.

When auth is disabled, `get_scopes_for_local_token` returns the full
set, so the iframe's `canMutate` / `canDestructive` flags evaluate
True — Phase 1 behavior preserved.

## 8. Configuration

| Env var | Required? | Default | Notes |
|---|---|---|---|
| `AUTH0_DOMAIN` | No (unset = off) | — | Auth0 tenant domain (e.g. `tenant.auth0.com`). Setting this enables enforcement. |
| `AUTH0_AUDIENCE` | When `AUTH0_DOMAIN` is set | — | Resource indicator (RFC 8707). Token `aud` must match. |
| `CAO_AUTH_JWKS_URI` | No | `https://<AUTH0_DOMAIN>/.well-known/jwks.json` | Override for non-Auth0 IdPs (Keycloak, Okta, etc.). |
| `CAO_AUTH_JWKS_CACHE_TTL` | No | `3600` (seconds) | How long the in-process JWKS cache holds keys. |
| `CAO_AUTH_CLOCK_LEEWAY` | No | `60` (seconds) | `iat`/`exp` validation leeway for clock skew. |
| `CAO_AUTH_TOKEN` | No (set by MCP host) | — | Operator's Bearer token. Read by `cao-mcp-server` to populate `snapshot.scopes` + run the precheck in `submit_command`. |

## 9. What ships in v1 vs deferred

**v1 (this PR):**
- PRM endpoint at `/.well-known/oauth-protected-resource`
- JWT validation (RS256, JWKS, audience check)
- Scope enforcement at FastAPI mutation endpoints
- Scope precheck at `_submit_command_impl`
- Snapshot scope propagation
- `_meta.ui.requiredScopes` annotation
- 49+ unit tests + RFC + operator docs

**Deferred to follow-up sibling-PRs:**

| Item | Why deferred | Tracking |
|---|---|---|
| ~~**WebSocket terminal stream auth** (`/terminals/{id}/ws`)~~ | ~~Same Bearer check; same dependency; needs a small WS-handshake path. Out of scope for v1 so the surface stays small.~~ | **Shipped 2.5.0a4** — [`cao-auth0-websocket-2026-05-11-v1.md`](cao-auth0-websocket-2026-05-11-v1.md). |
| **On-Behalf-Of (OBO) token exchange** (RFC 8693) | Lets an MCP host swap its token for a CAO-scoped one. Useful for chains (Claude Desktop → CAO → other-MCP-server) but not required for v1. | `cao-auth0-obo-2026-NN-NN-v1.md` |
| **Dynamic Client Registration** (RFC 7591) | Auto-registers MCP hosts in the IdP. v1 operators register manually. | Auth0-vendor concern; CAO doesn't host the AS. |
| **Multi-tenant CAO** | Different teams' Auth0 tenants pointing at the same CAO instance. The data model doesn't yet partition state by tenant. | Major effort; separate RFC. |
| **Read endpoint scope enforcement** | Reads default to "trusted in localhost mode"; v1 doesn't tighten this. | Trivial follow-up. |
| **Token introspection (RFC 7662) fallback** | For opaque tokens that can't be JWT-validated. v1 is JWT-only. | IdP-specific. |
| **Refresh token rotation** | CAO is a resource server; rotation is the client's concern. Document only. | Operator runbook. |

## 10. Operational concerns

**JWKS caching.** First request to a hot CAO instance fetches the JWKS
synchronously. Subsequent validations hit the in-memory cache until
`CAO_AUTH_JWKS_CACHE_TTL` elapses. Operators rotating their IdP signing
keys should plan for one full TTL of token-validation drift unless they
manually invalidate the cache (restart CAO or hit a future
`/admin/jwks/refresh` endpoint).

**Clock skew.** Auth0 + CAO can disagree on `iat`/`exp` by up to
~30 s in practice. The default 60 s leeway covers this. Operators
running CAO on a clock-drifted host should bump
`CAO_AUTH_CLOCK_LEEWAY`.

**Token leakage.** `CAO_AUTH_TOKEN` is passed via env var to
`cao-mcp-server`. The MCP host owns the secret; CAO never logs the
token body (the existing privacy boundary that strips `message` from
the rolling event log already covers this).

**Audience confusion.** A common misconfiguration: operator sets
`AUTH0_AUDIENCE=https://cao.example.com` but their token has
`aud=cao://example.com`. CAO returns 401 with a clear message naming
the expected audience. The PRM endpoint also advertises the expected
audience under `resource`.

**Backwards compatibility.** A v2.5.0a2 → v2.5.0a3 upgrade with
`AUTH0_DOMAIN` unset is byte-identical. The 2144-test Python suite
passes in default-off mode with no test changes.

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Read endpoints not scope-gated → information disclosure under auth | Low | Med | Documented in §9; tightening is a one-line per-endpoint addition. v1 ships a working defense-in-depth on mutations; reads stay as before. |
| JWKS endpoint flaky on first request → 503 chain | Med | Med | 1 h cache; surface clear 503 on cache miss + upstream fail. |
| Scope precheck in MCP layer disagrees with FastAPI endpoint | Low | High | Single dict (`_REQUIRED_SCOPE_BY_KIND`); table-driven test (`test_submit_command_authz.py`) asserts the mapping; FastAPI tests (`test_endpoint_authz.py`) assert the matching scope per endpoint. |
| Operator misconfigures audience → 401 storm | Med | Med | Clear error message naming expected `aud`. PRM endpoint advertises it. |
| ~~WebSocket auth gap~~ | ~~High in auth-enabled mode~~ | ~~Med~~ | **Mitigated 2.5.0a4** — sibling RFC `cao-auth0-websocket-2026-05-11-v1.md` ships subprotocol-bearer enforcement with the same scope taxonomy. |
| RFC scope-creeps the PR | Med | Med | Code ships the backbone; the design contract is the RFC. Reviewers comment on the design without blocking the backbone landing. |

## 12. Verification

End-to-end smoke (no-auth mode — must remain unchanged):

```sh
unset AUTH0_DOMAIN AUTH0_AUDIENCE
uv run cao-server &
SERVER_PID=$!
curl -s http://localhost:9889/sessions          # 200 OK, empty list
curl -s http://localhost:9890/.well-known/oauth-protected-resource  # 404
kill $SERVER_PID
```

Auth-enabled mode (hand-signed test token):

```sh
export AUTH0_DOMAIN="test.local"
export AUTH0_AUDIENCE="cao://localhost"
# Generate a read-only token via test helper:
READ_TOKEN=$(uv run python -m test.security.tokens_gen --scopes='cao:read')
ADMIN_TOKEN=$(uv run python -m test.security.tokens_gen --scopes='cao:read cao:write cao:admin')

uv run cao-server &
SERVER_PID=$!
curl -s -H "Authorization: Bearer $READ_TOKEN" \
     http://localhost:9889/sessions                                       # 200
curl -s -H "Authorization: Bearer $READ_TOKEN" \
     -X DELETE http://localhost:9889/sessions/cao-x                       # 403
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
     -X DELETE http://localhost:9889/sessions/cao-x                       # 200 or 404
curl -s http://localhost:9890/.well-known/oauth-protected-resource | jq   # PRM body
kill $SERVER_PID
```

Unit + parametric coverage:

- `test/security/test_auth.py` — 15 tests covering JWT happy/expired/
  wrong-audience/permissions-fallback/JWKS cache, default-off mode,
  scope-check 403.
- `test/agent_card/test_oauth_prm.py` — PRM 404-when-off, 200-when-on.
- `test/api/test_endpoint_authz.py` — 22 parametric tests asserting
  every mutation endpoint enforces the right scope (403 with
  insufficient, passes precheck with admin).
- `test/mcp_server/test_submit_command_authz.py` — 9 parametric tests
  asserting the MCP-tool precheck mirrors the endpoint authz.
- Existing 2144-test suite stays green in default-off mode (zero
  regressions).

Manual MCP smoke (Claude Desktop):

1. Configure Claude Desktop to launch `cao-mcp-server` with
   `CAO_AUTH_TOKEN=<read-scoped JWT>`, `AUTH0_DOMAIN`, and
   `AUTH0_AUDIENCE` in the env block.
2. Open the dashboard. Verify Shutdown / Interrupt / Pause / Resume
   are greyed out — `snapshot.scopes === ["cao:read"]`.
3. Replace the env var with an admin-scoped token. Reload. Verify the
   destructive controls enable.
4. From a separate shell, `curl -X DELETE` against `/sessions/...`
   with the read-only token → 403 with `cao:admin` in the message.

---

## Version history

| Version | Date | Author | Changes |
|---|---|---|---|
| v1 | 2026-05-11 | Patrick Lauer | Initial draft. Sibling RFC to cao-mcp-apps-implementation-plan-2026-05-10-v2 §11.1. Ships PRM endpoint, JWT validation, scope enforcement at FastAPI + MCP tool layers, snapshot propagation, `_meta.ui.requiredScopes`. Defers WS auth, OBO, DCR, multi-tenant to follow-up sibling PRs. |
| v1.1 | 2026-05-11 | Patrick Lauer | §3 / §9 / §11 amended in-place: WebSocket terminal stream auth is no longer deferred — see sibling RFC `cao-auth0-websocket-2026-05-11-v1.md` (shipped 2.5.0a4). No design changes to the FastAPI / MCP surface this RFC defines. |
