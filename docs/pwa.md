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

**Keep these tokens short-lived.** A query-string credential can surface in
places an `Authorization` header never would (browser history, proxy logs,
`Referer` headers), and it stays replayable until `exp`. CAO scrubs
`access_token` (and, pre-emptively, `ticket`) values from its own access
log, but that doesn't cover
intermediaries — so mint tokens with a short TTL (minutes, not hours) for
dashboard use. A short-lived single-use ticket handshake
(`POST /agui/v1/ticket` with header auth → `?ticket=`) and a dedicated
token-input UX are follow-ups.

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

## Generative UI

Any agent in the fleet — regardless of provider — can author a UI intent and
have it rendered uniformly on this surface. The safety model is what makes
that shippable over *untrusted* agents: an agent may only emit a **closed
allow-list of named components with JSON props** — no HTML, no script, no
`eval`, no iframe. An off-list component is **refused, never rendered**.

**Wire path.** An agent calls the `emit_ui` MCP tool (or
`POST /agui/v1/emit_ui`) → the intent rides a CAO event as a `ui` block
(`{component, props}`) → the AG-UI adapter maps it to a typed
`GENERATIVE_UI` frame → `GET /agui/v1/stream` emits it → any AG-UI client
renders it.

**Backend** (`services/agui_stream.py`): the closed allow-list
`GENERATIVE_UI_COMPONENTS = {approval_card, choice_prompt, diff_summary,
progress, metric, agent_card}`; unknown components are refused (mapped to
`RAW` with `rejected_component`); props must be JSON-serializable and are
size-bounded (8 KB), degrading safely.

**Frontend** (`cao_pwa/src/components/GenerativeUI.tsx`): a React renderer
with a client-side mirror of the allow-list (defense in depth). Each
component renders from JSON props only — no `dangerouslySetInnerHTML`, no
`eval`. Unknown → inert placeholder.

### Safety model

| Threat | Mitigation | Verified by |
|---|---|---|
| Agent emits arbitrary HTML/script | No HTML on the wire — only named components + JSON props | `TestGenerativeUI` (py) + `GenerativeUI.test.tsx` |
| Agent names an off-list component (e.g. `iframe`) | Refused server-side (→ RAW) *and* client-side (inert placeholder) | `test_unknown_component_is_refused_not_rendered`; `REFUSES an unknown/unsafe component` |
| Agent floods the bus with a huge payload | Props capped at 8 KB → `{_truncated: true}` | `test_oversized_props_are_truncated` |
| Non-serializable props crash the stream | Degrade to `{}` | `test_non_serializable_props_degrade_to_empty` |
| Message-body leakage | Bodies never in the props path (metadata-only contract) | privacy tests |

The refusal is asserted at three layers — the Python adapter, the React
component, and the e2e spec — so an off-list component cannot slip through
any of them.

### Visual proof

- **Live-path recording** — `cao_pwa/e2e/live-dashboard.spec.ts` boots a real
  `cao-server`, drives `emit_ui` through every allow-listed component plus an
  off-list refusal, exercises the `?since=` reconnect, and records video
  (`playwright.config.ts` has `video: on`). CI
  (`.github/workflows/cao-pwa-generative-ui.yml`) uploads the `.webm`/`.mp4`/
  `.gif` as build artifacts.
- **Self-contained replay** — `cao_pwa/demo/generative-ui-replay.html` renders
  a canned sequence (produced by the real adapter) in any browser with no
  server; useful for offline demos, not a substitute for the live path.

### Follow-ups

- **Bidirectional generative UI** — approve/choose actions POST
  `submit_command` (needs the Bearer-input UX from the auth work).
- **`STATE_DELTA` debounce/cache** — the `/agui/v1/stream` snapshot recompute
  is per-event today.
- **In-host (MCP Apps) parity** — render the same allow-list inside the MCP
  Apps iframe so the in-host and standalone surfaces match.

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
