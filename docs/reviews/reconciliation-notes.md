# PR #387 remediation — reconciliation notes (PR-A: AG-UI core)

This branch (`reconcile/pr387-agui-core`) reconciles the two independent
remediations of the upstream #387 review — `claude/pr387-agui-core` and
`kiro/pr387-agui-core` — per the approved plan
(`docs/reviews/pr387-reconciliation-plan.md`, evaluated head-to-head with
executed evidence). It starts from the Claude branch's history and ports the
Kiro branch's adjudicated wins; the sibling `reconcile/pr387-a2a-hardened`
carries the hardened A2A transport.

## What was ported / merged on top of the base history

| Change | Source | Commit |
|---|---|---|
| `agui-author` registered in `SHIPPED_SKILLS` → sync + packaging-parity coverage | Kiro | `fix(agui): renderer-true skill vocabulary…` |
| Renderer-true skill/demo prop vocabulary (`diff_summary.title`; `progress.value` 0.0–1.0) | Kiro (verified against `GenerativeUI.tsx`) | same |
| Live spec pins the previously-dodged props (diff heading text, `aria-valuenow`) | new | same |
| OTel: actionable warning when telemetry is requested without the `[otel]` extra; SDK-import guard for transitive-api installs | Kiro's degrade UX on Claude's full-extra packaging | `fix(telemetry): actionable degrade…` |
| Subprocess blocker on the `find_spec` protocol (Python 3.12-safe; the legacy finder was an executed 2-test failure on a 3.12 host) | evaluation finding | same |
| Hermetic default e2e + `test:e2e:live` / `playwright.live.config.ts` split | Kiro's separation, Claude's self-managed spec + Chromium hook | `test(pwa): hermetic default e2e…` |
| Reload-persistence step appended after the server-restart `?since=` replay step | Kiro (their spec's final reconnect proof) | same |
| Vite spawned wrapper-free (orphaned `vite preview` held :4173 across runs) | evaluation finding | same |
| Demo scripts: SSE-tail + mktemp/trap structure, graceful tmux degrade | Kiro | `feat(examples): merge the two agui-dashboard demos` |
| Demo scripts: `CAO_TOKEN` auth, strict per-emit asserts, README | Claude | same |
| Showcase PASS gate now requires the six `GENERATIVE_UI` frames on the live stream | new (was display-only / unchecked) | same |
| Forwarded-`?since=` assertion; truthy-`1` enablement spelling | Kiro | `test(agui): union the two remediations' unique cases…` |
| Equal-timestamp `?since=` boundary; msg+args redaction case; malformed-token WS `4401` e2e | new (gaps both sides shared) | same |
| `docs/pwa.md` names both scrubbed params; CHANGELOG `#generative-ui` anchor | Kiro | docs commit |

Everything else — the A2A subtraction at its strongest test-asserted form, the
PWA `?since=` cursor fix in `cao_pwa/src/api.ts`, the token-parse 401/4401
hardening on the real parse path, access-log redaction, the example-profile
validation suite, `test_oauth_prm.py` retention, the Copilot five, the folded
design doc — is the base history from `claude/pr387-agui-core`, unchanged;
see that branch's commit messages for the original finding→commit map.

## Correction carried from the evaluation

The earlier Claude PR body claimed the demo/skill "prop names [were] verified
against the actual renderers" — the evaluation found two props that were not
(`diff_summary.summary`, which the renderer never reads, and `progress.value`
on a 0–100 scale against the renderer's [0,1] clamp). **That claim was false
and is retracted**; this branch makes it true (Kiro's vocabulary adopted) and
adds live-spec assertions so the claim is enforced rather than asserted.

## Known state

- The `auth_enabled_env` fixture in `test/conftest.py` still references
  `reset_jwks_cache()`, which does not exist on this branch — a latent,
  pre-existing trap (nothing uses the fixture here). The sibling
  `reconcile/pr387-a2a-hardened` defines the function; the trap is repaired
  when it lands.
- Follow-ups tracked in the reply draft: short-lived-ticket handshake,
  `STATE_DELTA` debounce, `emit_ui` rate limiting, the fixed-path
  `term-42.mcp.json` test-hygiene fix on the base branch.
