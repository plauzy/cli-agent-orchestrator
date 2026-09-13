# Requirements Document

## Introduction

This feature delivers a repeatable, executable **audit runbook** for independently auditing the
two stacked, co-authored, signed pull requests that carry the PR #387 remediation on
`plauzy/cli-agent-orchestrator` (fork of `awslabs/cli-agent-orchestrator`) before they are
retargeted upstream to awslabs#387:

- **PR #24 (Phase-A)** — https://github.com/plauzy/cli-agent-orchestrator/pull/24
- **PR #25 (Phase-B)** — https://github.com/plauzy/cli-agent-orchestrator/pull/25

The runbook is a Markdown document **with an embedded, self-contained, runnable bash harness
(`audit.sh`)** that emits a `findings.md` artifact on every run — one table row per check with
columns **Check | Command | Evidence SHA/output | PASS/FAIL/NOTE** — followed by a prioritized
issue list (blocker → important → nit) gating "ready for awslabs#387". The audit's stance is
*verify, don't trust*: every criterion binds to an exact command and observable output, never to
a PR body's claim. This spec captures the runbook's **requirements only** (fast-task: no
design.md/tasks.md); the runbook itself is authored and executed in a later phase.

**Auditor environment:** git, uv, python 3.10–3.14, node 18–24, ripgrep, gh, open internet.

**Superseded predecessors expected closed** (still open as of 2026-07-12 16:00Z): PRs #22, #23.
**Co-author style reference:** awslabs@33c593d6c62af1475361e36521e687a3b8cb28d6.
**Adjudication ground truth cited throughout:** `docs/reviews/pr387-reconciliation-plan.md`
(plauzy #17), `docs/reviews/reconciliation-notes.md` (on the plauzy #19 branch),
`docs/reviews/pr387-phase1-verification-2026-07-07.md` and `docs/reviews/pr387-a2a-fixes/`
(landed via merged plauzy #21).

### Evidence anchors (verified 2026-07-12; the harness re-resolves refs at run time and NOTEs drift)

| Anchor | Value |
|---|---|
| PR #24 (Phase-A) | open; base `main`; head `kiro/pr387-phase-a-agui-core-signed` @ `6d9d408`; 155 files, +15,320/−121; 2 commits |
| PR #24 commits | feature `3147ba6` + merge `6d9d408` (conflicts resolved: `CHANGELOG.md`, `pyproject.toml`, `uv.lock`) |
| PR #25 (Phase-B) | open; base `kiro/pr387-phase-a-agui-core-signed`; head `kiro/pr387-phase-b-a2a-hardened-signed` @ `5f73aa8`; 40 files, +4,630/−10; 2 commits |
| PR #25 commits | feature `1f883d2` + merge `5f73aa8` |
| Commit identity | author `Pat Lauer <4451274+plauzy@users.noreply.github.com>`; trailer `Co-authored-by: Kiro Agent <244629292+kiro-agent@users.noreply.github.com>`; feature commits amended/re-signed (author-date ≠ committer-date; committer also plauzy) |
| Fork `main` tip | `deebf65` — v2.3.0 line (#419 ci, #418 changelog, #403 mcp fix, #402 GraphView, #395 profile lifecycle, #396 workflow engine, #366 fleet panel, #368 settings, OKF) |
| Comparison ground truth | `reconcile/pr387-agui-core` @ `a758d3a`; `reconcile/pr387-a2a-hardened` @ `6fe08fc` (includes merged #21: `aa8b51e` AgentCardListener.stop() socket-leak fix — the real root cause of the `:9890` port contention — and `d033cc4` tmux-fixture override) |
| API caveat | trimmed REST wrappers can omit the `verification` field — signature checks MUST use raw `gh api repos/plauzy/cli-agent-orchestrator/commits/<sha> --jq '.commit.verification'` |

## Requirements

### Requirement 1 — Setup & preconditions

**User Story:** As an auditor, I want a deterministic setup procedure that provisions every ref
and toolchain the checks depend on, so that a failed check reflects the audited code and never a
half-configured workspace.

#### Acceptance Criteria

1. WHEN the harness starts THEN audit.sh SHALL clone or fetch `plauzy/cli-agent-orchestrator`,
   add `upstream` = `https://github.com/awslabs/cli-agent-orchestrator`, and fetch
   `upstream/main`, `kiro/pr387-phase-a-agui-core-signed`, `kiro/pr387-phase-b-a2a-hardened-signed`,
   `reconcile/pr387-agui-core`, `reconcile/pr387-a2a-hardened`, and
   `feat/agentic-protocols-generative-ui`.
2. WHEN the refs are fetched THEN audit.sh SHALL run `uv sync --extra otel` in the checkout.
3. IF a required tool (git, uv, python, node/npm, rg, gh or curl) or a required ref is missing
   THEN audit.sh SHALL mark every dependent check **FAIL** (not NOTE, not skipped) and continue.
4. WHEN setup completes THEN audit.sh SHALL record the resolved SHAs of every fetched ref in
   findings.md, and IF any resolved SHA differs from this spec's evidence anchors THEN audit.sh
   SHALL append a **NOTE** row identifying the drift.

### Requirement 2 — Authorship & co-authoring

**User Story:** As a maintainer, I want every commit on both PR branches attributable to the
declared human author with exactly one agent co-author trailer, so that upstream provenance is
unambiguous.

#### Acceptance Criteria

1. WHEN audit.sh inspects each commit in `<base>..<head>` of both PRs (suggested:
   `git log --format='%H%n%an <%ae>%n%(trailers:key=Co-authored-by)' <base>..<head>`) THEN the
   check SHALL **PASS** only if every commit's author is exactly
   `Pat Lauer <4451274+plauzy@users.noreply.github.com>` and carries exactly one
   `Co-authored-by: Kiro Agent <244629292+kiro-agent@users.noreply.github.com>` trailer.
2. IF any commit has a missing, duplicated, or stray co-author trailer, or a different author
   identity THEN the check SHALL **FAIL**, itemizing the offending SHA(s).
3. WHEN author-date and committer-date differ on a commit THEN audit.sh SHALL report the
   committer identity as a **NOTE** (expected: also plauzy, from the re-signing amend).

### Requirement 3 — Signature verification

**User Story:** As a maintainer, I want the feature commits to be verified-signed via the GitHub
API, so that the "signed" claim in the PR titles is machine-checked rather than assumed.

#### Acceptance Criteria

1. WHEN audit.sh queries
   `gh api repos/plauzy/cli-agent-orchestrator/commits/<sha> --jq '.commit.verification'`
   (fallback: `curl -H "Authorization: Bearer $GITHUB_TOKEN"` on the same endpoint) for
   `3147ba6`, `6d9d408`, `1f883d2`, `5f73aa8` THEN it SHALL record `verified` and `reason` for
   each in findings.md.
2. IF a **feature** commit (`3147ba6`, `1f883d2`) is not `verified:true` THEN the check SHALL
   **FAIL**.
3. IF a **merge** commit (`6d9d408`, `5f73aa8`) is not `verified:true` THEN the check SHALL
   record a **NOTE** flagging that the session-2 signing key may not yet be registered (expected
   verified once it is).

### Requirement 4 — Latest-main incorporation

**User Story:** As a maintainer, I want proof that both branches fully contain the current
upstream main with none of its recent work reverted, so that merging the stack cannot regress
main.

#### Acceptance Criteria

1. WHEN audit.sh runs `git merge-base --is-ancestor upstream/main <head>` for both PR heads THEN
   both SHALL succeed, and `git log --oneline <head>..upstream/main` SHALL be empty; otherwise
   the check SHALL **FAIL** listing the missing commits.
2. WHEN audit.sh spot-asserts observable artifacts of main's recent work on both heads —
   profile lifecycle (#395), GraphView contract (#402), bundled cao-mcp-server launch fix
   (#403), the v2.3.0 version string, ci release-sync (#419), the workflow script-tier engine,
   the fleet web panel, OKF export/import, and settings enable/disable — THEN any
   reverted/absent artifact SHALL make the check **FAIL** with the missing item named.

### Requirement 5 — Content fidelity vs the reconciled branches

**User Story:** As a reviewer of the reconciliation, I want the Phase commits to reproduce the
adjudicated reconcile branches exactly — no silent additions or drops — so that the audit
transfers the reconciliation's verification to the new stack.

#### Acceptance Criteria

1. WHEN audit.sh compares the Phase-B head against the **current** `reconcile/pr387-a2a-hardened`
   head (which includes the #21 fixes) with
   `git diff <phase-b-head> reconcile/pr387-a2a-hardened -- src/cli_agent_orchestrator/a2a src/cli_agent_orchestrator/agent_card`
   THEN the diff SHALL be empty; otherwise **FAIL** with the differing paths.
2. WHEN audit.sh checks the Phase-A tree THEN `src/cli_agent_orchestrator/a2a/` and
   `src/cli_agent_orchestrator/agent_card/` SHALL be absent (core-first order); their presence
   SHALL **FAIL** the check.
3. WHEN audit.sh compares the Phase-A feature tree against the plauzy #19 reconciliation surface
   (sorted per-path digest comparison over the AG-UI feature paths) THEN differences SHALL be
   itemized and classified — mechanical rebase/conflict artifacts as **NOTE**, semantic drift as
   **FAIL**.
4. WHEN audit.sh checks Phase-B THEN the A2A surface SHALL be present but default-off
   (see Requirement 9 for the behavioral probe).

### Requirement 6 — Conflict-resolution correctness

**User Story:** As a maintainer, I want the three known merge-conflict files proven correctly
resolved, so that the "merge latest main" commits lose nothing from either side.

#### Acceptance Criteria

1. WHEN audit.sh greps `CHANGELOG.md` on the Phase heads THEN it SHALL find BOTH the AG-UI/A2A
   entries AND main's entries (e.g. the herdr backend #271 entry); a missing side SHALL **FAIL**.
2. WHEN audit.sh parses `pyproject.toml` THEN `[tool.mypy] python_version` SHALL equal `"3.10"`
   (NOT `"2.3.0"` — the upstream bump-script bug) while `[project] version` equals `"2.3.0"`;
   any other combination SHALL **FAIL**.
3. WHEN audit.sh checks `uv.lock` THEN it SHALL contain both `jinja2` and `joserfc` package
   entries AND `uv lock --check` SHALL pass; otherwise **FAIL**.

### Requirement 7 — Shift-left test execution

**User Story:** As a reviewer, I want the feature-scoped backend and frontend suites executed on
the audited tree, so that "tests pass" is an observed result with counts, not a checkbox.

#### Acceptance Criteria

1. WHEN audit.sh runs
   `uv run pytest test/api/test_agui_* test/services/test_agui_stream_mapping.py test/ext_apps test/a2a test/agent_card test/api/test_a2a_mount_guard.py test/api/test_default_off_listeners.py -m "not e2e"`
   on the Phase-B head THEN the check SHALL **PASS** only on 0 failures, recording the exact
   passed/skipped counts as evidence.
2. IF `test_a2a_mount_guard.py::test_loopback_bind_without_auth_still_mounts` is the sole
   failure THEN audit.sh SHALL re-run it in isolation; a pass-in-isolation SHALL downgrade the
   row to **NOTE** citing the known `:9890` port-contention behavior whose root cause was fixed
   by reconcile#21 `aa8b51e`.
3. WHEN audit.sh runs the frontend gates `npm ci && npx tsc --noEmit && npm test &&
   npm run build` in `cao_pwa/` THEN all four SHALL succeed; per the run-everything rule, an
   absent Node toolchain SHALL make this check **FAIL** (never NOTE).

### Requirement 8 — Video verification proof

**User Story:** As an upstream reviewer, I want the recorded walkthroughs and live-path harness
files present and referenced, so that the demo evidence is part of the audited tree rather than
external claims.

#### Acceptance Criteria

1. WHEN audit.sh runs `git cat-file -e <head>:docs/media/agui-generative-ui-demo.webm` and
   `git cat-file -e <head>:docs/media/agui-live-remediation-demo.webm` THEN both SHALL exist;
   a missing file SHALL **FAIL**.
2. WHEN audit.sh greps the two filenames under `docs/` THEN each SHALL be referenced at least
   once; zero references SHALL **FAIL**.
3. WHEN audit.sh checks for `cao_pwa/playwright.live.config.ts` and
   `examples/agui-dashboard/showcase.sh` THEN both SHALL be present; otherwise **FAIL**.

### Requirement 9 — Default-off / safety posture

**User Story:** As a security-conscious operator, I want the merged surfaces proven default-off
and allow-list-enforced on the audited tree, so that enabling nothing changes nothing.

#### Acceptance Criteria

1. WHEN audit.sh boots `cao-server` from the Phase-B tree with a clean environment THEN
   `GET /agui/v1/stream` and `POST /agui/v1/emit_ui` SHALL return 404 AND no `:9890` listener
   SHALL be bound; otherwise **FAIL**.
2. WHEN audit.sh re-boots with `CAO_AGUI_ENABLED=1` and POSTs an off-list `iframe` component to
   `/agui/v1/emit_ui` THEN the server SHALL refuse it with HTTP 400; otherwise **FAIL**.
3. WHEN audit.sh scans the audited trees with ripgrep patterns for committed secrets/keys/tokens
   THEN zero hits SHALL be required to PASS; audit.sh SHALL additionally record a **NOTE** row
   for the repository's secret-scanning API state when the token grants access.
4. WHEN audit.sh reviews sample/example data on the audited trees THEN it SHALL contain no PII;
   findings SHALL **FAIL** with the offending paths.

### Requirement 10 — Diff hygiene

**User Story:** As a reviewer, I want each PR's changed-file set classified against its declared
surface, so that out-of-scope changes cannot ride along unnoticed.

#### Acceptance Criteria

1. WHEN audit.sh fetches the changed-file lists (`gh pr view 24 --json files,changedFiles`,
   likewise for #25) THEN it SHALL confirm counts ≈ 155 (Phase-A) and ≈ 40 (Phase-B vs its
   base), recording exact numbers as evidence.
2. WHEN audit.sh classifies each changed path against the expected AG-UI (Phase-A) or
   A2A/agent-card (Phase-B) surfaces THEN out-of-scope paths SHALL be itemized — material ones
   (source/config outside the surface) as **FAIL**, immaterial ones (docs/tests adjacent) as
   **NOTE**.

### Requirement 11 — findings.md contract

**User Story:** As the audit's consumer, I want a single machine-checkable findings artifact per
run, so that "ready for upstream" is a computed verdict with evidence, not a narrative.

#### Acceptance Criteria

1. WHEN a run completes THEN audit.sh SHALL emit `findings.md` containing exactly one table row
   per check with columns **Check | Command | Evidence SHA/output | PASS/FAIL/NOTE**.
2. WHEN the table is emitted THEN findings.md SHALL end with a prioritized issue list
   (blocker → important → nit) stating what must be fixed before going upstream to awslabs#387.
3. WHEN all rows are PASS or NOTE THEN audit.sh SHALL exit 0; IF any row is FAIL THEN audit.sh
   SHALL exit non-zero.

### Requirement 12 — Harness behavior & secret handling

**User Story:** As an auditor, I want the harness self-contained, exhaustive, and incapable of
leaking credentials, so that it can run unattended in any shell-capable environment.

#### Acceptance Criteria

1. WHEN the runbook is published THEN audit.sh SHALL be embedded in it as a single
   self-contained script, extractable verbatim.
2. WHEN audit.sh runs THEN it SHALL use `set -euo pipefail` with per-check isolation so one
   failing check never aborts the remaining checks.
3. WHEN audit.sh runs THEN it SHALL execute **every check every time** — no opt-in tiers, no
   sampling; any bounded coverage SHALL be stated in findings.md.
4. WHEN audit.sh calls the GitHub API THEN it SHALL prefer `gh api` and fall back to
   `curl -H "Authorization: Bearer $GITHUB_TOKEN"`; the token SHALL come only from the
   environment, SHALL never be hardcoded, echoed into findings.md, or logged in command lines;
   and the runbook SHALL document the required scope (classic `repo` read, or fine-grained
   `contents:read` + `pull_requests:read`).

## Non-goals

- Executing the audit within this spec phase (the runbook runs in a later phase).
- Authoring `design.md` or `tasks.md` (fast-task spec: requirements only).
- Modifying any audited PR or branch (the audit is read-only; this spec's own branch is the
  single exception).
