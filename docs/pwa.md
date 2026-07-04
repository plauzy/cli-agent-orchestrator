# Standalone dashboard PWA

CAO 2.5.0a3+ ships an **L2 standalone dashboard PWA** under
[`cao_pwa/`](../cao_pwa). Sibling RFC:
[`cao-agui-l2-dashboard-2026-05-11-v1.md`](rfc/cao-agui-l2-dashboard-2026-05-11-v1.md).

The PWA consumes CAO's AG-UI typed-event stream (`/agui/v1/stream`)
and renders a multi-instance fleet dashboard from any browser — no MCP
host required.

## When to use the PWA vs the iframe

| Use the iframe (cao_mcp_apps) when… | Use the PWA (cao_pwa) when… |
|---|---|
| You're already in Claude Desktop / Cursor / VS Code | You only have a browser |
| You want the AI host to reason about UI actions | You're operating multiple CAO daemons |
| Your CAO is local-only | You want a hosted dashboard others can reach |

Both surfaces coexist; v2 plan §16 explicitly framed coexistence as
the long-term posture.

## Quick start

### Local dev (against the local CAO)

```sh
# Terminal 1
uv run cao-server                   # FastAPI on :9889

# Terminal 2
cd cao_pwa
npm ci
npm run dev                         # PWA on http://localhost:5174
```

Open http://localhost:5174 in your browser. Add the local CAO instance
(`http://localhost:9889`) when prompted. The dashboard streams live.

### Deployed (Vercel, internal Nginx, GitHub Pages)

```sh
cd cao_pwa
npm ci
npm run build
# Upload dist/ to your hosting target.
```

On the **CAO side**, allow the PWA's origin in CORS:

```sh
export CAO_PWA_ORIGIN="https://cao-dashboard.example.com"
uv run cao-server
```

Multiple origins: comma-separate (`CAO_PWA_ORIGIN="https://a.example.com,https://b.example.com"`).

## Multi-instance setup

Click **+ Add instance** in the header. Paste the CAO instance URL
(e.g. `http://team-cao.example.com:9889`) and a label. The PWA pings
`/health` before persisting; you can add instances that are currently
offline (e.g. while a teammate's CAO is starting up).

Each instance becomes a tab. State persists in IndexedDB — survives
reloads, cleared on browser data purge.

## Auth (when CAO has Auth0 enabled)

If CAO is running with `AUTH0_DOMAIN` set, the PWA needs an access
token. Native EventSource can't send `Authorization:` headers, so
tokens go through the `?access_token=<JWT>` query parameter (the
RFC documents this as the standard workaround).

**v1 limitation**: the PWA doesn't yet have a token-input UX. Workaround
for v1 — fetch a token via the Auth0 dashboard / CLI, paste it into
the URL bar:

```
https://cao-dashboard.example.com/?access_token=eyJhbGc...
```

The PWA picks up `access_token` from the URL and includes it on
EventSource connections. Bearer-input UI is v2 work.

## What the PWA shows (v1)

- **Sessions**: count + names of active CAO sessions.
- **Terminals**: per-terminal status (`running` / `terminated`),
  provider, agent profile.
- **Event stream**: live ticker of RAW + TEXT_MESSAGE events.

What's NOT in v1 (per the RFC §9):

- ❌ Live terminal output (xterm.js) — requires the WebSocket auth
  follow-up.
- ❌ Mutations (send_message, assign, interrupt, etc.) — requires the
  Bearer-input UX.
- ❌ Cross-instance aggregation — one tab per instance.
- ❌ mDNS / Bonjour discovery — manual entry only.

## Architecture

```
┌────────────────────────────┐         ┌────────────────────────────┐
│ Browser (PWA at own origin)│         │ CAO host                   │
│                            │         │                            │
│  cao_pwa/                  │         │  FastAPI :9889             │
│   ├ App.tsx                │ EvtSrc  │   ├ /agui/v1/stream  ──────┤
│   ├ InstancePicker.tsx     │◄──SSE───┤   ├ /events (legacy)       │
│   ├ InstanceTab.tsx        │         │   ├ /sessions, /terminals  │
│   ├ api.ts (connectAGUI)   │         │   │                        │
│   └ instances.ts (IDB)     │         │  services/agui_stream.py   │
│                            │ fetch   │   ├ to_agui_event(...)     │
│                            ├─/health─┤   └ 6 CAO→AG-UI mappings   │
└────────────────────────────┘         └────────────────────────────┘
```

## Privacy boundary

The `/agui/v1/stream` endpoint redacts message bodies (same as the
WAL + SSE bus + the L1 iframe). `TEXT_MESSAGE_CONTENT` events carry
metadata (sender, receiver, orchestration_type) but never the message
text.

## Troubleshooting

**Connection shows "✗ error"** — check CORS. Set `CAO_PWA_ORIGIN` to
the exact PWA origin (including scheme + port), restart CAO.

**401 on connect with auth enabled** — token missing or expired. Get
a fresh token from your Auth0 tenant and pass via `?access_token=`.

**Events stop after a while** — the EventSource may have been killed
by a proxy timeout. The PWA doesn't auto-reconnect in v1; reload the
tab. Auto-reconnect is a v2 chore.

**IndexedDB errors in Safari** — Safari occasionally throws on
private-browsing IndexedDB. The PWA falls back to in-memory state
(survives session, not reload). Documented baseline.

## Roadmap

- **v2**: Bearer-input UX; auto-reconnect; xterm.js (paired with WS auth follow-up).
- **v3**: Cross-instance aggregation; mDNS discovery; mobile layout.
- **v4**: Hosted at `dashboard.cao.dev` for the public hosted setup.

See the RFC for full deferred-list rationale.
