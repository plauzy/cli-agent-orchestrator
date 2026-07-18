# Plan: Upstream Integration PR — CAO in the AG-UI Dojo

> **Goal:** land `cli-agent-orchestrator` as a first-class integration in
> [ag-ui-protocol/ag-ui](https://github.com/ag-ui-protocol/ag-ui), rendered at
> [dojo.ag-ui.com](https://dojo.ag-ui.com/), following the repo's own
> [CONTRIBUTING.md](https://github.com/ag-ui-protocol/ag-ui/blob/main/CONTRIBUTING.md).
>
> **Grounding:** every upstream mechanical claim below was verified against
> **ag-ui main @ `b646b46`** (CONTRIBUTING.md, `apps/dojo/*`, `integrations/*`,
> `render.yaml`, `.github/workflows/dojo-e2e.yml`) on 2026-07-17. CAO-side
> capabilities reference the merged L1 (awslabs PR #436) and the Phase-2 spec in
> `.kiro/specs/agui-l2-constructs/` (this branch). This plan operationalizes the
> vision of awslabs issues **#386** / **#458** and the partnership offer in
> #386's "AG-UI roadmap alignment" section; it is the deferred Phase-3
> "AG-UI ecosystem/Dojo listing" item from #458, planned now so Phase 2 lands
> with the upstream target in view.
>
> When this gets promoted to an executable Kiro spec, split §8 into `tasks.md`
> and §§2–7 into `design.md`/`requirements.md`.

---

## 1. Objective and pitch (one paragraph)

Every existing AG-UI integration wraps an in-process agent framework (LangGraph,
Mastra, ADK, Strands, Pydantic AI, …). CAO is a different kind of source: an
**orchestrator of real CLI coding-agent processes** — Kiro CLI, Claude Code,
Codex, and seven more providers running in tmux terminals — that normalizes a
heterogeneous fleet into one event vocabulary and streams it over AG-UI. The
integration makes the Dojo render something no current integration can show:
**live OS processes as agents** — a multi-agent fleet with real handoffs and
delegations, shared fleet state kept convergent by RFC 6902 deltas, generative
UI authored by the agents themselves through a server-validated allow-list, and
— the flagship — **real provider permission prompts surfaced through AG-UI's
shipped interrupt lifecycle**, approved or denied from the browser and resumed
into a live terminal.

## 2. Why CAO is additive (the uniqueness case, evidence-backed)

Each claim below restates #386's "What CAO adds on top of AG-UI" list, now
verified against ag-ui main rather than asserted. "Verified absence" =
confirmed by grep/read of the current repo and docs.

| # | Claim | Upstream ground truth (@ `b646b46`) | CAO ground truth |
|---|---|---|---|
| 1 | **First real-process agent runtime.** | Zero hits for `tmux`/`pty` in `integrations/` + `apps/dojo`; nearest neighbor `claude-agent-sdk` drives a headless SDK-managed session (the SDK's own stdio subprocess) — no pty/tmux, no user-visible terminal, no fleet surface. Verified absence. | tmux-backed lifecycle: spawn, persist, resume, multiplex CLI processes; providers behind one base interface (`providers/base.py`) |
| 2 | **First heterogeneous multi-provider source.** Every integration is single-framework. | All 26 dojo integrations bind one framework/SDK each (`apps/dojo/src/menu.ts`) | 10 provider ids (`models/provider.py`) speak one normalized six-kind vocabulary (`services/event_primitives.py`); a new provider joins with zero protocol code |
| 3 | **First fleet semantics.** | No fleet/session-dashboard concept anywhere; `subgraphs` and `a2a_chat` are single-chat-pane; `background_agents` renders activities inside one conversation. Verified absence. | Session→terminal hierarchy, supervisor snapshot + rolling RFC-6902 deltas, first-class handoff/delegation timeline (Phase-2 L2 constructs) |
| 4 | **Permission prompts as standard interrupts — the shipped lifecycle's highest-volume real workload.** | The interrupt-aware run lifecycle is **shipped** (`docs/concepts/interrupts.mdx`; `RunFinishedEvent.outcome`, `RunAgentInput.resume` in the core schemas). In the Dojo, only Mastra lists the `interrupt` feature page; the native structured-outcome emitters are Mastra (default-on, `integrations/mastra/typescript/src/mastra.ts:384-405`) and AWS Strands TS (always-on, `integrations/aws-strands/typescript/src/agent.ts:1937-1950`), LangGraph keeps it opt-in-off — and every existing suspension is a mock/SDK tool | CAO maps **real** provider permission/trust prompts (`WAITING_USER_ANSWER` + provider patterns) onto `outcome=interrupt` with reasons following the documented `<framework>:<name>` convention (`claude-code:permission_request`, `kiro:trust_prompt`), approve/deny/**edit** resumption into a live terminal (Phase-2 R9/R12) |
| 5 | **Workspace semantics for coding agents.** | No typed representation of diffs/file-trees/terminal output; no coding-agent product mentioned anywhere in docs. Verified absence. | `file_mod`→`STATE_DELTA` convention + `diff_summary`/`progress` components (allow-list). *Honesty note: the `file_mod` producer is still forward-provisioned in CAO — position as "conventions established, wiring underway", not shipped* |
| 6 | **Privacy-bounded observability.** | Upstream privacy discussion is confined to reasoning/CoT (encryption, ZDR, redacted summaries — `docs/concepts/reasoning.mdx` §"Privacy and Compliance"); there is **no** privacy/redaction model for tool output, terminal content, or fleet observability. The declarative-generative-UI card (`introduction.mdx:84`) promises "agents propose trees and constraints, the app validates and mounts", yet neither it nor `docs/concepts/generative-ui-specs.mdx` specifies any validation/security model. Verified. | Metadata-only boundary (bodies never on the wire, test-asserted) + server-validated frozen component allow-list with refusal semantics — a concrete, security-conscious take AG-UI docs currently lack |
| 7 | **The construct programming model.** Others ship adapters. | Integrations are flat client bridges; no layered/subclassable model | L1 pure adapter → L2 named subclassable constructs → L3 composed surfaces (CDK-style), spec'd in `.kiro/specs/agui-l2-constructs/` |
| 8 | **Protocol triad in one runtime.** | `docs/agentic-protocols.mdx:23`: "a single agent can and often does use all 3 simultaneously"; AG-UI "front for" handshakes for MCP/A2A exist as middleware | CAO is the living proof: MCP (every agent gets `cao-mcp-server`), A2A-style handoffs/delegation (shipped), AG-UI (this work) — all over real processes |

**Roadmap alignment** — block names/wording from `docs/introduction.mdx:42-192`
("Building blocks (today & upcoming)"); that file labels no per-item status, so
statuses below are sourced separately (interrupts: shipped per
`docs/concepts/interrupts.mdx` + the core schemas; the rest: upcoming per the
public roadmap and #386):

| Upstream building block (status) | CAO as testbed/first implementation |
|---|---|
| Interrupts / HITL (**shipped**) | Highest-volume real workload: CLI permission prompts; first integration driving `outcome=interrupt`/`resume[]` from **real OS-process prompts** (today's native emitters — Mastra, AWS Strands TS — suspend on mock/SDK tools) |
| Sub-agents and composition (upcoming: "Nested delegation with scoped state, tracing, and cancellation") | CAO's handoff/assign/delegation is a shipping composition system across heterogeneous agents |
| Agent steering (upcoming) | CAO already steers live agents mid-run (input injection, inbox delivery) |
| Tool output streaming (upcoming) | Terminal output → FIFO → event-bus pipeline is a ready-made torture test |
| Shared state read-write (upcoming) | Fleet snapshot + RFC-6902 delta channel is a working read path; L2 defines the write path |
| Generative UI, declarative ("agents propose trees and constraints, the app validates and mounts") | `emit_ui` allow-list is the concrete validate-and-mount realization, refusal-tested |

**Positioning hooks to quote in the upstream issue/PR** (verbatim from their docs):
- Middleware quickstart, `docs/quickstart/middleware.mdx:25`: middleware is for
  "when you don't have direct control over the agent framework or system" — the
  CLI-subprocess case, literally. CAO is that pattern applied to real terminals.
- `docs/agentic-protocols.mdx:20`: AG-UI as the '"kitchen sink" protocol —
  informed by bottom-up, real-world needs' — CAO supplies exactly the bottom-up workload
  (fleets, permission prompts, terminal streams) the roadmap items describe.
- AWS precedent: introduction.mdx already lists **AWS Strands** and **Amazon
  Bedrock AgentCore** as 1st-party rows — awslabs is an established partner
  category; CAO slots beside them.

## 3. Upstream ground rules (CONTRIBUTING.md digest — all verbatim-verified)

1. **Issue first, always**: "Please PLEASE reach out to us first before starting
   any significant work." File an issue on ag-ui-protocol/ag-ui, tag a code
   owner (`.github/CODEOWNERS`) to get assigned, discuss in Discord
   `#-💎-contributing` (discord.gg/Jd3FzfdJa8). The middleware quickstart also
   points at the GitHub **Discussions** board for validating integration ideas.
2. **You maintain it**: "All community integrations … will need to be maintained
   by the community member who made the contribution."
3. **Required structure**: `integrations/cli-agent-orchestrator/python/` with
   `examples/` inside ("The dojo examples must live here"), **plus a required
   `typescript/` folder** ("No matter what language the integration is in …
   at minimum … TypeScript client code that re-exports the HTTP agent" — copy
   `integrations/adk-middleware/typescript/`).
4. **Server env contract**: bind `0.0.0.0` (or honor `HOST`), respect `PORT`.
5. **e2e tests are a hard gate**: "Every feature listed in your sidebar entry
   (in `menu.ts`) needs a corresponding end-to-end test. **Without tests, your
   PR will not be considered ready.**" One Playwright spec per feature under
   `apps/dojo/e2e/tests/caoTests/`, reusing `apps/dojo/e2e/featurePages/*`.
6. **External-PR CI quirk**: e2e doesn't run on external PRs — maintainers
   re-open an internal PR to trigger CI, then merge the contributor PR.
7. **PR description**: include `Fixes #<issue-number>`. No CLA/DCO, no
   changesets; npm publishing + release scopes + Render provisioning are
   maintainer-side follow-ups (see §7/§8 Phase 5).

## 4. Integration architecture

### Identity and constants

| Thing | Value |
|---|---|
| Menu/integration id (the key that must match everywhere) | `cli-agent-orchestrator` |
| Display name | `CLI Agent Orchestrator (awslabs)` |
| npm package (TS client) | `@ag-ui/cli-agent-orchestrator` |
| Env var / `envVars` key | `CAO_URL` / `caoUrl` |
| Dev/CI port | **8024** (verified next free; current allocations 8000–8023 + dojo 9999 + LLM mock 5555) |
| e2e suite | `suite: cli-agent-orchestrator`, `test_path: tests/caoTests`, `services: ["dojo", "cli-agent-orchestrator"]`, `wait_on: http://localhost:9999,tcp:localhost:8024` |

### What lives where (two repos, clean split)

**ag-ui repo (the upstream PR):**

```
integrations/cli-agent-orchestrator/
├── python/
│   ├── examples/                    # the dojo example server (CONTRIBUTING: "must live here")
│   │   ├── pyproject.toml           # uv-managed; dep: cli-agent-orchestrator[agui] (PyPI)
│   │   └── server/__init__.py       # FastAPI app: one AG-UI endpoint per feature
│   └── README.md
└── typescript/                      # REQUIRED thin client
    ├── package.json                 # @ag-ui/cli-agent-orchestrator, tsdown build, vitest,
    │                                #   publint+attw export checks, publishConfig.access=public
    └── src/index.ts                 # export class CliAgentOrchestratorAgent extends HttpAgent
```

**CAO repo (awslabs — prerequisites, mostly already spec'd in Phase 2):**
the protocol-faithful run plane (`POST /agui/v1/run`, Phase-2 R12), the interrupt
lifecycle mapping (R9), `mock_cli` scripted-prompt mode (Phase-2 Task 12), and —
new for the dojo — the **feature-scenario endpoints** the example server mounts
(see §5). Nothing dojo-specific leaks into CAO's core.

### The example server (the piece that makes demos real)

A thin FastAPI app (uv-run, `HOST`/`PORT`-compliant) that **boots and drives a
real `cao-server` + tmux + `mock_cli` fleet underneath**, and exposes one
AG-UI-protocol endpoint per dojo feature. It translates each standardized dojo
scenario into real fleet operations and streams the results back as protocol
events (via the official `ag-ui-protocol` encoder — same machinery as CAO's run
plane). Keyless by construction: `mock_cli` needs no credentials, satisfying the
CI reality that external API keys are absent (dojo CI routes LLM traffic to an
aimock server on `:5555` for nearly all suites — langroid alone needs a real
`OPENAI_API_KEY` secret and is skipped on fork PRs; CAO needs neither).

**Design rule learned from the recon**: dojo feature pages are *standardized
demos with fixed UI contracts* (the shared-state page is a recipe editor; HITL
is a step-planner; the exact event/tool/state contracts are documented in
`integrations/server-starter-all-features/python/examples/example_server/*.py`).
So CAO implements the *same scenarios* — but executed by real orchestrated
processes, which is precisely the demo-worthy difference (e.g. the HITL steps
are dispatched to a worker terminal on approve; the chat drives a supervisor
terminal).

## 5. Dojo feature set

**MVP (each one costs an e2e spec — keep it tight):**

| Feature id | CAO implementation | Wow factor |
|---|---|---|
| `agentic_chat` | Chat message → input to a supervisor terminal (`mock_cli` scripted; real providers documented for local runs); streamed reply as `TEXT_MESSAGE_*` | Table stakes; nearly every integration ships it, e2e helpers exist |
| `shared_state` | The standard recipe scenario, state held/updated by a CAO-driven agent, emitted as `STATE_SNAPSHOT`/RFC-6902 `STATE_DELTA` | Same contract, real process underneath |
| `human_in_the_loop` | Standard `generate_task_steps` contract; on the follow-up run the approved steps are **actually dispatched** as handoffs to worker terminals | First HITL demo whose plan executes on real agents |
| `interrupt` | **Flagship.** A real (scripted in CI, genuine locally) provider permission prompt → `RUN_FINISHED outcome={type:"interrupt", interrupts:[{reason:"claude-code:permission_request", ...}]}` → `resume[]` → keystrokes into the live terminal | First integration whose interrupt is a real process's permission gate; only Mastra ships this feature page today, and every native `outcome=interrupt` emitter (Mastra, AWS Strands TS) suspends on mock/SDK tools |

**Stretch (follow-up PRs, discuss in the issue):**
- `agentic_generative_ui` (long-running fleet task as step state + deltas) and
  `tool_based_generative_ui` (haiku scenario via `emit_ui`-style intents).
- A **net-new feature page** — `multi_agent_fleet` (working title): the CAO
  fleet dashboard (session→terminal hierarchy, handoff timeline, approval
  cards) rendered from the L2 constructs' event stream. This needs a new
  `Feature` union entry + `featureConfig` card + a `(v2)` page component
  upstream, so it lives or dies by maintainer appetite — raise it in the
  Phase-0 issue, don't spring it in the PR. It is the strongest possible
  ecosystem showcase ("no current integration renders N concurrent agents").

**Interrupt-feature evidence to cite in the issue**: the dojo interrupt page's
*rendering* contract still rides the legacy `on_interrupt` CUSTOM event via
CopilotKit's `useInterrupt` (the resume leg already flows through
`RunAgentInput.resume` on the pinned CopilotKit 1.61.2) — CAO can be the first
integration whose page contract is authored against the structured outcome
end-to-end, exactly what the protocol authors shipped it for.

## 6. Complete upstream file-touch checklist (verified against `aws-strands`/`watsonx` traces)

1. `integrations/cli-agent-orchestrator/{python,typescript}` — package + example
   server as in §4 (TS: copy `adk-middleware/typescript` shape; `tsdown` build,
   `vitest`, `publint --strict && attw --pack`).
2. `apps/dojo/src/agents.ts` — `import { CliAgentOrchestratorAgent } from "@ag-ui/cli-agent-orchestrator"` +
   ```ts
   "cli-agent-orchestrator": async () => ({
     ...mapAgents((path) => new CliAgentOrchestratorAgent({ url: `${envVars.caoUrl}/${path}` }),
       { agentic_chat: "agentic-chat", shared_state: "shared-state",
         human_in_the_loop: "human-in-the-loop", interrupt: "interrupt" }),
   }),
   ```
3. `apps/dojo/src/menu.ts` — `{ id: "cli-agent-orchestrator", name: "CLI Agent Orchestrator (awslabs)", features: ["agentic_chat", "shared_state", "human_in_the_loop", "interrupt"] }` (menu.ts is the single source of truth; `IntegrationId` derives from it — `types/integration.ts` needs edits only for a net-new feature).
4. `apps/dojo/src/env.ts` — `caoUrl: string;` + `caoUrl: process.env.CAO_URL || "http://localhost:8024"`.
5. `apps/dojo/package.json` — `"@ag-ui/cli-agent-orchestrator": "workspace:*"` (the `integrations/*/typescript` workspace glob picks the package up automatically).
6. `apps/dojo/scripts/generate-content-json.ts` — `agentFilesMapper` entry mapping each feature to the example-server source shown in the dojo code viewer; then regenerate + commit `apps/dojo/src/files.json` (`pnpm generate-content-json`; CI's `check-generated-files` job fails otherwise).
7. `apps/dojo/scripts/prep-dojo-everything.js` — `ALL_TARGETS["cli-agent-orchestrator"] = { command: "uv sync", cwd: integrations/cli-agent-orchestrator/python/examples }`.
8. `apps/dojo/scripts/run-dojo-everything.js` — `ALL_SERVICES` entry (`uv run dev`, `env: { PORT: 8024 }`) **and** `CAO_URL: "http://localhost:8024"` in both the `dojo` and `dojo-dev` entries.
9. `apps/dojo/e2e/tests/caoTests/` — one Playwright spec per MVP feature (reuse `featurePages/AgenticChatPage`, `HumanInTheLoopPage`, `SharedStatePage`; the interrupt spec follows the Mastra interrupt test pattern).
10. `.github/workflows/dojo-e2e.yml` — matrix entry per §4 table.
11. Docs: `docs/introduction.mdx` Supported-Integrations row (proposed placement: the 1st-party table beside AWS Strands / Bedrock AgentCore, subject to maintainer tiering) + `docs/integrations.mdx` bullet.
12. Optional: `.github/CODEOWNERS` line `integrations/cli-agent-orchestrator @ag-ui-protocol/copilotkit @plauzy`.

**Explicitly NOT in the contributor PR** (maintainer-side, request in the issue):
`prepare-release.yml` scope + npm trusted-publisher record for
`@ag-ui/cli-agent-orchestrator`; `render.yaml` service + `CAO_URL` env on the
hosted dojo; a docs.copilotkit.ai integration page (that's where per-integration
docs live — there are no per-integration pages in the ag-ui repo nav).

## 7. Hosted dojo (dojo.ag-ui.com) considerations

Production dojo is Render (`render.yaml`): 22 web services — the dojo app plus
21 integration backends — most with `rootDir: integrations/<x>/<lang>/examples`
and `uv sync`/`uv run dev` (exceptions: crew-ai via poetry at `python/`, mastra
via npm, the a2a services under `middlewares/`, the .NET server), wired to the
dojo app by `*_URL` env vars. For CAO the hosted service
additionally needs **tmux present in the runtime image** — likely a Docker-type
Render service rather than the native Python runtime. Mitigations, in order:
1. `mock_cli` fleet only on the hosted instance (keyless, deterministic, no
   external CLI installs beyond tmux).
2. If Docker-on-Render is unpalatable to maintainers, ship **local-first**
   (fully functional `run-dojo-everything` story + e2e) and add the hosted
   service as a follow-up with maintainer ops help — the CONTRIBUTING flow
   treats hosting as maintainer-side anyway.
3. Long-term: a small always-on demo fleet with scripted activity loops so the
   hosted page is alive without user input.

## 8. Phased execution plan

- [ ] **Phase 0 — Socialize (do first, per CONTRIBUTING).**
  - [ ] File the upstream issue: pitch (§1–2), MVP feature set (§5), hosted-demo
        question (§7), `multi_agent_fleet` feature-page question, maintenance
        commitment; tag a CODEOWNER; post in Discord `#-💎-contributing` /
        Discussions. Reference awslabs #386's partnership framing.
  - [ ] Get assigned; agree tiering (community vs 1st-party) and interrupt-
        feature scope with maintainers.
- [ ] **Phase 1 — CAO-side prerequisites (awslabs repo; already spec'd).**
  - [ ] Phase-2 spec Tasks 12/13 land: run plane + interrupts + `mock_cli`
        scripted prompts (`.kiro/specs/agui-l2-constructs/tasks.md`).
  - [ ] Publish `cli-agent-orchestrator[agui]` to PyPI at a version the example
        server can pin.
  - [ ] Add the four feature-scenario endpoints (thin, over the run plane /
        REST) — decide home: CAO `examples/` (imported by the upstream example
        server) vs. entirely inside the ag-ui example server. Default: in the
        ag-ui example server, so CAO core stays dojo-agnostic.
- [ ] **Phase 2 — Fork scaffold (ag-ui fork).**
  - [ ] `integrations/cli-agent-orchestrator/typescript` (client re-export,
        build/test/export checks green in the workspace).
  - [ ] `python/examples` server: four endpoints, `HOST`/`PORT` compliance,
        `uv run dev`, boots `cao-server` + tmux + mock fleet as a child.
  - [ ] Verify each endpoint against the stock verifier (`@ag-ui/client`) and
        against the reference contracts in `server-starter-all-features`.
- [ ] **Phase 3 — Dojo wiring + e2e (the §6 checklist).**
  - [ ] Items 2–8; `pnpm generate-content-json`; local proof:
        `./scripts/prep-dojo-everything.js --only dojo,cli-agent-orchestrator`
        + run + `pnpm test tests/caoTests/` from `apps/dojo/e2e`.
  - [ ] Playwright specs incl. the interrupt approve/deny path.
- [ ] **Phase 4 — PR + CI coordination.**
  - [ ] Docs touches (§6 item 11); PR with `Fixes #<issue>`; demo recording
        (GIF) in the PR body — CAO's own CI-generated-recording pattern
        (`examples/agui-eventsource-viewer/tools/record-demo.mjs`) is reusable
        here and matches how #436 proved its demos.
  - [ ] Expect the internal-PR CI dance for external contributors; iterate.
- [ ] **Phase 5 — Maintainer-side follow-ups (tracked in the issue).**
  - [ ] Release scope + npm trusted publishing for the TS package.
  - [ ] `render.yaml` service (Docker w/ tmux) + `CAO_URL` on hosted dojo.
  - [ ] docs.copilotkit.ai page; introduction.mdx tier placement.
  - [ ] Stretch: `multi_agent_fleet` feature page; `agentic_generative_ui` /
        `tool_based_generative_ui` follow-up PR.

## 9. Draft upstream issue skeleton (Phase 0)

> **Title:** Integration proposal: CLI Agent Orchestrator (awslabs) — real CLI
> coding-agent processes (Claude Code / Kiro / Codex) as an AG-UI source
>
> **What it is** — 2 paragraphs from §1, with the #386 architecture diagram.
> **What's new for the ecosystem** — the §2 table collapsed to six bullets:
> first real-process runtime · first heterogeneous multi-provider source ·
> first fleet semantics · permission prompts as your shipped interrupt
> lifecycle's highest-volume real workload (structured `outcome`/`resume[]`
> driven, for the first time, by real OS-process prompts — today's native
> emitters, Mastra and AWS Strands TS, suspend on mock/SDK tools) ·
> a validate-and-mount generative-UI
> realization with an actual security model · MCP + A2A-style handoffs + AG-UI
> in one runtime ("a single agent can and often does use all 3 simultaneously").
> **Proposed MVP** — §5 table; interrupt feature as flagship.
> **Questions for maintainers** — tiering; hosted demo (tmux/Docker on Render);
> appetite for a `multi_agent_fleet` feature page; interrupt e2e expectations.
> **Commitment** — we maintain the integration (CONTRIBUTING §community);
> CODEOWNERS entry offered; roadmap co-design offer per #386 (sub-agents,
> steering, tool-output streaming validated against real processes).

## 10. Risks and open questions

| Risk | Mitigation |
|---|---|
| Dojo demos are standardized scenarios; naive ports could look like "mock theater" over a real orchestrator | Make the real-process substrate visible in each demo (terminal ids, provider names in messages); flagship is the interrupt demo where realness is the point |
| Hosted dojo needs tmux in the image | §7 ladder: mock-fleet Docker service → local-first fallback |
| e2e determinism with real processes | `mock_cli` scripted mode everywhere in CI (keyless, deterministic); real providers are the documented local path |
| `interrupt` feature page currently consumes the legacy CUSTOM event via CopilotKit | Emit structured outcome **and** ride the existing page contract initially (Mastra emits both simultaneously — proven pattern); push the structured-resume page as follow-up |
| Maintainer bandwidth / partnership uncertainty | Issue-first per CONTRIBUTING; scope MVP small (4 features); every stretch item pre-flagged as optional |
| CAO Phase-2 timing (run plane not yet merged) | Phases 0 and 2 (scaffold + TS client) can start now; Phase 3 gates on Phase-2 Tasks 12/13 |
