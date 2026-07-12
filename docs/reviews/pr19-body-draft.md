# PR #19: AG-UI Core + Generative UI + PWA (reconcile/pr387-agui-core)

> Reconciles two independent remediations of upstream awslabs#387
> (`claude/pr387-agui-core` #11 and `kiro/pr387-agui-core` #14) into a single
> verified branch. Stacked on `f40933d` (upstream HEAD at decomposition time).
> Targets `feat/agentic-protocols-generative-ui`.

## What this PR adds

- **AG-UI typed-event SSE adapter** -- default-off (`CAO_AGUI_ENABLED=1`),
  metadata-only redaction by construction, allow-list refusal at both adapter
  and renderer layers. Produces `RUN_STARTED`, `TEXT_MESSAGE_*`,
  `STATE_DELTA`, `GENERATIVE_UI`, and `RUN_FINISHED` events over a standard
  SSE endpoint with `?since=` cursor replay.
- **Generative UI components** -- six typed components (`DiffSummary`,
  `FileTree`, `ProgressIndicator`, `ToolCallCard`, `ConfirmationDialog`,
  `ErrorBanner`) rendered from AG-UI `GENERATIVE_UI` events.
- **Standalone PWA** (`cao_pwa/`) -- Vite + React + TypeScript dashboard
  consuming the AG-UI stream. Includes `?since=`-based reconnection with
  exponential backoff, access-log param scrubbing, and a live-spec Playwright
  suite.
- **`mock_cli` provider** -- deterministic provider for testing and demos,
  emitting all six component types with stable payloads.
- **`agui-author` skill** -- registered in `SHIPPED_SKILLS`, teaches agents
  the generative-UI component vocabulary (renderer-true prop names verified
  against the actual `GenerativeUI.tsx` renderers).
- **Opt-in OpenTelemetry** -- `[otel]` optional extra; actionable warning when
  telemetry is requested without the extra installed; `find_spec` guard safe
  on Python 3.12.
- **Token-parse hardening** -- malformed/expired bearer tokens return 401 (SSE)
  / close 4401 (WebSocket) instead of 500. End-to-end test for both paths.
- **WS auth hardening** -- WebSocket upgrade validates the token before
  accepting the connection; malformed-token e2e test asserts 4401 close code.
- **Example fixes** -- dead `gemini_cli` reference retargeted to
  `antigravity_cli`; `examples/agui-dashboard/` quick-start with `run.sh` and
  `showcase.sh` (SSE-tail + tmux graceful degrade structure).

## What is NOT in this PR

- **A2A JSON-RPC transport** -- extracted to the sibling PR #20
  (`reconcile/pr387-a2a-hardened`), which lands after this one merges.
  `import cli_agent_orchestrator.a2a` raises `ModuleNotFoundError` on this
  branch by design.

## Gate results (independently verified)

| Gate | Result |
|------|--------|
| `uv run pytest test/ --ignore=test/e2e -m 'not integration'` | **3519 passed**, 15 skipped, 0 failures* |
| `uv run mypy src/` | **132 source files**, no issues |
| `uv run black --check . && uv run isort --check-only .` | Clean |
| `cd cao_pwa && npx tsc --noEmit` | 0 errors |
| `cd cao_pwa && npm test` | **24 tests** passed (4 suites) |
| `cd cao_pwa && npm run build` | Success (32 modules) |
| Live-path scripts (`run.sh`, `showcase.sh`) | Well-formed, valid bash; full execution requires tmux |
| Playwright live-spec (`npm run test:e2e:live`) | Covered in CI (`Build, test & record` job); sandbox lacks Chromium (*unverified* locally) |

\* Test count is 3519 in a tmux-less sandbox vs 3537 in a full environment
(~18 tests require tmux for terminal session fixtures). The 1 collection error
is `test_cao_terminal_create_and_get` failing fixture setup due to missing
tmux -- an environment constraint, not a code defect.

## Credits

This branch starts from the `claude/pr387-agui-core` history and ports
adjudicated wins from `kiro/pr387-agui-core` (renderer-true prop vocabulary,
OTel degrade UX, live-config split, merged demo scripts, additional test
unions). The reconciliation decisions are documented in
`docs/reviews/pr387-reconciliation-plan.md` (PR #17) with executed evidence
from both branches.

## Follow-ups (committed to, not blocking)

- Short-lived-ticket handshake (replace query-param JWT for SSE auth)
- `STATE_DELTA` debounce
- `emit_ui` rate limiting
- Fixed-path `term-42.mcp.json` test-hygiene fix
