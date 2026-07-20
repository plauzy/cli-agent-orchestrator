# FOLLOWUPS — AG-UI #458 hardening (branch `agui-458-hardening`)

Discovered during execution of the v2 kickoff. Recorded here per Ground Rule 3
(do not expand scope silently).

## Environment deviations from the plan's DoD assumptions (verified 2026-07-20)

1. **Rebase was clean — no NEW-1 conflicts.** `git rebase origin/main` (bae8007)
   applied all 13 commits with zero conflicts; both sides survived automatically
   (`markdown-it-py>=4.0.0` runtime dep + `[agui]` extra in pyproject.toml; both the
   Validate-Markdown-links step and the agui-construct-demos job in ci.yml). The
   predicted conflict did not materialize (additions sit in disjoint regions).

2. **mypy is NON-BLOCKING in CI** (`.github/workflows/ci.yml` → `Run type checker with
   mypy` has `continue-on-error: true`, mirroring main's policy for pre-existing errors).
   Baseline `uv run mypy src` (with `--extra agui`) = **90 errors**: 67 in `services/agui`
   (64 in `run_plane.py`, 3 in `approval_bridge.py`) + 23 pre-existing elsewhere. The
   run_plane errors are all one pattern: string-literal `type=` and `thread_id/run_id/
   step_id` kwargs the pinned `ag-ui-protocol==0.1.19` event models reject. **These only
   surface when the agui extra is installed** (CI's mypy job does not install it), which is
   why the author's "this PR introduces no mypy errors" holds in CI but not under the
   documented `uv sync --extra agui` flow. → **DoD correction:** treat `mypy src` as
   informational, not a hard gate. Optional follow-up: type-clean run_plane against the
   pinned SDK (would remove 64 errors) — not required for merge given continue-on-error.

3. **`scripts/security-scan.sh` wraps trivy + CodeQL only (NOT bandit), and both tools are
   absent on this machine** (scan exits 0 as a no-op with SKIP notices). F-SL5's "bandit"
   framing is inaccurate. → DoD correction: security-scan is best-effort locally; real
   coverage is the CI CodeQL/Trivy jobs.

4. **"712 tests"** = exact pass count of `test/services/agui test/api` combined at baseline
   (confirms P1-7: the number is a subset count, not AG-UI-specific). After P0-1 it is 719
   (712 + 7 new).

## Deferred to stacked follow-up PR / issues (per F-DF1)

Do NOT scaffold in this hardening PR (scope creep by the plan's own rule):
- Plugin `agui_event_forwarder` — path `src/cli_agent_orchestrator/plugins/builtin/`
  (NOT top-level `plugins/`; F-DF3a), registered via the `cao.plugins` entry point.
- Plugin `approval_notifier` — carries external network egress (Slack/Discord/webhook) into
  a localhost-only codebase; needs a security-review egress/consent design note (F-DF3c).
- Skills `agui-construct-author`, `cao-agui-dashboard-ops`.
- `cao workflow` spec for the shift-left GIF pipeline.
- Each deferred artifact ships with its own tests + default-off gate + test double (F-DF4).

## Cross-repo (plauzy/ag-ui — separate repository, not cloned here)

- **P0-3**: TS README org link `plauzy/` → `awslabs/` in
  `integrations/cli-agent-orchestrator/typescript/README.md`.
- **F-SL4**: recurrence guard test asserting no `plauzy/` GitHub URLs in shipped docs.
  Requires cloning plauzy/ag-ui (`feat/cli-agent-orchestrator-integration`, head a6101be).
