# PR #387 remediation — Claude implementation notes

Working record of the review-remediation implementation on
`claude/pr387-agui-core` (this branch) and `claude/pr387-a2a-hardened`, built
for a side-by-side quality comparison against the Kiro agent's implementation
of the same scope. Companion documents: the full audit
(`pr387-review-audit-synthesis-2026-07-06.md`) and the paste-ready reply
(`pr387-agui-response-draft-v2.md`).

Both branches stack on the PR #387 head (`f40933d`); nothing was pushed to
`feat/agentic-protocols-generative-ui` itself.

## Finding → change map (this branch)

| Review finding | Verdict | Change |
|---|---|---|
| Scope: split the PR; hold A2A until auth is wired (blocking; also fanhongy's ask) | Accept | `refactor(agui): split the A2A/Agent Card transport out of the AG-UI core` — a2a/, agent_card/, their suites, the lifespan wiring, and their deps all removed; the hardened A2A returns on `claude/pr387-a2a-hardened` |
| Token-parse exceptions → 500 / opaque WS error (important) | Accept | `fix(auth): map token-parse failures to 401/4401…` — broad catch on the SSE path (401) and `_extract_ws_scopes` (None → 4401); malformed-token tests run the REAL parse path; expired-token behavior pinned |
| JWT in query string leaks to access logs (important) | Accept the leak, reject "token-in-URL is the bug" (EventSource can't set headers) | same commit — `RedactQueryTokenFilter` on `uvicorn.access` (idempotent install before `uvicorn.run`), short-TTL guidance in docs/pwa.md, ticket handshake filed as follow-up |
| `?since=` replay stubbed at the endpoint test (nit) | Accept | `test(agui): exercise the ?since= replay boundary end-to-end…` — fake log honors the strictly-greater-than contract; boundary include/exclude asserted through the endpoint |
| `_agui_enabled()` also true under `CAO_MCP_APPS_ENABLED` (nit) | Accept as docs problem — behavior is deliberate (shared event source) | same commit + docstring rewrite; parametrized tests pin both enablement paths and falsey values |
| OTel/authlib/multipart as unconditional runtime deps (nit) | Accept | split commit — OTel → `[otel]` extra with a no-op fallback (`telemetry/__init__.py`), subprocess tests prove a base install imports `api.main` without the SDK; authlib → dev group (test fixtures need it); multipart leaves with A2A |
| Provider deletion / missing `### Removed` CHANGELOG (important) | **Reject — misattributed.** This PR deletes nothing (117 A / 40 M / 0 D); q_cli/gemini_cli were removed upstream in #353, in the merge base | Counter-fix for the real defect no review caught: `fix(examples): retarget the gemini_cli data-analyst profile to antigravity_cli` — the PR *added* an example for a nonexistent provider. `test_example_profiles.py` now validates every example's provider against `ProviderType` |
| Copilot: stray `tests/__init__.py`; mypy 3.11 vs floor 3.10; RFC 9114 mis-cite; `InstancePicker` nested interactive; `test_headless_ci` docstring | Accept all five | `fix: resolve the five Copilot inline findings…` — incl. sibling-buttons restructure with component tests pinning "no interactive content inside any button" |
| Dated design log `generative-ui-implementation-2026-07-04.md` (nit) | Accept | `docs: fold the dated generative-UI design log into docs/pwa.md` |
| whitelist terms / inbox-delivery drift / `npm install` in ci.yml / `.coverage-baseline.json` "introduced" | **Reject — all misattributed** (files untouched by this PR; verified against upstream main) | No change here by design; offered as a separate hygiene PR (see the synthesis doc, Phase E) |
| "README/CODEBASE prose reformatting adds noise" (nit) | **Reject — misattributed**: README.md/CODEBASE.md are not in this PR's diff | No change |
| "~400 files" | Correct the record: 157 files (+16,288/−119) | PR body rewrite (see response draft v2) |

## Demonstration & proof (beyond the review's asks)

- **Live-path recording** — `cao_pwa/e2e/live-dashboard.spec.ts` boots a real
  `cao-server` + the built PWA, connects through the real add-instance dialog,
  drives `emit_ui` through all six components, asserts the off-list `iframe`
  is refused (400, nothing renders), then proves `?since=` recovery by
  emitting while the page is offline and asserting the missed card appears
  after reconnect. Video recorded (config `video: "on"`); the committed
  capture is `docs/media/agui-live-remediation-demo.webm`. The prior harness
  only drove a canned replay page — the live path was the fork's own stated
  standard for demos.
- **`examples/agui-dashboard/`** — runnable, credentials-free quick start
  (mock fleet + component showcase); `showcase.sh` doubles as a deployment
  smoke test (exits non-zero unless six accepts + one refusal).
- **`agui-author` skill** (both skill trees) — teaches any agent the
  component vocabulary, the 8 KB bound, and the refusal contract, with prop
  names verified against the actual renderers.
- **CI** — the recording workflow gained the uv/Python toolchain so the
  live-path spec runs on every PR touching `cao_pwa/` or `src/`; artifacts
  upload as before.

## Verification summary

- Full Python suite green (3,524 passed / 0 failed at the 1B checkpoint;
  re-run before push), including the 40 pre-existing AG-UI tests plus the
  new auth-hardening, enablement, replay-boundary, telemetry-fallback,
  log-redaction, and example-validation tests.
- `mypy --strict` green at the 3.10 floor; black/isort clean.
- `cao_pwa`: tsc clean, 22 vitest tests green (component a11y structure
  pinned), live-path Playwright spec green with real video output.
- Default-off contract re-asserted at the stronger level: the A2A modules
  don't exist, no `/a2a` routes mount, AG-UI 404s with no flags.
