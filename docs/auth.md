# Authentication & authorization

CAO ships **OAuth 2.1 + Auth0-for-MCP** support.

**Default is off.** With `AUTH0_DOMAIN` unset, every CAO release before
This release behaves identically: localhost-only Host-header check, no auth
required. The opt-in switch flips when an operator points CAO at their
IdP.

## When to enable auth

Enable auth when **any** of these is true:

- CAO runs on a host accessible to multiple users (team SSH tunnel,
  shared workstation, cloud VM).
- You want a read-only role for a team lead who shouldn't be able to
  shut down sessions.
- Your MCP host (Claude Desktop, ChatGPT, Cursor) talks to a remote
  CAO instance over a non-loopback connection.

Don't enable auth when:

- CAO runs locally on your laptop with only your processes hitting it.

## Quick setup (Auth0)

1. **Create an API in your Auth0 tenant.**
   - Identifier (audience): `cao://my-host` — this is what CAO's
     `AUTH0_AUDIENCE` env var must match.
   - Signing algorithm: RS256.
   - Enable RBAC + add permissions in the API settings: `cao:read`,
     `cao:write`, `cao:admin`.

2. **Assign permissions to your users.**
   - Each user (or Machine-to-Machine application) gets one or more of
     the three scopes. The frontend disables UI affordances they lack;
     the backend enforces independently.

3. **Configure CAO.**

   ```sh
   export AUTH0_DOMAIN="tenant.auth0.com"
   export AUTH0_AUDIENCE="cao://my-host"
   uv run cao-server
   ```

4. **Configure your MCP host.**
   Pass an access token to `cao-mcp-server` via the `CAO_AUTH_TOKEN`
   env var. For Claude Desktop:

   ```jsonc
   {
     "mcpServers": {
       "cao": {
         "command": "uv",
         "args": ["run", "cao-mcp-server"],
         "env": {
           "AUTH0_DOMAIN": "tenant.auth0.com",
           "AUTH0_AUDIENCE": "cao://my-host",
           "CAO_AUTH_TOKEN": "eyJhbGciOiJSUzI1NiIs..."
         }
       }
     }
   }
   ```

5. **Verify.**
   ```sh
   curl -s http://localhost:9889/.well-known/oauth-protected-resource | jq
   # Returns {resource, authorization_servers, scopes_supported, ...}
   ```

## Scope-to-role mapping

| Scope        | Allowed actions                                                              |
|--------------|------------------------------------------------------------------------------|
| `cao:read`   | View dashboard, list sessions/terminals, read events, fetch terminal output  |
| `cao:write`  | Send messages, assign tasks, create sessions, interrupt / pause / resume     |
| `cao:admin`  | Shutdown sessions, delete terminals, manage flows, change server settings    |

Recommended role assignments:

- **Operators / on-call**: `cao:read`, `cao:write`, `cao:admin`
- **Reviewers / team leads**: `cao:read`
- **CI service accounts**: `cao:read`, `cao:write` (no admin)

## Configuration reference

| Env var | Required | Default | Notes |
|---|---|---|---|
| `AUTH0_DOMAIN` | No (unset = auth off) | — | E.g. `tenant.auth0.com`. Setting this enables enforcement. |
| `AUTH0_AUDIENCE` | When `AUTH0_DOMAIN` is set | — | RFC 8707 resource indicator; token `aud` must match. |
| `CAO_AUTH_JWKS_URI` | No | `https://<AUTH0_DOMAIN>/.well-known/jwks.json` | Override for non-Auth0 IdPs (Keycloak, Okta, internal). |
| `CAO_AUTH_JWKS_CACHE_TTL` | No | `3600` (seconds) | In-process JWKS cache lifetime. |
| `CAO_AUTH_CLOCK_LEEWAY` | No | `60` (seconds) | `iat`/`exp` validation leeway for clock skew. |
| `CAO_AUTH_TOKEN` | No (set by MCP host) | — | Operator's Bearer token. Read by `cao-mcp-server` to populate the iframe's scopes + run the `submit_command` precheck. |

## Token rotation workflow

CAO is a **resource server** — it validates tokens but never issues
them. Rotation is your IdP's responsibility:

1. The IdP issues a new token (typically via OAuth 2.1 refresh-token
   flow on the MCP host side).
2. Update `CAO_AUTH_TOKEN` in your MCP host config (Claude Desktop:
   restart Claude to reload).
3. CAO's JWKS cache may serve the old key for up to
   `CAO_AUTH_JWKS_CACHE_TTL` seconds after a key rotation. Restart CAO
   to force a fresh JWKS fetch.

## Troubleshooting

**`401 Invalid token: aud mismatch`** — the token's `aud` claim
doesn't match `AUTH0_AUDIENCE`. Check both values match exactly. The
PRM endpoint advertises the expected audience under `resource`:

```sh
curl -s http://localhost:9889/.well-known/oauth-protected-resource | jq .resource
```

**`401 Invalid token: token is expired`** — clock skew between your
host and Auth0. Default leeway is 60 s; bump
`CAO_AUTH_CLOCK_LEEWAY=120` if your host clock drifts.

**`401 Invalid token: bad signature`** — JWKS rotation. Restart CAO
to clear the JWKS cache, or wait for the TTL to elapse.

**`403 Required scope not granted: cao:admin`** — your token lacks
the scope. Check your Auth0 user's assigned permissions for the API.

**`503 Authorization server unreachable`** — JWKS endpoint can't be
reached. Check `AUTH0_DOMAIN` is correct and your host has outbound
HTTPS to the IdP.

## WebSocket terminals

The live terminal stream at `/terminals/{id}/ws` validates the same
JWT scopes the HTTP mutation endpoints do.

Browsers cannot set `Authorization` headers on the WebSocket
handshake, so the JWT travels in the `Sec-WebSocket-Protocol` list as
`cao.bearer.<jwt>`. The server validates the token, then echoes only
the bare protocol name (`cao.bearer`) back in the handshake response —
the JWT suffix is never repeated.

**Scope policy.**

| Action | Scope required |
|---|---|
| Connect (stream output) | `cao:read` |
| `type: "input"` frame (PTY keystrokes) | `cao:write` |
| `type: "resize"` frame | `cao:write` |

A connection with `cao:read` but not `cao:write` is a **read-only
viewer**: output streams, but typed keystrokes are silently dropped
server-side. A single per-connection warning is logged
(`WS write frame dropped — caller lacks cao:write`) when the first
write frame arrives.

**Close codes.**

| Code | Reason | Cause |
|---|---|---|
| 4003 | `WebSocket access is restricted to localhost` | Peer is not loopback. |
| 4401 | `Unauthorized` | Auth-enabled and no `cao.bearer.*` subprotocol, or token failed JWT validation. |
| 4403 | `Insufficient scope` | Valid token but `cao:read` not granted. |
| 4004 | `Terminal not found` | Terminal id doesn't resolve. |

**Bundled web UI access in auth-enabled mode.** The bundled web UI
(`http://localhost:9889`) reads the JWT from two sources, in order:

1. `?access_token=<jwt>` URL query parameter (bookmark-friendly).
2. `localStorage["cao.auth.token"]` (persists across reloads).

If neither is set, the WS connection is unauthenticated and the server
returns close code 4401 in auth-enabled mode. In default-off mode
(`AUTH0_DOMAIN` unset) the bundled UI works without a token, the same
in this release.

**Direct client (curl, scripts, wscat).** Pass the bearer as the WS
subprotocol:

```sh
wscat -c ws://localhost:9889/terminals/<id>/ws \
      -s "cao.bearer.$(< token.jwt)"
```

A read-only token connects but keystrokes drop; a `cao:read cao:write`
token is a full operator.

**Default-off behavior.** When `AUTH0_DOMAIN` is unset, the WS endpoint
is byte-identical to prior releases — loopback peer check only, no token
required, no subprotocol echoed.

## Gaps (deferred to follow-up sibling-PRs)

- **OBO token exchange** (RFC 8693) — if your MCP host wants to swap
  its own token for a CAO-scoped one, not yet supported.
- **DCR auto-registration** (RFC 7591) — MCP hosts must be manually
  registered in your Auth0 tenant.
- **Multi-tenant CAO** — different Auth0 tenants targeting the same
  CAO instance; not yet partitioned.
