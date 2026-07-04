# Standalone dashboard PWA

CAO ships a **standalone dashboard PWA** under [`cao_pwa/`](../cao_pwa). It
consumes CAO's AG-UI typed-event stream (`/agui/v1/stream`) and renders a
multi-instance fleet dashboard from any browser — no MCP host required.

## When to use the PWA vs the in-host iframe

| Use the iframe (cao_mcp_apps) when… | Use the PWA (cao_pwa) when… |
|---|---|
| You're already in Claude Desktop / Cursor / VS Code | You only have a browser |
| You want the AI host to reason about UI actions | You're operating multiple CAO daemons |
| Your CAO is local-only | You want a hosted dashboard others can reach |

Both surfaces coexist; they serve different operator personas (in-host vs
standalone browser).

## Enabling the AG-UI surface

`/agui/v1/stream` is **default-off**. It returns `404` unless the AG-UI surface
is enabled:

```sh
export CAO_AGUI_ENABLED=true      # dedicated AG-UI flag
# (or CAO_MCP_APPS_ENABLED=true, which also enables it)
```

## Quick start

### Local dev (against the local CAO)

```sh
# Terminal 1 — CAO server with the AG-UI surface enabled
export CAO_AGUI_ENABLED=true
uv run cao-server                   # FastAPI on :9889

# Terminal 2 — the PWA dev server
cd cao_pwa
npm ci
npm run dev                         # PWA on http://localhost:5174
```

Open http://localhost:5174 and add the local CAO instance
(`http://localhost:9889`) when prompted. `http://localhost:5174` and
`http://127.0.0.1:5174` are in CAO's default CORS allow-list, so local dev
works with no extra CORS configuration. The dashboard then streams live.

### Deployed (Vercel, internal Nginx, GitHub Pages)

```sh
cd cao_pwa
npm ci
npm run build
# Upload dist/ to your hosting target.
```

On the **CAO side**, allow the PWA's origin in CORS via `CAO_CORS_ORIGINS`
(comma-separated; appended to the localhost defaults):

```sh
export CAO_AGUI_ENABLED=true
export CAO_CORS_ORIGINS="https://cao-dashboard.example.com"
uv run cao-server
```

Multiple origins: `CAO_CORS_ORIGINS="https://a.example.com,https://b.example.com"`.

## Multi-instance setup

Click **+ Add instance** in the header. Paste the CAO instance URL
(e.g. `http://team-cao.example.com:9889`) and a label. The PWA pings `/health`
before persisting; you can add instances that are currently offline. Each
instance becomes a tab. State persists in IndexedDB.

## Auth (when CAO has Auth0 enabled)

If CAO runs with `AUTH0_DOMAIN` set, `/agui/v1/stream` requires a `cao:read`
JWT. Native EventSource can't send an `Authorization:` header, so the token
travels as the `?access_token=<JWT>` query parameter — the same pattern as the
WebSocket `cao.bearer` subprotocol.

The PWA reads `access_token` from its own page URL and forwards it on every
EventSource connection, so pasting a token into the address bar works:

```
https://cao-dashboard.example.com/?access_token=eyJhbGc...
```

A dedicated token-input UX (rather than a URL parameter) is a follow-up.

## Connection resilience

The client manages reconnection itself: on a dropped connection it backs off
(capped exponential) and reopens with `?since=<last event timestamp>`, so it
resumes without a gap — the server replays buffered history and the client
dedupes by event id.

## What the PWA shows

- **Sessions**: count + names of active CAO sessions.
- **Terminals**: per-terminal status (`running` / `terminated`), provider, profile.
- **Generative UI**: agent-authored, allow-listed components (approval cards,
  choice prompts, diff summaries, metrics, …).
- **Event stream**: live ticker of AG-UI events.

Not yet included:

- Live terminal output (xterm.js) — paired with the WebSocket auth work.
- Mutations (send_message, assign, interrupt, …) — needs the bidirectional
  command surface.
- Cross-instance aggregation — one tab per instance.
- mDNS / Bonjour discovery — manual entry only.

## Privacy boundary

`/agui/v1/stream` redacts message bodies (same contract as the SSE bus and the
in-host iframe). `TEXT_MESSAGE_CONTENT` events carry metadata (sender, receiver,
orchestration_type) but never the message text.

## Troubleshooting

**Connection shows "✗ error"** — check that `CAO_AGUI_ENABLED` is set (else the
endpoint 404s) and that the PWA origin is allowed via `CAO_CORS_ORIGINS`
(exact scheme + host + port), then restart CAO.

**401 on connect with auth enabled** — token missing or expired. Get a fresh
token from your Auth0 tenant and pass it via `?access_token=`.

**Events stop after a proxy idle timeout** — the client auto-reconnects with
backoff and resumes via `?since=`; no manual reload needed.

**IndexedDB errors in Safari** — Safari can throw on private-browsing
IndexedDB; the PWA falls back to in-memory state (survives the session).
