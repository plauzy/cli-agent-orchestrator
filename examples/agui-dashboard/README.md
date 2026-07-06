# AG-UI dashboard demo

A runnable, credentials-free tour of CAO's AG-UI surface: a mock fleet, the
full generative-UI component set, the safety refusal, and a live dashboard —
in about a minute.

![Live demo](../../docs/media/agui-live-remediation-demo.webm)

## What you'll see

- A real 2-worker fleet (deterministic `mock_cli` provider — no API keys, no
  real CLI binaries) appearing as `STATE_SNAPSHOT` / terminal events.
- All six allow-listed generative-UI components rendering live:
  `agent_card`, `progress`, `metric`, `diff_summary`, `choice_prompt`,
  `approval_card`.
- The safety contract in action: an off-list `iframe` intent is **refused
  server-side (400)** and nothing renders.
- SSE reconnect resuming via `?since=` with no gap.

## Quick start

```sh
# Terminal 1 — CAO server with the AG-UI surface enabled
CAO_AGUI_ENABLED=true uv run cao-server

# Terminal 2 — fleet + component showcase (cleans up on exit)
examples/agui-dashboard/run.sh

# Terminal 3 — pick a viewer:
curl -N http://localhost:9889/agui/v1/stream     # raw AG-UI frames, or…
cd cao_pwa && npm ci && npm run dev              # the dashboard at :5173
```

`showcase.sh` can also run standalone against any reachable CAO
(`CAO_URL=… CAO_TOKEN=… ./showcase.sh`) — it exits non-zero unless all six
components are accepted *and* the off-list component is refused, so it doubles
as a smoke test for a deployment.

## How agents do this for real

The showcase drives `POST /agui/v1/emit_ui` with curl; a real agent calls the
`emit_ui` MCP tool (already registered on `cao-mcp-server`). Teach any agent
the component vocabulary with the bundled **`agui-author`** skill
(`skills/agui-author/SKILL.md`): when to emit which component, props shapes,
the 8 KB bound, and the refusal behavior.

## Auth

Default-off local runs need no tokens. When CAO has Auth0 enabled, pass
`CAO_TOKEN` (a `cao:write` JWT) to `showcase.sh` and open the dashboard with
`?access_token=<cao:read JWT>` — see [docs/auth.md](../../docs/auth.md) and
the short-TTL guidance in [docs/pwa.md](../../docs/pwa.md).

## Files

| File | Purpose |
|---|---|
| `run.sh` | Launch the mock fleet, run the showcase, clean up on exit |
| `showcase.sh` | Drive all six components + the refusal via `emit_ui` (usable standalone as a smoke test) |
| `fleet_worker.md` | `mock_cli` agent profile the fleet runs on |
