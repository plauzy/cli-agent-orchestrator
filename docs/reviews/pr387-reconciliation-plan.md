<!--
Fork-only working document. Head-to-head evaluation of the Kiro and Claude
remediations of upstream awslabs/cli-agent-orchestrator#387, plus a
reconciliation plan. PLAN ONLY — no reconciliation code is written until this
plan is approved. Do not post any of this upstream until the fork maintainer
approves.
-->

# PR #387 — Kiro vs Claude remediation: head-to-head evaluation & reconciliation plan

- **Date:** 2026-07-06
- **Subject:** two independent remediations of the "Request changes" review
  ([4632216702](https://github.com/awslabs/cli-agent-orchestrator/pull/387#pullrequestreview-4632216702))
  on upstream PR [#387](https://github.com/awslabs/cli-agent-orchestrator/pull/387)
  (implements [#386](https://github.com/awslabs/cli-agent-orchestrator/issues/386)).
- **Base / PR head:** `feat/agentic-protocols-generative-ui @ f40933d`
  (`f40933db2504cee2a23e70a29f41f5dc5e521e7b`, confirmed by fresh checkout).
- **Branches evaluated (all stacked on `f40933d`):**
  - Kiro — PR-A [#14](https://github.com/plauzy/cli-agent-orchestrator/pull/14) `kiro/pr387-agui-core`; PR-B [#13](https://github.com/plauzy/cli-agent-orchestrator/pull/13) `kiro/pr387-a2a-hardened`
  - Claude — PR-A [#11](https://github.com/plauzy/cli-agent-orchestrator/pull/11) `claude/pr387-agui-core`; PR-B [#12](https://github.com/plauzy/cli-agent-orchestrator/pull/12) `claude/pr387-a2a-hardened`

## Method & evidence provenance

All four branches plus the base were fetched as source trees and compared with
`git diff --no-index`; every runnable gate was executed on the **exact toolchain
the task specified** — Python **3.12.13**, `uv sync --all-extras --dev`, then
`uv run pytest / mypy src/ / black --check / isort --check-only`. Verdicts cite
`file:line`, executed command output, or diff hunks. Provenance is set aside:
where a PR body claims a number, it is marked **verified** only if reproduced
here, otherwise **unverified**.

**Environment limits (disclosed for honesty).** This sandbox has **no Chromium**
(`/opt/pw-browsers` is empty) and its shell guard blocks starting a `cao-server`,
so the **browser Playwright live specs and the live `showcase.sh` run were NOT
executed here** — those claims are marked *unverified (env-limited)*. Their
Python-level equivalents (the `?since=` endpoint tests, the `emit_ui` suites,
the redaction suites) *did* run as part of the full pytest suites below.

---

## Gate results (executed — the empirical spine of this report)

| Branch | black | isort | mypy `src/` | pytest (full) | Verdict |
|---|---|---|---|---|---|
| `kiro/pr387-agui-core` | clean | clean | Success, 132 files | **3484 passed, 22 skipped, 0 failed** | **GREEN** |
| `claude/pr387-agui-core` | clean | clean | Success, 132 files | 3523 passed, 21 skipped, **2 FAILED** | **RED** |
| `kiro/pr387-a2a-hardened` | clean | clean | Success, 142 files | **3597 passed, 21 skipped, 0 failed** | **GREEN** |
| `claude/pr387-a2a-hardened` | clean | clean | Success, 142 files | 3592 passed, 21 skipped, 0 failed* | **AMBER** |

\* full suite green, but one test is **order-dependent / flaky** (see PR-B §2).

**Claude PR-A's 2 failures** are both in its own `test/telemetry/test_optional_extra.py`
(`test_telemetry_package_noops_without_otel_sdk`, `test_api_main_imports_without_otel_sdk`).
Root cause, confirmed by direct probe on this interpreter: the test blocks
`opentelemetry` with a `sys.meta_path` finder that implements the **legacy
`find_module`/`load_module`** API, which the import system **no longer calls on
Python ≥ 3.12**. So OTel is never actually blocked, `telemetry.OTEL_AVAILABLE`
is `True`, and `assert ... is False` fails. This is reproducible under the
specified gate command (`--all-extras` installs `[otel]`). Claude's
implementation notes claim "3,524 passed / 0 failed" — **falsified on this
toolchain**; the fallback branch the test intends to prove is not exercised on
3.12 at all. (On a 3.11 runner the legacy hook still fires, so it would pass
there — a CI-Python-version dependency worth naming either way.)

---

## Phase 1 — Scorecard

Scoring key: **K** = Kiro stronger, **C** = Claude stronger, **=** = parity / both acceptable.

### PR-A pair (AG-UI core)

| Dimension | Kiro | Claude | Win | Evidence |
|---|---|---|---|---|
| **Gate green (specified toolchain)** | 3484 passed, 0 failed | 3523 passed, **2 failed** | **K** | Executed above; Claude's OTel subprocess test breaks on Py 3.12 |
| **AC1 default-off (test-asserted)** | `emit_ui`→404 + `_agui_enabled()` both-paths unit test | `test_default_off_listeners.py` (module `ImportError` + no `/a2a` routes + **both** endpoints 404) **and** `test_agui_enablement.py` matrix | **C** | Kiro **deleted** `test_default_off_listeners.py`; Claude kept+strengthened it |
| **AC2 `?since=` cursor correctness (PWA)** | `cao_pwa/src/api.ts` **byte-identical to base** — native `EventSource` retries original URL from CONNECTING, silently dropping the `since` cursor | api.ts `onerror` **always closes + reconnects with a fresh cursor** (+ `api.test.ts`) | **C** | `git diff base api.ts`: Kiro empty; Claude adds the fix with an explanatory comment |
| **Reconnect/live proof** | `page.reload()` only (fresh connection); relies on Python `test_stream_since_*` for replay. Adds real CORS-origins fix for the preview port | **hard-`SIGKILL`s the real server mid-stream** and asserts the gap event arrives via `?since=` replay; spawns `.venv/bin/cao-server` directly to avoid orphaning the `uv run` child; honors `PLAYWRIGHT_CHROMIUM_EXECUTABLE` | **C** | Kiro's own PR #14 history: `setOffline` does **not** sever an established SSE in Chromium, so it downgraded to reload. Claude's proof needs (and has) the cursor fix |
| **OTel dependency hygiene** | keeps lightweight `opentelemetry-api` in base (native no-ops), moves SDK+exporter to `[otel]` — simpler, no shim | moves **all three** to `[otel]` + try/except no-op shim (leanest base install, most literal reading of the nit) — **but its proof test is broken on 3.12** | **=** | `pyproject.toml` lines; `telemetry/__init__.py` vs `telemetry/otel.py`; failing test above |
| **Demo video artifact** | CI-produced webm only (no binary committed) | commits `docs/media/agui-live-remediation-demo.webm` | **K** | Repo-artifact hygiene: a committed binary can't be diff-reviewed and bloats history |
| **Skill registration** | adds `agui-author` to `SHIPPED_SKILLS`, so the pre-existing `test_skill_packaging_parity.py` actively guards the canonical↔package mirror | ships the skill (works via dynamic `resources.files(...).iterdir()` seeding) but leaves it **out** of `SHIPPED_SKILLS`, so parity never checks it (the parity test only asserts `SHIPPED_SKILLS ⊆ package_dirs`, no reverse) | **K** | `scripts/sync_skills.py` diff; `test/test_skill_packaging_parity.py:110` |
| **Test breadth** | skill-parity coverage | `test_example_profiles.py` (every `examples/**` profile's `provider` validated against `ProviderType` — generalizes the dead `gemini_cli` fix), enablement matrix, log-redaction suite | **C** | file lists; both green except Claude's telemetry test |
| **`?since=` endpoint de-stub** | `test_agui_stream_endpoint.py` +141 lines | +26 lines | **K** | Kiro's endpoint replay coverage is materially more thorough |
| **Docs / response draft** | folds dated doc; response draft v2 accurate | folds dated doc; response draft v2 accurate; also commits the shared audit synthesis | **=** | both drafts withdraw the false deletion concession correctly |

**PR-A net:** Claude wins the two properties #386 weights highest — **AC1 default-off strength** and **AC2 `?since=` cursor correctness** (it fixes a real PWA bug Kiro's branch still carries) — plus higher-fidelity live proof and broader tests. Kiro wins **gate-green on the specified toolchain**, artifact hygiene, skill-guard wiring, and endpoint-replay depth. Neither is a clean sweep.

### PR-B pair (A2A hardened)

| Dimension | Kiro | Claude | Win | Evidence |
|---|---|---|---|---|
| **Gate green** | 3597 passed, 0 failed; a2a subset 120 passed deterministically | 3592 passed; mount-guard test **flaky** | **K** | `test/api/test_a2a_mount_guard.py::test_loopback_bind_without_auth_still_mounts` failed in the `a2a+agent_card+mount+roundtrip` selection, passed alone and on re-run |
| **Auth-test fidelity (the B1 bypass)** | ~28-case matrix, but **monkeypatches `extract_scopes_from_token → _fake_extract`** — decision logic only, not real tokens | mints **real RS256 JWTs against a live in-process JWKS server** (`jwt_factory`+`jwks_server`), tests **expired** tokens, asserts **docstring-truth** (`rpc_mod.__doc__`/`stream_mod.__doc__`) | **C** | `test/a2a/test_auth.py:57-64` (mocked) vs `test/a2a/test_auth_enforcement.py:53-58,183-190` (real path) |
| **`reset_jwks_cache` latent break** | **not fixed** — base `test/conftest.py:113,115` calls `_auth_mod.reset_jwks_cache()`, but `src/security/auth.py` never defines it; dormant only because no Kiro test uses that fixture | **fixed** — adds `def reset_jwks_cache()` to `src/security/auth.py:210` with a docstring naming the break | **C** | `grep 'def reset_jwks_cache'` present in Claude src, absent in Kiro/base src |
| **Mount guard** | extracts pure `_should_mount_a2a(bind_host, a2a_disabled, auth_enabled)` (`api/main.py:335`) + parametrized decision tests — deterministic | inline lifespan guard + `TestClient` integration test binding the **real** listener + `app.state` — higher fidelity but order-fragile | **K** (testability) / **C** (fidelity) | flaky failure above; Kiro subset stable |
| **Store-full error semantics** | `RESOURCE_EXHAUSTED` / **HTTP 429** (transport backpressure), tested (`test_send_full_returns_resource_exhausted_429`, asserts 429) | `TASK_LIMIT_EXCEEDED` / **HTTP 200** + JSON-RPC error body (spec-compliant app error) | **C** (compliance) | `a2a/store.py`, `a2a/rpc.py`; JSON-RPC 2.0 delivers application errors with HTTP 200 |
| **Enforcement order** | `_authorize` after envelope validation (400s) but **before** method lookup | **authenticates before body parse** (surface never leaks) + returns `WWW-Authenticate: Bearer` (RFC 7235) | **C** | `rpc.py` dispatch bodies; both correctly short-circuit when auth disabled |
| **Bearer parsing edge cases** | `split(None,1)`, case-insensitive, rejects empty token | `split()`, case-insensitive, rejects empty token, adds challenge header | **=** | both `_extract_bearer` / `_resolve_request_scopes` |
| **Dependency hygiene** | on **PR-A**; argues **no `[a2a]` extra** should exist because `src/` imports neither `authlib` nor `python-multipart` (Agent Card signing uses `cryptography` via `pyjwt[crypto]`) | folds dep hygiene into **PR-B**; response draft references an `[a2a]` extra carrying `authlib`/`multipart` | **K** | `grep -rE '(import\|from)\s+(authlib\|multipart)' src/` = **empty on both PR-B branches** → the `[a2a]`-runtime-extra claim is inaccurate; authlib is test-only |
| **Scope map** | `task.send`/`task.cancel`→`cao:write`, `task.get`→`cao:read`, `cao:admin` any, write⇒read | same mapping | **=** | both `_METHOD_*_SCOPE` maps |

**PR-B net:** Claude has materially stronger auth evidence (real JWT/JWKS vs a mocked extractor — decisive for a *security bypass* fix), repairs the shared `reset_jwks_cache` infra, and orders enforcement more conservatively. Kiro has the deterministic (non-flaky) suite, the cleaner testable mount-guard decision function, a tested backpressure path, and the correct dependency-hygiene call. The store-full status code is the one genuine either/or.

---

## What BOTH sides missed (fresh eyes)

1. **The short-lived-ticket handshake (review I2) is deferred by both.** Query-token
   exposure is mitigated only by access-log scrubbing + short-TTL guidance; the
   single-use ticket handshake both PR bodies "file as follow-up" is **not**
   implemented on any branch. The *important* finding is mitigated, not closed.
2. **`emit_ui` / `GENERATIVE_UI` has no rate limit.** Both enforce an 8 KB
   per-component payload bound (`services/agui_stream.py:102,309`) but neither
   caps the **frequency** of emissions. A local/authorized agent (or a
   compromised MCP client) can flood generative-UI frames — the same DoS class
   the reviewer raised for the A2A store (B2), on the AG-UI producer side.
   Lower severity (requires authorized/local access; default-off) but unaddressed
   by both.
3. **`STATE_DELTA` debounce** — both list it as a follow-up; neither implements
   coalescing, so a chatty fleet produces one SSE frame per primitive event.
4. **Bidirectional generative UI** — acknowledged as future by both; not a
   review blocker, noted for completeness.

**Not a gap (verified, so neither is faulted):** the AG-UI `?since=` replay
draws from `EventLog`, a `deque(maxlen=500)` with TTL
(`services/event_log_service.py:1,41`) — **bounded by construction**, unlike the
A2A store that needed B2. Good pre-existing hygiene.

**Regressions to repair during reconciliation:** Claude PR-A's 2 Py-3.12 telemetry
failures; Claude PR-B's flaky mount-guard test; Kiro's dormant `reset_jwks_cache`
landmine.

---

## Phase 2 — Reconciliation plan (implement only after approval)

Produce two branches stacked on `f40933d`: **`reconcile/pr387-agui-core`** and
**`reconcile/pr387-a2a-hardened`**. For each contrast, take the objectively
better implementation (cherry-pick/port; don't rewrite what one side got right)
and **union where genuinely complementary**. Every decision below carries a
one-line rationale tied to the priority-ordered goals (1 = #386 ACs, 2 = review
closure, 3 = fork working agreements, 4 = engineering quality).

### `reconcile/pr387-agui-core` — per-contrast decisions

| # | Decision | Source | Rationale (goal) |
|---|---|---|---|
| A1 | **Default-off**: take Claude's `test_default_off_listeners.py` (module-`ImportError` + no `/a2a` routes + both endpoints 404) **and** `test_agui_enablement.py`, plus Kiro's `_agui_enabled()` both-paths unit test | Claude + Kiro | strongest test-asserted default-off (goal 1/3) |
| A2 | **Carry the PWA cursor-loss fix** (`api.ts` always-close+reconnect-with-fresh-cursor + `api.test.ts`) | Claude (mandatory) | AC2 `?since=` correctness; fixes a real bug Kiro lacks (goal 1) |
| A3 | **One live spec with BOTH reconnect scenarios**: Claude's real-server-`SIGKILL`→`?since=` replay (spawn `.venv/bin/cao-server` directly; honor `PLAYWRIGHT_CHROMIUM_EXECUTABLE`) **and** Kiro's `page.reload()` reconnect; carry Kiro's `CAO_CORS_ORIGINS` preview-port fix | Claude + Kiro | highest-fidelity proof + reload path + CORS fix (goal 1/3) |
| A4 | **OTel**: adopt Claude's all-three-to-`[otel]` + no-op shim **but replace the broken subprocess test** — use a modern `importlib.abc.MetaPathFinder.find_spec` block (or uninstall-in-clean-venv) so it passes on Py ≥ 3.12 | Claude (fixed) | leanest base install + literal reviewer ask, **gates green** (goal 2/4). *Fallback:* if the robust fallback test proves fragile, take Kiro's keep-`api`-in-base approach (no shim, no test needed) |
| A5 | **Demo video**: do **not** commit a webm; produce it on CI only; prove the live path headlessly | Kiro | repo-artifact hygiene (goal 4) |
| A6 | **Skill registration**: register `agui-author` in `SHIPPED_SKILLS` so `test_skill_packaging_parity.py` guards the mirror | Kiro | no unwired/unguarded scaffolding (goal 3/4) |
| A7 | **Union the test suites**: Claude's `test_example_profiles.py` + enablement matrix + log-redaction suite **and** Kiro's skill-parity + fuller `?since=` endpoint coverage | Claude + Kiro | every accepted fix has a test (goal 2) |
| A8 | **Examples**: union `run.sh` + `showcase.sh` + `fleet_worker.md` (Kiro) + `README.md` (Claude); retarget the dead `data_analyst_gemini_cli.md` → `antigravity_cli` (both already do) | Claude + Kiro | runnable demo, correct example (goal 2/3) |
| A9 | Copilot five, dated-doc fold, `_agui_enabled()` docstring: identical on both — take either | = | review closure (goal 2) |

### `reconcile/pr387-a2a-hardened` — per-contrast decisions

| # | Decision | Source | Rationale (goal) |
|---|---|---|---|
| B1 | **Auth tests**: base on Claude's real-RS256-JWT-vs-live-JWKS fixture (`jwt_factory`+`jwks_server`), expired-token case, and docstring-truth assertions; **union** Kiro's broader scope-decision matrix (write⇒read, admin-any, unknown-method→read) | Claude (base) + Kiro | the *security bypass* must be proven on the real token path, then breadth (goal 1/2) |
| B2 | **`reset_jwks_cache`**: add the function to `src/security/auth.py` (mandatory) | Claude | repairs shared fixture infra; removes Kiro's latent landmine (goal 4) |
| B3 | **Mount guard**: keep Kiro's extracted pure `_should_mount_a2a()` + parametrized decision tests, **and** add a *hermetic* integration smoke (reset `app.state`, avoid real port binding / guarantee teardown) so it is not flaky | Kiro (core) + Claude (hardened) | testability + integration fidelity, **no flaky tests** (goal 3/4) |
| B4 | **Store-full status**: **HTTP 200 + JSON-RPC error body** with a descriptive code; put a retry hint in `error.data` | Claude | A2A is JSON-RPC 2.0 — application errors ride 200 so **stock clients parse the error** (goal 1 AC3 spirit). *Kiro's 429 is defensible for infra backpressure but risks naive JSON-RPC clients treating non-200 as a transport failure; if a 429 is wanted, expose it at a proxy, not the protocol layer.* Carry Kiro's tested exhaustion path, adapted to 200 |
| B5 | **Enforcement order**: authenticate **before** body parse; return `WWW-Authenticate: Bearer`; keep the explicit `is_auth_enabled()` short-circuit both have | Claude | no surface leak to anonymous callers; HTTP-correct (goal 4) |
| B6 | **Dependency hygiene**: land it on **PR-A**; do **not** invent an `[a2a]` runtime extra (verified: `src/` imports neither `authlib` nor `multipart`); `authlib`→dev group, drop `python-multipart` | Kiro | truthful dependency declaration; survives either PR landing first (goal 2/3) |
| B7 | Bounded+TTL store, per-method scope map, 401-before-dispatch: equivalent on both — take either, with B4's status code | = | B1/B2 closure (goal 2) |

### Gates the reconciled branches must pass (exact commands + expected posture)

Run on Python 3.12 (and mirror on the CI 3.11 matrix):

```
uv sync --all-extras --dev
uv run black --check .           # expect: clean
uv run isort --check-only .      # expect: clean
uv run mypy src/                 # expect: Success (132 files core / 142 files A2A)
uv run pytest -q                 # expect: 0 failed, 0 flaky
# cao_pwa/:
npm ci && npx tsc --noEmit && npm test && npm run build   # expect: clean, all vitest green
```

Expected counts (targets, re-baselined after the unions land):
- `reconcile/pr387-agui-core`: ≥ 3523 passed (Claude's count) **plus** Kiro's skill-parity/endpoint tests, **0 failed** (the 2 telemetry failures fixed via A4).
- `reconcile/pr387-a2a-hardened`: ≥ 3597 passed, **0 failed and 0 flaky** (B3 de-flakes the mount guard; the a2a subset must also pass **in isolation**, not only in full-suite order).

### Properties to preserve at their strongest verified form

- **Default-off**: A2A modules **absent** from PR-A entirely (asserted by
  `ImportError` + no `/a2a` routes), AG-UI 404s with no flags (both endpoints).
- **Metadata-only redaction**: keep the by-construction guarantee + the
  redaction test suite (Claude's `test_log_redaction.py` unioned with Kiro's
  `test_logging.py`).

### Truthful PR descriptions

Rewrite both reconciled PR bodies to match their final diffs exactly (the
original I1 finding was description oversell). No `[a2a]` runtime extra claim
(B6). State demo proof honestly: CI-recorded video + headless showcase, live
spec covers server-restart **and** reload reconnect.

### Updated upstream reply

Revise `docs/reviews/pr387-agui-response-draft-v2.md` where reconciliation
changes a claim:
- OTel: "moved to `[otel]` (base install carries no OpenTelemetry package)" — matches A4.
- Dependency hygiene: drop any `[a2a]` extra wording; `authlib` is **test-only**, `python-multipart` removed (B6).
- Reconnect: describe both the server-restart `?since=` replay and the reload path; note the native-`EventSource` cursor-loss bug that was found and fixed.
- Keep: B1/B2 acceptance, decomposition, 157-not-400, EventSource query-token pushback, Copilot five, the misattributed-findings corrections (R1–R6).

### Retarget sequencing (per @fanhongy)

1. Land **`reconcile/pr387-agui-core`** on upstream first (the verified core).
2. Then **`reconcile/pr387-a2a-hardened`**, once auth + bounded store + the
   per-method 401/403 test matrix are in — never before.
3. Follow-ups (separate PRs): ticket handshake (I2), `emit_ui` rate limiting,
   `STATE_DELTA` debounce, the inclusive-language/`.coverage-baseline` hygiene PR.

### Constraints (hard)

- Never push to `feat/agentic-protocols-generative-ui` or to any existing
  `kiro/*` / `claude/*` branch. New work lands **only** on `reconcile/*`.
- Open the eventual reconciled PRs as **drafts**, base
  `feat/agentic-protocols-generative-ui`.
- No reconciliation code until this plan is approved.

---

## Appendix — reproduction

```
# public fork; branches fetched as codeload tarballs (gateway git needs an AuthToken)
for b in kiro/pr387-agui-core kiro/pr387-a2a-hardened \
         claude/pr387-agui-core claude/pr387-a2a-hardened \
         feat/agentic-protocols-generative-ui; do
  curl -sSL "https://codeload.github.com/plauzy/cli-agent-orchestrator/tar.gz/refs/heads/$b" | tar xz
done
# per tree: uv sync --all-extras --dev && uv run black --check . && uv run isort --check-only . \
#           && uv run mypy src/ && uv run pytest -q
```
