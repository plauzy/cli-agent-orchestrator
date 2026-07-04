# Generative UI over Heterogeneous CLI Agents

| Field | Value |
|---|---|
| **Created** | July 4, 2026 |
| **Status** | Implemented |
| **Surfaces** | `services/agui_stream.py`, `GET /agui/v1/stream`, `cao_pwa/` |

## 1. What this adds

CAO orchestrates a heterogeneous fleet of CLI coding agents — Claude Code, Amazon Q,
Kiro, Codex, Gemini/Antigravity, Cursor, Copilot, OpenCode, Kimi, Hermes — each a real
process with its own auth and tools. This feature lets **any** of those agents author a
UI intent and have it rendered **uniformly on one surface**: the operator cannot tell
(and does not need to) which provider produced which card.

The safety model is what makes this shippable over *untrusted* agents, and it is the key
difference from arbitrary-HTML approaches: an agent may only emit a **closed allow-list of
named components with JSON props** — no HTML, no script, no `eval`, no iframe. An off-list
component is **refused, never rendered**.

## 2. Design

**Wire path.** An agent authors a UI intent that rides a CAO event as a `ui` block
(`{component, props}`) → the AG-UI adapter maps it to a typed `GENERATIVE_UI` frame →
`GET /agui/v1/stream` emits it → any AG-UI client renders it.

**Backend** (`services/agui_stream.py`):
- Typed event `AGUI_GENERATIVE_UI` and a closed allow-list
  `GENERATIVE_UI_COMPONENTS = {approval_card, choice_prompt, diff_summary, progress, metric, agent_card}`.
- `to_agui_event` dispatches generative-UI first: a record carrying `ui.component`
  (top-level or in `detail`) maps to a `GENERATIVE_UI` frame; unknown components are
  **refused → `RAW` with `rejected_component`**; props are validated JSON-serializable and
  size-bounded (8 KB), degrading safely.

**Frontend** (`cao_pwa/src/components/GenerativeUI.tsx`):
- A React renderer with a **client-side mirror of the allow-list** (defense in depth). Each
  component renders from JSON props only — no `dangerouslySetInnerHTML`, no `eval`. Unknown
  → inert placeholder. Wired into `InstanceTab`'s reducer as a `GENERATIVE_UI` case + panel.

## 3. Safety model

| Threat | Mitigation | Verified by |
|---|---|---|
| Agent emits arbitrary HTML/script | No HTML on the wire — only named components + JSON props | `TestGenerativeUI` (py) + `GenerativeUI.test.tsx` |
| Agent names an off-list component (e.g. `iframe`) | Refused server-side (→ RAW) *and* client-side (inert placeholder) | `test_unknown_component_is_refused_not_rendered`; `REFUSES an unknown/unsafe component` |
| Agent floods the bus with a huge payload | Props capped at 8 KB → `{_truncated: true}` | `test_oversized_props_are_truncated` |
| Non-serializable props crash the stream | Degrade to `{}` | `test_non_serializable_props_degrade_to_empty` |
| Message-body leakage | Bodies never in the props path (metadata-only contract) | privacy tests |

The refusal is asserted at **three** layers — the Python adapter, the React component, and
the replay artifact — so an off-list component cannot slip through any of them.

## 4. Shift-left testing (all runnable locally)

| Layer | Suite | Result |
|---|---|---|
| Backend mapping + safety | `test/services/test_agui_stream_mapping.py` | 31 passed (incl. 6 generative-UI + 3 state-channel + privacy) |
| Frontend component + safety | `cao_pwa/src/test/GenerativeUI.test.tsx` | 10 passed (part of 18/18 in `cao_pwa`) |
| Build gate | `cao_pwa` `tsc` + `vite build` | clean; ~49.5 KB gz |
| Artifact correctness | headless render of the replay artifact in node | 5 components render, 1 refusal, 0 iframes ever emitted |

## 5. Visual proof (screen recording)

1. **Self-contained replay** — `cao_pwa/demo/generative-ui-replay.html`. Open it in any
   browser (no server). It replays a real event sequence produced by the actual
   `to_agui_event` adapter across three providers (`kiro_cli`, `claude_code`, `codex`),
   renders each component with a play/step timeline, and shows the `iframe` intent as
   **⛔ REFUSED**. Regenerate the embedded sequence from `cao_pwa/demo/generative-ui-sequence.json`.
2. **CI recording harness** — `cao_pwa/e2e/generative-ui.spec.ts` + `playwright.config.ts`
   (`video: on`, `screenshot: on`) and `.github/workflows/cao-pwa-generative-ui.yml`. On CI
   `npm run test:e2e:install && npm run test:e2e` drives the replay, asserts every component
   renders + the refusal, and uploads `.mp4`/`.gif`/`.webm` + the full-page screenshot as
   build artifacts.

## 6. Additive-value proof matrix

| Feature | Additive value | Shift-left test | Recording moment |
|---|---|---|---|
| `GENERATIVE_UI` mapping | Agents author UI, not just text | `test_allow_listed_component_maps_to_generative_ui` | any card appears |
| Uniform multi-provider render | One surface for kiro_cli + claude_code + codex UI | `test_every_allow_listed_component_round_trips` + component tests | provider badges on distinct cards |
| Safety refusal | Untrusted agent can't inject markup | 3-layer refusal tests | ⛔ REFUSED badge for `iframe` |
| `approval_card` HITL | Approve/reject a handoff from the dashboard | `wires approval actions to the onAction handler` | approval card with buttons |
| `STATE_SNAPSHOT`/`STATE_DELTA` | Client holds live shared fleet state (RFC-6902) | state-channel tests | snapshot on connect |

## 7. Follow-ups

- **Bidirectional generative UI** — approve/choose actions POST `submit_command` (needs the
  Bearer-input UX from the auth work).
- **`STATE_DELTA` debounce/cache** — the `/agui/v1/stream` snapshot recompute is per-event today.
- **In-host (MCP Apps) parity** — render the same allow-list inside the MCP Apps iframe so
  the in-host and standalone surfaces match.
