# PR #387 remediation — head-to-head evaluation & reconciliation plan (Kiro × Claude)

- **Date:** 2026-07-06
- **Scope:** the four remediation branches for the upstream review on
  [awslabs/cli-agent-orchestrator#387](https://github.com/awslabs/cli-agent-orchestrator/pull/387)
  (review 4632216702 + @fanhongy's decomposition ask), all stacked on the PR head `f40933d`:
  - PR-A pair: [#14](https://github.com/plauzy/cli-agent-orchestrator/pull/14) `kiro/pr387-agui-core @ 660e3f4` · [#11](https://github.com/plauzy/cli-agent-orchestrator/pull/11) `claude/pr387-agui-core @ 7bf2b06`
  - PR-B pair: [#13](https://github.com/plauzy/cli-agent-orchestrator/pull/13) `kiro/pr387-a2a-hardened @ a708259` · [#12](https://github.com/plauzy/cli-agent-orchestrator/pull/12) `claude/pr387-a2a-hardened @ 61b1dd1`
- **Method:** provenance-blind, evidence-only. Every gate below was **executed in this session**
  (worktrees per branch, sequential runs after a parallel-run pytest race was identified and
  excluded); both live demo paths were run against real servers; the cross-diffs
  (`git diff kiro/… claude/…`) were walked hunk by hunk. A claim not reproduced here is marked
  *unverified*. Commands are in the appendix.
- **This is a plan, not an implementation.** No `reconcile/*` branch exists yet; nothing here
  touches `feat/agentic-protocols-generative-ui` or the four existing branches.
- **Relationship to [#15](https://github.com/plauzy/cli-agent-orchestrator/pull/15):** a parallel
  evaluation of the same four branches landed on `docs/pr387-reconciliation` while this one was
  in flight (macOS arm64, Python 3.12, no browsers available). The two reach the **same major
  verdicts independently** (cursor fix, auth-before-parse, `reset_jwks_cache`, extracted guard +
  integration tests, union-the-suites). Material evidence deltas: #15 executed the suites on
  **Python 3.12**, where claude-A's two subprocess OTel tests **genuinely fail** (`find_module`
  removed — upgrading the 3.12 wart flagged below from latent to executed; the fix is scheduled
  at P2-A step 4); this evaluation uniquely **ran every live path** (both browser specs, both
  showcases, the A2A e2e roundtrips, wheel builds) on Linux/Python 3.11, which #15 could not.

---

## 0. Executed evidence (the numbers everything below cites)

| Gate | base `f40933d` | kiro-A | claude-A | kiro-B | claude-B |
|---|---|---|---|---|---|
| `uv run pytest` | **3569 P / 21 S / 108 desel** | **3484 P / 22 S / 107** | **3525 P / 21 S / 107** | **3597 P / 21 S / 109** | **3592 P / 21 S / 109** ¹ |
| `uv run mypy src/` | 142 files, clean | 132, clean | 132, clean | 142, clean | 142, clean |
| `black --check` + `isort` | clean | clean | clean | clean | clean |
| `cao_pwa` tsc / vitest / build | clean / **18** / clean | clean / **18** / clean | clean / **24** / clean | n/a (cao_pwa untouched) | n/a |
| Live browser spec | n/a | **1 passed** ² | **1 passed, as-committed** ³ | n/a | n/a |
| `showcase.sh` live | n/a | **PASS** (6×200 + 400 + snapshot + 6 GENERATIVE_UI frames off the real SSE stream) | **PASS** (6×200 + 400; POST-only, never reads the stream) | n/a | n/a |
| A2A e2e roundtrip (`-m e2e`) | n/a | n/a | n/a | **2 passed** ⁴ | **2 passed** (real RS256 JWTs vs live JWKS) |
| Targeted new suites | n/a | n/a | n/a | `test_auth.py` **28 passed** | auth+bounds+guard **23 passed** |
| Wheel ships `agui-author` | n/a | ✓ (`unzip -l`) | ✓ (`unzip -l`) | n/a | n/a |

¹ claude-B's first run showed 1 failure in `test_claude_code_unit.py` — reproduced as a
**cross-worktree tmpfile race from running two suites concurrently in this evaluation**
(the helper `unlink()`s a path keyed by a fixed fake terminal id); it passes in isolation and
the solo re-run is 3592/0. Not a branch defect.
² kiro-A's spec **cannot run as-committed in a restricted sandbox**: its config has no
executable override, `@playwright/test 1.61.1` wants chromium rev 1228, the preinstalled build
is 1194, and the CDN is blocked. With a rev-shim (symlink 1194→1228) it passes — so its CI-only
posture is honest and its logic sound, but the artifact is not sandbox-portable.
³ claude-A's spec ran unmodified via its `PLAYWRIGHT_CHROMIUM_EXECUTABLE` hook. The server log
captured the decisive moment: after SIGKILL + restart,
`GET /agui/v1/stream?since=2026-07-06T20:25:14…` — the preserved cursor doing gap replay.
⁴ Both roundtrips are in-process ASGI tests; kiro-B's "tmux-gated in the sandbox" note was
over-cautious — it runs without tmux-dependent fixtures.

**PR-body claim ledger:** claude-A "3,525 / mypy 132 / 24 vitest / live spec green with video" —
all reproduced. claude-B "3,592 / e2e 2 passed / mypy 142" — reproduced. kiro-A "mypy 132 /
tsc+vitest 18 / build / showcase PASS / AC1 404-404" — reproduced (its "159 passed" was a
targeted subset; full suite 3484 green). kiro-B "3596 P / 21 S with one xdist flake" —
reproduced at 3597/21 sequentially (one better than claimed; the flake note is consistent).
kiro-A's "video is CI-only because the Playwright CDN is blocked" — accurate. **One false PR-body
claim found:** claude-A's "prop names verified against the actual renderers" (see A6).

---

## 1. Phase 1 — PR-A pair scorecard (`kiro/pr387-agui-core` vs `claude/pr387-agui-core`)

### Review-finding closure (per accepted finding)

| Finding | kiro-A | claude-A | Verdict |
|---|---|---|---|
| Split: A2A out of the core PR | ✓ subtracts `a2a/`+`agent_card/`+suites+lifespan+`:9890` | ✓ identical subtraction, **plus** a regression suite asserting the stronger contract (`import a2a` → `ImportError`, no `/a2a` routes, no listener state, AG-UI 404s: `test_default_off_listeners.py`) | **claude** — kiro deleted that file and asserts absence nowhere |
| Token-parse → 401 / 4401 (I3) | ✓ same fix shape (broad catch → 401 / None→4401), tests **monkeypatch the extractor to raise** — the real JWT parse never runs (the exact "mocked extract" the review nit called out) | ✓ same fix + `logger.info(exc_info=True)` before failing closed; tests run the **real parser** on malformed tokens (SSE + WS), plus valid-token over-catch guards and missing-bearer case | **claude** |
| JWT in access logs (I2) | ✓ `RedactQueryTokenFilter` + idempotent installer; regex without `\b` (over-redacts `my_access_token`, benign); tests cover the **args path only** — its own `msg` branch is untested | ✓ near-identical filter with `\b`-anchored regex; tests cover **msg and args** paths + real `uvicorn.access` wiring + idempotency | **claude** (small) |
| `?since=` endpoint de-stub | ✓ genuine strict-`>` fake; uniquely asserts the **forwarded** `since` value | ✓ genuine strict-`>` fake; brackets the boundary with a stale+new event pair in one pass | **even** — union both (neither tests the equal-timestamp case) |
| `_agui_enabled()` docs + enablement tests | ✓ docstring rewrite; parametrized **helper-level** test (covers truthy `1`) | ✓ docstring rewrite; **route-level** 404/≠404 matrix (`0/false/no/off/""` falsey set) | **claude** (route-level is the contract); port kiro's `1` case |
| Dead `gemini_cli` example (the defect no reviewer caught) | ✓ retargeted to `antigravity_cli` | ✓ retargeted **plus** `test/examples/test_example_profiles.py` validating every `examples/**` profile's provider against `ProviderType` (would have caught this class of defect) | **claude** |
| Copilot five | ✓ all five | ✓ all five, plus component tests pinning the `InstancePicker` sibling-button restructure (4 vitest) | **claude** (tests land with the fix; kiro pins nothing) |
| Dated design doc → docs/pwa.md | ✓ | ✓ + "Verified by" column citing real tests | **even/claude** |
| OTel dep hygiene (nit) | keeps `opentelemetry-api` core; SDK+exporter → `[otel]`; **graceful warning** if telemetry enabled without the extra | all three → `[otel]`; hand-written no-op fallback proven by **subprocess tests** (meta-path blocker; also proves `api.main` imports on a base install) | **claude's shape, kiro's robustness** — see A1 |
| PR-body truthfulness (I1) | body accurate; PR-A description doc committed | body accurate except the **"props verified against the actual renderers"** claim (A6) | **kiro** on this one axis |

### AC compliance (issue #386)

- **AC1 default-off:** both keep the pre-existing 404 tests; only claude-A asserts the *stronger*
  post-split form (modules absent, no routes, no listener). **claude**.
- **AC2 stream + `?since=` replay:** server side equal; client side **only claude-A** preserves
  the cursor across drops — kiro-A's `cao_pwa/src/api.ts` is byte-identical to base, so the
  pre-existing bug (native `EventSource` retries its original URL from CONNECTING, silently
  dropping the advanced `?since=` cursor; server frames carry no `id:` so `Last-Event-ID`
  can't save it) **remains on kiro-A, unfixed and untested** — while kiro-A's `docs/pwa.md`
  still claims "resumes without a gap". claude-A fixed it (`api.ts`: always take over reconnection
  with capped backoff), added 2 vitest reconnect tests, and proved it end-to-end (see next).
  **claude, decisively.**
- **AC3 zero-adapter client / live demo:** both drive the live path. claude-A's spec is the
  stronger proof *and* sandbox-portable (ran here as-committed): 6 components + refusal +
  **hard-kill + restart + event emitted during the outage arrives via replay** (count 6→7 pins
  no-dup and no-gap). kiro-A's spec (CI-only here without a shim) proves 6 components + refusal +
  reload-persistence; its own CI history (commit `660e3f4`) established that
  `page.context().setOffline(true)` **does not sever an established SSE in Chromium** — the
  original offline/online reconnect step never fired and was honestly replaced by `page.reload()`,
  which exercises IndexedDB persistence, **not** `?since=` recovery (and even the original
  version only asserted status-pill classes, never a missed event's arrival). **claude**, with
  kiro's reload-persistence step worth keeping as an *additional* scenario.
- **AC4 metadata-only:** unchanged on both (pre-existing redaction suite; reviewer-verified on the
  base). **even**.

### Remaining contrast points

**A1 — OTel strategy.** The reviewer's ask was "optional extras (`[otel]`) to keep base install
lean". claude-A is the strict reading (base install carries zero OTel packages; subprocess tests
prove the fallback and that `api.main` imports without the SDK). kiro-A leans on OTel's own
design (the api package is a safe no-op dependency) — less bespoke code, zero drift risk, and a
**better failure mode**: telemetry requested without the extra logs an actionable warning
("install cli-agent-orchestrator[otel]"), where claude-A's stub is silent and its `otel.py`
would raise on the transitive-api-present/SDK-absent edge (caught by the lifespan's
failure-isolated `try/except` — logged, never boot-blocking, but ugly). Two warts on claude-A:
the fallback needs a `type: ignore`, and the subprocess test's meta-path blocker uses the legacy
`find_module` protocol removed in Python 3.12 — **confirmed as an executed 2-test failure on a
Python 3.12 host by the parallel evaluation (#15)**; green here on 3.11. **Reconcile:
claude's packaging + kiro's degrade behavior** (P2-A step 4).

**A2 — Demo video.** claude-A commits `docs/media/agui-live-remediation-demo.webm` (88,974 B,
a real recording of the live spec) + CI recording; kiro-A produces video only on CI. Decisive
context: `docs/media/` **already contains committed demo binaries on the base branch**
(mp4/webm/gif from earlier features), so the committed webm follows established repo convention
and gives reviewers immediate proof; 88 KB is negligible. One bug: claude-A's example README
embeds it with `![]()` image syntax, which GitHub won't play — link it instead. **claude**, with
the README fix; offer upstream to drop the binary if maintainers prefer artifact-only.

**A3 — Reconnect proof.** Settled above (AC2/AC3): claude's restart+replay spec is the only
artifact that discriminates the cursor bug; offline/online is empirically non-viable in
headless Chromium (kiro's own CI); kiro's reload step tests a real, different property
(IndexedDB persistence + auto-activation). **Union in one spec** (P2-A step 6). Also fix a wart
found while running claude's spec here: its `afterAll` SIGTERMs the `npm run preview` *wrapper*,
orphaning the vite child (it held :4173 after the run — the exact wrapper-orphan failure the
spec itself documents and avoids for `cao-server`).

**A4 — Skill registration.** The codebase uses **both** mechanisms: runtime seeding is dynamic
(`resources.files(...).iterdir()` in `cli/commands/init.py`), but `scripts/sync_skills.py`
(pre-existing, #347) declares an explicit `SHIPPED_SKILLS` allowlist whose own comment says to
keep it in sync with what ships, and the pre-existing `test_skill_packaging_parity.py`
parametrizes over that list. Both branches' skills ship in the wheel and seed (verified by
`uv build` + `unzip -l`). But kiro-A registered `agui-author` in `SHIPPED_SKILLS`, which puts the
skill under the sync/parity machinery (5 parity tests; the "22nd skip" in kiro-A's suite is
exactly `parity[agui-author]: no references/ subdir` — evidence the coverage engaged); claude-A's
skill sits outside it — `sync_skills.py --check` reports "9 in sync" and would never catch its
two trees drifting. **kiro.**

**A5 — Test breadth.** claude-A adds 5 suites kiro-A has no equivalent for (auth-hardening on
the real parse path, route-level enablement, log-redaction msg+args, example-profile validation,
A2A-absence regression) + 6 vitest (a11y + reconnect cursor); kiro-A's only unique test assets
are the forwarded-`since` assertion, the truthy-`1` enablement case, and the parity coverage via
registration (A4). kiro-A also **deleted `test/api/test_oauth_prm.py` (139 lines) although the
main-app OAuth PRM / RBAC layer it tests still ships on its branch** — a coverage regression vs
`f40933d` (the endpoint lives in `api/main.py` + `security/auth.py`, not in the removed
`agent_card/`); claude-A kept it green. **claude.**

**A6 — Demo/skill prop fidelity (found by this evaluation; neither side's docs mention it).**
The shared renderer (`GenerativeUI.tsx`, byte-identical on both branches) reads
`diff_summary.title` (line 84) and clamps `progress.value` to **[0,1]** (line 109). kiro-A's
showcase/spec/skill teach exactly that (`title`, `value: 0.42`). claude-A's `showcase.sh`,
live spec, and `agui-author/SKILL.md` emit/teach `diff_summary.summary` (silently dropped —
card falls back to "Changes") and `progress.value: 35/60` (clamps to a **full bar**) — while the
SKILL.md asserts "the table lists what the reference renderers display" and the PR body claims
"props verified against the actual renderers". HTTP 200 masks all of it, and the spec's
assertions dodge the affected props. **kiro's vocabulary is the correct one**; claude's demo
layer needs the prop fix and the overclaim retracted. Related script quality: kiro's showcase
tails the real SSE stream (frames visible) and uses `mktemp`+traps but has **no auth support**;
claude's supports `CAO_TOKEN` and asserts exact per-emit codes but never reads the stream and
hardcodes `/tmp/agui-showcase-resp.json`. kiro's `run.sh` is self-contained (starts the server,
degrades gracefully without tmux) but leaks its mktemp'd server log and reads `CAO_API_PORT`
without passing it to the server; claude's `run.sh` hard-requires tmux+mock_cli and expects a
pre-started server, but has a README (kiro-A ships **no README** for the example). **Merge**
(P2-A step 7).

**Diff hygiene & commit structure.** claude-A: 12 focused commits (finding→commit map holds up),
66 files, +1817/−3456. kiro-A: 1 mega-commit (`c2a0c9d`, reshape+all fixes) + demo + 2 CI fixups,
60 files, +1390/−3597; the squash makes "tests with or before fixes" unverifiable. claude-A also
ships the shared evidence docs (audit synthesis lives only there). **claude.**

**Regressions vs `f40933d` (PR-A):** kiro-A — `test_oauth_prm.py` deletion (A5);
`docs/pwa.md` reconnect claim now overstates its own code (AC2); default-off listener suite
deleted without replacement. claude-A — none found as regressions; new-artifact defects are the
prop-fidelity issues + vite-orphan + README embed (A6/A3).

---

## 2. Phase 1 — PR-B pair scorecard (`kiro/pr387-a2a-hardened` vs `claude/pr387-a2a-hardened`)

### Blocking-finding closure

Both close **B1** (per-method scope: send/cancel→`cao:write`, get/stream→`cao:read`,
admin-implies-all, write-implies-read; truthful docstrings; 401/403 with JSON-RPC bodies) and
**B2** (cap `CAO_A2A_MAX_TASKS`=1000 + TTL `CAO_A2A_TASK_TTL`=3600, oldest-terminal-first
eviction, refuse-when-full-of-live) with the same decision tables. The differences are in the
edges:

| Axis | kiro-B | claude-B | Verdict |
|---|---|---|---|
| Enforcement order | parse(400) → envelope(400) → auth(401)/scope(403) → method lookup. Anonymous peers can still exercise the JSON parser; 401s echo the request id; error message **echoes internal exception text** (`f"invalid token: {exc}"`) | **auth before any body read** (anonymous peers learn nothing, parser never runs unauthenticated), `WWW-Authenticate: Bearer` on 401 (RFC 6750), generic peer-facing message + server-side `logger.info(exc_info=True)`; 401 body has `id:null` (spec-sanctioned — id unparsed yet) | **claude** |
| Store-full semantics | `RESOURCE_EXHAUSTED` (gRPC-canonical name) + **HTTP 429** — "auth failures are not tunnelled through 200" applied consistently to capacity | `TASK_LIMIT_EXCEEDED` + **HTTP 200** + JSON-RPC error body ("app errors ride 200") | **kiro** — see B1 below |
| Mount guard | **extracted pure `_should_mount_a2a()`** + parametrized decision-table tests (no socket) | inline lifespan guard + **integration tests through the real lifespan** (caplog asserts the refusal log; loopback mounts; default-off no listener) | **both** — extract + keep integration tests |
| Stream router auth | **router-level** `dependencies=[...]` — a future route inherits the gate (fail-closed by construction) | per-route `Depends` (explicit, greppable) | **kiro** (defensive default) |
| Store internals | env parsing tolerant of malformed values (`_env_int` falls back to default); documented `<=0 disables` — which **re-opens the unbounded vector as a config footgun**; TTL sweep ignores tasks with `updated_at=None`; evicts first-in-insertion-order terminal | `from_env()` classmethod (explicit at the mount site, unit-testable) but `int()` **raises on malformed env**; `max_tasks=0` silently means "refuse everything" (fail-closed but undocumented); TTL falls back `updated_at or created_at`; evicts the true timestamp-oldest terminal; `while` loop handles cap shrinkage | **merge** — claude's shape + kiro's tolerant parsing + explicit `<=0` semantics |
| Auth test depth | **28 cases** incl. `cao:admin` acceptance and authenticated-unknown-method — but the whole matrix (and the e2e) **monkeypatches `extract_scopes_from_token` to a dict lookup**: no JWT is ever parsed, "malformed" = "not in the dict". SSE `/stream/{id}` route untested (REST poll only) | **23 tests + 2 e2e on real RS256 JWTs against a live in-process JWKS** (reuses the base branch's own `jwt_factory`/`jwks_server` fixtures — the reuse-existing-infra agreement), incl. expired-token, enforcement-order pin ("auth beats method dispatch"), SSE+REST route tests, docstring-truth regression tests, store env-config tests. Misses an explicit admin-scope case | **claude** for fidelity; port kiro's admin/unknown-method cases onto real JWTs |
| `reset_jwks_cache` latent break | untouched — `test/conftest.py:113,115` still calls a function that exists nowhere (verified on base and kiro-B); latent because nothing uses the fixture, but the next test that does breaks | **fixed** (`security/auth.py` gains the 10-line function; claude-B's own fixtures depend on it). The PR-body claim is accurate *for this branch* — note the same trap persists on both PR-A branches until PR-B lands | **claude** |
| Dep hygiene placement | rides PR-A only (PR-B touches no pyproject): "no `[a2a]` extra should exist — src imports neither authlib nor multipart" (verified). Rebases cleanly onto a landed PR-A | duplicated into PR-B (pyproject+uv.lock hunks identical in content to its PR-A) — self-contained if B landed alone, but **guaranteed rebase conflict** in the agreed A-then-B order | **kiro** — fanhongy's sequencing is A-first by design |
| Docs | CHANGELOG bullet detailed (429 semantics, doc anchor); auth.md scope **table** + guard + bounds | CHANGELOG accurate; auth.md same content + **copy-pasteable 401→403→200 curl walkthrough** | **merge** |

**B1 — Error semantics decision: adopt kiro-B's `RESOURCE_EXHAUSTED` + HTTP 429** (optionally
`Retry-After: 30`). Rationale: JSON-RPC 2.0 is transport-agnostic and *both* implementations
already dual-encode auth failures with matching 401/403 HTTP statuses — so "app errors always
ride 200" is already not the branch invariant; capacity refusal is an operational backoff
condition, not a domain result (task-not-found stays 200), and 429 is the signal HTTP-native
retry middleware, proxies, and dashboards act on without understanding A2A error codes. The
gRPC-canonical name beats the invented `TASK_LIMIT_EXCEEDED`. Keep claude's dual encoding (429
**and** the JSON-RPC error body) so status-ignoring JSON-RPC clients still see the failure.

**Regressions vs `f40933d` (PR-B):** none found on either side (both suites are strict
supersets: base 3569 → kiro-B 3597, claude-B 3592, all green sequentially; `mypy` 142 clean on
both; default-off posture byte-identical asserted by both).

---

## 3. What both missed (and what neither could have seen)

1. **Review 4638092590 (@anilkmr-a2z, 2026-07-06T17:04Z — submitted *after* both remediations
   pushed).** Three must-fix + two nits. Two are already closed by both PR-Bs (auth enforcement;
   bounded store — the review even points at the in-repo `WORKFLOW_OUTPUT_STORE_MAX_ENTRIES`
   precedent) and one nit (authlib→dev) is closed by both PR-As. **Two are genuinely new and
   unaddressed on all four branches:**
   - *must-fix:* `task.send` accepts a peer-supplied `id` verbatim and `store.upsert` will
     **overwrite any existing task** — peer-controlled state injection/cancellation. Both sides'
     bounds tests (`update-existing-when-full is OK`) currently *pin* the upsert behavior.
   - *nit:* `Task.from_dict` does `str(data["id"])` → `KeyError` when a peer omits `id`
     (both sides' tests always send `id: ""`, dodging it).
   Both must be fixed in the reconciled PR-B (P2-B step 5).
2. **WS `4401` close-code is never asserted end-to-end for a malformed/expired token** on either
   PR-A — both stop at "`_extract_ws_scopes` returns None"; the only live 4401 assertion is the
   pre-existing no-token e2e.
3. **The exact equal-timestamp `?since=` boundary** (strictly-greater contract at `ts == since`)
   is untested by both endpoint suites.
4. **`STATE_DELTA` debounce** — `api/main.py:847` carries the base branch's own
   "recomputes on every event; for high event rates a debounce" note; #386 Phase 1 names
   debouncing in its gate. Neither remediation touched it (the review didn't demand it):
   keep as a filed follow-up, not CR-blocking.
5. **`emit_ui` has no rate limiting / abuse bound** (only the 8 KB size cap). Same status:
   follow-up alongside the short-lived-ticket handshake — which both sides *document* as a
   follow-up but neither filed as a tracked issue.
6. **Bearer-parsing edge tests** (scheme case-variants, multiple Authorization headers,
   `Bearer` with no token) are asserted on neither side, though both implementations handle
   them equivalently (first-header wins; empty → 401).
7. **Store `max_tasks<=0` semantics** diverge silently (kiro: disables the cap — re-opening the
   DoS by config; claude: refuses all inserts) and neither documents its choice (P2-B step 4).
8. **Base test-hygiene defect (chargeable to neither side):**
   `test_claude_code_unit.py::test_build_command_mcp_injects_terminal_id`'s helper reads and
   `unlink()`s a **fixed** path keyed to the fake terminal id (`…/tmp/term-42.mcp.json`) — it
   raced across this evaluation's concurrent suites *and* flaked independently on #15's host.
   Follow-up on the base branch: unique-per-test terminal id or tmp_path.
9. Housekeeping: PRs #13/#14 are not actually Draft (Kiro tooling limitation — noted in their
   bodies); the `auth_enabled_env`/`reset_jwks_cache` trap persists on both PR-A branches until
   PR-B lands.

---

## 4. Phase 2 — Reconciliation plan (implementation only after approval)

### Strategy

Two new branches, both stacked on `f40933d`, built by **starting from the branch that won the
most axes and porting the other side's surgical wins** (cherry-pick/adapt, don't rewrite):

- `reconcile/pr387-agui-core` ← start from `claude/pr387-agui-core@7bf2b06`
  (cursor fix + live restart proof + test breadth + retained suites + granular history),
  port kiro-A's five wins (skill registration/parity, prop-correct demo vocabulary,
  showcase/run.sh robustness, OTel degrade UX, config separation for the live spec).
- `reconcile/pr387-a2a-hardened` ← start from `claude/pr387-a2a-hardened@61b1dd1`
  (real-JWT tests, auth-before-parse, `reset_jwks_cache`, from_env shape, docs walkthrough),
  port kiro-B's wins (429/`RESOURCE_EXHAUSTED`, extracted guard + decision-table tests,
  router-level dependency, admin/unknown-method cases, tolerant env parsing, no-pyproject-diff
  sequencing) and add the anilkmr fixes.

Both existing histories remain untouched; `reconcile/*` are new branches; the eventual PRs open
as **drafts with base `feat/agentic-protocols-generative-ui`**.

### P2-A — `reconcile/pr387-agui-core` (steps in commit order)

1. **Branch:** `git checkout -b reconcile/pr387-agui-core 7bf2b06` (claude-A head; its 12-commit
   history is kept as the base narrative).
2. **Skill governance (from kiro-A):** add `"agui-author"` to `SHIPPED_SKILLS` in
   `scripts/sync_skills.py` — the pre-existing parity suite then covers the skill (expect
   +4 passed / +1 skipped `parity[agui-author]` — the references-subdir skip is normal).
3. **Prop-fidelity fix (kiro-A's vocabulary; closes A6):** replace the `diff_summary`/`progress`
   payloads in `showcase.sh`, `live-dashboard.spec.ts`, and both `agui-author/SKILL.md` trees
   with the renderer-true forms (`title`; `value` in [0,1]); keep claude's more precise
   disabled-shape/refusal wording in the SKILL; re-run `scripts/sync_skills.py` so both trees
   stay byte-identical; add spec assertions on the previously-dodged props (the diff title
   text and `aria-valuenow`) so a future renderer/vocabulary drift fails the live spec.
4. **OTel merge (A1):** keep claude's `[otel]`-extra packaging + subprocess proofs; port kiro's
   degrade UX — the fallback `init_telemetry` stub logs kiro's actionable warning when
   `OTEL_SDK_DISABLED=false`, and `otel.py` regains the inner `try/except ImportError` for the
   transitive-api-present edge; switch the subprocess test's blocker to the `find_spec`
   protocol (3.12-safe).
5. **Live-spec hygiene (A3):** fix the vite orphan (spawn `node_modules/.bin/vite preview`
   directly, mirroring the `.venv/bin/cao-server` rationale already in the spec) and append
   kiro's reload-persistence step after the restart-replay step (assert the instance
   auto-reactivates from IndexedDB and reconnects). Offline/online is **not** included —
   non-viable per kiro's CI evidence (`660e3f4`).
6. **Config separation (from kiro-A):** keep claude's `PLAYWRIGHT_CHROMIUM_EXECUTABLE` hook in
   the shared config, add `testIgnore: /live-dashboard/` to the default config + a
   `test:e2e:live` script (kiro's separation) so `npm run test:e2e` stays hermetic; CI job keeps
   claude's shape (uv toolchain + `src/**` path trigger) and runs the live project explicitly.
7. **Demo scripts merge (A6):** `showcase.sh` = kiro's structure (SSE tail + frame display +
   `mktemp`/trap hygiene) + claude's `CAO_TOKEN` support and exact per-emit assertions, and the
   frame check becomes part of the PASS gate (assert ≥6 `GENERATIVE_UI` frames captured);
   `run.sh` = kiro's self-contained graceful version (+ pass `CAO_API_PORT` through to the
   server, clean up the server log; keep claude's auto-showcase as an opt-in flag); keep
   claude's README with the webm as a **link** (not `![]()`); README documents both scripts.
8. **Test unions (small):** kiro's forwarded-`since` assertion and truthy-`1` enablement case;
   new equal-timestamp boundary case; a redaction case with the token in msg *and* args
   (items 2/3/6 of §3 stay follow-ups unless trivially reachable — the 4401 e2e is PR-A-scoped
   and should be attempted: drive a live WS handshake with a malformed token and assert the
   4401 close).
9. **Docs:** `docs/pwa.md` — keep claude's version (accurate reconnect claim + intermediaries
   caveat), add kiro's explicit `?ticket=`-also-redacted mention; CHANGELOG — adopt kiro's
   `docs/pwa.md#generative-ui` anchor; keep the OTel bullet in claude's (full-extra) wording.
10. **Evidence docs:** update `claude-implementation-notes.md` → `reconciliation-notes.md`
    (finding→commit map for the reconciled branch), retract the "props verified" overclaim
    explicitly, and revise `pr387-agui-response-draft-v2.md` (see §4.4).
11. **Gates (must all pass; counts pinned on the first green run):**
    - `uv run pytest` → **0 failed, ≥ 3,530 passed / 22 skipped** (floor = claude-A's 3,525 +
      parity[agui-author] ×4 + the unioned cases; the 22nd skip is `parity[agui-author]`
      references-subdir)
    - `uv run mypy src/` → clean, 132 files · `black --check .` + `isort --check-only .` → clean
    - `cao_pwa`: `npx tsc --noEmit` clean · `npm test` → **≥ 24 vitest** · `npm run build` clean
    - Live: `npx playwright test e2e/live-dashboard.spec.ts` → **1 passed** (restart-replay +
      reload steps, video artifact) · `examples/agui-dashboard/showcase.sh` → **PASS with ≥6
      GENERATIVE_UI frames asserted**
    - `uv build` + `unzip -l` → `skills/agui-author/SKILL.md` in the wheel;
      `python scripts/sync_skills.py --check` → 10 skills in sync
    - Default-off probe: no flags → `/agui/v1/stream` 404, `/agui/v1/emit_ui` 404,
      `import cli_agent_orchestrator.a2a` → ImportError (the strongest form, kept test-asserted)

### P2-B — `reconcile/pr387-a2a-hardened` (steps in commit order)

1. **Branch:** `git checkout -b reconcile/pr387-a2a-hardened 61b1dd1` (claude-B head).
2. **Drop the dep hunk (kiro's sequencing):** revert claude-B's `pyproject.toml`/`uv.lock`
   changes — dependency hygiene lands exactly once, in PR-A (its content is already identical
   there). PR-B then rebases cleanly onto a landed PR-A; its body states "no dependency changes;
   hygiene rides the core PR". (`authlib` stays importable either way — it's a dev-group dep
   after PR-A, a runtime dep before.)
3. **Error semantics (B1 decision):** rename `TASK_LIMIT_EXCEEDED` → `RESOURCE_EXHAUSTED`
   (code 6), return **HTTP 429** + JSON-RPC error body (+ `Retry-After: 30`) from the
   store-full path — restoring kiro's `_RpcException.http_status` seam (or an equivalent
   explicit catch); update store docstring, `docs/auth.md`, CHANGELOG wording accordingly.
4. **Store merge:** keep claude's `from_env()` + timestamp-based oldest-terminal eviction +
   `updated_at or created_at` sweep; port kiro's tolerant env parsing into `from_env`
   (malformed value → default + one warning); define and document `<=0` explicitly as
   "invalid → default + warning" (never "disable the cap" — that re-opens B2 by config, and
   never silent refuse-all).
5. **anilkmr fixes (new work, §3.1):** `Task.from_dict` → `data.get("id", "")`;
   `_handle_task_send` gains idempotent-create semantics — a `task.send` whose `id` already
   exists in the store is refused with `INVALID_PARAMS` ("task id already exists"; the executor's
   internal `store.upsert` transitions are unaffected). Tests: resubmit-same-id → error;
   omitted-id → server-generated UUID (no KeyError); empty-id → UUID (existing behavior); adjust
   both inherited "update-existing-when-full" bounds tests to exercise the store layer (internal
   transition) rather than a second `task.send`.
6. **Mount guard (both):** extract kiro's pure `_should_mount_a2a(bind_host, a2a_disabled,
   auth_enabled)` and call it from claude's lifespan block (keep `logger.error` + both remedies
   in the message); port kiro's parametrized decision-table tests **and** keep claude's three
   lifespan integration tests (caplog + real listener).
7. **Stream router:** adopt kiro's router-level `dependencies=[Depends(require_any_scope(...))]`
   (future routes inherit the gate); keep claude's per-route tests for both REST and SSE routes.
8. **Auth test union (on claude's real-JWT foundation):** port kiro's `cao:admin` acceptance
   (send/get/cancel), authenticated-unknown-method → METHOD_NOT_FOUND, and default-off
   per-route cases as real-JWT tests; keep claude's expired-token, enforcement-order,
   docstring-truth, and env-config tests; add the missing bearer-edge cases (scheme case,
   `Bearer` with no token, duplicate Authorization headers) since the surface is being touched
   anyway. Target: one `test/a2a/test_auth_enforcement.py` superset (~40 cases), no stubbed
   token parsing anywhere.
9. **Docs:** `docs/auth.md` = kiro's scope **table** + claude's curl walkthrough (updated to
   429 + `Retry-After` + the idempotent-create error); CHANGELOG = kiro's detailed wording with
   the anchor, adjusted for the same.
10. **Gates:**
    - `uv run pytest` → **0 failed, ≈ 3,610 ± a few passed / 21 skipped** (floor 3,592 + ported
      matrix cases + anilkmr tests − the renamed/moved duplicates; exact count pinned at first
      green run) · `uv run mypy src/` → clean, 142 files · black/isort clean
    - `uv run pytest test/e2e/test_a2a_roundtrip.py -m e2e -o addopts=""` → **2 passed**
      (real JWTs; runs in-sandbox — no tmux gate)
    - Default-off probe: auth layer off → untokened requests behave byte-identically
      (existing tests keep asserting it); non-loopback + no-auth → routes refuse to mount
      (unit + integration)

### 4.3 PR descriptions (truthful to the final diffs)

- Reconciled PR-A body: claude-A's structure, with (a) the "props verified against the actual
  renderers" claim now *true* (step 3 makes it so — state that the reconciliation found and
  fixed the mismatch), (b) credit both sources per section (provenance-neutral: "from the Kiro
  implementation" / "from the Claude implementation"), (c) the reload-persistence scenario
  added to the demo description, (d) an explicit note that the offline/online scenario was
  dropped for cause (Chromium does not sever established SSE on `setOffline` — evidence: kiro
  CI round `660e3f4`).
- Reconciled PR-B body: claude-B's structure with the 429/`RESOURCE_EXHAUSTED` semantics, the
  "no dependency changes" scope note (kiro's), the anilkmr-review section (2 fixed here,
  2 already covered, 1 in PR-A), and the ~40-case real-JWT matrix numbers.
- Mark both drafts; if tooling can't, say so in the body (as #13/#14 did).

### 4.4 Upstream reply (`docs/reviews/pr387-agui-response-draft-v2.md`)

Base: claude-A's version (the more detailed of the two — they share ~80% content). Required
edits before it's paste-ready:

1. **Fix the one falsehood:** "`authlib`/`python-multipart` leave with the A2A PR, under
   `[a2a]`" → "…`authlib` moves to the dev group (only test fixtures import it),
   `python-multipart` is removed (nothing imports it); no `[a2a]` extra is invented because the
   A2A runtime imports neither" — matching what *both* implementations actually do.
2. OTel bullet stays "all OTel deps under `[otel]`" (matches the reconciled choice); drop
   kiro-draft's "api stays core" phrasing.
3. Add one paragraph replying to review **4638092590** (@anilkmr-a2z): auth + bounds fixed in
   the A2A PR (with the per-method table), the task-`id` injection fixed via idempotent-create +
   `from_dict` KeyError fixed (his option (b)), authlib→dev done in the core PR.
4. Add the store-full semantics one-liner (429 + `RESOURCE_EXHAUSTED` + JSON-RPC body) and the
   proof-layer sentence (live-path Playwright recording incl. server-restart `?since=` replay;
   committed webm + CI artifact; offer to drop the committed binary if the maintainers prefer
   artifact-only).
5. Keep all six misattribution pushbacks (R1–R6) unchanged — nothing in this evaluation
   weakened them.

### 4.5 Upstream sequencing (per @fanhongy: core first, A2A after)

1. After fork-side approval of both reconciled drafts: push `reconcile/pr387-agui-core`'s
   content to the upstream PR #387 branch (an in-place reshape of
   `feat/agentic-protocols-generative-ui` — **a step executed only with the fork maintainer's
   explicit go-ahead; not part of this plan's implementation**), post the revised reply, and
   re-request review from @gutosantos82 / @fanhongy / @anilkmr-a2z.
2. Once PR-A merges upstream: rebase `reconcile/pr387-a2a-hardened` onto the new head — its
   diff is purely additive re-hardened A2A (no pyproject overlap by design, step P2-B-2), so the
   rebase is mechanical — and open it as the follow-up PR referencing the review commitments.
3. File the follow-up issues named in the reply so they're trackable: short-lived-ticket
   handshake for the SSE token, `STATE_DELTA` debounce, `emit_ui` rate limiting.

### Constraints (restated, binding for the implementation pass)

- Never push to `feat/agentic-protocols-generative-ui`, any `kiro/*`, or any `claude/*` branch.
- New work lands only on `reconcile/pr387-agui-core` and `reconcile/pr387-a2a-hardened`
  (both rooted at `f40933d`).
- The eventual fork PRs open as **drafts** with base `feat/agentic-protocols-generative-ui`.
- Default-off at its strongest form (A2A modules absent from PR-A; AG-UI 404s with no flags;
  test-asserted) and metadata-only redaction are non-negotiable invariants of the reconciled
  branches.

---

## Appendix — commands executed for this evaluation

```text
# per-branch worktrees at /home/user/wt/{base,kiro-a,claude-a,kiro-b,claude-b}
uv sync --all-extras --dev                    # all five, clean
uv run pytest                                 # counts in §0 (claude-B re-run solo after the
                                              #   tmpfile race; raced test passes in isolation)
uv run mypy src/ ; black --check . ; isort --check-only .
cd cao_pwa && npm ci && npx tsc --noEmit && npm test && npm run build
uv build --wheel && unzip -l dist/*.whl | grep agui-author        # both PR-A branches
# live paths
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium \
  npx playwright test e2e/live-dashboard.spec.ts                  # claude-A: 1 passed
CAO_AGUI_ENABLED=1 .venv/bin/cao-server & ./examples/agui-dashboard/showcase.sh
                                              # kiro-A: PASS (6×200+400+frames); claude-A: PASS
PLAYWRIGHT_BROWSERS_PATH=<shim: chromium-1194→1228 symlinks> CI=true \
  npx playwright test -c playwright.live.config.ts                # kiro-A: 1 passed (shim req.)
# PR-B targeted
uv run pytest test/a2a/test_auth.py                               # kiro-B: 28 passed
uv run pytest test/a2a/test_auth_enforcement.py test/a2a/test_store_bounds.py \
  test/api/test_a2a_mount_guard.py                                # claude-B: 23 passed
uv run pytest test/e2e/test_a2a_roundtrip.py -m e2e -o addopts="" # 2 passed on each
# primary instruments
git diff kiro/pr387-agui-core claude/pr387-agui-core              # walked hunk-by-hunk
git diff kiro/pr387-a2a-hardened claude/pr387-a2a-hardened
git diff f40933d <each branch>                                    # regression sweeps
```
