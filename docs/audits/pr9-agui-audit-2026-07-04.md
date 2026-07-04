# Audit: PR #9 — "feat: agentic protocol surface + generative UI for the operator dashboard"

- **Date:** 2026-07-04
- **Scope:** `plauzy/cli-agent-orchestrator` PR #9, branch `feat/agentic-protocols-generative-ui` (head `ba707c2`) against base `main` (`4dc8bf7`)
- **Author of PR:** opened by @plauzy via @kiro-agent (Kiro Web); both commits authored by "Kiro Agent"
- **Method:** full PR metadata/diff review, local inspection of the fetched branch, and a wiring sweep of every new backend package. Key negative findings (missing subscriptions, missing query params, default bind) were re-verified directly against branch file contents.

## 1. Summary verdict

PR #9 is really three PRs living in one:

1. **Near-production-grade work** — the AG-UI SSE adapter, WebSocket auth, and OpenTelemetry integration are careful, well-tested, and correctly layered on existing infrastructure.
2. **Demo-ware** — the headline "generative UI" feature has no producer and no live consumer; it only works in a canned replay artifact, which is also what the CI "proof" video records.
3. **Unwired scaffolding** — roughly 5–6k source lines (orchestration, observability, cache, refinery, persistence, ACP, budget) ship ahead of any consumer, referencing future "commits" that don't exist in the PR.

The PR's central claim — "every new surface is default-off" — is **false** for its largest new attack surface (AUD-04).

Recommendation: split into a reviewable series, land the production-grade parts, fix the P0s, and park the scaffolding. See `docs/proposals/kiro-continuation-plan.md`.

## 2. PR metadata

| Field | Value |
|---|---|
| Title | feat: agentic protocol surface + generative UI for the operator dashboard |
| State | Open, not draft, mergeable_state clean, CI pending (0 check runs on head) |
| Size | 243 files, +35,663 / −45 |
| Commits | 2: `5ba62a1` (entire feature, one mega-commit), `ba707c2` (CI fix + deletion of 344 lines of admitted dead code to pass the coverage floor) |
| Supersedes | PR #8 |
| Reviews/comments | None |

Size breakdown: `src/` 72 files (+10,827), `test/` 84 files (+14,163) plus a second `tests/validation/` tree (~1,100 lines), `cao_pwa/` 23 files (~4,900 incl. lockfile), `docs/` 11 files (~1,900), `zellij/` 7 files incl. a committed 632 KB `zellaude.wasm`, plus `.github/`, `.devcontainer/`, `examples/`, and root `AGENTS.md`/`CLAUDE.md`/`GEMINI.md`.

## 3. What the PR implements

### 3.1 AG-UI backend (solid)

- `src/cli_agent_orchestrator/services/agui_stream.py` (377 lines): a pure, well-documented adapter mapping the existing six-primitive event vocabulary (`services/event_primitives.py`, already on main) onto AG-UI typed events:

  | CAO primitive | AG-UI event |
  |---|---|
  | `launch` | `RUN_STARTED` (session) / `STEP_STARTED` (terminal) |
  | `completion` | `RUN_FINISHED` / `STEP_FINISHED` |
  | `handoff` | `TEXT_MESSAGE_CONTENT` with **empty delta** — metadata only, bodies redacted by design |
  | `a2a_delegation` | `TOOL_CALL_START` |
  | `file_mod` | `STATE_DELTA` with **empty patch** (acknowledged stub, `agui_stream.py:181`) |
  | `error` | `RUN_ERROR` |
  | other | `RAW` with `cao_type` |

  Plus `state_snapshot_frame`/`state_delta_frame` wrapping main's existing `ui_state_service.build_dashboard_snapshot`/`diff_snapshot` (RFC 6902).
- `GET /agui/v1/stream` (`api/main.py`, +248/−5 net): SSE endpoint over the existing `SseBus`; emits named SSE frames, `STATE_SNAPSHOT` on connect, then `STATE_DELTA` computed by recomputing the full fleet snapshot after every event (no debounce — self-acknowledged). Gated behind `CAO_MCP_APPS_ENABLED` (reuses the MCP Apps gate; no dedicated AG-UI flag) plus `cao:read` scope floor.
- `GENERATIVE_UI` typed event — a CAO extension, not an AG-UI spec event (spec purists would use `CUSTOM`). Events carrying `ui: {component, props}` map through a frozen allow-list `{approval_card, choice_prompt, diff_summary, progress, metric, agent_card}`; off-list components are refused to `RAW` with `rejected_component`; props JSON-validated and capped at 8 KB.

### 3.2 Frontend — `cao_pwa/`

Standalone React/Vite PWA (:5174): EventSource client (`api.ts`), IndexedDB instance picker, pure-reducer `InstanceTab`, `GenerativeUI.tsx` (149 lines; JSON-props-only renderers, no `dangerouslySetInnerHTML`, client-side allow-list mirror), a self-contained `demo/generative-ui-replay.html` with a pre-baked 199-event sequence, and a Playwright spec + CI workflow that records a video of the **demo replay HTML** — not the live app.

### 3.3 Other protocol surfaces

- `a2a/` (~810 lines): JSON-RPC 2.0 router + SSE task stream + in-memory task store; `agent_card/` (~500 lines): Ed25519-signed Agent Card, JWKS, RFC 9728 PRM router — mounted on a **second uvicorn listener on 0.0.0.0:9890**, started in the app lifespan by default.
- `acp/` (~580 lines): stdio Agent Client Protocol server (`cao-acp` entry point) — handler returns a literal placeholder string (`acp/handlers.py:199-208`).
- WebSocket auth on `/terminals/{id}/ws`: JWT via `Sec-WebSocket-Protocol: cao.bearer.<jwt>` subprotocol, 4401/4403 close codes, per-frame write-scope check with silent input drop for read-only viewers. Real, tested (368-line e2e test), default-off, preserves the no-auth localhost contract.
- `telemetry/` OTel: real, opt-in, wired into lifespan; `traceparent` propagated through `plugins/events.py`.
- Providers: `gemini_cli.py` (815 lines), `q_cli.py` (167), `mock_cli.py` (113), registered in `providers/manager.py`, with extensive fixtures and unit tests.
- Not wired to anything at runtime: `orchestration/` (~1,700 lines — DAG, swarm, "Polecat", dispatch, hybrid cluster, topology router), `observability/` (~1,350 — "ASI" evaluator, mitigations, phantom state), `cache/` (~790), `refinery/` (~980, Cedar-policy write queue that "doesn't yet replace the direct db.commit() calls"), `persistence/` WAL (~490, `init_wal` never called), `services/budget_service.py`, `web/ai_manifest.py`, `services/zellij_bridge.py` + zellij WASM plugin.

## 4. Findings

### P0 — must fix before merge

| ID | Finding | Evidence |
|---|---|---|
| **AUD-01** | **No producer for generative-UI intents.** Nothing in providers, MCP tools, or plugins ever emits an event carrying `ui.component`; `GENERATIVE_UI` appears in `src/` only inside `agui_stream.py`. Agents have no mechanism to author a UI intent. The pipeline only runs in tests and the canned demo. | `git grep GENERATIVE_UI` on the branch: matches only `services/agui_stream.py` |
| **AUD-02** | **The live client can never receive the headline events.** `cao_pwa/src/api.ts` registers EventSource listeners only for `RUN_STARTED, RUN_FINISHED, STEP_STARTED, STEP_FINISHED, TEXT_MESSAGE_CONTENT, RAW`. Named SSE events `GENERATIVE_UI`, `STATE_SNAPSHOT`, `STATE_DELTA`, `TOOL_CALL_START`, `RUN_ERROR` are never subscribed — the Generative-UI panel and shared-state channel are unreachable from a live server. Component tests pass because they bypass the SSE layer; the CI video drives the static replay HTML. | `cao_pwa/src/api.ts:31-38` |
| **AUD-03** | **Client/server contract mismatch.** The client sends `?since=` and `?access_token=` on `/agui/v1/stream`; the endpoint accepts neither (no `since` param; auth reads the Authorization header only). `docs/pwa.md` claims the PWA picks up `access_token` from the URL; no code reads `location.search`. | `cao_pwa/src/api.ts:24-25` vs `api/main.py:708-711` |
| **AUD-04** | **"Default-off" claim is false for the biggest new surface.** The Agent Card / A2A listener starts by default in the lifespan (`CAO_AGENT_CARD_DISABLED` defaults false) and binds `0.0.0.0:9890`, deliberately outside the main app's TrustedHost/CORS posture. On an otherwise localhost-only tool, `cao-server` now opens an externally reachable port with A2A JSON-RPC mounted unless `CAO_A2A_DISABLED` is set. Directly contradicts the PR description. | `agent_card/listener.py:97` (`CAO_AGENT_CARD_HOST` default `"0.0.0.0"`) |
| **AUD-05** | **Docs quick start cannot work.** `docs/pwa.md` never mentions that `/agui/v1/stream` returns 404 unless `CAO_MCP_APPS_ENABLED` is set; the PWA dev server runs on :5174 but the default CORS origins allow only :3000/:5173; docs tell operators to set `CAO_PWA_ORIGIN`, which exists nowhere in `src/` (the real variable is `CAO_CORS_ORIGINS`). | `api/main.py` (`_require_mcp_apps_enabled()` in the endpoint), `docs/pwa.md` |

### P1 — should fix before/while landing

| ID | Finding |
|---|---|
| **AUD-06** | ~5–6k lines of unwired scaffolding (`orchestration/`, `observability/`, `cache/`, `refinery/`, `persistence/`, `acp/` placeholder, `budget_service`, `ai_manifest`) shipped ahead of any consumer, covered only by their own unit tests. Code comments defer wiring to "commit 14/22/26/27" — commits that don't exist in this PR. Commit `ba707c2` deleted three *other* orphaned modules specifically to lift coverage past the floor (86.59% → 87.39%), i.e. the coverage gate was gamed rather than the dead code confronted. |
| **AUD-07** | Re-adds the Amazon Q CLI and Gemini CLI providers (~1,000 src + ~2,000 test lines + 2 CI workflows + docs) that upstream deliberately removed in #353, without addressing why they were removed. |
| **AUD-08** | Dangling design references: docs and code cite `docs/rfc/cao-agui-l2-dashboard-2026-05-11-v1.md`, `cao-auth0-mcp-integration-2026-05-11-v1.md`, `cao-auth0-websocket-2026-05-11-v1.md` (specific sections, e.g. "§6", "§9") — none of these files exist on the branch, main, or base. The design rationale the docs lean on is unreviewable. |
| **AUD-09** | `file_mod → STATE_DELTA` emits an empty RFC-6902 patch (`agui_stream.py:181`); `STATE_DELTA` frames are produced by recomputing the full fleet snapshot per event (no debounce/cache). Both self-acknowledged as follow-ups. |
| **AUD-10** | 632 KB compiled `zellij/zellaude.wasm` committed to the repo and force-included in the wheel — an unauditable binary artifact. |

### P2 — hygiene

| ID | Finding |
|---|---|
| **AUD-11** | Second top-level `tests/validation/` tree (repo convention is `test/`). |
| **AUD-12** | `pyproject.toml` sets `[tool.mypy] python_version = "2.1.1"` (nonsense value). |
| **AUD-13** | Internal planning jargon throughout ("Bolt 3", "commit 22/26/27", "Q1=A", "B3-BR-14", "Polecat", "ASI", "Deacon") with no glossary; root-level `AGENTS.md`/`CLAUDE.md`/`GEMINI.md` agent-instruction files pushed in a feature PR. |
| **AUD-14** | `CHANGELOG.md` contains none of the PR's own features. |
| **AUD-15** | `GENERATIVE_UI` and the AG-UI gate share `CAO_MCP_APPS_ENABLED`; AG-UI surfaces deserve a dedicated flag so the two features can be enabled independently. |

## 5. What is genuinely good (keep and land)

- **`agui_stream.py`** — pure functions, total mapping, explicit privacy boundary (message bodies never on the wire, with tests asserting non-leakage), thoughtful failure isolation. This is the right shape: a thin, version-pinnable, single-file adapter over the existing event backbone — exactly what the RFC series calls for.
- **WebSocket auth** — accept-then-close so 4xxx codes reach browsers; single-warn input drop for read-only viewers; reuses the existing `security/auth.py` scope taxonomy; genuinely default-off.
- **Generative-UI sanitization** — defense-in-depth done right (server-side allow-list refusal + inert client placeholder + demo assertion), even though the pipeline lacks a producer.
- **Test discipline** — the tests read are real behavioral tests (e.g. `test/services/test_agui_stream_mapping.py`: 31 tests covering redaction, refusal, truncation, RFC-6902 deltas), not padding.
- **Correct layering** — the AG-UI stream re-maps main's existing pipeline (`event_primitives` → `EventLogPublisher` → `SseBus` → `/events`) and reuses `ui_state_service` pure functions rather than inventing a parallel event backbone.

## 6. Relationship to the existing codebase

- **Extends correctly:** AG-UI stream, state channel, WS auth, OTel, providers all plug into existing mechanisms (event bus, auth module, lifespan/plugins, provider manager).
- **Bypasses:** the :9890 listener runs a second uvicorn outside the main app's TrustedHost/CORS posture; `orchestration/` builds a parallel dispatch/topology universe alongside the existing handoff/assign/workflow engine (integration explicitly deferred); `cao_pwa/` is a third frontend alongside `web/` and the MCP Apps surface, with types copy-pasted from `cao_mcp_apps/src/shared/types.ts`.
- **Contradicts upstream direction:** re-adds providers removed in #353 (AUD-07).

## 7. Disposition

Findings AUD-01…AUD-15 are picked up as work items, with owners and sequencing, in `docs/proposals/kiro-continuation-plan.md`. The strategic framing that the salvageable parts of this PR serve is written up as an upstream proposal in `docs/proposals/upstream-issue-agui-construct-model.md`.
