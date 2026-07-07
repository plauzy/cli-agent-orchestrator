# PR #387 Reconciliation & Orchestration Plan

**Status: FINAL — ready for execution handoff.** Version **v1.0**. This finalized runbook supersedes all earlier drafts of this plan; it is the single authoritative document to execute the #387 reconciliation.

---

## 0. Kickoff for a Fresh Kiro Session (Start Here)

> **Read this section first.** It is a self-contained runbook written for a **brand-new Kiro session with zero memory** of the conversation that produced this plan. Everything needed to execute cold is here or cross-referenced by section number. Read the whole document once before touching any code.

### 0.1 Mission (one paragraph)

Produce **two professional-ready, upstream-submittable pull requests** — **PR-A (AG-UI core)** first, then **PR-B (A2A hardened)** — that resolve **every** review comment on upstream [awslabs/cli-agent-orchestrator#387](https://github.com/awslabs/cli-agent-orchestrator/pull/387). Get there by **auditing all existing work** — every Kiro branch **and all five Claude-drafted PRs (#11, #12, #17, #19, #20)** — and building the definitive **"sum total" reconciliation** that takes the strongest form of every win, closes every remaining gap (including the post-hoc review `4638092590` findings), and ships mandatory media evidence. The two Claude-executed reconciliations **#19** (`reconcile/pr387-agui-core`) and **#20** (`reconcile/pr387-a2a-hardened`) are the **strongest existing baseline** to audit and beat — not branches to regenerate from scratch.

### 0.2 Environment Setup

- **Clone via the GitHub Power**, never raw `git clone` / `git push` — the `plauzy` origin gateway requires the Power's auth (direct `git fetch` / `git ls-remote` / `git push` fail with an auth error). Use the Power's `repo_set_up` / `clone_repository` / `pull_repository` to fetch and `push_to_remote` to push.
- **Repo:** `plauzy/cli-agent-orchestrator` (a fork of `awslabs/cli-agent-orchestrator`).
- **Base branch / commit for all reconciliation work:** `feat/agentic-protocols-generative-ui` — the PR #387 head is commit **`f40933d`**. All branch diffs are measured against this base.
- **Toolchain:**
  - Python: `uv` (e.g., `uv run pytest`, `uv run mypy src/`), plus `black` and `isort` for formatting gates.
  - PWA (`cao_pwa/`): `npm` with `tsc --noEmit`, `vitest`/`npm test`, and `vite`/`npm run build`.
- **Working discipline:** do all work on `reconcile/*` branches only (see hard constraints in 0.5).

### 0.3 Branches to Fetch and Their Roles

| Role | PR# | Branch |
|------|-----|--------|
| **Base** (PR #387 head `f40933d`) | 9 | `feat/agentic-protocols-generative-ui` |
| **Kiro impl — PR-A** | 14 | `kiro/pr387-agui-core` |
| **Kiro impl — PR-B** | 13 | `kiro/pr387-a2a-hardened` |
| **Claude impl — PR-A** | 11 | `claude/pr387-agui-core` |
| **Claude impl — PR-B** | 12 | `claude/pr387-a2a-hardened` |
| **Claude eval / plan** (docs-only scorecard) | 17 | `claude/pr387-remediation-reconcile-jlcpmy` |
| **Claude EXECUTED reconciliation — PR-A (baseline)** | 19 | `reconcile/pr387-agui-core` |
| **Claude EXECUTED reconciliation — PR-B (baseline)** | 20 | `reconcile/pr387-a2a-hardened` |
| **Docs eval 1** | 15 | `docs/pr387-reconciliation` |
| **Docs eval 2** (Linux / Py3.12 run) | 16 | `docs/pr387-reconciliation-2` |

### 0.4 Ordered Start Sequence (with section cross-references)

1. **Audit all five Claude-drafted PRs — #11, #12, #17, #19, #20 — per [Section 2.1](#21-mandatory-audit-of-all-claude-drafted-prs-11-12-17-19-20).** Read each full diff (not just PR bodies), verify every PR-body claim against the actual code/tests (claims-vs-code fidelity), and **independently re-run the full gate suite on #19 and #20**, recording **real** pass/skip/fail counts vs. the numbers claimed. Confirm the review `4638092590` fixes (RC-03/RC-05) are actually present and tested in #20.
2. **Treat #19 and #20 as the strongest existing baseline ([Section 6](#6-variant-generation-approach)).** Audit them **line-by-line** against the reconciliation spec. **Do not modify them** — they are read-only audit inputs.
3. **Build the definitive final `reconcile/*` result** that closes any remaining gap, including review `4638092590` — **RC-03** (task-id injection → idempotent-create `task.send`) and **RC-05** (`Task.from_dict` uses `data.get("id", "")`). See the resolution registry in [Section 3](#3-upstream-review-comment-registry) and the cherry-pick spec in [Section 6](#6-variant-generation-approach).
4. **Produce the mandatory media deliverables per [Section 8](#8-media--visual-evidence-requirements)** for every major feature update (both tracks).
5. **Score candidates via `/cao-eval` per [Section 7](#7-cao-eval-criteria-and-success-gates)** — the final build wins only if it matches or exceeds the #19/#20 baseline after their claims are independently verified.
6. **Submit upstream: PR-A first, then PR-B ([Section 9](#9-reconciliation-workflow), Step 10).**

### 0.5 Hard Constraints (restated up front)

- **Never commit to** `feat/agentic-protocols-generative-ui`, any `kiro/*` branch, or any `claude/*` branch. All work lands on `reconcile/*` branches.
- **Treat #19 and #20 as read-only audit inputs** — audit and re-verify them, but do not modify them; the final authoritative result is a separate `reconcile/*` branch.
- **PR-A lands before PR-B** (upstream reviewer sequencing: PR-B's A2A layer consumes PR-A's streaming surface).
- **Media is a pass/fail gate for every major feature update:** a full-quality `.mp4` of the live feature path (canonical), a derived looping `.gif`, and annotated screenshots — the **mp4 embedded as a plain markdown link, never `![]()` image syntax** — in both the feature docs and the PR body. See [Section 8](#8-media--visual-evidence-requirements).

### 0.6 Definition of Done (checklist)

- [ ] All 11 review comments **RC-01 … RC-11** resolved and **verified in the diff** ([Section 3](#3-upstream-review-comment-registry)).
- [ ] Review `4638092590` fixes present **and tested** (RC-03 idempotent-create `task.send` → `INVALID_PARAMS` on id stomp; RC-05 `Task.from_dict` uses `data.get("id", "")`; `test/a2a/test_task_id_integrity.py` passes).
- [ ] Full gate suite green with **real, recorded counts** (pytest / mypy / black / isort / vitest / tsc / build / e2e / showcase — [Section 7](#7-cao-eval-criteria-and-success-gates)).
- [ ] **Every PR-body claim verified against the code** (claims-vs-code fidelity) — no unverified or contradicted assertion ships.
- [ ] Media deliverables present and **correctly embedded** (mp4 as plain link; gif/png inline with alt text + captions) in **both** the docs and the PR body, for both tracks ([Section 8](#8-media--visual-evidence-requirements), checklist [8.5](#85-media-deliverables-checklist-required-in-every-reconciled-pr-description)).
- [ ] **Two upstream PRs opened in order** (PR-A then PR-B) against `awslabs/cli-agent-orchestrator`, each with the completed media checklist.

### 0.7 Where This Plan Lives

This document is maintained on branch **`reconcile/pr387-orchestration-plan`** (fork **PR #18**) for reference. It is the FINAL handoff artifact; the sections below (1–11) are its detailed body.

---

## 1. Executive Summary

**Goal:** Produce professional-ready, upstream-submittable pull requests that address every review comment on [awslabs/cli-agent-orchestrator#387](https://github.com/awslabs/cli-agent-orchestrator/pull/387).

**Decomposition:**

| Shape | Scope | Lands |
|-------|-------|-------|
| **PR-A** (AG-UI core) | AG-UI protocol adapter, SSE streaming, PWA integration, plugin events | First |
| **PR-B** (A2A hardened) | A2A JSON-RPC endpoint, auth enforcement, task store hardening, agent-card listener | Second |

This sequencing follows the upstream reviewer recommendation (@fanhongy): PR-A provides the streaming surface that PR-B's agent-to-agent layer consumes, so PR-A must land first.

**Approach:** Audit **all** existing work first — every Kiro branch **and every Claude-drafted PR (#11, #12, #17, #19, #20)** per the mandatory checklist in [Section 2.1](#21-mandatory-audit-of-all-claude-drafted-prs-11-12-17-19-20). Because Claude has **already executed** its "best of both" reconciliations in **#19** (`reconcile/pr387-agui-core`) and **#20** (`reconcile/pr387-a2a-hardened`), those two PRs are treated as the **strongest existing baseline**, not as branches to regenerate from scratch. Kiro's definitive final build audits #19/#20 line-by-line, independently re-runs their gates, closes anything they still miss, and produces the authoritative final `reconcile/*` result. CAO's parallel multi-provider orchestration (`/cao`) and `/cao-eval` are then used to score the candidates and confirm the winner per PR shape before submitting upstream.

**Visual evidence mandate:** Every major feature update produced by this plan MUST ship visual evidence — a full-quality `.mp4` screen recording of the live feature path (the canonical artifact), a derived looping `.gif`, and comprehensive annotated screenshots — embedded in both the project documentation and the PR description. This is an enforceable gate, not an aspiration: see [Section 8 (Media & Visual Evidence Requirements)](#8-media--visual-evidence-requirements). It applies to GUI surfaces (Track A / PR-A) and non-GUI surfaces (Track B / PR-B) alike.

---

## 2. Branch Inventory

All PRs are open against `plauzy/cli-agent-orchestrator` and target `feat/agentic-protocols-generative-ui` as the base branch. **There are currently 10 open PRs/branches in scope (PR #9 base + 9 work/eval branches).** Five of them are **Claude-drafted** — **#11, #12, #17, #19, #20** — and every one is a **mandatory audit input** for this plan (see [Section 2.1](#21-mandatory-audit-of-all-claude-drafted-prs-11-12-17-19-20)). PR #19 and PR #20 are the newest and most consequential: they are Claude's **already-executed** "best of both" reconciliations — i.e., Claude has already built the `reconcile/*` result branches this plan originally proposed to generate from #11–#14.

| PR# | Branch | Shape | Provider | Description | Status |
|-----|--------|-------|----------|-------------|--------|
| 9 | `feat/agentic-protocols-generative-ui` | Original | plauzy | Original monolithic PR (feat: agentic protocol surface + generative UI) | Open - base for decomposition |
| 11 | `claude/pr387-agui-core` | PR-A | Claude | AG-UI core implementation | Open - **Claude draft — mandatory audit input** |
| 12 | `claude/pr387-a2a-hardened` | PR-B | Claude | A2A hardened implementation | Open - **Claude draft — mandatory audit input** |
| 13 | `kiro/pr387-a2a-hardened` | PR-B | Kiro | A2A hardened implementation | Open - evaluation candidate |
| 14 | `kiro/pr387-agui-core` | PR-A | Kiro | AG-UI core + live demo | Open - evaluation candidate |
| 15 | `docs/pr387-reconciliation` | Eval | docs | Kiro x Claude evaluation and reconciliation plan | Open - reference |
| 16 | `docs/pr387-reconciliation-2` | Eval | docs | Independent Linux/Py3.12 evaluation run | Open - reference |
| 17 | `claude/pr387-remediation-reconcile-jlcpmy` | Eval | Claude | Remediation scorecard + reconciliation plan (docs-only; the plan #19/#20 were built from) | Open - **Claude draft — mandatory audit input** |
| 19 | `reconcile/pr387-agui-core` | PR-A | Claude | **EXECUTED reconciled PR-A** ("best of both") — built on `claude/pr387-agui-core`, ports Kiro wins (skill governance, renderer-true demo vocab, Py3.12-safe OTel, union live spec, merged showcase/run) | Open - **Claude draft — mandatory audit input** |
| 20 | `reconcile/pr387-a2a-hardened` | PR-B | Claude | **EXECUTED reconciled PR-B** ("best of both" + closes review 4638092590) — built on `claude/pr387-a2a-hardened`, ports Kiro wins (reverts dep hunk for clean A-first rebase, `RESOURCE_EXHAUSTED`+429+`Retry-After`, `_should_mount_a2a()` + decision table, union ~40-case JWT matrix) plus idempotent-create `task.send` and `Task.from_dict` KeyError fix | Open - **Claude draft — mandatory audit input** |

---

### 2.1 Mandatory Audit of All Claude-Drafted PRs (#11, #12, #17, #19, #20)

**Guarantee:** This plan **explicitly reviews and audits every Claude-drafted PR** — **#11, #12, #17, #19, and #20** — with no exception. No reconciled `reconcile/*-final` result may be selected, and no upstream PR may be submitted, until each of these five PRs has been through the mandatory audit checklist below and the findings recorded. This requirement is a hard gate alongside the [media gate (Section 8)](#8-media--visual-evidence-requirements).

**Why #19 and #20 are the priority.** #19 (`reconcile/pr387-agui-core`) and #20 (`reconcile/pr387-a2a-hardened`) are Claude's **own already-executed** "best of both" reconciliations — the result branches this plan set out to produce. They therefore become the **strongest existing baseline** that Kiro's definitive final build must audit, independently re-verify, and improve on — *not* branches to be regenerated from scratch (see [Section 6](#6-variant-generation-approach)). #17 is the docs-only scorecard/plan they were built from; #11 and #12 are the underlying PR-A/PR-B implementations they descend from. Auditing all five gives full provenance from source implementation → plan → executed reconciliation.

**Per-PR mandatory audit checklist (apply to EACH of #11, #12, #17, #19, #20):**

- **(a) Read the full diff, not just the PR body.** Review the complete `git diff` of the branch against base `f40933d` (`feat/agentic-protocols-generative-ui`), every changed file, not just the PR description or commit messages.
- **(b) Verify every PR-body claim against the actual code/tests.** Treat each assertion in the PR body as a hypothesis to confirm against the diff. **Flag any unverified or contradicted claim** — exactly as the #17 evaluation did when it caught the "props verified against the actual renderers" falsehood in #11. Record a claims-vs-code fidelity result per PR.
- **(c) Run the full gate suite on the branch and record REAL pass/fail counts vs. claimed.** Independently execute the [gate command suite (Section 7)](#7-cao-eval-criteria-and-success-gates) on the branch and record actual pytest passed/skipped/failed, vitest, mypy, e2e, and showcase results, then compare them to the numbers claimed in the PR body (e.g., #19 claims 3,537 passed / 22 skipped / 0 failed, 24 vitest, live e2e 1 passed, 6-frame showcase PASS, WS auth 5 passed; #20 claims 3,609 passed / 21 skipped / 0 failed, e2e 2 passed, mypy 142, auth 17 + store 8 + id-integrity 4 + guard 11). Note any discrepancy.
- **(d) Catalog wins, regressions vs. base `f40933d`, and remaining gaps.** Record what each PR does better than its peers, any regression introduced relative to the base branch, and anything still missing (e.g., #11's known 2 telemetry subprocess tests failing on Py3.12 via legacy `find_module`).
- **(e) Confirm the review 4638092590 fixes are actually present and tested in #20.** Verify the idempotent-create `task.send` behavior (resubmitting an existing id → `INVALID_PARAMS`), that `Task.from_dict` uses `data.get("id", "")` (RC-05), and that `test/a2a/test_task_id_integrity.py` exists and passes. Do not accept the PR body's word — confirm in the diff and by running the test.
- **(f) Verify media deliverables (Section 8) for #19 and #20.** Confirm the required `.mp4` + derived `.gif` + annotated screenshots exist under `docs/media/`, are embedded correctly (mp4 as a plain link, never `![]()`), and actually depict the live feature path — for #19's AG-UI/PWA surface and #20's A2A CLI walkthroughs (`401 → 403 → 200` auth flow and store-full `429` path).

**Output of the audit:** a per-PR record (wins / regressions / gaps / claims-vs-code fidelity / real gate counts) that feeds the [audit matrix (Section 4)](#4-head-to-head-branch-audit-matrix) and the [/cao-eval scoring (Section 7)](#7-cao-eval-criteria-and-success-gates). These records are the authoritative inputs to Kiro's definitive final "sum total" implementation.

---

## 3. Upstream Review Comment Registry

Every comment from [awslabs/cli-agent-orchestrator#387](https://github.com/awslabs/cli-agent-orchestrator/pull/387) mapped to resolution ownership.

### Blocking (must-fix before merge)

| ID | File:Line | Author | Summary | Agreed Fix | Owner |
|----|-----------|--------|---------|------------|-------|
| RC-01 | `rpc.py:24` | @fanhongy | A2A auth bypass - no auth enforcement despite docstring claims | Per-method scope enforcement using `require_any_scope`/`is_auth_enabled` (`task.send`/`cancel` -> `cao:write`; `task.get`/`stream` -> `cao:read`) | PR-B |
| RC-02 | `store.py:47` | @fanhongy | Unbounded in-memory store - OOM vector | Size cap + TTL eviction (env-tunable), `task.send` rejected when full | PR-B |
| RC-03 | `rpc.py:150` | @fanhongy | Task id injection - peer-controlled key overwrites other tasks | Server-side UUID generation OR reject if id already exists | PR-B |
| RC-04 | `listener.py:56` | @fanhongy | A2A endpoint on agent-card listener has no auth | `FastAPI Depends()` on `/a2a/v1/rpc` that validates Bearer token via JWKS when auth enabled | PR-B |

### Important / Nit

| ID | File:Line | Author | Summary | Agreed Fix | Owner |
|----|-----------|--------|---------|------------|-------|
| RC-05 | `types.py:112` | reviewer | `Task.from_dict` KeyError when id missing | Use `data.get("id", "")` instead of `data["id"]` | PR-B |
| RC-06 | `pyproject.toml:50` | reviewer | `authlib` as production dep but only used in tests | Move to `[dev]` dependency group | PR-B |

### Copilot Nits

| ID | File:Line | Author | Summary | Agreed Fix | Owner |
|----|-----------|--------|---------|------------|-------|
| RC-07 | `tests/__init__.py` | copilot | Stray `tests/__init__.py` confusing test discovery | Remove file | PR-A |
| RC-08 | `mypy.ini` | copilot | `python_version = 3.11` vs `requires-python >= 3.10` | Set `python_version = 3.10` | PR-A |
| RC-09 | `events.py` | copilot | Wrong RFC citation (9114 vs W3C Trace Context) | Correct to W3C Trace Context reference | PR-A |
| RC-10 | `InstancePicker.tsx` | copilot | Nested interactive elements (a11y violation) | Refactor to avoid nesting `<button>` inside clickable container | PR-A |
| RC-11 | `test_headless_ci.py` | copilot | Stale docstring | Update docstring to match current test behavior | PR-A |

---

## 4. Head-to-Head Branch Audit Matrix

> **Scope of this matrix:** the columns below now cover the underlying implementations **and** Claude's executed reconciliation, PR **#19** (`reconcile/pr387-agui-core`). Every `Yes`/`No`/`Partial` for #19 must be **verified against its diff and a real gate run** per the [Section 2.1 audit checklist](#21-mandatory-audit-of-all-claude-drafted-prs-11-12-17-19-20) — do not copy the PR body's claims.

### PR-A Resolution Status

| ID | Issue | `kiro/pr387-agui-core` (#14) | `claude/pr387-agui-core` (#11) | `reconcile/pr387-agui-core` (#19, executed) | Notes |
|----|-------|:---:|:---:|:---:|-------|
| RC-07 | Stray `tests/__init__.py` | Partial | Partial | Verify in diff | #19 claims a clean tree; confirm removal |
| RC-08 | mypy `python_version` mismatch | Yes | No | Verify in diff | Kiro sets 3.10; Claude #11 leaves 3.11; confirm #19 carries the fix |
| RC-09 | Wrong RFC citation | Yes | Yes | Verify in diff | Both fix the reference |
| RC-10 | Nested interactive elements | No | Partial | Verify in diff | Confirm #19's renderer-true refactor is a11y-clean |
| RC-11 | Stale docstring | Yes | Yes | Verify in diff | Both update |

> **#19 claims to verify (real gate run required):** 3,537 passed / 22 skipped / 0 failed; 24 vitest; `npm run test:e2e:live` 1 passed; showcase 6-frame gate PASS; WS auth 5 passed; wheel ships `agui-author`; `sync_skills --check` 10 in sync; default-off ImportError. Also confirm #19 **retracts** the "props verified against the actual renderers" falsehood that #11 carried, and check whether #11's 2 Py3.12 telemetry subprocess failures (legacy `find_module`) are resolved via `find_spec`.

**PR-A Provider Wins:**

| Aspect | Winner | Rationale |
|--------|--------|-----------|
| Py3.10 compatibility | Kiro | Green on Py3.10, mypy version set correctly |
| Skill governance (`SHIPPED_SKILLS`) | Kiro | Ships guard preventing unregistered skills |
| Demo prop fidelity | Kiro | Props match actual AG-UI event schema |
| Committed demo media | Claude | Claude commits a `.webm` demo file; under the [Section 8](#8-media--visual-evidence-requirements) media mandate, committing demo media under `docs/media/` is now **required** (following established repo convention), so this is a Claude advantage to carry forward — the reconciled PR-A must ship mp4 + gif + screenshots regardless |
| PWA `?since=` cursor-loss fix | Claude | Kiro ships the reconnect cursor bug |
| Stronger default-off guard (module-absent) | Claude | Better isolation when AG-UI module not present |
| Live reconnect proof | Claude | Real e2e assertion for SSE reconnection |

### PR-B Resolution Status

The columns below cover the underlying implementations **and** Claude's executed reconciliation, PR **#20** (`reconcile/pr387-a2a-hardened`). As with PR-A, every entry for #20 must be **verified against its diff and a real gate run** per [Section 2.1](#21-mandatory-audit-of-all-claude-drafted-prs-11-12-17-19-20).

| ID | Issue | `kiro/pr387-a2a-hardened` (#13) | `claude/pr387-a2a-hardened` (#12) | `reconcile/pr387-a2a-hardened` (#20, executed) | Notes |
|----|-------|:---:|:---:|:---:|-------|
| RC-01 | Auth bypass | Partial | Yes | Verify in diff | Claude #12 enforces auth-before-parse; Kiro wires scopes but parse order differs; confirm #20's router-level stream auth |
| RC-02 | Unbounded store | Yes | Yes | Verify in diff | Both implement cap + eviction; confirm #20 folds in Kiro's `RESOURCE_EXHAUSTED` + HTTP 429 + `Retry-After: 30` |
| RC-03 | Task id injection | No | No | **Claimed fixed in #20** | #11/#12 both missed; **verify** #20's idempotent-create `task.send` (resubmitted id → `INVALID_PARAMS`) actually present + tested (review 4638092590) |
| RC-04 | Listener no auth | Yes | Yes | Verify in diff | Both add `Depends()` guard |
| RC-05 | `Task.from_dict` KeyError | No | No | **Claimed fixed in #20** | #11/#12 both missed; **verify** #20 uses `data.get("id", "")` |
| RC-06 | `authlib` dep placement | Partial | Yes | Verify in diff | Confirm #20 reverts the dep hunk for a clean A-first rebase |

> **#20 claims to verify (real gate run required):** 3,609 passed / 21 skipped / 0 failed; e2e 2 passed; mypy 142; auth 17 + store 8 + id-integrity 4 + guard 11. Confirm the extracted `_should_mount_a2a()` + 8-case decision table + 3 lifespan integration tests, the union ~40-case real-JWT auth matrix (incl. admin/unknown-method + bearer edges), and `test/a2a/test_task_id_integrity.py`.

**PR-B Provider Wins:**

| Aspect | Winner | Rationale |
|--------|--------|-----------|
| Auth-before-parse enforcement | Claude | Validates token before JSON-RPC parse (prevents oracle attacks) |
| Real JWT/JWKS tests | Claude | Full integration tests with actual token validation |
| `reset_jwks_cache` fix | Claude | Correctly invalidates cache on key rotation |
| `WWW-Authenticate` header | Claude | Standards-compliant 401 response |
| `RESOURCE_EXHAUSTED` + HTTP 429 semantics | Kiro | Correct gRPC status code + HTTP mapping |
| Extracted `_should_mount_a2a()` guard | Kiro | Clean separation of mount decision |
| 28-case test matrix | Kiro | Comprehensive parametrized coverage |
| Correct dep sequencing in pyproject.toml | Kiro | Proper optional dependency ordering |

### Gaps Found Across Evaluations (status now that #19/#20 exist)

The "both missed" gaps below predate Claude's executed reconciliations. #19 and #20 **claim** to close several of them; each "closed" claim is **pending verification** under the [Section 2.1 audit](#21-mandatory-audit-of-all-claude-drafted-prs-11-12-17-19-20) — Kiro's final build must confirm or re-open it.

| Gap | Severity | Source | Status / Notes |
|-----|----------|--------|-------|
| Task id upsert injection (RC-03) | Blocking | Post-remediation review | #11/#12 both missed; **#20 claims fixed** (idempotent-create `task.send`, review 4638092590) — verify present + tested |
| `Task.from_dict` KeyError (RC-05) | Important | Review comment | #11/#12 both missed; **#20 claims fixed** (`data.get("id", "")`) — verify in diff |
| WS 4401 never asserted e2e on malformed token | Medium | Evaluation PR #16 | **#19 claims a malformed-token WS 4401 e2e** — verify the test exists and passes |
| Equal-timestamp `?since=` boundary | Medium | Evaluation PR #15 | **#19 claims an equal-timestamp `?since=` boundary assertion** — verify in the union spec |
| `STATE_DELTA` debounce / `emit_ui` rate limiting | Follow-up | All evaluations agree | Out of scope for this PR stack (confirm neither #19 nor #20 silently changes this) |

---

## 5. /cao Parallel Orchestration Strategy

This section defines how to use CAO's multi-agent orchestration primitives to generate reconciled variants.

### Agent Topology

```
+---------------------------+
|   Supervisor Agent        |
|   (plauzy/orchestrator)   |
|   Profile: multi-provider |
+---------------------------+
       |           |
   handoff      handoff
       |           |
  +--------+  +--------+
  | Worker |  | Worker |
  | Kiro   |  | Claude |
  +--------+  +--------+
```

### Orchestration Primitives Used

| Primitive | Usage |
|-----------|-------|
| `handoff` | Supervisor hands off PR-A reconciliation to each worker (sync, wait for completion) |
| `assign` | Supervisor assigns PR-B reconciliation (async, fire-and-forget) once PR-A winner is selected |
| `send_message` | Inbox delivery of audit matrix, review comment registry, and evaluation criteria to workers |

### Branch Naming Convention

| Purpose | Pattern | Example |
|---------|---------|---------|
| PR-A reconciliation variant | `reconcile/pr-a-v{N}` | `reconcile/pr-a-v1`, `reconcile/pr-a-v2` |
| PR-B reconciliation variant | `reconcile/pr-b-v{N}` | `reconcile/pr-b-v1`, `reconcile/pr-b-v2` |
| Final winner (selected) | `reconcile/pr-a-final`, `reconcile/pr-b-final` | - |

### Parallel Execution Plan

```
Phase 1: PR-A Reconciliation (parallel)
  cao launch --headless --async \
    --supervisor orchestrator \
    --workers kiro,claude \
    --task "reconcile PR-A from audit matrix"

  Worker-Kiro:  reconcile/pr-a-v1 (starts from kiro/pr387-agui-core)
  Worker-Claude: reconcile/pr-a-v2 (starts from claude/pr387-agui-core)

Phase 2: /cao-eval PR-A
  cao-eval --branches reconcile/pr-a-v1,reconcile/pr-a-v2 \
    --rubric pr387-reconciliation-rubric.yaml

Phase 3: PR-B Reconciliation (parallel, after PR-A selected)
  cao launch --headless --async \
    --supervisor orchestrator \
    --workers kiro,claude \
    --task "reconcile PR-B from audit matrix"

  Worker-Kiro:  reconcile/pr-b-v1 (starts from kiro/pr387-a2a-hardened)
  Worker-Claude: reconcile/pr-b-v2 (starts from claude/pr387-a2a-hardened)

Phase 4: /cao-eval PR-B
  cao-eval --branches reconcile/pr-b-v1,reconcile/pr-b-v2 \
    --rubric pr387-reconciliation-rubric.yaml
```

---

## 6. Variant Generation Approach

> **Reframed now that #19/#20 exist.** Claude has **already executed** the "best of both" reconciliations this section originally described generating from #11–#14: **#19** (`reconcile/pr387-agui-core`) is the executed PR-A and **#20** (`reconcile/pr387-a2a-hardened`) is the executed PR-B. The cherry-pick tables below (which Kiro win ports to which base) remain the **specification of what a correct reconciliation must contain** — use them as the audit rubric against #19/#20, not as a from-scratch build recipe. Concretely, Kiro's definitive final implementation: (1) takes #19 (PR-A) and #20 (PR-B) as the **strongest existing baseline**; (2) audits each **line-by-line** and **independently re-runs their full gate suites** per [Section 2.1](#21-mandatory-audit-of-all-claude-drafted-prs-11-12-17-19-20); (3) confirms every item in the tables below is actually present (flagging anything missing or overclaimed); (4) closes any remaining gap; and (5) produces the authoritative final `reconcile/*` result with the [Section 8](#8-media--visual-evidence-requirements) media deliverables. **Constraints still apply:** no commits to `feat/*`, `kiro/*`, or `claude/*` branches; **#19 and #20 themselves are audit inputs and must not be modified**; PR-A lands before PR-B; media is mandatory.

### PR-A Reconciliation

**Base:** `kiro/pr387-agui-core` (rationale: green on Py3.10, skill governance, minimal/clean diff). Note: the reconciled PR-A must still add the required demo media under `docs/media/` per [Section 8](#8-media--visual-evidence-requirements) — the media mandate reframes "no committed artifacts" as "only the *required* feature-prefixed media, nothing stray."

**Cherry-pick from `claude/pr387-agui-core`:**

| Aspect | What to Port | Files Affected |
|--------|--------------|----------------|
| PWA `?since=` cursor-loss fix | SSE reconnect cursor persistence logic | `cao_pwa/src/hooks/useAgUIStream.ts` |
| Stronger default-off guard | Module-absent check before AG-UI route registration | `src/cli_agent_orchestrator/services/agui_stream.py` |
| Live reconnect proof | E2e assertion for SSE reconnection | `test/e2e/test_agui_reconnect.py` |

**Additionally address (both missed):**

| RC | Fix | Implementation |
|----|-----|----------------|
| RC-07 | Remove stray `tests/__init__.py` | `git rm tests/__init__.py` if present |
| RC-08 | Set `python_version = 3.10` in mypy config | Edit `mypy.ini` |
| RC-09 | Correct RFC citation | Fix `src/cli_agent_orchestrator/plugins/events.py` reference |
| RC-10 | Fix nested interactive elements | Refactor `cao_pwa/src/components/InstancePicker.tsx` |
| RC-11 | Update stale docstring | Edit `test/test_headless_ci.py` |

### PR-B Reconciliation

**Base:** `claude/pr387-a2a-hardened` (rationale: auth-before-parse enforcement, real JWT/JWKS tests, standards-compliant responses)

**Cherry-pick from `kiro/pr387-a2a-hardened`:**

| Aspect | What to Port | Files Affected |
|--------|--------------|----------------|
| `RESOURCE_EXHAUSTED` + HTTP 429 | Correct gRPC status + HTTP status mapping for capacity errors | `src/cli_agent_orchestrator/a2a/rpc.py` |
| `_should_mount_a2a()` guard | Extracted predicate for A2A endpoint mounting decision | `src/cli_agent_orchestrator/a2a/__init__.py` |
| 28-case parametrized test matrix | Comprehensive auth/store/rpc test coverage | `test/a2a/test_rpc.py` |
| Correct dep sequencing | Optional dependency ordering in pyproject.toml | `pyproject.toml` |

**Additionally address (both missed):**

| RC | Fix | Implementation |
|----|-----|----------------|
| RC-03 | Task id injection | Server-side UUID generation; reject `task.send` if caller-supplied id already exists in store |
| RC-05 | `Task.from_dict` KeyError | Replace `data["id"]` with `data.get("id", "")` in `src/cli_agent_orchestrator/a2a/types.py:112` |
| RC-06 | `authlib` dep placement | Move `authlib` from `[project.dependencies]` to `[project.optional-dependencies.dev]` |

---

## 7. /cao-eval Criteria and Success Gates

### Evaluation Rubric

Each candidate is scored against the following criteria (weighted). **Candidates scored include the Kiro/Claude variants AND Claude's executed reconciliations #19 (PR-A) and #20 (PR-B)** — the executed reconciliations are audited and scored on the same rubric, since they are the baseline Kiro's final build must beat or match.

| Category | Weight | Criteria |
|----------|--------|----------|
| **Blocking comments resolved** | 30% | All RC-01 through RC-04 (for PR-B), or relevant nits (PR-A) fully addressed |
| **Important comments resolved** | 10% | RC-05 and RC-06 (PR-B) correctly fixed |
| **Nits addressed** | 10% | RC-07 through RC-11 (PR-A) all fixed |
| **Gate commands pass** | 20% | Full gate suite green, run **independently on the branch** with real counts recorded (see below) |
| **Claims-vs-code fidelity** | 10% | **Every assertion in the PR body is verified against the actual diff/tests.** Any unverified or contradicted claim is flagged and docked (Claude PRs have a history of one-off overclaims — e.g., #11's "props verified against the actual renderers" falsehood). A candidate with material overclaims cannot score full marks here. |
| **Visual evidence / media deliverables** | 15% | mp4 + derived gif + comprehensive screenshots exist under `docs/media/` and are correctly embedded per [Section 8](#8-media--visual-evidence-requirements) (mp4 as plain link; gif/png inline with alt text + caption) in BOTH the feature docs and the PR description |
| **Clean diff** | 5% | No unrelated changes, minimal diff vs base (note: demo media under `docs/media/` is expected and required, not counted as unrelated) |

> **Hard gate:** The media deliverables are also a pass/fail prerequisite — a variant that scores well on code but is missing any required artifact (mp4, gif, or screenshots) or embeds them incorrectly is marked **not done** and cannot win, regardless of weighted score. See Pass/Fail Determination below.

### Gate Command Suite

```bash
# Python gates
uv run pytest test/ --ignore=test/e2e -m 'not integration' -v
uv run mypy src/
black --check .
isort --check-only .

# PWA gates
cd cao_pwa && npx tsc --noEmit && npm test && npm run build

# Web UI gates (if touched)
cd web && npx tsc --noEmit && npm test && npm run build

# Media gates (record live feature path, derive gif, capture screenshots)
#   Track A (GUI): Playwright live spec + CI recording job
npx playwright test cao_pwa/e2e/live-dashboard.spec.ts   # produces the live recording
bash showcase.sh                                          # headless proof fallback
#   Derive the looping gif from the canonical mp4
ffmpeg -i docs/media/<feature>-demo.mp4 -vf "fps=12,scale=960:-1:flags=lanczos" docs/media/<feature>-demo.gif
#   Verify artifacts exist and mp4 is NOT embedded with image syntax
test -f docs/media/<feature>-demo.mp4 && test -f docs/media/<feature>-demo.gif
! grep -Rus '!\[[^]]*\](.*\.mp4)' docs/   # mp4 must be a plain link, never ![]()
```

### When to Run /cao-eval

- After 2+ variants exist for a given PR shape (PR-A or PR-B)
- After each variant passes the gate command suite independently
- Before selecting a winner or performing a merge-best operation

### Pass/Fail Determination

A variant **passes** if:
1. All blocking review comments for its shape are resolved (verified by code inspection)
2. All gate commands exit 0
3. No regressions introduced vs. `main` (diff-test against main's test suite)
4. Diff is scoped to the PR shape's files (no cross-contamination between PR-A and PR-B concerns)
5. **Media deliverables present and correct (hard gate):** a full-quality `.mp4` of the live feature path, a derived looping `.gif`, and comprehensive annotated screenshots all exist under `docs/media/` and are embedded per [Section 8](#8-media--visual-evidence-requirements) — mp4 as a plain link, gif/png inline with alt text + caption — in both the feature docs and the PR description. A variant missing any artifact, or embedding the mp4 with `![]()` image syntax, **fails** regardless of code quality.
6. **Claims-vs-code fidelity verified (hard gate):** every claim in the PR body has been checked against the actual diff/tests and the gate suite has been re-run on the branch with real counts recorded. Any **material** unverified or contradicted claim must be flagged and resolved (corrected in the final build or documented) before the candidate can pass.

A variant **wins** if it scores highest on the weighted rubric across all passing variants. **Because #19 and #20 are Claude's executed reconciliations, they are the incumbent baseline: Kiro's final build wins only if it matches or exceeds them on the rubric after their claims have been independently verified.**

---

## 8. Media & Visual Evidence Requirements

**Policy (mandatory, enforceable):** Every major feature update produced by this plan MUST ship visual evidence. A variant, reconciled PR, or feature update is **not "done"** until the media deliverables below exist, are stored per repo convention, and are correctly embedded in **both** the project documentation **and** the PR description. This section is referenced as a hard gate by the [/cao-eval rubric](#7-cao-eval-criteria-and-success-gates) and by the [Track A and Track B success gates](#84-per-track-success-gates).

### 8.1 Required Artifacts (per major feature update)

| # | Artifact | Format | Role | Embedding |
|---|----------|--------|------|-----------|
| 1 | Full-quality screen recording of the **live** feature path | `.mp4` | **Canonical artifact** — authoritative proof the feature works end to end | Plain markdown **link** (never `![]()`) |
| 2 | Short looping clip **derived from the mp4** | `.gif` | Inline preview for docs and PR body | Inline image `![alt](path)` |
| 3 | Comprehensive **annotated screenshots** of each key state / component / step | `.png` | Static reference for every UI state (GUI) or CLI step (non-GUI) | Inline image `![alt](path)` |

Every embed MUST carry descriptive alt text **and** a one-line caption.

### 8.2 Production & Storage

- **Recorded by** the Playwright live spec (`cao_pwa/e2e/live-dashboard.spec.ts`) and the CI recording job; the `showcase.sh` headless proof is the scriptable fallback.
- **mp4 is captured first** from the live run and is the canonical artifact. The **gif is derived from that mp4** (downscaled, looping — same source execution). **Screenshots are captured in the same live run**, so all three artifacts describe one consistent execution rather than three unrelated captures.
- **Stored under `docs/media/`**, following the established repo convention — the base branch already commits `.mp4`/`.webm`/`.gif`/`.png` demo binaries there, so committing media is the norm, not an exception.
- **Naming:** `{feature}-demo.mp4`, `{feature}-demo.gif`, `{feature}-{state}.png` (e.g., `agui-generative-ui-demo.mp4`, `a2a-auth-flow-401.png`).

### 8.3 Embedding Rules (GitHub-safe)

| Rule | Reason |
|------|--------|
| Reference the mp4 as a **plain markdown link** — `[Watch the live demo](docs/media/x-demo.mp4)` — **never** with image syntax `![]()` | A committed video embedded with `![]()` image syntax will **not play on GitHub**; it renders as a broken image |
| Embed the gif and every png **inline** with `![descriptive alt](path)` immediately followed by a caption line | gif/png render inline in both docs and PR bodies |
| Every embed carries **descriptive alt text + a one-line caption** | Accessibility and reviewer context |
| Apply the media to **BOTH** the project documentation (`docs/pwa.md` and the relevant feature docs) **AND** the PR description | Evidence must live where both readers and reviewers are |

**Non-viable technique (do not attempt):** offline/online reconnect emulation in headless Chromium — it is not reliable in that environment. To demonstrate reconnection, use server `SIGKILL` + restart + page reload and record that instead.

### 8.4 Per-Track Success Gates

Media is a first-class success gate for **both** reconciliation tracks. A track's `reconcile/*-final` branch cannot be selected until its media gate is green.

**Track A — `reconcile/pr387-agui-core` (PR-A, AG-UI / GUI):**
- Live mp4 of the AG-UI generative-UI path (agent stream -> PWA render -> reconnect via SIGKILL+reload).
- Derived looping gif + annotated screenshots of each key PWA state (instance picker, live event stream, generative-UI component render, post-reconnect resume).
- Embedded in `docs/pwa.md` and the PR-A description per 8.3.

**Track B — `reconcile/pr387-a2a-hardened` (PR-B, A2A transport / non-GUI):**
Track B has no PWA, but the "every major feature" guarantee still holds. Track B MUST ship **screen-recorded CLI walkthroughs** as mp4 + derived gif + screenshots for:

| Scenario | What the recording must show |
|----------|------------------------------|
| Auth enforcement flow | `401` (missing/invalid token) → `403` (valid token, insufficient scope) → `200` (valid token, correct scope) against `/a2a/v1/rpc` |
| Store-full capacity path | `task.send` rejected with `RESOURCE_EXHAUSTED` / HTTP `429` once the task-store cap is reached |

Record these via a scripted terminal session (e.g., `asciinema` or an `ffmpeg` screen capture of the CLI), store under `docs/media/`, and embed per 8.3 in the A2A feature doc and the PR-B description.

### 8.5 Media Deliverables Checklist (required in every reconciled PR description)

Both reconciled PRs (PR-A and PR-B) MUST include this checklist with every box checked before the PR is considered submittable:

- [ ] Full-quality `.mp4` of the **live** feature path committed under `docs/media/`
- [ ] `.mp4` embedded in the feature doc **and** PR body as a **plain link** (not `![]()`)
- [ ] Looping `.gif` **derived from the mp4**, embedded inline with alt text + caption
- [ ] Comprehensive annotated screenshots of **every** key state/step, embedded inline with alt text + captions
- [ ] Feature doc updated with the same media (`docs/pwa.md` for PR-A; A2A feature doc for PR-B)
- [ ] **(Track B only)** CLI walkthrough recordings for the `401 → 403 → 200` auth flow **and** the store-full `429` path
- [ ] Verified `mp4` is NOT embedded with image syntax anywhere (`grep` guard from the Media gate passes)

---

## 9. Reconciliation Workflow

### Step-by-Step Operational Procedure

```
Step 1: Sync main
  For each implementation branch:
    git fetch origin main
    git rebase origin/main
  Resolve any conflicts. Ensure gate commands still pass.

Step 2: Create reconcile/* branches
  git checkout feat/agentic-protocols-generative-ui
  git checkout -b reconcile/pr-a-v1
  git checkout -b reconcile/pr-a-v2
  (repeat for pr-b-v1, pr-b-v2)

Step 3: Supervisor dispatches PR-A reconciliation
  Supervisor agent uses `handoff` to assign:
    - Worker-Kiro: "Reconcile PR-A starting from kiro/pr387-agui-core,
       incorporating claude wins per Section 6, fixing all RC-07..RC-11"
    - Worker-Claude: "Reconcile PR-A starting from claude/pr387-agui-core,
       incorporating kiro wins per Section 6, fixing all RC-07..RC-11"
  Workers receive the audit matrix via `send_message`.

Step 4: Workers implement PR-A variants
  Each worker:
    a. Checks out their reconcile/pr-a-v{N} branch
    b. Applies base branch changes
    c. Cherry-picks winning patterns from the other provider
    d. Addresses all "both missed" gaps for PR-A
    e. Runs full gate command suite
    f. Produces media deliverables (Section 8): records the live AG-UI path
       via the Playwright live spec / CI recording job to an .mp4 under
       docs/media/, derives the looping .gif from that mp4, captures annotated
       screenshots of each key PWA state, and embeds them (mp4 as plain link;
       gif/png inline with alt text + captions) in docs/pwa.md
    g. Commits with message: "feat(agui): reconciled PR-A variant v{N}"

Step 5: /cao-eval for PR-A
  Run evaluation comparing reconcile/pr-a-v1 vs reconcile/pr-a-v2:
    - Automated gate pass/fail
    - Code review against RC-07..RC-11 checklist
    - Diff size comparison
    - Py3.10 compatibility verification
  Select winner -> tag as reconcile/pr-a-final

Step 6: Supervisor dispatches PR-B reconciliation
  Uses `assign` (async) since PR-B is independent post-selection:
    - Worker-Kiro: "Reconcile PR-B starting from kiro/pr387-a2a-hardened,
       incorporating claude wins per Section 6, fixing RC-03 and RC-05"
    - Worker-Claude: "Reconcile PR-B starting from claude/pr387-a2a-hardened,
       incorporating kiro wins per Section 6, fixing RC-03 and RC-05"

Step 7: Workers implement PR-B variants
  Each worker:
    a. Checks out their reconcile/pr-b-v{N} branch
    b. Applies base branch changes (including PR-A final, since PR-B stacks on PR-A)
    c. Cherry-picks winning patterns from the other provider
    d. Addresses all "both missed" gaps for PR-B (RC-03, RC-05)
    e. Runs full gate command suite
    f. Produces media deliverables for the non-GUI surface (Section 8.4):
       screen-records CLI walkthroughs to .mp4 under docs/media/ for the auth
       401 -> 403 -> 200 flow and the store-full RESOURCE_EXHAUSTED / HTTP 429
       path, derives the looping .gif from each mp4, captures step screenshots,
       and embeds them (mp4 as plain link; gif/png inline with alt text +
       captions) in the A2A feature doc
    g. Commits with message: "feat(a2a): reconciled PR-B variant v{N}"

Step 8: /cao-eval for PR-B
  Run evaluation comparing reconcile/pr-b-v1 vs reconcile/pr-b-v2:
    - Automated gate pass/fail
    - Security-focused review (auth bypass, injection, OOM)
    - Code review against RC-01..RC-06 checklist
    - Integration test coverage comparison
  Select winner -> tag as reconcile/pr-b-final

Step 9: Final gate verification
  On reconcile/pr-a-final:
    - Full gate suite (pytest, mypy, black, isort, tsc, npm test, npm build)
    - Media gate (Section 8): mp4 + derived gif + screenshots present under
      docs/media/, correctly embedded in docs/pwa.md (mp4 as plain link),
      grep guard confirms no ![]() image-syntax mp4 embeds
    - Manual review of diff vs feat/agentic-protocols-generative-ui
  On reconcile/pr-b-final (stacked on pr-a-final):
    - Full gate suite
    - Security audit of auth enforcement paths
    - Media gate (Section 8.4): CLI-walkthrough mp4s (401->403->200 auth flow
      and store-full 429 path) + derived gifs + step screenshots present and
      correctly embedded in the A2A feature doc
    - Verify no cross-contamination with PR-A files

Step 10: Submit upstream
  Create PRs against awslabs/cli-agent-orchestrator:
    - PR-A first (stacks on the existing #387 discussion)
    - PR-B second (stacks on PR-A once merged)
  Each PR references this reconciliation plan and the /cao-eval results.
  Each PR description embeds the media deliverables (Section 8): the mp4 as a
    plain link, the derived gif and screenshots inline with alt text + captions,
    and includes the completed media checklist (Section 8.5).
  In the upstream reply, note that demo media is committed under docs/media/ per
    fork convention, and offer to drop the committed binaries in favor of
    artifact-only delivery (CI-produced downloads) if maintainers prefer — the
    fork-side deliverable remains the embedded media.
```

---

## 10. Constraints and Non-Goals

### Hard Constraints

- **Do NOT commit to `feat/agentic-protocols-generative-ui` directly.** All reconciliation work happens on `reconcile/*` branches.
- **Audit ALL Claude-drafted PRs — #11, #12, #17, #19, #20 — with no exception** ([Section 2.1](#21-mandatory-audit-of-all-claude-drafted-prs-11-12-17-19-20)). No `reconcile/*-final` may be selected and no upstream PR submitted until each has passed the mandatory audit checklist (full-diff read, claims-vs-code verification, real gate run, wins/regressions/gaps catalog, and — for #20 — confirmed review 4638092590 fixes).
- **Do NOT modify #19 or #20 (or any `kiro/*` / `claude/*` branch).** They are audit inputs. Kiro's final build consumes them read-only and produces a separate authoritative `reconcile/*` result.
- **PR-A lands before PR-B.** This is the agreed sequencing per upstream reviewer recommendation.
- **All gate commands must pass** before any PR is submitted upstream.
- **Pull latest `main`** into all branches before beginning reconciliation.
- **Every major feature update ships visual evidence.** A full-quality `.mp4` of the live feature path (canonical), a derived looping `.gif`, and comprehensive annotated screenshots MUST exist under `docs/media/` and be correctly embedded (mp4 as a plain link; gif/png inline with alt text + captions) in both the feature docs and the PR description — for GUI (Track A) and non-GUI (Track B) surfaces alike. See [Section 8](#8-media--visual-evidence-requirements). This is a pass/fail gate, not a follow-up.

### Non-Goals (Explicit Follow-ups)

These items were identified during evaluation but are out of scope for this PR stack:

| Item | Rationale |
|------|-----------|
| `STATE_DELTA` debounce | Performance optimization, not a correctness fix |
| `emit_ui` rate limiting | Performance optimization, not a correctness fix |
| Equal-timestamp `?since=` boundary handling | Edge case requiring separate design discussion |
| WS 4401 e2e assertion on malformed token | Nice-to-have test, not blocking |

### Scope Boundaries

- PR-A touches: `src/cli_agent_orchestrator/services/agui_stream.py`, `src/cli_agent_orchestrator/plugins/events.py`, `cao_pwa/`, `test/test_headless_ci.py`, `mypy.ini`, `tests/__init__.py`, plus `docs/pwa.md` and PR-A media under `docs/media/` (Section 8)
- PR-B touches: `src/cli_agent_orchestrator/a2a/`, `src/cli_agent_orchestrator/agent_card/listener.py`, `src/cli_agent_orchestrator/security/`, `pyproject.toml`, `test/a2a/`, `test/security/`, plus the A2A feature doc and PR-B CLI-walkthrough media under `docs/media/` (Section 8.4)
- No overlap between PR-A and PR-B file scopes (by design). `docs/media/` is a shared, additive location — each PR only adds its own feature-prefixed artifacts, so there is no scope collision.
- **Committed demo media under `docs/media/` is expected and required** (Section 8), following established repo convention; it is not treated as an "unrelated change" or a stray artifact.

---

## 11. Appendix

### Links

| Resource | URL |
|----------|-----|
| Upstream PR #387 | [awslabs/cli-agent-orchestrator#387](https://github.com/awslabs/cli-agent-orchestrator/pull/387) |
| Fork: all open PRs | [plauzy/cli-agent-orchestrator/pulls](https://github.com/plauzy/cli-agent-orchestrator/pulls?q=is%3Apr+is%3Aopen+sort%3Aupdated-desc) |
| PR #9 (original) | [feat/agentic-protocols-generative-ui](https://github.com/plauzy/cli-agent-orchestrator/pull/9) |
| PR #11 (Claude PR-A) | [claude/pr387-agui-core](https://github.com/plauzy/cli-agent-orchestrator/pull/11) |
| PR #12 (Claude PR-B) | [claude/pr387-a2a-hardened](https://github.com/plauzy/cli-agent-orchestrator/pull/12) |
| PR #13 (Kiro PR-B) | [kiro/pr387-a2a-hardened](https://github.com/plauzy/cli-agent-orchestrator/pull/13) |
| PR #14 (Kiro PR-A) | [kiro/pr387-agui-core](https://github.com/plauzy/cli-agent-orchestrator/pull/14) |
| PR #15 (Eval 1) | [docs/pr387-reconciliation](https://github.com/plauzy/cli-agent-orchestrator/pull/15) |
| PR #16 (Eval 2) | [docs/pr387-reconciliation-2](https://github.com/plauzy/cli-agent-orchestrator/pull/16) |
| PR #17 (Eval 3, Claude) | [claude/pr387-remediation-reconcile-jlcpmy](https://github.com/plauzy/cli-agent-orchestrator/pull/17) |
| PR #19 (Claude executed reconciled PR-A) | [reconcile/pr387-agui-core](https://github.com/plauzy/cli-agent-orchestrator/pull/19) |
| PR #20 (Claude executed reconciled PR-B) | [reconcile/pr387-a2a-hardened](https://github.com/plauzy/cli-agent-orchestrator/pull/20) |

### CAO Primitives Reference

| Primitive | Type | Description |
|-----------|------|-------------|
| `handoff` | Sync | Wait for worker completion before proceeding |
| `assign` | Async | Fire-and-forget task dispatch |
| `send_message` | Delivery | Inbox message between agents |
| `cao launch --headless --async` | CLI | Unattended execution mode |
| Profiles | Config | Pin agents to providers via frontmatter |
| Supervisor-worker hierarchy | Architecture | Orchestration over MCP |

### Review Comment Quick Reference

| ID | Severity | Shape | One-liner |
|----|----------|-------|-----------|
| RC-01 | Blocking | PR-B | A2A auth bypass |
| RC-02 | Blocking | PR-B | Unbounded in-memory store |
| RC-03 | Blocking | PR-B | Task id injection |
| RC-04 | Blocking | PR-B | Agent-card listener no auth |
| RC-05 | Important | PR-B | `Task.from_dict` KeyError |
| RC-06 | Important | PR-B | `authlib` wrong dep group |
| RC-07 | Nit | PR-A | Stray `tests/__init__.py` |
| RC-08 | Nit | PR-A | mypy `python_version` mismatch |
| RC-09 | Nit | PR-A | Wrong RFC citation |
| RC-10 | Nit | PR-A | Nested interactive elements |
| RC-11 | Nit | PR-A | Stale docstring |
