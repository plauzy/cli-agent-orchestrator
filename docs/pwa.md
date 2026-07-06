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

### Query-parameter tokens and log hygiene

Because the token rides in the URL, it can otherwise leak into access logs,
reverse-proxy logs, and `Referer` headers, where it is replayable until `exp`.
Two mitigations:

- **CAO scrubs it server-side.** `cao-server` installs a log filter that masks
  `?access_token=` (and `?ticket=`) values in uvicorn's access log, so the
  token is not written to disk while normal access logging stays on.
- **Use short token TTLs.** Configure your IdP to issue short-lived
  `cao:read` tokens for dashboard use so a leaked URL has a small replay window.

A short-lived, single-use **ticket handshake** — `POST /agui/v1/ticket` with a
header-borne JWT that returns an opaque `?ticket=` good for one connection — is
a planned follow-up that removes the standing bearer from the URL entirely. It
is intentionally **not** part of this change.

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

CAO orchestrates a heterogeneous fleet of CLI coding agents (Claude Code, Kiro,
Codex, Antigravity, Cursor, Copilot, OpenCode, Kimi, Hermes). Generative UI lets
**any** of them author a UI intent that renders **uniformly on one surface** —
the operator can't tell (and doesn't need to) which provider produced which
card.

What makes this shippable over *untrusted* agents — and the key difference from
arbitrary-HTML approaches — is the safety model: an agent may only emit a
**closed allow-list of named components with JSON props**. No HTML, no script,
no `eval`, no iframe. An off-list component is **refused, never rendered**.

### Wire path

An agent authors a UI intent that rides a CAO event as a `ui` block
(`{component, props}`) → the AG-UI adapter maps it to a typed `GENERATIVE_UI`
frame → `GET /agui/v1/stream` emits it → any AG-UI client renders it. Agents
author intents via the `emit_ui` MCP tool / `POST /agui/v1/emit_ui`.

- **Backend** (`services/agui_stream.py`): the typed `GENERATIVE_UI` event and a
  closed allow-list `GENERATIVE_UI_COMPONENTS = {approval_card, choice_prompt,
  diff_summary, progress, metric, agent_card}`. `to_agui_event` maps a record
  carrying `ui.component` (top-level or in `detail`) to a `GENERATIVE_UI` frame;
  unknown components are **refused → `RAW` with `rejected_component`**; props are
  validated JSON-serializable and size-bounded (8 KB), degrading safely.
- **Frontend** (`cao_pwa/src/components/GenerativeUI.tsx`): a React renderer with
  a **client-side mirror of the allow-list** (defense in depth). Each component
  renders from JSON props only — no `dangerouslySetInnerHTML`, no `eval`. Unknown
  components render as an inert placeholder.

### Safety model

| Threat | Mitigation |
|---|---|
| Agent emits arbitrary HTML/script | No HTML on the wire — only named components + JSON props |
| Agent names an off-list component (e.g. `iframe`) | Refused server-side (→ `RAW`) **and** client-side (inert placeholder) |
| Agent floods the bus with a huge payload | Props capped at 8 KB → `{_truncated: true}` |
| Non-serializable props | Degrade to `{}` rather than crashing the stream |
| Message-body leakage | Bodies never enter the props path (metadata-only contract) |

The refusal is asserted at three layers — the Python adapter, the React
component, and the browser-openable replay artifact
(`cao_pwa/demo/generative-ui-replay.html`) — so an off-list component cannot slip
through any of them. The Playwright harness (`cao_pwa/e2e/generative-ui.spec.ts`)
drives that replay in CI, asserting every allow-listed component renders and the
`iframe` intent is refused.

### Follow-ups

- **Bidirectional generative UI** — approve/choose actions POST `submit_command`
  (needs the Bearer-input UX from the auth work).
- **`STATE_DELTA` debounce/cache** — the `/agui/v1/stream` snapshot recompute is
  per-event today.
- **In-host (MCP Apps) parity** — render the same allow-list inside the MCP Apps
  iframe so the in-host and standalone surfaces match.

## Live demo & recording

Two ways to see the generative-UI path against a **live** server (not a canned
replay):

- **Runnable, headless (no browser needed):**
  [`examples/agui-dashboard/`](../examples/agui-dashboard/) — `run.sh` starts a
  real `cao-server` with the AG-UI surface enabled; `showcase.sh` drives all six
  allow-listed components through `POST /agui/v1/emit_ui` and tails
  `GET /agui/v1/stream`, printing the real `GENERATIVE_UI` frames and showing the
  off-list `iframe` refused with HTTP 400.
- **Real video (CI):** the `live-dashboard` job in
  [`.github/workflows/cao-pwa-generative-ui.yml`](../.github/workflows/cao-pwa-generative-ui.yml)
  runs `cao_pwa/e2e/live-dashboard.spec.ts` against a real `cao-server` + the real
  PWA, records a `.webm` of the six cards rendering + the refusal + an
  offline→online `?since=` reconnect, and uploads it as the
  **`agui-live-remediation-demo`** artifact. (The Playwright browser CDN is
  blocked in the build sandbox, so the video is produced on CI runners rather
  than committed as a binary.)

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
