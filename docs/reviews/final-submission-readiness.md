# Final Submission Readiness

> Date: 2025-07-07
> Branch: `reconcile/pr387-agui-core`
> Purpose: Document what has been independently verified, what artifacts are ready
> to ship, and what actions require explicit maintainer approval.

---

## 1. Verification Summary

### Branch A: `reconcile/pr387-agui-core` (PR #19)

| Gate | Result | Notes |
|------|--------|-------|
| `uv sync --all-extras --dev` | PASS | Clean install |
| `uv run pytest` (unit/integration) | **3519 passed**, 15 skipped, 0 failures | 1 collection ERROR: `test_cao_terminal_create_and_get` (missing tmux in sandbox -- environment, not code) |
| `uv run mypy src/` | PASS | 132 source files, no issues |
| `uv run black --check .` | PASS | 350 files unchanged |
| `uv run isort --check-only .` | PASS | 3 files skipped, 0 errors |
| PWA: `npm ci` | PASS | |
| PWA: `npx tsc --noEmit` | PASS | 0 errors |
| PWA: `npm test` | PASS | 4 suites, 24 tests |
| PWA: `npm run build` | PASS | 32 modules, dist produced |

**Spot-verified properties (in code, not just tests):**

1. `import cli_agent_orchestrator.a2a` raises `ModuleNotFoundError` on branch A -- CONFIRMED
2. `cao_pwa/src/api.ts` always takes over reconnection (exponential backoff, since-based resume) -- CONFIRMED

**Not verified (environment limitation):**

- Playwright e2e (`npm run test:e2e:live`) -- requires Chromium, which is unavailable in the sandbox. CI job "Build, test & record" on PR #19 covers this; result not independently reproduced.
- `run.sh` / `showcase.sh` live execution -- requires tmux, which is absent in sandbox. Script syntax and structure verified statically.

---

### Branch B: `reconcile/pr387-a2a-hardened` (PR #20)

| Gate | Result | Notes |
|------|--------|-------|
| `uv sync --all-extras --dev` | PASS | 121 packages resolved |
| `uv run pytest` (unit/integration) | **3590 passed**, 14 skipped, 1 FAILED | `test_loopback_bind_without_auth_still_mounts` -- port 9890 contention in same process; passes in isolation. 1 ERROR: same tmux fixture issue. |
| `uv run mypy src/` | PASS | 142 source files, no issues |
| `uv run black --check .` | PASS | 373 files unchanged |
| `uv run isort --check-only .` | PASS | 5 files skipped, 0 errors |

**Spot-verified properties (in code, not just tests):**

3. `rpc.py` authenticates before body parse -- CONFIRMED (explicit `_resolve_request_scopes(request)` before `await request.body()`)
4. Store-full produces HTTP 429 + `RESOURCE_EXHAUSTED` JSON-RPC error + `Retry-After: 30` header -- CONFIRMED
5. `task.send` refuses an existing task id (idempotent-create, closes review 4638092590 must-fix) -- CONFIRMED

**Not verified (environment limitation):**

- `test/e2e/test_a2a_roundtrip.py` -- skipped by conftest `require_tmux()` fixture. The test itself uses in-process ASGI and does not need tmux, but the session-scoped autouse fixture gates the entire `test/e2e/` directory.

---

## 2. Ready Artifacts

The following documents have been authored, verified against Phase 1 runs, and committed on `reconcile/pr387-agui-core`:

| Artifact | Path | Purpose |
|----------|------|---------|
| PR #19 body draft | `docs/reviews/pr19-body-draft.md` | Replacement body for the AG-UI core PR |
| PR #20 body draft | `docs/reviews/pr20-body-draft.md` | Replacement body for the A2A hardened PR |
| Upstream reply v2 | `docs/reviews/pr387-agui-response-draft-v2.md` | Paste-ready comment on awslabs#387, addresses all three reviews (including 4638092590) |
| Reconciliation notes | `docs/reviews/reconciliation-notes.md` | Maps every ported change between source implementations |

All numerical claims in the PR bodies and reply draft have been cross-referenced against independent Phase 1 results. Claims that could not be independently reproduced (Playwright) are explicitly marked as unverified/CI-only.

---

## 3. Actions Awaiting Maintainer Approval

The following actions CANNOT proceed without explicit maintainer go-ahead:

### A. Push branch A content to `feat/agentic-protocols-generative-ui`

This reshapes upstream awslabs#387 in place. The content of `reconcile/pr387-agui-core` would become the new HEAD of the feature branch that #387 tracks.

### B. Post response draft v2 as comment on awslabs#387

The paste-ready reply at `docs/reviews/pr387-agui-response-draft-v2.md` addresses:
- Review 4632216702 (2 blocking / 6 important / 7 nits)
- @fanhongy's decomposition ask (AG-UI core first, A2A held back)
- Review 4638092590 (@anilkmr-a2z: task-id upsert injection must-fix + `Task.from_dict` KeyError nit)

### C. Re-request review from upstream reviewers

After push + reply: re-request from @gutosantos82, @fanhongy, @anilkmr-a2z.

### D. Open branch B as follow-up upstream PR

After branch A merges: rebase `reconcile/pr387-a2a-hardened` onto new HEAD (mechanical -- no pyproject.toml diff by design), then open as the A2A follow-up PR.

### E. Update PR #19 and #20 bodies on GitHub

Replace current draft PR descriptions with the contents of `pr19-body-draft.md` and `pr20-body-draft.md`.

---

## 4. Follow-up Issues to File (After Merge)

These are commitments made in the upstream response draft and should be filed as GitHub issues post-merge:

| # | Title | Context |
|---|-------|---------|
| a | Short-lived-ticket handshake for AG-UI stream auth | Currently WS auth uses long-lived tokens; a ticket-exchange flow limits exposure window |
| b | STATE_DELTA debounce | High-frequency UI state updates should be debounced to reduce wire traffic |
| c | `emit_ui` rate limiting | Prevent runaway generative UI emission from overwhelming the client |
| d | Fixed-path `term-42.mcp.json` test race | Test uses a hardcoded path that can collide under parallel execution |

---

## 5. Fork Housekeeping

### PRs to mark as superseded (comment + close, keep branches as audit trail):

- **#11** `claude/pr387-agui-core` -- superseded by reconciled #19
- **#12** `claude/pr387-a2a-hardened` -- superseded by reconciled #20
- **#13** `kiro/pr387-a2a-hardened` -- superseded by reconciled #20
- **#14** `kiro/pr387-agui-core` -- superseded by reconciled #19
- **#15** evaluation (claude-side)
- **#16** evaluation (kiro-side)
- **#18** orchestration plan -- superseded by reconcile branches

### PRs that remain open:

- **#17** -- evaluation record (adjudication scorecard + per-finding decisions). Kept as the audit trail.
- **#19** -- active reconciled PR (AG-UI core, branch A)
- **#20** -- active reconciled PR (A2A hardened, branch B)

### Branch policy:

- NEVER force-push or rewrite `kiro/*`, `claude/*`, or evaluation branches
- `reconcile/*` branches may be extended with normal commits only
