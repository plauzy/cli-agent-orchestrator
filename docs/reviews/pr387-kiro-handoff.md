<!-- Operative handoff prompt for the fresh Kiro session. This is the authoritative, self-contained kickoff; the orchestration plan (docs/pr387-reconciliation-orchestration-plan.md, Sections 1-11) is supporting detail/audit reference. -->
# Finish and author the PR #387 remediation — final pass (Kiro-owned)

You are working in `plauzy/cli-agent-orchestrator` (fork of `awslabs/cli-agent-orchestrator`).
The evaluation and reconciliation phases are DONE; your job is to take ownership of the result,
verify it independently, and author the final upstream-facing submission. You authored one of the
two source implementations — set that aside; you are finishing the *merged* work, and the final
artifacts carry your authorship.

## State of the world (verify, don't trust — every claim below has in-repo evidence)

- Upstream awslabs#387 ("AG-UI protocol adapter…", head `f40933d`) is blocked by review
  4632216702 (2 blocking / 6 important / 7 nits), @fanhongy's decomposition ask (AG-UI core
  first, A2A held), and review 4638092590 (@anilkmr-a2z: task-id upsert injection must-fix +
  `Task.from_dict` KeyError nit — this review post-dates everything below except the reconcile
  branches).
- Two independent remediations exist as history: `kiro/pr387-agui-core` (#14) /
  `kiro/pr387-a2a-hardened` (#13) and `claude/pr387-agui-core` (#11) / `claude/pr387-a2a-hardened`
  (#12). They were adjudicated head-to-head with every gate executed and both live demo paths run:
  the scorecard + per-finding decisions are in `docs/reviews/pr387-reconciliation-plan.md` on
  branch `claude/pr387-remediation-reconcile-jlcpmy` (PR #17). Sibling evaluations #15/#16 agree
  on every major verdict (#16 is yours); your orchestration plan #18 is largely superseded — the
  reconcile branches it planned already exist.
- The RECONCILED branches are pushed and fully gated, both stacked on `f40933d`, both draft PRs
  based on `feat/agentic-protocols-generative-ui`:
  - **#19 `reconcile/pr387-agui-core`** — claude-A history + 6 commits porting the kiro-side wins
    (SHIPPED_SKILLS registration + parity, renderer-true prop vocabulary with new live-spec
    assertions, OTel warn-on-absence + find_spec test hook, live-config split + reload-persistence
    step + vite orphan fix, merged showcase/run scripts with a 6-frame stream gate, test unions
    incl. an end-to-end malformed-token WS 4401). Gates: 3,537 P / 22 S / 0 F · mypy 132 ·
    vitest 24 · live spec + showcase + wheel + `sync_skills --check` green.
  - **#20 `reconcile/pr387-a2a-hardened`** — claude-B history + 5 commits (no-pyproject-diff
    sequencing, `RESOURCE_EXHAUSTED` @ HTTP 429 + Retry-After, tolerant env bounds, idempotent-
    create task ids + `from_dict` fix closing 4638092590, extracted `_should_mount_a2a()` +
    8-case table + kept integration tests, router-level stream auth, ~40-case real-JWT matrix).
    Gates: 3,609 P / 21 S / 0 F · mypy 142 · e2e roundtrip 2 passed (real JWTs).
  - The paste-ready upstream reply is `docs/reviews/pr387-agui-response-draft-v2.md` **on #19's
    branch** (it answers all three reviews incl. 4638092590; its one prior falsehood — a promised
    `[a2a]` extra — is fixed). `docs/reviews/reconciliation-notes.md` maps every ported change.

## Phase 1 — Independent verification (your name goes on this; check it yourself)

Fetch `reconcile/pr387-agui-core` and `reconcile/pr387-a2a-hardened`. On each:
`uv sync --all-extras --dev` → `uv run pytest` → `uv run mypy src/` → `uv run black --check . &&
uv run isort --check-only .`; on A also `cd cao_pwa && npm ci && npx tsc --noEmit && npm test &&
npm run build`, then the live paths: `examples/agui-dashboard/run.sh` + `showcase.sh` (must PASS
with ≥6 GENERATIVE_UI frames) and `npm run test:e2e:live` (browser needed — if your sandbox lacks
Chromium/CDN, rely on the green `Build, test & record` CI job on #19 and say so explicitly); on B
also `uv run pytest test/e2e/test_a2a_roundtrip.py -m e2e -o addopts=""`. Spot-verify the five
load-bearing properties in code, not just tests: (1) `import cli_agent_orchestrator.a2a` raises
ImportError on A; (2) `cao_pwa/src/api.ts` always takes over reconnection; (3) rpc.py
authenticates before body parse; (4) store-full → 429 + JSON-RPC body; (5) `task.send` refuses an
existing id. Anything you find wrong: fix ON the `reconcile/*` branches with focused commits —
do not fork new variants.

## Phase 2 — Author the final submission

1. Rewrite the four PR bodies (#19/#20 now; upstream #387 body at retarget time) in your voice,
   truthful to the final diffs — that was review finding I1; no oversell, no unverified claims.
   Credit both source implementations neutrally.
2. Finalize `pr387-agui-response-draft-v2.md` as YOUR reply, verifying every number in it against
   your Phase-1 runs. Get maintainer approval, then post it on awslabs#387.
3. With the maintainer's explicit go-ahead: reshape upstream #387 in place (push A's content to
   `feat/agentic-protocols-generative-ui`), re-request review from @gutosantos82 / @fanhongy /
   @anilkmr-a2z. After A merges: rebase B onto the new head (it carries no pyproject diff by
   design — rebase is mechanical) and open it as the follow-up upstream PR.
4. File the follow-up issues the reply commits to: short-lived-ticket handshake, STATE_DELTA
   debounce, emit_ui rate limiting, the fixed-path `term-42.mcp.json` test race.
5. Close out the fork housekeeping: mark #11–#16/#18 as superseded (comment + close, don't
   delete branches), keep #17 as the evaluation record.

## Constraints

- Never force-push or rewrite `kiro/*`, `claude/*`, or the evaluation branches — they are the
  audit trail. `reconcile/*` is yours to extend with normal commits.
- Nothing goes to `feat/agentic-protocols-generative-ui` or upstream without the maintainer's
  explicit approval in this session.
- Every gate you cite in a PR body or the reply must be one you ran (or a CI run you link).
  A claim you didn't reproduce is marked *unverified*, never assumed.

Environment notes: Chromium may be preinstalled at `/opt/pw-browsers` (`PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium` — the live config honors it; never run `playwright install`, the CDN is blocked). Kill stray servers between runs with `pkill -f 'cao[-]server'` (bracket trick avoids self-match). tmux may be absent in your sandbox — the A2A e2e roundtrip does NOT need it (in-process ASGI); the WS-auth e2e does.
