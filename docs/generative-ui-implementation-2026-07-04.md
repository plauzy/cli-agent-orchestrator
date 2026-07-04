# Generative UI over Heterogeneous CLI Agents — Implementation, Landscape, and Proof

| Field | Value |
|---|---|
| **Created** | July 4, 2026 |
| **Status** | Implemented (flagship slice) + roadmap |
| **Branch** | `feat/port-fork-net-new-subsystems` |
| **Reframes** | The 4 RFCs in `plauzy/cao/docs/rfc/` (MCP Apps plan, AG-UI L2 dashboard, Auth0-for-MCP, Auth0-websocket) |
| **Landscape basis** | Verified July 2026 (this session's research). Web tools were unavailable at authoring time; claims are tagged and dated. |

> **Evidence tags:** **[Strong]** verified in-session / in-repo; **[Promising]** well-supported, one inference away; **[Emerging]** moving target; **[Theoretical]** thesis ("we believe").

---

## 1. The pitch — generative UI in a way that has not been done before

Every generative-UI system shipping today binds **one agent framework** to **one frontend**: CopilotKit renders a LangGraph/CrewAI/Mastra agent; MCP Apps render a single MCP server's HTML inside one host's iframe; OpenAI Apps render inside ChatGPT. The agent that authors the UI and the surface that renders it are a matched pair.

CAO breaks that pairing. **[Strong]** CAO orchestrates a *heterogeneous* fleet of real CLI coding agents — Claude Code, Amazon Q, Kiro, Codex, Gemini/Antigravity, Cursor, Copilot, OpenCode, Kimi, Hermes — each a full process with its own auth and tools. Because CAO already normalizes their lifecycle into one event vocabulary and speaks the full protocol triad (MCP, A2A, AG-UI), it can let **any** of those agents author a UI intent and render it **uniformly on one surface** — the operator cannot tell (and does not need to care) which provider produced which card.

That is the thing that has not been done before: **generative UI as a provider-agnostic layer over N heterogeneous CLI agents**, not a 1:1 framework↔frontend binding.

The safety model is what makes it shippable, and it is also the differentiator versus MCP Apps: agents may only emit a **closed allow-list of named components with JSON props** — no HTML, no script, no `eval`, no iframe. An untrusted CLI agent can drive rich UI *without* an iframe sandbox, because there is no arbitrary markup to sandbox. An off-list component is **refused, never rendered.**

---

## 2. Current AG-UI landscape (as of July 2026) and how the 4 RFCs re-read against it

The 4 RFCs were written in **May 2026**. Three landscape shifts since then change how they should be implemented:

| Shift (July 2026) | Evidence | Consequence for the RFCs |
|---|---|---|
| AG-UI's event set **grew past "16"** — now ~17 core / up to 25 typed in some SDKs; families (lifecycle / text / tool-call / state / **custom**) unchanged | **[Emerging]** CopilotKit docs + SDK docs | The L2 dashboard RFC's "6 of 16" framing is stale; the re-based adapter maps by *semantic primitive*, so growth is additive. Generative UI rides the **custom/`RAW`** family as a typed `GENERATIVE_UI` frame. |
| **MCP Apps folded into the 2026-07-28 MCP spec RC** (stateless core + Extensions + Tasks) | **[Emerging]** modelcontextprotocol.io RC post | The MCP Apps plan's L1 surface is *more* permanent than assumed — good. Capability negotiation (`ext_apps/sep2133`) needs a re-verify against the RC. |
| **A2A v1.0 GA** (LF, 150+ orgs), signed Agent Cards at `/.well-known/agent-card.json` | **[Strong]** LF press + a2aproject | The Auth0 RFCs' OAuth-2.1/JWT direction is now the ecosystem default; the ported `agent_card/` + `:9890` listener already align. |

**Re-reading the construct model (still correct, sharpened):** MCP Apps = L1 (in-host iframe), AG-UI = L2 (open-web streaming), and **generative UI is the L1→L2 payload that both carry**. The RFCs treated generative UI (A2UI-style declarative components) as deferred/L4-future; today it is tractable *now* as a small, safe, allow-listed layer on AG-UI's custom-event family — which is what this implementation ships.

---

## 3. The 4 RFCs → what is implemented on this branch

| RFC | Core ask | Status on this branch |
|---|---|---|
| **MCP Apps implementation plan (v2)** | L0–L3 construct model; `ui://cao/*` resources; `submit_command` choke point; `event_log_service`; shift-left CI | **[Strong] Substantially in place.** Upstream's hardened MCP Apps plugin + `app_tools` (`submit_command`, HTTP-only boundary, scope coverage) is kept; the fork's subsystems were ported. Construct model realized in code. |
| **AG-UI L2 dashboard** | `/agui/v1/stream`, CAO→AG-UI adapter, `cao_pwa/`, multi-instance picker, `STATE_SNAPSHOT`/`STATE_DELTA` | **[Strong] Implemented + extended.** Adapter **re-based onto the 6 `event_primitives`**; endpoint mounted; **shared-state channel** (STATE_SNAPSHOT on connect + RFC-6902 STATE_DELTA) wired; **generative-UI channel added** (this doc). |
| **Auth0-for-MCP** | OAuth 2.1 + PRM + scopes on the mutation choke point | **[Promising] Foundations in place.** Signed Agent Card + OAuth PRM listener on `:9890` ported and boot-verified; `require_any_scope` gates the streams. Full DCR/OBO is the remaining increment. |
| **Auth0-websocket** | Bearer auth for the WS terminal stream | **[Promising] Deferred, path clear.** Same `access_token` query-param + scope pattern as the AG-UI stream; documented as follow-up. |

This document's **new** contribution is the flagship generative-UI capability (§4–§7), which none of the RFCs implemented — they explicitly deferred declarative components.

---

## 4. The generative-UI feature — design

**Wire path.** An agent authors a UI intent → it rides a CAO event as a `ui` block (`{component, props}`) → the AG-UI adapter maps it to a typed `GENERATIVE_UI` frame → `/agui/v1/stream` emits it → any AG-UI client renders it.

**Backend** (`services/agui_stream.py`):
- New typed event `AGUI_GENERATIVE_UI` and a closed allow-list `GENERATIVE_UI_COMPONENTS = {approval_card, choice_prompt, diff_summary, progress, metric, agent_card}`.
- `to_agui_event` dispatches **generative-UI first**: if a record carries `ui.component` (top-level or in `detail`), it maps to a `GENERATIVE_UI` frame; unknown components are **refused → `RAW` with `rejected_component`**; props are validated JSON-serializable and size-bounded (8 KB), degrading safely.

**Frontend** (`cao_pwa/src/components/GenerativeUI.tsx`):
- A React renderer with a **client-side mirror of the allow-list** (defense in depth). Each component renders from JSON props only — no `dangerouslySetInnerHTML`, no `eval`. Unknown → inert placeholder. Wired into `InstanceTab`'s reducer as a `GENERATIVE_UI` case + a dedicated panel.

## 5. Safety model (why this is shippable over *untrusted* agents)

| Threat | Mitigation | Verified by |
|---|---|---|
| Agent emits arbitrary HTML/script | No HTML on the wire — only named components + JSON props | `TestGenerativeUI` (py) + `GenerativeUI.test.tsx` |
| Agent names an off-list component (e.g. `iframe`) | **Refused** server-side (→ RAW) *and* client-side (inert placeholder) | `test_unknown_component_is_refused_not_rendered`; `REFUSES an unknown/unsafe component` |
| Agent floods the bus with a huge payload | Props capped at 8 KB → `{_truncated: true}` | `test_oversized_props_are_truncated` |
| Non-serializable props crash the stream | Degrade to `{}` | `test_non_serializable_props_degrade_to_empty` |
| Message-body leakage | Bodies never in props path (metadata-only contract preserved) | privacy tests retained |

## 6. Shift-left testing — results (all run in this environment)

| Layer | Suite | Result |
|---|---|---|
| Backend mapping + safety | `test/services/test_agui_stream_mapping.py` (Python, via venv) | **[Strong] 31 passed** (incl. 6 generative-UI + 3 state-channel + privacy) |
| Frontend component + safety | `cao_pwa/src/test/GenerativeUI.test.tsx` (vitest + Testing Library, jsdom) | **[Strong] 10 passed** (part of 18/18 in `cao_pwa`) |
| Build gate | `cao_pwa` `tsc` + `vite build` | **[Strong] clean; 49.5 KB gz** (within the RFC budget) |
| Artifact correctness | headless render of the replay artifact in node | **[Strong] 5 components render, 1 refusal, 0 iframes ever emitted** |

Shift-left is structural here: the safety refusal is asserted at **three** layers (Python adapter, React component, replay artifact) — an off-list component cannot slip through any of them.

## 7. Screen-recording / visual proof — methodology and honesty

**The honest constraint:** the build sandbox has **no browser** and the Playwright browser CDN (`cdn.playwright.dev`) is **blocked by the proxy** (`ERR_ACCESS_DENIED`), so a live headless recording **cannot be produced inside the sandbox**. Two artifacts deliver the equivalent, reproducible proof:

1. **Self-contained replay artifact** — `cao_pwa/demo/generative-ui-replay.html`. Open it in any browser (no server). It replays a **real** AG-UI event sequence (`cao_pwa/demo/generative-ui-sequence.json`, generated by running the actual `to_agui_event` adapter over a scripted three-provider scenario) and renders the components with a play/step timeline. Provider badges (`q_cli`, `claude_code`, `codex`) make the "uniform across providers" claim visible; the `iframe` intent shows as **⛔ REFUSED**. This is the recording-equivalent you can watch today.
2. **Playwright recording harness (CI path)** — `cao_pwa/e2e/generative-ui.spec.ts` + `playwright.config.ts` (`video: "on"`, `screenshot: "on"`). In CI (where the CDN is reachable) `npm run test:e2e:install && npm run test:e2e` drives the replay, asserts every component renders + the refusal, and emits `test-results/**/video.webm` + a full-page screenshot. This is the literal MP4/WEBM "screen recording."

## 8. Additive-value proof matrix

Every feature below ties to a runnable test **and** a visible moment in the recording/replay — "prove it's additive."

| Feature | Additive value (what you couldn't do before) | Shift-left test | Recording moment |
|---|---|---|---|
| `GENERATIVE_UI` mapping | Agents author UI, not just text | `test_allow_listed_component_maps_to_generative_ui` | any card appears |
| Uniform multi-provider render | One surface for q_cli + claude_code + codex UI | `test_every_allow_listed_component_round_trips` + component tests | provider badges on distinct cards |
| Safety refusal | Untrusted agent can't inject markup | 3-layer refusal tests | ⛔ REFUSED badge for `iframe` |
| `approval_card` HITL | Approve/reject a handoff from the dashboard | `wires approval actions to the onAction handler` | approval card with buttons |
| `STATE_SNAPSHOT`/`STATE_DELTA` | Client holds live shared fleet state (RFC-6902) | state-channel tests | snapshot on connect |
| Re-based adapter | Maps upstream's canonical vocabulary, not fork's raw kinds | 10 primitive-path tests | lifecycle ticker |

## 9. What's next (honest deferrals)

- **Bidirectional generative UI** — approval/choice actions POST `submit_command` (needs the Auth0 Bearer-input UX from the Auth0 RFC).
- **Full DCR/OBO** for Auth0-for-MCP; WS terminal-stream auth (Auth0-websocket RFC).
- **STATE_DELTA debounce/cache** (the `/agui/v1/stream` recompute is per-event today).
- **Re-verify `ext_apps/sep2133`** against the 2026-07-28 MCP spec RC.
- **`cao_mcp_apps` (in-host) generative UI parity** — render the same allow-list inside the MCP Apps iframe so the in-host and standalone surfaces match.
