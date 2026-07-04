# Draft GitHub issue for awslabs/cli-agent-orchestrator

> Ready to paste. Suggested labels: `enhancement`, `rfc`, `discussion`.
> Everything below the line is the issue body; the first heading is the suggested title.

---

# Proposal: AG-UI protocol support as a composable construct layer — one face over many CLI agents

## Summary

CAO already orchestrates heterogeneous CLI coding agents (Kiro CLI, Claude Code, Codex, and friends) as real processes, and already exposes an agent↔tools surface via MCP. This proposal adds the third leg of the agentic protocol stack — [AG-UI](https://docs.ag-ui.com/introduction), the Agent–User Interaction Protocol — as a **strictly additive, default-off** streaming surface. But rather than a point integration ("CAO now emits AG-UI events"), it proposes structuring the work as a **building-block construct programming model**, in the spirit of AWS CDK's L1/L2/L3 construct levels: raw event primitives at the bottom, named, subclassable, opinionated compositions in the middle, and full orchestration surfaces composed from those blocks at the top.

The outcome: any stock AG-UI client — CopilotKit, the [AG-UI Dojo](https://docs.ag-ui.com/quickstart/applications), a custom dashboard — can render a live CAO fleet with zero custom adapter code, and downstream builders assemble agent-operations UIs from typed CAO building blocks instead of scraping terminals or hand-rolling SSE wiring.

## Motivation

CAO's daily reality is exactly the set of problems AG-UI was designed for ([introduction](https://docs.ag-ui.com/introduction)): agents are **long-running** and stream intermediate work; they are **nondeterministic**; they mix structured and unstructured output (text alongside tool calls, file edits, status changes); and they need **human-in-the-loop** interaction (permission prompts, approvals, handoffs). Today every CAO user-facing surface — the bundled web dashboard, any MCP Apps experiments, ad-hoc scripts polling `/terminals/{id}/output` — solves these problems with bespoke wiring. There is no standard way for an external UI to consume "what is my agent fleet doing right now."

Meanwhile CAO already has the right internal shape for this: an event-driven backbone (in-process pub/sub bus carrying `terminal.{id}.output` / `terminal.{id}.status`, documented in [docs/event-driven-architecture.md](https://github.com/awslabs/cli-agent-orchestrator/blob/main/docs/event-driven-architecture.md)) and a normalized event vocabulary. Mapping that vocabulary onto a standard wire protocol is a thin, low-risk adapter — not a re-architecture.

## Background: the agentic protocol triad

AG-UI positions itself as complementary to the two protocols CAO users already know ([agentic protocols overview](https://docs.ag-ui.com/agentic-protocols)):

| Layer | Protocol | Purpose |
|---|---|---|
| Agent ↔ Tools & Data | **MCP** | Connect agents to tools and data (CAO ships an MCP server today) |
| Agent ↔ Agent | **A2A** | Coordination across agents (CAO's handoff/inbox model is a natural fit) |
| Agent ↔ User | **AG-UI** | Real-time, event-based connection between agents and user-facing apps |

AG-UI is an open, Apache-2.0, event-based protocol (~16 core event types across lifecycle, text streaming, tool calls, and state sync) with SSE/WebSocket/binary transports, first-party integrations for LangGraph, CrewAI, Mastra, Pydantic AI, Google ADK, Microsoft Agent Framework — and notably **AWS Strands Agents and Amazon Bedrock AgentCore**. A CAO AG-UI surface would slot into an ecosystem AWS is already invested in.

## The vision: a construct programming model, not a point integration

Every existing AG-UI integration binds **one framework to one frontend** (LangGraph→CopilotKit, Mastra→CopilotKit, …). CAO's situation is structurally different: it fronts **N heterogeneous CLI agents as real OS processes**, and new providers arrive regularly. If each provider×surface pairing needs bespoke adapter code, the integration cost grows multiplicatively. The fix is to make *the act of binding itself* composable — the same move AWS CDK made for infrastructure:

**L1 — raw event primitives (the protocol adapter).** A single, pure, version-pinned module mapping CAO's normalized event vocabulary 1:1 onto AG-UI typed events, exposed at `GET /agui/v1/stream` (SSE), default-off:

| CAO event | AG-UI event |
|---|---|
| session/terminal launch | `RUN_STARTED` / `STEP_STARTED` |
| completion | `RUN_FINISHED` / `STEP_FINISHED` |
| handoff | `STEP_STARTED` + `TOOL_CALL_START`/`TOOL_CALL_END` |
| agent-to-agent delegation | `TOOL_CALL_START` / `TOOL_CALL_RESULT` |
| file modification | `STATE_DELTA` (RFC 6902 JSON Patch) against a fleet snapshot (`STATE_SNAPSHOT` on connect) |
| error | `RUN_ERROR` |
| anything else | `RAW` with a `cao_type` discriminator |

Privacy boundary by design: message *bodies* never go on the wire — only lifecycle metadata. Operators opt into content-bearing streams separately.

**L2 — named, opinionated, subclassable constructs.** Compositions of L1 events that encode CAO's orchestration semantics, shipped as a small library:

- `SupervisorDashboardStream` — fleet-wide `STATE_SNAPSHOT` + rolling `STATE_DELTA`s: everything a mission-control view needs in one subscription.
- `AgentHandoffWithApproval` — human-in-the-loop handoff using AG-UI's interrupt-aware run lifecycle (`RUN_FINISHED` with an `interrupt` outcome, resumed with an approval payload).
- `CrossProviderStateSync` — N heterogeneous workers (Kiro CLI + Claude Code + Codex) merged into one coherent AG-UI thread.
- `MultiAgentSessionTimeline` — handoffs, delegations, tool calls, and errors in a single ordered, renderable log.

A new provider participates in all of these by implementing the base provider interface — one subclass, not a new adapter per surface.

**L3 — composed surfaces.** Reference applications assembled *entirely* from L2 constructs: a standalone fleet dashboard PWA, an authenticated team control plane, an embedded CAO panel inside Strands/AgentCore-based apps. L3 exists to prove the constructs compose; none of it requires bespoke event wiring.

## Unique positioning: the empty axis

Two mature neighborhoods exist today, and nothing occupies the space between them:

- **Multi-CLI orchestrators** (Claude Squad, cmux, etc.): manage heterogeneous CLI agents as processes, but expose no standard protocol surface — every UI scrapes terminals.
- **AG-UI-speaking frameworks** (LangGraph, CrewAI, Mastra, …): speak the protocol fluently, but front in-process API agents, not real CLI processes.

CAO with an AG-UI construct layer would be the only runtime that orchestrates heterogeneous CLI coding agents as real processes **and** exposes them across the full protocol triad. Concretely, it would fill gaps the AG-UI ecosystem itself has today:

1. **No terminal-CLI-agent integrations exist.** AG-UI's own [middleware quickstart](https://docs.ag-ui.com/quickstart/middleware) blesses bridging "virtually any backend," yet no one bridges Claude Code / Kiro / Codex CLI processes. CAO already owns that lifecycle.
2. **No multi-agent fleet UI conventions.** The protocol has multi-agent primitives, but nothing standardizes rendering N concurrent sessions, handoffs, and supervisor views. CAO's L2 constructs would define them.
3. **No workspace/diff semantics for coding agents.** Diffs, file trees, and terminal output have no typed representation; CAO can establish the `STATE_DELTA`/`CUSTOM` conventions coding-agent UIs need.
4. **Permission prompts ↔ interrupts.** AG-UI's interrupt lifecycle (namespaced reasons like `langgraph:database_modification`) maps naturally onto CLI permission prompts (`claude-code:permission_request`, `kiro:trust_prompt`); nobody ships that mapping.
5. **Process lifecycle is out of scope for AG-UI.** Spawning, persisting, resuming, and multiplexing long-lived local processes is left to the implementer — it is precisely what CAO does.

## Long-term additive benefits

- **Strictly additive and default-off.** One new endpoint behind an explicit flag; zero behavior change for existing users. The adapter is a thin pure module over the existing event bus and state-snapshot services — no new event backbone, no schema migration.
- **Every AG-UI client becomes a CAO client for free.** CopilotKit apps, the Dojo, custom dashboards — no CAO-specific SDK needed.
- **Compounding surface area.** Each new provider automatically appears in every L2 construct and every L3 surface; each new L2 construct benefits every provider.
- **Protocol-risk hedging built in.** AG-UI is CopilotKit-stewarded (not yet foundation-governed) and the MCP spec is evolving fast. Keeping L1 a single version-pinned file bounds the blast radius of any spec change to one module; L2/L3 depend on CAO's own construct API, not raw wire events.
- **Ecosystem visibility.** An AG-UI integration listing puts CAO in front of the CopilotKit/AG-UI community as *the* way to drive CLI coding agents from a web UI — adjacent to the existing first-party Strands and Bedrock AgentCore integrations.

## Proposed phasing

Each phase has a demoable acceptance gate:

1. **Phase 0 — Spike.** Read-only L1 adapter behind a flag; acceptance: a stock AG-UI client (Dojo or CopilotKit) renders a live CAO run with zero custom adapter code.
2. **Phase 1 — Complete L1.** Full primitive map including real RFC-6902 `STATE_DELTA` payloads, `TOOL_CALL_*` completion, snapshot debouncing, dedicated config flag, docs. Acceptance: protocol-conformance tests + the Phase 0 demo running against every mapped event kind.
3. **Phase 2 — L2 construct library.** The four named constructs, including bidirectional human-in-the-loop via AG-UI interrupts mapped to CAO's command surface, validated across ≥3 providers.
4. **Phase 3 — L3 reference surface.** A fleet dashboard composed purely from L2 constructs; optional authenticated team mode; AG-UI ecosystem listing.

## Prior art & references

- AG-UI: [introduction](https://docs.ag-ui.com/introduction), [agentic protocols](https://docs.ag-ui.com/agentic-protocols), [quickstarts](https://docs.ag-ui.com/quickstart/introduction) ([server](https://docs.ag-ui.com/quickstart/server), [middleware](https://docs.ag-ui.com/quickstart/middleware), [clients](https://docs.ag-ui.com/quickstart/clients), [applications](https://docs.ag-ui.com/quickstart/applications)), [protocol repo](https://github.com/ag-ui-protocol/ag-ui)
- CopilotKit example gallery (what AG-UI clients look like in practice): https://www.copilotkit.ai/examples
- CAO's existing event backbone: [docs/event-driven-architecture.md](https://github.com/awslabs/cli-agent-orchestrator/blob/main/docs/event-driven-architecture.md)
- A working proof-of-concept of the L1 adapter (pure single-file mapping, privacy boundary, RFC-6902 state channel) exists in a fork and can be contributed as the Phase 0/1 starting point.

## Open questions

1. **Governance appetite:** AG-UI is Apache-2.0 but CopilotKit-stewarded rather than foundation-governed (unlike MCP/A2A). Is that acceptable for an awslabs dependency if the adapter is version-pinned and isolated to one module?
2. **MCP trajectory:** upcoming MCP spec work (stateless core, extensions, tasks) may grow to cover some of this territory. Does the thin-adapter hedge above satisfy maintainers, or should Phase 2+ wait for the next MCP release?
3. **v1 scope:** read-only stream first (this proposal's Phase 0–1), or is there appetite to include bidirectional interrupts (Phase 2) in the initial RFC?
4. **Where should the L2 construct library live** — in-tree, or as a separate package depending on CAO?
