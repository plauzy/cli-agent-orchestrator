# Requirements Document

## Introduction

This document specifies the requirements for the **upstream AG-UI Dojo integration
PR** -- landing `cli-agent-orchestrator` as a first-class integration in the
[ag-ui-protocol/ag-ui](https://github.com/ag-ui-protocol/ag-ui) repository, rendered
at [dojo.ag-ui.com](https://dojo.ag-ui.com/).

The feature is the Phase-3 "AG-UI ecosystem / Dojo listing" item from tracking issue
awslabs/cli-agent-orchestrator **#458**, deferred from Phase 2 so that Phase 2 (the
L2 construct library, `.kiro/specs/agui-l2-constructs/`) lands with the upstream
target in view. This spec operationalizes the partnership offer in issue **#386**'s
"AG-UI roadmap alignment" section.

**Grounding:** every upstream structural/mechanical claim was verified against
**ag-ui main @ `b646b46`** (CONTRIBUTING.md, `apps/dojo/*`, `integrations/*`,
`render.yaml`, `.github/workflows/dojo-e2e.yml`) on 2026-07-17, and re-audited
2026-07-18 @ **ag-ui `3a7433e`** / **CAO `41c8ce7`** (no cited surface changed;
see `.kiro/specs/agui-l2-constructs/audit.md` addendum). CAO-side capabilities
reference the merged L1 (awslabs PR #436) and the Phase-2 spec in
`.kiro/specs/agui-l2-constructs/`.

**Out of scope:** Phase-2 L2 construct implementation (separate spec); hosted dojo
Render service provisioning (maintainer-side follow-up); `multi_agent_fleet` net-new
feature page (stretch, subject to maintainer appetite); `docs.copilotkit.ai`
integration page (not in the ag-ui repo); release-scope / npm publishing
(maintainer-side).

## Glossary

- **Dojo**: the AG-UI reference playground app at `apps/dojo/` rendering integration
  demos per feature page.
- **Integration_Id**: `cli-agent-orchestrator` -- the key that must match across
  `menu.ts`, `agents.ts`, `env.ts`, the npm package scope, the TS/Python workspace
  directories, and CI.
- **Feature_Page**: a standardized dojo demo scenario with a fixed UI contract (e.g.
  the shared-state recipe editor, the HITL step-planner, the interrupt
  approve/deny card).
- **TS_Client**: the required TypeScript thin-client package
  `@ag-ui/cli-agent-orchestrator` re-exporting `HttpAgent` with the CAO base URL.
- **Example_Server**: the FastAPI example server in
  `integrations/cli-agent-orchestrator/python/examples/` that drives a real
  `cao-server` + tmux + `mock_cli` fleet underneath and exposes one AG-UI-protocol
  endpoint per dojo feature.
- **Stock_Client**: an unmodified upstream AG-UI client (`@ag-ui/client` HttpAgent /
  CopilotKit / AG-UI Dojo page) containing zero CAO-specific adapter code.
- **Mock_Fleet**: a keyless, deterministic fleet driven by `mock_cli` scripted mode
  (CI-safe, no external API keys required).
- **Feature_Set**: the four MVP features (`agentic_chat`, `shared_state`,
  `human_in_the_loop`, `interrupt`) listed in the dojo sidebar entry.
- **Dev_Port**: 8024 (verified next free; current allocations 8000-8023 + dojo 9999
  + LLM mock 5555).
- **Env_Var**: `CAO_URL` / `caoUrl` -- the environment variable wiring the dojo app
  to the example server.

## Requirements

### Requirement 1: Upstream issue filed and assigned (Phase 0 socialization)

**User Story:** As the integration maintainer, I want an upstream issue filed per
CONTRIBUTING.md's "Issue first, always" rule, so that scope is agreed with
maintainers before significant work begins.

#### Acceptance Criteria

1. THE integration author SHALL file an issue on `ag-ui-protocol/ag-ui` pitching the integration (uniqueness case, MVP feature set, hosted-demo question, maintenance commitment), tag a CODEOWNER, and post in Discord `#-💎-contributing` / Discussions.
2. THE issue SHALL reference awslabs #386's partnership framing and propose tiering (community vs 1st-party, beside AWS Strands / Bedrock AgentCore).
3. THE issue SHALL explicitly ask maintainers about appetite for a `multi_agent_fleet` feature page and the interrupt-feature scope.
4. THE integration author SHALL NOT open the implementation PR until assigned on the issue.

### Requirement 2: TypeScript thin-client package

**User Story:** As a dojo consumer, I want a TypeScript client package that re-exports
an HttpAgent pointing at the CAO example server, so that the dojo app can instantiate
the integration like any other.

#### Acceptance Criteria

1. THE TS client SHALL live at `integrations/cli-agent-orchestrator/typescript/` with a `package.json` naming the package `@ag-ui/cli-agent-orchestrator`, build via `tsdown`, test via `vitest`, export checks via `publint --strict && attw --pack`, and `publishConfig.access: "public"`.
2. THE TS client SHALL export a class `CliAgentOrchestratorAgent` extending `HttpAgent` that accepts a `url` constructor parameter and requires no CAO-specific wire decoding.
3. THE TS client's package shape SHALL match the `integrations/adk-middleware/typescript/` reference (CONTRIBUTING.md: "copy adk-middleware/typescript shape").
4. IF `pnpm build` is run in the TS client workspace, THEN it SHALL produce a working ESM/CJS bundle passing `publint --strict && attw --pack` without errors.

### Requirement 3: Python example server

**User Story:** As a dojo operator, I want a Python example server that boots a real
CAO fleet and exposes one AG-UI endpoint per feature, so that the dojo renders demos
driven by real orchestrated processes.

#### Acceptance Criteria

1. THE example server SHALL live at `integrations/cli-agent-orchestrator/python/examples/` with a `pyproject.toml` managed by `uv`, depending on `cli-agent-orchestrator[agui]` from PyPI.
2. THE example server SHALL bind `0.0.0.0` (or honor the `HOST` env var) and respect the `PORT` env var, defaulting to port 8024.
3. THE example server SHALL boot a `cao-server` instance with tmux and a `mock_cli` fleet as a child process, keyless and deterministic (no external API keys required for CI).
4. THE example server SHALL expose one AG-UI-protocol endpoint per MVP feature: `/agentic-chat`, `/shared-state`, `/human-in-the-loop`, `/interrupt`.
5. WHEN any feature endpoint receives a valid `RunAgentInput` POST, THE example server SHALL translate the dojo scenario into real fleet operations and stream results as protocol events via the official `ag-ui-protocol` encoder.
6. IF the example server is started via `uv run dev`, THEN it SHALL be ready to accept connections within 30 seconds.
7. THE example server SHALL expose a `/health` route at the root path and SHALL NOT combine `allow_credentials=True` with a wildcard CORS origin, following the `CORS_ALLOW_ORIGINS` pattern upstream applied across example servers (ag-ui `3b370a5`, #1939/#1940: credentials only for explicit, non-wildcard origins).

### Requirement 4: Dojo menu and agents wiring

**User Story:** As a dojo visitor, I want CLI Agent Orchestrator to appear in the dojo
sidebar with its feature pages, so that I can navigate to its demos.

#### Acceptance Criteria

1. THE dojo `apps/dojo/src/menu.ts` SHALL include an entry `{ id: "cli-agent-orchestrator", name: "CLI Agent Orchestrator (awslabs)", features: ["agentic_chat", "shared_state", "human_in_the_loop", "interrupt"] }`.
2. THE dojo `apps/dojo/src/agents.ts` SHALL import `CliAgentOrchestratorAgent` from `@ag-ui/cli-agent-orchestrator` and map each feature to a URL path under `envVars.caoUrl`.
3. THE dojo `apps/dojo/src/env.ts` SHALL declare `caoUrl: string` with default `process.env.CAO_URL || "http://localhost:8024"`.
4. THE dojo `apps/dojo/package.json` SHALL depend on `"@ag-ui/cli-agent-orchestrator": "workspace:*"`.
5. WHEN `pnpm generate-content-json` is run, THE generated `apps/dojo/src/files.json` SHALL include the example-server source for the dojo code viewer, and the `check-generated-files` CI job SHALL pass.

### Requirement 5: Dojo scripts integration

**User Story:** As a developer running the full dojo locally, I want the CAO example
server to start alongside all other integrations, so that all feature pages work
out of the box.

#### Acceptance Criteria

1. THE `apps/dojo/scripts/prep-dojo-everything.js` SHALL include a `cli-agent-orchestrator` target with `command: "uv sync"` and `cwd` pointing to `integrations/cli-agent-orchestrator/python/examples`.
2. THE `apps/dojo/scripts/run-dojo-everything.js` SHALL include a `cli-agent-orchestrator` service entry running `uv run dev` with `env: { PORT: "8024" }`.
3. THE `run-dojo-everything.js` SHALL inject `CAO_URL: "http://localhost:8024"` into both the `dojo` and `dojo-dev` service entries' environment.
4. WHEN `./scripts/prep-dojo-everything.js --only dojo,cli-agent-orchestrator` followed by `./scripts/run-dojo-everything.js` is executed, THEN the dojo app and example server SHALL both start and the CAO feature pages SHALL render.

### Requirement 6: End-to-end Playwright tests

**User Story:** As a maintainer, I want end-to-end tests for every listed feature, so
that the integration's PR meets the hard gate ("Without tests, your PR will not be
considered ready").

#### Acceptance Criteria

1. THE integration SHALL provide one Playwright spec per MVP feature in `apps/dojo/e2e/tests/caoTests/` (four specs total: agentic chat, shared state, human-in-the-loop, interrupt).
2. THE specs SHALL reuse existing feature page helpers (`featurePages/AgenticChatPage`, `SharedStatePage`, `HumanInTheLoopPage`) where available, following the patterns established by existing integration tests.
3. THE interrupt spec SHALL test both approve and deny paths, following the Mastra interrupt test pattern.
4. IF any spec requires a service running, THEN the spec SHALL wait for the service (e.g. `wait_on: tcp:localhost:8024`) before executing assertions.
5. THE e2e tests SHALL pass deterministically against the `mock_cli` fleet (no flaky external API dependencies).

### Requirement 7: CI workflow entry

**User Story:** As a CI system, I want the dojo-e2e workflow to include the CAO
integration in its test matrix, so that regressions are caught on every PR.

#### Acceptance Criteria

1. THE `.github/workflows/dojo-e2e.yml` SHALL include a matrix entry: `suite: cli-agent-orchestrator`, `test_path: tests/caoTests`, `services: ["dojo", "cli-agent-orchestrator"]`, `wait_on: http://localhost:9999,tcp:localhost:8024`.
2. THE CI entry SHALL require no external API keys (mock_cli fleet is keyless).
3. IF the external-PR CI quirk applies (e2e doesn't run on external PRs), THEN the PR description SHALL note this for maintainers to re-trigger via an internal PR.

### Requirement 8: Documentation touches

**User Story:** As a prospective user browsing the AG-UI docs, I want CLI Agent
Orchestrator listed in the supported integrations, so that I can discover it.

#### Acceptance Criteria

1. THE `docs/introduction.mdx` Supported-Integrations table SHALL include a row for CLI Agent Orchestrator (proposed placement: beside AWS Strands / Bedrock AgentCore in the 1st-party table, subject to maintainer tiering decision).
2. THE `docs/integrations.mdx` SHALL include a bullet for CLI Agent Orchestrator with a link to the integration directory.
3. THE PR description SHALL include `Fixes #<issue-number>` referencing the Phase 0 issue.

### Requirement 9: Agentic chat feature implementation

**User Story:** As a dojo visitor, I want the agentic_chat feature page to show a live
conversation with a real CAO-driven agent, so that I can see the orchestrator in action.

#### Acceptance Criteria

1. WHEN a chat message is submitted on the agentic_chat page, THE example server SHALL route the message as input to a supervisor terminal (mock_cli scripted in CI; real providers documented for local runs).
2. THE example server SHALL stream the reply as `TEXT_MESSAGE_START`, `TEXT_MESSAGE_CONTENT` (deltas), and `TEXT_MESSAGE_END` events following the standard lifecycle ordering.
3. THE response stream SHALL pass the stock client verifier's lifecycle rules.

### Requirement 10: Shared state feature implementation

**User Story:** As a dojo visitor, I want the shared_state feature page to show state
managed by a CAO-driven agent, so that I can see fleet state convergence in action.

#### Acceptance Criteria

1. THE example server SHALL implement the standard recipe scenario (the dojo's shared-state contract: recipe title, ingredients, instructions managed by the agent).
2. THE agent SHALL hold and update state, emitting `STATE_SNAPSHOT` followed by `STATE_DELTA` (RFC 6902 ops) as the recipe is modified.
3. THE state updates SHALL originate from a real CAO-managed process (mock_cli scripted to produce the recipe scenario).

### Requirement 11: Human-in-the-loop feature implementation

**User Story:** As a dojo visitor, I want the human_in_the_loop feature page to show a
real plan-then-execute workflow where approved steps are dispatched to worker
terminals, so that I can see the first HITL demo whose plan executes on real agents.

#### Acceptance Criteria

1. THE example server SHALL implement the standard `generate_task_steps` contract (the dojo's HITL scenario: generate steps, present for approval, execute approved steps).
2. WHEN the user approves steps on the follow-up run, THE example server SHALL dispatch the approved steps as handoffs to worker terminals in the mock_cli fleet.
3. THE dispatched steps SHALL execute as real process operations (not mocked at the protocol level).

### Requirement 12: Interrupt feature implementation (flagship)

**User Story:** As a dojo visitor, I want the interrupt feature page to show a real
provider permission prompt surfaced through AG-UI's interrupt lifecycle, so that I can
approve or deny a real OS-process permission gate from the browser.

#### Acceptance Criteria

1. THE example server SHALL drive a scripted (in CI) or genuine (locally) provider permission prompt, emitting `RUN_FINISHED` with `outcome: {type: "interrupt", interrupts: [{reason: "claude-code:permission_request", ...}]}`.
2. WHEN the user submits a resume decision (approve or deny), THE example server SHALL deliver the decision as keystrokes to the live terminal through the standard interrupt `resume[]` protocol path.
3. THE interrupt SHALL follow the AG-UI documented contract: emit `STATE_SNAPSHOT` before the interrupting `RUN_FINISHED`; `resume[]` must cover all open interrupts; custom reasons use the `<framework>:<name>` convention.
4. THE interrupt feature SHALL be the first integration whose interrupt is a real process's permission gate (not a mock/SDK tool suspension).

### Requirement 13: PR structure and submission

**User Story:** As a contributor, I want the PR to follow all upstream submission
rules, so that it is accepted without process objections.

#### Acceptance Criteria

1. THE PR description SHALL include `Fixes #<issue-number>`, a demo recording (GIF) showing the interrupt feature in action, and a feature summary.
2. THE PR SHALL NOT include: `prepare-release.yml` scope changes, npm trusted-publisher records, `render.yaml` service definitions, or `docs.copilotkit.ai` page content (these are maintainer-side follow-ups).
3. THE PR SHALL include a `.github/CODEOWNERS` line `integrations/cli-agent-orchestrator @ag-ui-protocol/copilotkit @plauzy` (optional per CONTRIBUTING, but offered).
4. IF the PR passes local e2e validation, THEN it SHALL be submitted with a note about the external-PR CI dance (maintainers re-open internal PR to trigger CI).

### Requirement 14: CAO-side prerequisites satisfied

**User Story:** As the integration author, I want CAO Phase-2 prerequisites landed
before the dojo PR depends on them, so that the example server has a stable foundation.

#### Acceptance Criteria

1. THE Phase-2 spec Tasks 12/13 (run plane + interrupts + mock_cli scripted prompts) SHALL be merged in awslabs/cli-agent-orchestrator before the upstream PR is submitted.
2. THE `cli-agent-orchestrator[agui]` extra SHALL be published to PyPI at a version the example server can pin.
3. THE four feature-scenario endpoints SHALL be implemented inside the ag-ui example server (keeping CAO core dojo-agnostic).

### Requirement 15: Hosted dojo considerations

**User Story:** As a dojo.ag-ui.com visitor, I want the integration to work on the
hosted dojo eventually, so that I do not need a local setup.

#### Acceptance Criteria

1. THE example server SHALL be designed to run in a Docker container with tmux present (Render Docker-type service).
2. IF Docker-on-Render is unpalatable to maintainers, THEN the integration SHALL ship local-first (fully functional `run-dojo-everything` story + e2e) with the hosted service as a documented follow-up.
3. THE hosted instance SHALL use mock_cli fleet only (keyless, deterministic, no external CLI installs beyond tmux).

