---
name: agui-author
description: Use when a CAO agent should surface structured UI to the operator dashboard — approvals, choices, diffs, progress, metrics, or agent status — via the emit_ui MCP tool. Covers the six allow-listed components, their props schemas, the 8 KB bound, and the refusal behavior. Do NOT use for building the dashboard itself — that's cao_pwa/.
allowed-tools: [Bash, Read, Grep, Glob]
user-invocable: true
---

# Authoring Generative UI from any CAO agent

Any agent in a CAO fleet — regardless of provider — can render structured UI
on the operator dashboard by calling the **`emit_ui`** MCP tool. The card
appears live on every connected AG-UI client (the `cao_pwa/` dashboard, or any
stock AG-UI consumer of `GET /agui/v1/stream`).

Requires the AG-UI surface to be enabled on the server (`CAO_AGUI_ENABLED=true`
or `CAO_MCP_APPS_ENABLED=true`). When disabled, `emit_ui` returns
`{"ok": false, "reason": "AG-UI surface disabled …"}` — treat that as a no-op,
not an error.

## The contract

- You may emit **only** the six allow-listed components below, with **JSON
  props** — no HTML, no markup, no scripts. Anything off-list is refused
  server-side (400) and never rendered.
- Props must be JSON-serializable and **under 8 KB** once serialized; larger
  payloads are truncated to `{_truncated: true}`. Summarize — don't dump.
- Never put message bodies, credentials, or file contents in props. The AG-UI
  stream is metadata-only by contract; keep your UI intents the same.

## When to emit which component

| Component | Emit when… | Core props |
|---|---|---|
| `approval_card` | you need a human go/no-go before a risky step | `title` (str), `detail` (str), `risk` (`"low"\|"medium"\|"high"`) |
| `choice_prompt` | the operator should pick between options | `question` (str), `choices` (list of str or `{label,value}`) |
| `diff_summary` | you changed files and want the change surfaced | `files` (list of `{path, additions, deletions}`), `summary` (str) |
| `progress` | a long task should show liveness | `label` (str), `value` (0–100 number) or omit for indeterminate |
| `metric` | one number tells the story (coverage %, latency, cost) | `label` (str), `value` (number/str), `unit` (str) |
| `agent_card` | you want your identity/status pinned on the board | `name` (str), `provider` (str), `status` (str) |

Props are free-form JSON — the table lists what the reference renderers
(`cao_pwa/src/components/GenerativeUI.tsx`) display; unknown extra keys are
ignored, not refused.

## Examples

Announce yourself when you start:

```
emit_ui(component="agent_card",
        props={"name": "data_analyst", "provider": "kiro_cli", "status": "working"})
```

Show progress during a long analysis, then the result:

```
emit_ui(component="progress", props={"label": "Analyzing dataset", "value": 60})
emit_ui(component="metric", props={"label": "Mean latency", "value": 42.1, "unit": "ms"})
```

Ask for a go/no-go before something destructive:

```
emit_ui(component="approval_card",
        props={"title": "Drop 3 stale tables?",
               "detail": "backup verified 2026-07-06", "risk": "high"})
```

Surface a code change:

```
emit_ui(component="diff_summary",
        props={"summary": "auth hardening",
               "files": [{"path": "api/main.py", "additions": 18, "deletions": 2}]})
```

## What NOT to do

- Do not try `iframe`, `html`, `script`, `markdown`, or any component not in
  the table — the server refuses it (400) and dashboards show nothing. There
  is no escape hatch by design.
- Do not encode HTML inside string props expecting it to render — renderers
  treat every prop as plain text.
- Do not emit in a tight loop; one `progress` update per meaningful step is
  plenty (the stream is drop-on-slow, so spam only hurts your own updates).
- Approval/choice cards are **display + operator-side actions**; today the
  action routes to the dashboard's command surface, not back to you as a tool
  result. Pair an `approval_card` with your provider's own wait-for-input
  mechanism.

## Verifying locally

```bash
# 1. Server with the surface on
CAO_AGUI_ENABLED=true uv run cao-server

# 2. Watch the stream (SSE frames print as they arrive)
curl -N 'http://localhost:9889/agui/v1/stream'

# 3. Emit from anywhere (the MCP tool does exactly this)
curl -sX POST http://localhost:9889/agui/v1/emit_ui \
  -H 'Content-Type: application/json' \
  -d '{"component":"metric","props":{"label":"demo","value":1}}'
```

A `GENERATIVE_UI` frame with your component appears on the stream; an
off-list component returns `{"detail":"unknown component …"}` with 400.
