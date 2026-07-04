# Kiro continuation plan: from PR #9 to the AG-UI construct vision

- **Date:** 2026-07-04
- **Inputs:** the PR #9 audit (`docs/audits/pr9-agui-audit-2026-07-04.md`, findings `AUD-01`…`AUD-15`), the RFC series (MCP Apps implementation plan, AG-UI L2 dashboard, Auth0 MCP + WebSocket, and the AG-UI vision & fork assessment), and the upstream proposal draft (`docs/proposals/upstream-issue-agui-construct-model.md`).
- **Audience:** Kiro (the agent executing the work) and the human reviewing its PRs.

## North star

Deliver the construct model from the vision RFC — L1 raw AG-UI event primitives → L2 named subclassable constructs → L3 composed surfaces — such that by the end of Phase 3 a stock AG-UI client renders a live CAO fleet with zero custom adapter code, and the work is packaged as an upstream (awslabs) contribution.

PR #9 already contains the seed of L1 (`services/agui_stream.py` is the right shape) plus valuable auth and telemetry work. The plan below salvages that, fixes what the audit found, and sequences the rest.

## Phase 0 — Make PR #9 honest and mergeable (split it)

**Goal:** replace the 243-file mega-PR with a short series of reviewable PRs; every claim in every PR description is true.

Split into this series (each independently mergeable, roughly in this order):

| # | PR | Contents | Blocking fixes |
|---|---|---|---|
| 0a | AG-UI SSE stream + adapter | `services/agui_stream.py`, `/agui/v1/stream`, mapping tests, docs | AUD-15 (dedicated `CAO_AGUI_ENABLED` flag, decoupled from MCP Apps), AUD-03 server side (implement `?since=` replay from event history, or drop the param everywhere), AUD-08 (commit the cited RFC docs into `docs/rfc/` or strip the references) |
| 0b | WebSocket auth | `cao.bearer.<jwt>` subprotocol, close codes, e2e tests | none — this is clean; keep default-off contract test |
| 0c | OTel telemetry | `telemetry/`, lifespan wiring, `traceparent` plumbing | none material |
| 0d | Agent Card / A2A listener | `agent_card/`, `a2a/` | **AUD-04**: invert the gate (off unless `CAO_AGENT_CARD_ENABLED`), default bind `127.0.0.1`, document the exposure; drop the ACP placeholder (AUD-06) until it has a real executor |
| 0e | `cao_pwa/` dashboard | PWA, generative-UI renderers, demo | **AUD-02** (subscribe `GENERATIVE_UI`, `STATE_SNAPSHOT`, `STATE_DELTA`, `TOOL_CALL_START`, `RUN_ERROR`; add EventSource auto-reconnect), AUD-03 client side (`access_token` handling that matches the server, read it from `location.search` or remove the docs claim), AUD-05 (fix `CAO_PWA_ORIGIN`→`CAO_CORS_ORIGINS`, add :5174 to CORS docs, document the gate in the quick start) |
| 0f | Providers (Gemini/Q) | provider modules + fixtures | **AUD-07**: open an upstream discussion referencing #353 first; do not merge until the removal rationale is addressed. `mock_cli` can land separately — it's test infrastructure. |

**Park, do not merge:** `orchestration/`, `observability/`, `cache/`, `refinery/`, `persistence/` WAL, `budget_service`, `ai_manifest`, zellij bridge + WASM (AUD-06, AUD-10). Move them to a clearly-labeled experimental branch. Each returns later only in the same PR as its first real consumer.

**Hygiene sweep (one small PR or folded into 0a):** merge `tests/validation/` into `test/` (AUD-11); fix `[tool.mypy] python_version` (AUD-12); scrub internal codenames or add a glossary (AUD-13); add CHANGELOG entries per feature (AUD-14); remove root agent-instruction files from the feature series; delete the committed `.wasm` (AUD-10).

**Exit criteria:** PR #9 closed with a comment linking the series; every replacement PR ≤ ~2k lines; CI green without coverage-floor games; a test asserts `cao-server` with no flags opens no listener beyond :9889.

*(Fallback if speed is preferred over reviewability: fix AUD-01…AUD-05 in place on PR #9 and land it whole. Not recommended — the 243-file review will stall.)*

## Phase 1 — Complete L1 (the protocol adapter)

**Goal:** the full primitive→event map is real, not stubbed; acceptance is a stock client, not a canned replay.

1. **Real `STATE_DELTA` payloads** (AUD-09): wire `ui_state_service.diff_snapshot` as the per-event RFC-6902 patch source for `file_mod` and fleet-state changes; add debounce/coalescing so the fleet snapshot is not recomputed per event.
2. **Complete the tool-call lifecycle:** emit `TOOL_CALL_ARGS`/`TOOL_CALL_END`/`TOOL_CALL_RESULT` for handoffs and delegations, not just `TOOL_CALL_START`.
3. **A producer for UI intents** (AUD-01): an MCP tool (e.g. `emit_ui(component, props)`) on the CAO MCP server plus a provider hook, validated against the frozen allow-list server-side. This is what makes `GENERATIVE_UI` a feature instead of a demo.
4. **Replay:** `?since=` on `/agui/v1/stream` backed by the event history buffer, with client-side dedup by event id.
5. **Conformance:** run the endpoint against the AG-UI Dojo / a stock CopilotKit client.

**Exit criteria (the Phase 0 spike demo from the RFC):** a stock AG-UI client renders a live CAO run — launch, handoff, file mods, completion — with zero custom adapter code. The CI demo video records the live path (never a canned replay — that was the PR #9 mistake).

## Phase 2 — L2 construct library

**Goal:** the four named constructs from the vision RFC, as subclassable classes over the L1 stream.

1. `SupervisorDashboardStream` — fleet `STATE_SNAPSHOT` + rolling deltas (mostly exists after Phase 1; formalize the API).
2. `AgentHandoffWithApproval` — bidirectional HITL: map provider permission/trust prompts onto AG-UI's interrupt lifecycle (`RUN_FINISHED` with `interrupt` outcome → resume with approval payload → route to the command surface, e.g. `submit_command`). Namespace interrupt reasons per provider: `claude-code:permission_request`, `kiro:trust_prompt`, etc.
3. `CrossProviderStateSync` — one coherent thread over N heterogeneous workers; validated on ≥3 providers (Kiro CLI, Claude Code, Codex).
4. `MultiAgentSessionTimeline` — ordered merge of handoff/delegation/tool-call/error events.

Design rule: a new provider gets all four constructs by implementing the base provider interface — if adding a provider requires touching a construct, the abstraction is wrong.

**Exit criteria:** each construct has its own docs page + a runnable example; the HITL construct approves/denies a real Claude Code permission prompt from a browser.

## Phase 3 — L3 surface + upstream contribution

1. Recompose `cao_pwa` so its views are built only from L2 constructs (delete bespoke SSE wiring).
2. Optional team mode: enable the Auth0 scope taxonomy (`cao:read/write/admin`) shipped in Phase 0b across the AG-UI surface.
3. **Upstream:** open the issue drafted in `docs/proposals/upstream-issue-agui-construct-model.md` on awslabs/cli-agent-orchestrator; follow with an RFC and the Phase 0a adapter PR as the first concrete contribution; submit an AG-UI ecosystem/integration listing.

## Working agreements (distilled from the audit — apply to every PR)

1. **No unwired scaffolding.** Code lands in the same PR as its first real consumer. "Commit N will wire this" is not a consumer.
2. **PRs ≤ ~2k lines** excluding lockfiles and fixtures.
3. **Default-off means default-off.** Every new network surface ships behind an explicit *enable* flag, binds loopback by default, and has a test asserting no new listeners appear without flags.
4. **Demos drive the live path.** CI proof videos and acceptance demos must exercise the real server + real client, never a canned replay artifact.
5. **No committed binaries.** Build artifacts (wasm, bundles) are produced by CI, not checked in.
6. **No internal codenames** in code, docs, or commit messages ("Polecat", "Bolt 3", "commit 26") — write for a reviewer with no access to the planning context, or ship a glossary.
7. **Every feature gets a CHANGELOG entry** and user-facing docs whose quick start has been executed as written.
8. **Cite designs that exist.** If a doc references an RFC section, that RFC is in `docs/rfc/` in the same PR.
9. **Don't relitigate upstream decisions silently.** Re-adding anything upstream removed (e.g. providers from #353) starts with a discussion issue, not a diff.
