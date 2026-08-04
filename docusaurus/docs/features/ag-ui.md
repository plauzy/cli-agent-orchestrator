---
sidebar_label: AG-UI
title: AG-UI — live fleet observability
---

# AG-UI

CAO exposes its normalized fleet events as an
[AG-UI](https://github.com/ag-ui-protocol/ag-ui) typed-event stream. Any
AG-UI-compatible client — CopilotKit apps, the AG-UI Dojo, or a plain
`EventSource` — renders a live CAO fleet with **no CAO-specific adapter code**.
Agents can also author allow-listed **generative UI** onto the same stream.

The surface is **default-off** and **metadata-only** (message bodies never
cross the wire).

## 🥋 See it: the CAO AG-UI Dojo

The **[AG-UI Dojo](pathname:///dojo/index.html)** is a live, replayable showcase
of CAO's headline angle — **multi-provider orchestration** (a `kiro_cli`
supervisor delegating to `claude_code` and `codex` workers), rendered through
the AG-UI stream. It shows the four L2 projections and all six generative-UI
components in one page.

Two frontier-team practices power how the dojo is built ([why this matters](https://kiro.dev/topics/frontier-teams/)):

- **Dog-food (feed agents, don't babysit).** The dojo's data is produced by a
  *real CAO orchestration*, captured on the production AG-UI path — not
  hand-authored. CAO builds and observes its own showcase.
- **Shift-left (verify before the pipeline).** Every dojo artifact is gated by
  an assertion that runs before CI: a frame-contract + privacy test, and a
  renderer assertion that must paint all panels and refuse the off-list
  component before any demo media is exported. A broken dojo can't produce a
  passing build.

> Source: [`examples/ag-ui/ag-ui-dojo/`](https://github.com/awslabs/cli-agent-orchestrator/tree/main/examples/ag-ui/ag-ui-dojo)

## Enabling the surface

`/agui/v1/stream`, `/agui/v1/run`, and `/agui/v1/emit_ui` return `404` unless
enabled:

```sh
export CAO_AGUI_ENABLED=true
uv run cao-server
```

## The two planes

| Plane | Endpoint | Use it for |
|---|---|---|
| **Ambient** | `GET /agui/v1/stream` (SSE) | Long-lived dashboards; `EventSource` auto-reconnect + replay |
| **Run** | `POST /agui/v1/run` | CopilotKit / AG-UI Dojo; stock wire dialect + interrupt/resume |
| **Producer** | `POST /agui/v1/emit_ui` | Agents author allow-listed generative UI |

## Generative UI — the safety model

An agent may emit **only** a closed allow-list of named components with JSON
props — **no HTML, no script, no iframe**. Off-list components are refused
server-side (and mirrored client-side as defense in depth).

`approval_card` · `choice_prompt` · `diff_summary` · `progress` · `metric` ·
`agent_card`

Teach an agent the vocabulary with the bundled
[`agui-author`](https://github.com/awslabs/cli-agent-orchestrator/tree/main/skills/agui-author)
skill.

## Watch a live fleet in the dojo

Point the dojo at your own running server:

```
pathname:///dojo/index.html?server=http://localhost:9889
```

## Reference

The full stream/replay/generative-UI specification lives in
[`docs/agui.md`](https://github.com/awslabs/cli-agent-orchestrator/blob/main/docs/agui.md)
in the repository.
