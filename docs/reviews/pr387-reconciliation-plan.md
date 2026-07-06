# PR #387 — Kiro × Claude head-to-head evaluation & reconciliation plan

- **Date:** 2026-07-06
- **Subject:** [awslabs/cli-agent-orchestrator#387](https://github.com/awslabs/cli-agent-orchestrator/pull/387) remediation — two independent implementations of the *same* scope.
- **Base (PR head) audited:** `feat/agentic-protocols-generative-ui @ f40933d`.
- **Branches under evaluation (fetched, worktree-isolated, gates executed):**
  - Kiro PR-A `kiro/pr387-agui-core` @ `660e3f4`; Kiro PR-B `kiro/pr387-a2a-hardened` @ `a708259`
  - Claude PR-A `claude/pr387-agui-core` @ `7bf2b06`; Claude PR-B `claude/pr387-a2a-hardened` @ `61b1dd1`
- **Provenance is set aside.** Every verdict below cites an artifact: a diff hunk, an executed command, a test result, or a source line. Where a PR-body/notes claim was *not* reproduced, it is marked **UNVERIFIED** or **CONTRADICTED**, never assumed.
- **This is a plan.** No reconciliation code is written until it is approved. Constraints honored: nothing here pushes to `feat/agentic-protocols-generative-ui`, `kiro/*`, or `claude/*`.

---

## 0. How this was verified (environment + method)

- **Host:** macOS (Darwin arm64, M2), `uv` 0.11.26, Python 3.12 venv (uv-managed), node v24.18, npm 11.16, tmux 3.7.
- **Isolation:** five `git worktree` checkouts (`kiro-agui`, `claude-agui`, `kiro-a2a`, `claude-a2a`, `base`); a fresh `uv sync --all-extras --dev` per branch.
- **Python gates per branch:** `uv run pytest -m 'not e2e'`, `uv run mypy src/`, `uv run black --check .`, `uv run isort --check-only .`.
- **PWA gates (core branches):** `npm ci`, `npx tsc --noEmit`, `npm test`, `npm run build` in `cao_pwa/`.
- **Diffs:** `git diff f40933d <branch>` per file; `git diff kiro/… claude/…` pairwise, walked hunk by hunk.
- **Environment deviation from the task brief (material):** there is **no `/opt/pw-browsers`** on this host. The `ms-playwright` cache contains **only `chrome-headless-shell`** (no full Chromium binary; `chromium-1228/` has no executable), and both live specs record video (`video: "on"`), which requires full Chromium — CDN-blocked per the configs' own notes. **Live Playwright execution is therefore environment-blocked** and is reported as such; reconnect correctness was instead verified from source + the PWA unit suites (which ran green). This is the one runnable-item I could not run, and the reason is documented rather than hand-waved.

### Executed gate results (exact numbers)

| Branch | pytest (`-m 'not e2e'`) | mypy | black / isort | PWA (`npm test` / tsc / build) |
|---|---|---|---|---|
| `kiro/pr387-agui-core` | **3487 passed, 0 failed**, 19 skipped, 107 deselected | Success, 132 files | clean / clean | **18 passed** (3 files) / clean / built |
| `claude/pr387-agui-core` | **3 failed**, 3525 passed, 18 skipped | Success, 132 files | clean / clean | **24 passed** (4 files) / clean / built |
| `kiro/pr387-a2a-hardened` | **1 failed**, 3599 passed, 18 skipped | Success | clean / clean | n/a |
| `claude/pr387-a2a-hardened` | **3595 passed, 0 failed**, 18 skipped | Success, 142 files | clean / clean | n/a |

**Failure triage (every failure classified against the diff):**

- `claude/pr387-agui-core` — 3 failures:
  1. `test/telemetry/test_optional_extra.py::test_telemetry_package_noops_without_otel_sdk` — **real, Claude-introduced.** The subprocess blocker uses `sys.meta_path` finder methods `find_module`/`load_module`, **removed in Python 3.12**; under the prescribed `uv sync --all-extras` the `[otel]` packages are installed and the broken finder never intercepts, so `OTEL_AVAILABLE` stays `True` and the assertion `"fallback branch not taken"` fails.
  2. `test/telemetry/test_optional_extra.py::test_api_main_imports_without_otel_sdk` — same root cause.
  3. `test/services/test_fifo_reader.py::…test_stop_right_after_writer_eof_does_not_leak` — **pre-existing macOS flake** (`OSError ENXIO` on a temp FIFO); passes 3/3 in isolation on `base`; not in either diff. **Not a Claude regression.**
- `kiro/pr387-a2a-hardened` — 1 failure:
  1. `test/providers/test_claude_code_unit.py::…test_build_command_mcp_injects_terminal_id` — `FileNotFoundError: ~/.aws/cli-agent-orchestrator/tmp/term-42.mcp.json`. **Pre-existing environment/isolation flake**; the file is untouched by PR-B's 10-file diff. **Not a Kiro regression.**

Net: **Kiro PR-A is fully green; Claude PR-A has 2 genuinely broken (Py3.12) tests** it authored. **Claude PR-B is fully green; Kiro PR-B is green modulo one unrelated env flake.** Both are mypy-strict/black/isort clean on every branch.

---

## Phase 1 — Deep comparison scorecard

### 1.0 What is identical (so the deltas below are the whole story)

Both PR-A branches make the *same* structural moves, verified by `git diff --name-status f40933d …`:

- **A2A + Agent Card fully removed** — `a2a/{__init__,rpc,store,stream,types}.py`, `agent_card/{__init__,builder,listener,router,signing}.py`, `test/a2a/*`, `test/agent_card/*`, `test/e2e/test_a2a_roundtrip.py` all `D`. Default-off achieved at the strongest level: the modules do not exist in PR-A.
- Stray `tests/__init__.py` deleted; dated `docs/generative-ui-implementation-2026-07-04.md` folded into `docs/pwa.md`; `examples/cross-provider/data_analyst_gemini_cli.md` → `…antigravity_cli.md` (`R097`) — the **G4 counter-fix** (the dead example targeting a nonexistent provider) that *neither reviewer* caught.
- `[tool.mypy] python_version` `3.11 → 3.10` (Copilot nit); `authlib`/`python-multipart` dropped from runtime deps; the five Copilot inline fixes.

Both sides reach **identical finding verdicts** on review 4632216702: accept `B1` (auth), `B2` (bounded store), `I1` (oversell → doc-only), `I2` (log-leak; reject "token-in-URL is the bug" — `EventSource` can't set headers), `I3` (token-parse → 401/4401), and all nits; **reject-as-misattributed** `R1` (provider deletion landed upstream in #353, in the merge base), `R2` (inclusive-language terms pre-exist), `R4` (`npm install` is in untouched `ci.yml`), `R6` ("~400 files" is 157). **Closure breadth is at parity.** Everything that follows is *execution fidelity*.

---

### 1.1 PR-A pair scorecard (`…/pr387-agui-core`)

| Dimension | Kiro `660e3f4` | Claude `7bf2b06` | Edge |
|---|---|---|---|
| Review-finding closure (breadth) | All accepted fixes present | All accepted fixes present | **Tie** |
| #386 AC1 (default-off, *test-asserted*) | A2A removed; asserts via `_agui_enabled()` both-paths unit test + `emit_ui`/stream 404; **deleted `test_default_off_listeners.py` and `test_oauth_prm.py`** | A2A removed; **adapted** `test_default_off_listeners.py` (route-table assertion, closest to AC1's "byte-identical route table") + kept `test_oauth_prm.py` | **Claude** |
| #386 AC2 (`STATE_SNAPSHOT`+RFC-6902+`?since=`) | De-stubs `?since=` deeply — `test_agui_stream_endpoint.py` **+141** | De-stubs `?since=` — same file **+26** | **Kiro** (depth) |
| #386 AC3 (stock clients, zero adapter) | `cao_pwa/src/api.ts` **byte-identical to base** → ships the native-`EventSource` cursor-loss bug | **Fixes** `api.ts` `onerror`: always `es?.close(); scheduleReconnect()`, preserving the `?since=` cursor | **Claude** (real correctness fix) |
| #386 AC4 (metadata-only, test-asserted) | `test/utils/test_logging.py` **+67** redaction suite | `test/utils/test_log_redaction.py` **+74** redaction suite | **Tie** |
| OTel dependency hygiene | `opentelemetry-api` stays **core**; SDK+exporter → `[otel]`; `try/except ImportError` no-op in `otel.py` | **All three** → `[otel]`; full no-op stubs in `telemetry/__init__.py` | see §1.3 |
| OTel fallback *proof* | none needed (api always importable) | subprocess test — **FAILS on Py3.12** (`find_module` removed) | **Kiro** (green); Claude's proof is broken |
| Demo / proof quality | `examples/agui-dashboard/showcase.sh` proves the live path **headlessly** (6× `emit_ui` 200 + `iframe` 400); video is CI-only; **no committed binary** | commits `docs/media/agui-live-remediation-demo.webm` (88,974 B) + live spec | split — see §1.3 |
| Test breadth | skill-packaging parity suite (`test_skill_packaging_parity.py`); deeper stream test | example-profile validation, enablement matrix, log-redaction, auth-hardening, telemetry-fallback; PWA `InstancePicker.test.tsx` + `api.test.ts` reconnect (24 vs 18 PWA tests) | **Claude** (breadth) |
| Skill shipping | adds `agui-author` to `SHIPPED_SKILLS` (`scripts/sync_skills.py`) + byte-identity parity test | relies on dynamic `resources.files(...).iterdir()` seeding | **Kiro** (parity guard) — but see §1.3 (Kiro's *note* misstates the seeding mechanism) |
| Diff hygiene | 60 files | 66 files (webm + more tests) | **Tie** |
| Gates | **all green** | 2 self-authored telemetry tests fail on Py3.12 | **Kiro** |
| In-repo evidence | `kiro-implementation-notes.md`, `pr387-A-description.md` | **`pr387-review-audit-synthesis-2026-07-06.md`** (per-finding proofs + the 6 misattributed findings) + notes | **Claude** (the synthesis is the reusable ground-truth) |

### 1.2 PR-B pair scorecard (`…/pr387-a2a-hardened`, both stacked on `f40933d`)

| Dimension | Kiro `a708259` | Claude `61b1dd1` | Edge |
|---|---|---|---|
| B1 auth — enforcement order | authorize **after** body-parse + request-validation, before method lookup (leaks JSON-RPC 400 parse errors to anonymous callers) | authenticate **first, before body parse** ("unauthenticated peer learns nothing"); adds `WWW-Authenticate: Bearer` | **Claude** |
| B1 auth — 500→401 (I3/G7) | broad `except Exception` → 401 | broad `except Exception` → 401 (+ `logger.info exc_info`) | **Tie** (Claude marginally better observability) |
| B1 auth — scope map | `_METHOD_REQUIRED_SCOPE`: send/cancel→write, get→read, write⇒read, admin any | `_METHOD_SCOPES` tuples: send/cancel→(write,admin), get→(read,write,admin) | **Tie** |
| B1 auth — header edge cases | `split(None,1)`; accepts `"Bearer a b c"` as token | `split()` + `len==2`; rejects multi-segment | **Tie** (JWT has no spaces; Claude marginally stricter) |
| B2 store — error semantics | `RESOURCE_EXHAUSTED` + **HTTP 429** | `TASK_LIMIT_EXCEEDED` + **HTTP 200** (JSON-RPC error body) | see §1.4 decision |
| B2 store — bounds correctness | cap + TTL; evict oldest **terminal** by insertion order; refuse when all live | cap + TTL; evict oldest terminal by **timestamp** `min(...)`; more robust sweep fallback `(updated_at or created_at or now)` | **Claude** (marginal) |
| B2 store — env wiring | env read **inside `__init__`** via `_env_int`/`_env_float` (swallow bad values); `InMemoryTaskStore()` is auto env-aware | `from_env()` classmethod (bare `int()`/`float()`, no fallback); `main.py` **does** call `.from_env()` (production correct) | **Tie** (both correct; Kiro more defensive, Claude's plain ctor ignores env — a latent footgun) |
| Mount guard | pure `_should_mount_a2a(*, bind_host, a2a_disabled, auth_enabled)` — unit-testable decision matrix; `logger.warning` | inline lifespan guard + `test/api/test_a2a_mount_guard.py` TestClient integration test; `logger.error` | **Split** — reconcile takes both (§2) |
| `reset_jwks_cache` latent break | **left unfixed** — `conftest.py:113/115` still call a function `auth.py` doesn't define (only `_JWKSCache.clear()`); dormant because Kiro's auth tests don't consume the `auth_enabled_env` fixture | **fixed** — adds module-level `reset_jwks_cache()`; its `test_a2a_roundtrip.py` **consumes** `auth_enabled_env` (real JWKS path) | **Claude** |
| Auth test design | `test/a2a/test_auth.py` ~291 lines, **28-case matrix**, but **monkeypatches** `is_auth_enabled` + `extract_scopes_from_token` (enforcement logic, auth stubbed) | `test_auth_enforcement.py`(192)+`test_store_bounds.py`(122)+`test_a2a_mount_guard.py`(53) + **authenticated e2e roundtrip** minting a real RS256 JWT through real `extract_scopes_from_token` | **Split** — Kiro broader matrix, Claude higher fidelity; reconcile unions both (§2) |
| Dep placement | **no `[a2a]` extra** — `src/` imports neither `authlib` nor `multipart` (Agent Card signs via `pyjwt[crypto]`); dep hygiene rides PR-A | folds `[a2a]` extra into PR-B `pyproject.toml` | see §1.4 decision |
| Docstring truth (G5) | rewritten to describe real enforcement | rewritten to describe real enforcement | **Tie** |
| Gates | green modulo 1 unrelated env flake | **all green** | **Claude** (marginal) |

### 1.3 PR-A contrast points — adjudicated

- **OTel strategy.** *Leaner base:* Claude (removes all three otel packages). *Safer against import/stub drift:* Kiro (keeping `opentelemetry-api` core means `telemetry/__init__.py` never needs signature-matched no-op stubs; note Claude's `extract_traceparent` stub already needs `# type: ignore[misc]`). *Matches the reviewer's literal ask ("move the three OTel deps to `[otel]`"):* Claude. **Decisive tiebreak — the proof:** the review asks for *default-off proven*; Claude's proof (`test_optional_extra.py`) **does not pass** on the interpreter the venv uses (Py3.12 removed `find_module`), so the safety it advertises is **currently unverified by a green test**, while Kiro needs no such test. Reconcile (§2) takes **Claude's all-three-`[otel]` move (leanest, matches the ask) with a corrected fallback test** (`importlib.abc.MetaPathFinder.find_spec`, and assert *both* the installed and blocked paths).
- **Demo video.** Repo-artifact hygiene (an 88 KB binary `.webm` committed to the tree) vs immediate, reviewable, CI-reproducible proof. The fork's working agreement is "demos drive the **live path**." Claude's committed webm *is* a live-path recording, but a committed binary is review-noise and drifts; Kiro's `showcase.sh` proves the same live path headlessly and is inspectable as text + re-runs in CI. **Reconcile: keep Kiro's `showcase.sh` as the canonical live proof; produce the webm in CI only (Claude's recording workflow), do not commit the binary.**
- **Reconnect proof + cursor-loss fix.** This is the single most important PR-A correctness delta. **Claude found and fixed a real PWA bug** (`cao_pwa/src/api.ts`): native `EventSource` retries its *original* URL from `CONNECTING`, silently dropping the `?since=` cursor and losing the gap replay; the fix forces `es.close()` + a `scheduleReconnect()` that re-derives the cursor. **Kiro's `api.ts` is byte-identical to `f40933d`** (`git diff` = 0 lines) — Kiro **ships the bug**, and its live spec uses offline/online emulation, which in headless Chromium does not reliably sever an *already-established* SSE stream, so the test can pass without ever exercising a real reconnect. **This fix is carried into the reconcile regardless of source, with Claude's `api.test.ts` reconnect unit assertions.**
- **Skill registration.** `SHIPPED_SKILLS` is a real allowlist — but it lives in `scripts/sync_skills.py` (a **CI packaging/parity** mechanism), *not* the runtime. `cao init`'s `seed_default_skills()` seeds via dynamic `resources.files("cli_agent_orchestrator.skills").iterdir()`, so **both** skills seed correctly (both ship `src/cli_agent_orchestrator/skills/agui-author/SKILL.md` — confirmed present via `git cat-file -e`). Kiro's addition (`SHIPPED_SKILLS += "agui-author"` + `test_skill_packaging_parity.py` byte-identity guard) is **better packaging hygiene** and is adopted. Caveat recorded for honesty: Kiro's implementation-note claim *"added to `SHIPPED_SKILLS` **so `cao init` seeds it**"* is **causally wrong** — `cao init` never reads `SHIPPED_SKILLS`; the note wording is corrected in the reconcile.
- **Test breadth.** Claude's example-profile validation suite (`test_example_profiles.py` — every `examples/**` profile's `provider` checked against `ProviderType`, generalizing the G4 fix), enablement matrix, and log-redaction suite are genuinely broader; Kiro's stream `?since=` depth (+141) and skill-parity suite are genuinely deeper in their lane. **Reconcile unions all of them.**

### 1.4 PR-B contrast points — adjudicated

- **Error semantics (store-full).** A2A is JSON-RPC 2.0 over HTTP; JSON-RPC §5 returns *application* errors in the Response object over a normal (200) transaction. A store-at-capacity condition is an application error, and a generic JSON-RPC/A2A client may treat a non-200 as a transport failure and never parse the error body (hurts AC3 "stock clients work"). **Decision: adopt Claude's HTTP-200 + JSON-RPC error body**, but **name the error with the canonical A2A/gRPC code `RESOURCE_EXHAUSTED` (Kiro's naming)** rather than a bespoke `TASK_LIMIT_EXCEEDED`, and include a `retry-after`-style hint in the error `data`. Rationale: transport correctness (Claude) + canonical, ecosystem-legible code (Kiro). *Flag to verify before finalize:* confirm `RESOURCE_EXHAUSTED` exists in the A2A error taxonomy the branch's `A2AErrorCode` enum encodes.
- **Mount guard.** Testability vs integration fidelity is a false choice — take **both**: Kiro's extracted pure `_should_mount_a2a()` (parametrized decision matrix, no socket) **and** Claude's `test_a2a_mount_guard.py` TestClient test that binds the real app and asserts the routers are absent. Use `logger.warning` (intentional safe refusal, not a system error).
- **Dep-hygiene placement.** Kiro's argument is correct on the merits: `src/` imports neither `authlib` nor `python-multipart` (the Agent Card signs via `pyjwt[crypto]`), so inventing an `[a2a]` runtime extra would be a false claim. But the two PRs must survive landing **in either order**, and PR-B is the one that *reintroduces* the A2A surface. **Decision: dep hygiene (drop the two runtime deps, `authlib`→dev) lands in PR-A (Kiro's placement); PR-B adds an `[a2a]` extra *only if* it introduces a real runtime import** — audit at reconcile time; if `src/` still imports neither, ship **no** `[a2a]` extra (Kiro is right) and document why in the PR-B body. This keeps every PR description truthful to its diff.
- **Auth tests.** Union: keep Kiro's 28-case enforcement matrix (fast, monkeypatched — exhaustive on the decision logic) **and** Claude's authenticated e2e roundtrip (real RS256 JWT through real `extract_scopes_from_token` + JWKS stub — proves the wiring, not just the logic). **Carry Claude's `reset_jwks_cache()` fix regardless** — it repairs a real dead reference in base `conftest.py` and is the precondition for any in-process auth-enabled test.
- **Enforcement order.** Adopt **Claude's authenticate-before-parse** ordering (an anonymous peer gets 401 even on a malformed body — no method-surface or parser-behavior leakage) **plus** its `WWW-Authenticate: Bearer` header. Keep Kiro's per-method scope table (identical semantics).

### 1.5 What BOTH sides missed (fresh eyes)

1. **`emit_ui` rate limiting — absent on both** (`git grep` for rate-limit/throttle in `services/agui_stream.py` + `api/main.py` returns only the *pre-existing memory* increment limiter). The generative-UI producer endpoint (`POST /agui/v1/emit_ui`) has no per-agent throttle; a busy or misbehaving agent can flood the SSE surface. Neither branch closed it. **Recommend: file as a follow-up** (out of PR-A/PR-B scope, but name it in the reply so it isn't a silent gap).
2. **`STATE_DELTA` recompute has no debounce — acknowledged but unaddressed on both.** Both carry the *identical* inherited comment at `api/main.py:789`: *"this recomputes on every event; for high event rates a debounce would help."* Neither implemented it. **Recommend: follow-up ticket** (performance hardening, not a correctness/AC blocker).
3. **Not a miss (correctly deferred by both):** the short-lived single-use ticket handshake for the AG-UI stream — both filed it as a follow-up per the review's own I2 guidance. Listing it here only to pre-empt it being counted as an omission.

### 1.6 Regressions vs `f40933d`

- **Kiro PR-A:** deleted `test/api/test_oauth_prm.py` (139 lines) **while retaining** the `oauth_protected_resource` endpoint (`git grep` count = 2 on the branch, same as base) → a **test-coverage regression** on a shipped endpoint. Also leaves the `reset_jwks_cache` dead reference in `conftest.py` (dormant — no consumer on the branch, but a footgun for any future auth-enabled in-process test).
- **Claude PR-A:** introduced **2 tests that fail** under the prescribed `uv sync --all-extras` on Python 3.12 (`test_optional_extra.py`) — a broken proof / test-theater regression: the branch does not pass its own suite on a supported interpreter.
- **Neither** regresses `src/` runtime behavior; both are mypy-strict clean; both keep AG-UI default-off.

---

## Phase 2 — Reconciliation plan (implement only after approval)

Produce two branches stacked on `f40933d`: **`reconcile/pr387-agui-core`** and **`reconcile/pr387-a2a-hardened`**. Method: **cherry-pick/port the objectively better implementation per point; union complementary tests; never rewrite what one side already got right.**

### 2.1 `reconcile/pr387-agui-core` — step by step

1. **Start from Kiro's core** (`660e3f4`) — it is fully green and its A2A subtraction, `?since=` depth (+141), and `SHIPPED_SKILLS` parity guard are the stronger base. `git switch -c reconcile/pr387-agui-core f40933d` then apply Kiro's tree.
2. **Port Claude's `cao_pwa/src/api.ts` cursor-loss fix verbatim** + `cao_pwa/src/test/api.test.ts` reconnect assertions + `InstancePicker.test.tsx`. *(Priority-1: AC3 real-client correctness.)*
3. **Restore the AC1 route-table assertion:** take Claude's adapted `test_default_off_listeners.py` (byte-identical-route-table style) **and** keep Kiro's `_agui_enabled()` both-paths unit test + `emit_ui`/stream 404. **Restore `test_oauth_prm.py`** (or fold its assertions in) since the endpoint still ships. *(Priority-1: AC1 test-asserted; closes Kiro's coverage regression.)*
4. **OTel:** adopt Claude's all-three-`[otel]` layout; **rewrite the fallback test** to use `importlib.abc.MetaPathFinder.find_spec` (Py3.12-correct) and assert *both* the blocked (no-op) and installed paths. Gate must be green under `--all-extras`. *(Priority-2: closure + Priority-4: honest proof.)*
5. **Union the test breadth:** carry Claude's `test_example_profiles.py`, `test_agui_enablement.py`, `test_log_redaction.py`, `test_agui_auth_hardening.py` **and** Kiro's `test_skill_packaging_parity.py` + deeper `test_agui_stream_endpoint.py`. Keep whichever redaction suite is broader; drop the duplicate.
6. **Demo:** keep Kiro's `showcase.sh` headless live proof as canonical; wire Claude's CI recording workflow to emit the webm as a **CI artifact**; **do not commit the binary**.
7. **Skill note fix:** keep `SHIPPED_SKILLS += agui-author` + parity test; correct the note wording (`cao init` seeds via dynamic `iterdir`, `SHIPPED_SKILLS` guards packaging parity).
8. **Both fixes carried:** mypy `python_version = "3.10"`, the five Copilot fixes, dated-doc fold, G4 example retarget (already in both).

### 2.2 `reconcile/pr387-a2a-hardened` — step by step

1. **Start from Claude's PR-B** (`61b1dd1`) — it is fully green, authenticates-before-parse, fixes `reset_jwks_cache`, and exercises the real auth path. `git switch -c reconcile/pr387-a2a-hardened f40933d` then apply Claude's tree.
2. **Store error semantics:** keep Claude's **HTTP 200 + JSON-RPC error body**; **rename the code to `RESOURCE_EXHAUSTED`** (canonical) and add a `retry-after` hint in `data`. Verify the enum encodes it.
3. **Mount guard:** refactor Claude's inline guard into Kiro's pure `_should_mount_a2a(*, bind_host, a2a_disabled, auth_enabled)`; keep Claude's `test_a2a_mount_guard.py` TestClient test **and** add Kiro's parametrized decision-matrix unit test. Use `logger.warning`.
4. **Store env-wiring:** adopt Kiro's defensive `_env_int`/`_env_float` (swallow malformed env → default) inside the constructor so a plain `InMemoryTaskStore()` is env-aware; keep a `from_env()` alias for call-site clarity.
5. **Auth tests:** union Kiro's 28-case monkeypatched matrix **and** Claude's authenticated RS256 e2e roundtrip; keep `reset_jwks_cache()`.
6. **Dep placement:** confirm `src/` imports neither `authlib` nor `python-multipart`; if so, ship **no `[a2a]` extra** (Kiro is correct) and state that in the PR-B body; dep hygiene stays in PR-A.
7. **Docstrings** describe the enforcement that exists (both already do).

### 2.3 Strongest properties preserved at their strongest form

- **Default-off:** A2A modules **absent from PR-A entirely** (file-level, not flag-gated); AG-UI **404s with no flags**, asserted by the restored route-table test + `_agui_enabled()` unit test.
- **Metadata-only redaction:** union redaction suite + the reviewer's canary-secret test remain green (AC4).

### 2.4 Gates on both reconciled branches (exact commands + expected)

```bash
uv sync --all-extras --dev
uv run pytest -m 'not e2e'      # PR-A: ≥ 3525 passed, 0 failed (Kiro base + Claude's suites + corrected otel test)
                                #        — the 2 Py3.12 telemetry failures MUST be gone
uv run mypy src/                # Success (≥132 files PR-A / ≥142 PR-B)
uv run black --check . && uv run isort --check-only .   # clean
# PR-A only:
cd cao_pwa && npm ci && npx tsc --noEmit && npm test && npm run build
                                # ≥ 24 tests passed (union incl. api.ts reconnect), tsc clean, build ok
# PR-B: 0 failed (the 1 provider env flake is environment-specific; pin/skip or run in CI)
```
The pre-existing `test_fifo_reader` and `test_claude_code_unit` env flakes are documented as environment-specific; CI (Linux) does not exhibit them.

### 2.5 Truthful PR descriptions + upstream reply

- Rewrite each reconciled PR body to list **only** what its diff contains (the `I1` finding). PR-A: AG-UI core + generative UI + PWA (incl. the reconnect fix) + `mock_cli` + OTel `[otel]` extra + WS/query-token auth hardening. PR-B: A2A + Agent Card with per-method auth, bounded store, mount guard — and an explicit "no `[a2a]` extra because `src/` imports neither lib" line if that holds.
- **Update `docs/reviews/pr387-agui-response-draft-v2.md`** for the two claims reconciliation changes: (a) the reconnect/`?since=` recovery is now proven by a real fix + unit assertions (not offline emulation); (b) OTel is the all-`[otel]` layout with a Py3.12-correct fallback test. Keep every existing accepted/rejected verdict (they're unchanged).
- **Sequencing (per @fanhongy):** land **PR-A first** (retarget `reconcile/pr387-agui-core` onto upstream `awslabs#387`); open **PR-B after** PR-A merges (or when reviewers ask). Both opened as **drafts with base `feat/agentic-protocols-generative-ui`**.

### 2.6 Constraints honored

Never push to `feat/agentic-protocols-generative-ui`, `kiro/*`, or `claude/*`. New work lands only on `reconcile/*`. This plan itself lands on `docs/pr387-reconciliation` as a draft PR for review **before** any reconciliation code is written.

---

## Appendix — evidence index (reproduce)

- Gate logs: `.worktrees/{kiro,claude}-{agui,a2a}/GATES.log`, `…/PWA.log`.
- Diffs: `.worktrees/diffs/*.diff` (per-file vs `f40933d`), `PAIR-{agui,a2a}.stat.txt`.
- Cursor-loss: `git diff f40933d kiro/pr387-agui-core -- cao_pwa/src/api.ts` = **0 lines**; `…claude… -- cao_pwa/src/api.ts` = **21 lines**.
- OTel test breakage: `test/telemetry/test_optional_extra.py` uses `find_module`/`load_module` (removed in Py3.12); venv is `cpython-3.12`.
- `reset_jwks_cache`: `git show f40933d:test/conftest.py` lines 113/115 call it; `git show f40933d:src/…/security/auth.py` defines only `_JWKSCache.clear()`; Claude adds it, Kiro does not.
- `SHIPPED_SKILLS`: only in `scripts/sync_skills.py`; `cao init` seeds via `resources.files(...).iterdir()` (`src/…/cli/commands/init.py`).
- Both-missed: `git grep` rate-limit/throttle → only pre-existing memory limiter; `api/main.py:789` debounce comment identical on both.
- **Reconnect (corroborated by Kiro's own commit `660e3f4`):** its message states `page.context().setOffline(true)` *"does NOT reliably drop an already-established SSE connection in Chromium, so EventSource.onerror never fired"*, so Kiro **replaced the offline test with a `page.reload()` reconnect** and **reworded away from** *"claiming an offline→online `?since=` resume"* — i.e., Kiro's live spec proves a reload-reconnect, not the client-side `?since=` cursor recovery, and Kiro never fixed the `api.ts` cursor-loss path. This is primary evidence for the AC3 adjudication in §1.3.
- **Commit authorship (both sides):** `kiro/*` commits have git author = committer = `Kiro Agent <244629292+kiro-agent@users.noreply.github.com>` with a *self-referential* `Co-authored-by: Kiro Agent` trailer (so GitHub shows only kiro-agent, not `plauzy` + kiro-agent); `claude/*` likewise author as `Claude`. Dual human+agent attribution requires the **author** to be the human (`plauzy`) with the agent in a `Co-authored-by` trailer — recorded here as a process note, not a code finding.
